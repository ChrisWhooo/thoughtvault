from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thoughtvault.scanner import scan
from thoughtvault.recall import recall
from thoughtvault.search import search
from thoughtvault.sources import add_source


class Phase1ScanTests(unittest.TestCase):
    def test_scan_tracks_new_changed_unchanged_and_deleted_documents(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            note = source / "note.md"
            note.write_text("# Hello\n", encoding="utf-8")
            ignored = source / "image.png"
            ignored.write_bytes(b"not indexed")
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["project"], db_path=str(db_path))

            first = scan(str(db_path))
            self.assertEqual(first.new, 1)
            self.assertEqual(first.scanned_files, 1)

            second = scan(str(db_path))
            self.assertEqual(second.unchanged, 1)

            note.write_text("# Hello\nUpdated\n", encoding="utf-8")
            third = scan(str(db_path))
            self.assertEqual(third.changed, 1)

            note.unlink()
            fourth = scan(str(db_path))
            self.assertEqual(fourth.deleted, 1)

            conn = sqlite3.connect(db_path)
            try:
                status = conn.execute(
                    "SELECT document_status FROM documents WHERE path = 'note.md'"
                ).fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(status, "deleted")

    def test_scan_extracts_chunks_traces_and_search_results(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            note = source / "architecture.md"
            note.write_text(
                "# Architecture\n\n"
                "This project uses Python, FastAPI, and SQLite FTS5.\n\n"
                "Decision: keep original source files local.\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["project"], db_path=str(db_path))
            summary = scan(str(db_path))
            self.assertEqual(summary.new, 1)

            conn = sqlite3.connect(db_path)
            try:
                chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
                trace_count = conn.execute("SELECT COUNT(*) FROM traces").fetchone()[0]
            finally:
                conn.close()

            self.assertGreaterEqual(chunk_count, 1)
            self.assertGreaterEqual(trace_count, 4)

            chunk_results = search("FastAPI", str(db_path))
            self.assertTrue(any(row["result_type"] == "chunk" for row in chunk_results))

            trace_results = search("sqlite", str(db_path))
            self.assertTrue(any(row["result_type"] == "trace" for row in trace_results))

            mixed_query_results = search("SQLite FTS5?", str(db_path))
            self.assertTrue(mixed_query_results)

            recall_results = recall("FastAPI", str(db_path))
            self.assertEqual(recall_results[0]["path"], "architecture.md")
            self.assertTrue(recall_results[0]["evidence"])
            self.assertIn("fastapi", recall_results[0]["technologies"])


if __name__ == "__main__":
    unittest.main()
