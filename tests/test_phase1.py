from __future__ import annotations

import sqlite3
import sys
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from thoughtvault.scanner import scan
from thoughtvault.ask import (
    Evidence,
    answer_question,
    build_answer_prompt,
    retrieve_evidence,
    verified_direct_answer,
    verified_numeric_answer,
)
from thoughtvault.exporter import export_markdown
from thoughtvault.embeddings import build_embeddings, embedding_status
from thoughtvault.evaluation import load_evaluation_cases, run_evaluation
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

    def test_ask_falls_back_to_evidence_when_ai_fails(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes"
            source.mkdir()
            note = source / "memory.md"
            note.write_text(
                "# Memory System\n\n"
                "ThoughtVault keeps answers grounded in source-backed evidence.\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["memo"], db_path=str(db_path))
            scan(str(db_path))

            def failing_generator(prompt: str, model: str, host: str, timeout: float) -> str:
                raise RuntimeError("local model unavailable")

            result = answer_question(
                "source-backed evidence",
                str(db_path),
                generator=failing_generator,
            )
            self.assertIn("AI generation failed", str(result["answer"]))
            self.assertIn("memory.md", str(result["answer"]))
            self.assertEqual(result["ai_error"], "local model unavailable")
            self.assertTrue(result["evidence"])

    def test_ask_retrieves_cross_language_review_date(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes"
            source.mkdir()
            (source / "review.md").write_text(
                "# 検索品質レビュー\n\n"
                "次回レビューは 2026-07-16 14:00、新宿オフィスで実施する。\n",
                encoding="utf-8",
            )
            (source / "roadmap.md").write_text(
                "# Roadmap\n\n检索质量稳定后建设 Wiki。\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["project"], db_path=str(db_path))
            scan(str(db_path))

            evidence = retrieve_evidence(
                "下一次检索质量评审是什么时候？",
                str(db_path),
            )
            self.assertTrue(evidence)
            self.assertEqual(evidence[0].path, "review.md")
            self.assertIn("2026-07-16", evidence[0].snippet)

    def test_ask_limits_duplicate_evidence_and_uses_strict_prompt(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes"
            source.mkdir()
            (source / "may.md").write_text(
                "# 5月交通费\n\n交通费合计：2,580 日元。\n\n"
                "## 明细\n\n5月交通费由四次往返组成。\n\n"
                "## 备注\n\n金额已经确认。\n",
                encoding="utf-8",
            )
            (source / "june.md").write_text(
                "# 6月交通费\n\n交通费合计：2,460 日元。\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"

            add_source(str(source), ["personal"], db_path=str(db_path))
            scan(str(db_path))

            evidence = retrieve_evidence("5月和6月哪个月交通费更高？", str(db_path), limit=5)
            self.assertEqual({item.path for item in evidence[:2]}, {"may.md", "june.md"})
            path_counts = {
                path: sum(item.path == path for item in evidence)
                for path in {item.path for item in evidence}
            }
            self.assertTrue(all(count <= 2 for count in path_counts.values()))

            prompt = build_answer_prompt("4月交通费是多少？", evidence)
            self.assertIn("Never copy a value from a different date or month", prompt)
            self.assertIn("calculate the difference", prompt)
            self.assertIn("Do not add a Sources or Evidence section", prompt)

    def test_ask_calculates_monthly_totals_without_using_the_model(self) -> None:
        evidence = [
            Evidence("S1", "demo", "may.md", "2026 年 5 月", "chunk", "交通费合计：2,580 日元", 10),
            Evidence("S2", "demo", "june.md", "2026 年 6 月", "chunk", "交通费合计：2,460 日元", 9),
        ]
        answer = verified_numeric_answer("5月和6月哪个月交通费更高？", evidence)
        self.assertEqual(
            answer,
            "5 月为 2,580 日元 [S1]，6 月为 2,460 日元 [S2]。"
            "因此 5 月更高，相差 120 日元。",
        )

    def test_ask_refuses_to_borrow_total_from_another_month(self) -> None:
        evidence = [
            Evidence("S1", "demo", "may.md", "2026 年 5 月", "chunk", "交通费合计：2,580 日元", 10),
        ]
        answer = verified_numeric_answer("4月交通费是多少？", evidence)
        self.assertEqual(
            answer,
            "现有本地资料中没有找到 4 月的明确交通费合计，因此无法可靠确认。",
        )

    def test_ask_returns_explicit_next_datetime_without_model(self) -> None:
        evidence = [
            Evidence(
                "S1",
                "demo",
                "review.md",
                "検索品質レビュー",
                "chunk",
                "次回レビューは 2026-07-16 14:00、新宿オフィスで実施する。",
                10,
            ),
        ]
        answer = verified_direct_answer("下一次评审是什么时候？", evidence)
        self.assertEqual(answer, "下一次安排是 2026 年 7 月 16 日 14:00 [S1]。")

    def test_ask_refuses_missing_phone_number_in_query_language(self) -> None:
        evidence = [
            Evidence("S1", "demo", "meeting.md", "会议", "chunk", "参加者：武汉、田中美咲", 10),
        ]
        answer = verified_direct_answer("田中美咲的电话号码是什么？", evidence)
        self.assertEqual(answer, "现有本地资料中没有找到该电话号码，因此无法确认。")

    def test_embeddings_build_incrementally_and_enable_semantic_retrieval(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "notes"
            source.mkdir()
            (source / "review.md").write_text(
                "# レビュー\n\n検索品質を確認した。\n\n"
                "## 次回\n\n次回レビューは 2026-07-16 14:00、新宿で実施する。\n",
                encoding="utf-8",
            )
            (source / "unrelated.md").write_text(
                "# Lunch\n\n昼食はサンドイッチだった。\n",
                encoding="utf-8",
            )
            db_path = root / "thoughtvault.sqlite"
            add_source(str(source), ["memo"], db_path=str(db_path))
            scan(str(db_path))

            def fake_embedder(
                texts: list[str],
                model: str,
                host: str,
                timeout: float,
            ) -> list[list[float]]:
                vectors = []
                for text in texts:
                    if "# レビュー" in text or "下一次评审" in text:
                        vectors.append([1.0, 0.0, 0.0])
                    else:
                        vectors.append([0.0, 1.0, 0.0])
                return vectors

            first = build_embeddings(
                str(db_path),
                model="test-embedding",
                batch_size=1,
                embedder=fake_embedder,
            )
            self.assertEqual(first.embedded, 3)
            self.assertEqual(first.unchanged, 0)

            second = build_embeddings(
                str(db_path),
                model="test-embedding",
                embedder=fake_embedder,
            )
            self.assertEqual(second.embedded, 0)
            self.assertEqual(second.unchanged, 3)

            status = embedding_status(str(db_path), "test-embedding")
            self.assertEqual(status["embedded_chunks"], 3)
            self.assertEqual(status["dimensions"], 3)

            evidence = retrieve_evidence(
                "下一次评审是什么时候？",
                str(db_path),
                limit=2,
                embedding_model="test-embedding",
                embedder=fake_embedder,
            )
            self.assertTrue(evidence)
            self.assertTrue(
                any(
                    item.path == "review.md" and "2026-07-16" in item.snippet
                    for item in evidence
                )
            )

    def test_evaluation_suite_checks_sources_answers_and_refusals(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "evaluation.json"
            suite.write_text(
                json.dumps(
                    {
                        "cases": [
                            {
                                "id": "known",
                                "query": "When?",
                                "expected_paths": ["review.md"],
                                "answer_contains": ["2026-07-16"],
                            },
                            {
                                "id": "missing",
                                "query": "Phone?",
                                "expect_refusal": True,
                                "answer_not_contains": ["090-0000-0000"],
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            evidence = [
                Evidence("S1", "demo", "review.md", "Review", "chunk", "2026-07-16", 10),
            ]

            def fake_answerer(query: str, db_path: str | None, **kwargs: object) -> dict[str, object]:
                if query == "When?":
                    return {"answer": "The date is 2026-07-16 [S1].", "evidence": evidence}
                return {"answer": "没有找到该电话号码，因此无法确认。", "evidence": evidence}

            cases = load_evaluation_cases(suite)
            self.assertEqual(len(cases), 2)
            summary = run_evaluation(suite, answerer=fake_answerer)
            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.passed, 2)
            self.assertEqual(summary.failed, 0)


if __name__ == "__main__":
    unittest.main()
