from __future__ import annotations

import sqlite3
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thoughtvault.scanner import scan
from thoughtvault.ask import answer_question
from thoughtvault.exporter import export_markdown
from thoughtvault.recall import recall
from thoughtvault.reference import build_reference_cards, search_reference_cards
from thoughtvault.search import search
from thoughtvault.sources import add_source
from thoughtvault.synthesis import build_synthesis_notes, search_synthesis_notes


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

    def test_scan_extracts_excel_workbook_text(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            workbook_path = source / "company.xlsx"

            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Submission"
            sheet.append(["Document code", "0061_202605"])
            sheet.append(["Submission keyword", "勤怠表"])
            workbook.save(workbook_path)

            db_path = root / "thoughtvault.sqlite"
            add_source(str(source), ["company", "reference"], db_path=str(db_path))
            summary = scan(str(db_path))
            self.assertEqual(summary.new, 1)

            results = search("0061_202605", str(db_path))
            self.assertTrue(results)
            self.assertTrue(any(row["path"] == "company.xlsx" for row in results))

    def test_reference_cards_are_built_from_reference_sources(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "reference"
            source.mkdir()
            note = source / "application.md"
            note.write_text(
                "# Application Record\n\n"
                "Company: Example Corp\n"
                "Submitted Date: 2026-07-01\n"
                "Contact URL: https://example.com/application\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["reference", "company"], db_path=str(db_path))
            scan(str(db_path))

            cards = build_reference_cards(str(db_path))
            self.assertEqual(len(cards), 1)
            self.assertEqual(cards[0]["category"], "company_info")
            self.assertEqual(cards[0]["sensitivity"], "high")

            results = search_reference_cards("Example", str(db_path))
            self.assertTrue(results)
            self.assertEqual(results[0]["source_path"], "application.md")

    def test_markdown_export_writes_index_sources_and_reference_cards(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "reference"
            source.mkdir()
            note = source / "application.md"
            note.write_text(
                "# Application Record\n\n"
                "Company: Example Corp\n"
                "Submitted Date: 2026-07-01\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"
            output = root / "Vault"

            add_source(str(source), ["reference", "company"], db_path=str(db_path))
            scan(str(db_path))
            build_reference_cards(str(db_path))

            first = export_markdown(output, str(db_path))
            self.assertGreaterEqual(first.written, 3)
            self.assertTrue((output / "_Index.md").exists())
            self.assertTrue(any((output / "Sources").glob("*.md")))
            self.assertTrue(any((output / "References").glob("*.md")))

            index = (output / "_Index.md").read_text(encoding="utf-8")
            self.assertIn("ThoughtVault Index", index)

            second = export_markdown(output, str(db_path))
            self.assertEqual(second.written, 0)
            self.assertGreater(second.skipped, 0)

            third = export_markdown(output, str(db_path), overwrite=True)
            self.assertGreater(third.written, 0)

    def test_synthesis_notes_are_built_and_exported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "project"
            source.mkdir()
            note = source / "architecture.md"
            note.write_text(
                "# Architecture\n\n"
                "The project uses Python, FastAPI, SQLite FTS5, and Markdown export.\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"
            output = root / "Vault"

            add_source(str(source), ["project"], db_path=str(db_path))
            scan(str(db_path))

            notes = build_synthesis_notes(str(db_path))
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0]["note_type"], "project_synthesis")

            results = search_synthesis_notes("FastAPI", str(db_path))
            self.assertTrue(results)

            export_markdown(output, str(db_path))
            self.assertTrue(any((output / "Knowledge").glob("*.md")))

    def test_ai_synthesis_notes_use_injected_generator(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "project"
            source.mkdir()
            note = source / "architecture.md"
            note.write_text(
                "# Architecture\n\n"
                "The project uses Python, FastAPI, SQLite FTS5, and Markdown export.\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["project"], db_path=str(db_path))
            scan(str(db_path))

            def fake_generator(prompt: str, model: str, host: str, timeout: float) -> str:
                self.assertIn("FastAPI", prompt)
                self.assertEqual(model, "test-model")
                self.assertEqual(host, "http://test-host")
                self.assertEqual(timeout, 3.0)
                return "# AI Note\n\n## Key Details To Recall\n\n- FastAPI was used."

            notes = build_synthesis_notes(
                str(db_path),
                use_ai=True,
                model="test-model",
                ollama_host="http://test-host",
                timeout=3.0,
                generator=fake_generator,
            )
            self.assertEqual(len(notes), 1)
            self.assertEqual(notes[0]["status"], "ai_suggested")

            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT body, prompt_version, model, status FROM synthesis_notes"
                ).fetchone()
            finally:
                conn.close()

            self.assertIn("AI Note", row[0])
            self.assertEqual(row[1], "ollama-v1")
            self.assertEqual(row[2], "test-model")
            self.assertEqual(row[3], "ai_suggested")

    def test_ask_uses_retrieved_evidence_and_injected_generator(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes"
            source.mkdir()
            note = source / "memory.md"
            note.write_text(
                "# Memory System\n\n"
                "ThoughtVault uses local AI with Ollama to answer from source-backed evidence.\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["memo"], db_path=str(db_path))
            scan(str(db_path))

            def fake_generator(prompt: str, model: str, host: str, timeout: float) -> str:
                self.assertIn("local AI", prompt)
                self.assertIn("memory.md", prompt)
                self.assertEqual(model, "test-model")
                return "ThoughtVault can answer with local AI from evidence [S1]."

            result = answer_question(
                "How does local AI help?",
                str(db_path),
                model="test-model",
                generator=fake_generator,
            )
            self.assertIn("local AI", str(result["answer"]))
            self.assertTrue(result["evidence"])


if __name__ == "__main__":
    unittest.main()
