from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .db import init_db
from .embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    build_embeddings,
    embedding_status,
)
from .evaluation import run_evaluation
from .exporter import export_markdown
from .facts import (
    build_facts,
    fact_status,
    list_fact_conflicts,
    list_facts,
    review_fact,
    review_facts,
)
from .knowledge import (
    build_knowledge_pages,
    discover_topics,
    get_knowledge_page,
    list_knowledge_pages,
    search_knowledge_pages,
)
from .ask import (
    DEFAULT_EVIDENCE_LIMIT,
    answer_question,
    evidence_to_dict,
    get_ask_record,
    list_ask_records,
)
from .recall import recall
from .reference import build_reference_cards, list_reference_cards, search_reference_cards
from .scanner import list_documents, scan
from .search import search
from .sources import add_source, list_sources
from .synthesis import (
    DEFAULT_OLLAMA_HOST,
    DEFAULT_OLLAMA_MODEL,
    build_synthesis_notes,
    list_synthesis_notes,
    search_synthesis_notes,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="thoughtvault",
        description="Local-first personal memory and knowledge system",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to the SQLite database. Defaults to .thoughtvault/thoughtvault.sqlite.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Initialize the ThoughtVault database.")

    source_parser = subparsers.add_parser("source", help="Manage source roots.")
    source_subparsers = source_parser.add_subparsers(dest="source_command", required=True)

    source_add = source_subparsers.add_parser("add", help="Add or update a source root.")
    source_add.add_argument("path", help="Local folder to scan.")
    source_add.add_argument(
        "--category",
        action="append",
        default=[],
        help="Source category. Can be repeated. Defaults to unknown.",
    )
    source_add.add_argument("--name", default=None, help="Source display name.")

    source_subparsers.add_parser("list", help="List configured source roots.")

    scan_parser = subparsers.add_parser("scan", help="Scan configured source roots.")
    scan_parser.add_argument(
        "--source-id",
        type=int,
        default=None,
        help="Scan only one source id.",
    )

    subparsers.add_parser("documents", help="List indexed documents.")

    search_parser = subparsers.add_parser("search", help="Search indexed chunks and traces.")
    search_parser.add_argument("query", help="Search query.")
    search_parser.add_argument("--limit", type=int, default=10, help="Maximum results to show.")

    embeddings_parser = subparsers.add_parser(
        "embeddings",
        help="Build and inspect semantic vector indexes.",
    )
    embeddings_subparsers = embeddings_parser.add_subparsers(
        dest="embeddings_command",
        required=True,
    )
    embeddings_build = embeddings_subparsers.add_parser(
        "build",
        help="Generate missing or changed chunk embeddings.",
    )
    embeddings_build.add_argument(
        "--model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Ollama embedding model. Defaults to {DEFAULT_EMBEDDING_MODEL}.",
    )
    embeddings_build.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama host URL. Defaults to {DEFAULT_OLLAMA_HOST}.",
    )
    embeddings_build.add_argument("--timeout", type=float, default=120.0)
    embeddings_build.add_argument("--batch-size", type=int, default=16)

    embeddings_status = embeddings_subparsers.add_parser(
        "status",
        help="Show semantic index coverage.",
    )
    embeddings_status.add_argument(
        "--model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Ollama embedding model. Defaults to {DEFAULT_EMBEDDING_MODEL}.",
    )

    ask_parser = subparsers.add_parser("ask", help="Ask a source-backed local AI question.")
    ask_parser.add_argument(
        "query",
        nargs="+",
        help='Question to answer, or "history" / "show <id>".',
    )
    ask_parser.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Ollama model to use. Defaults to {DEFAULT_OLLAMA_MODEL}.",
    )
    ask_parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama host URL. Defaults to {DEFAULT_OLLAMA_HOST}.",
    )
    ask_parser.add_argument("--timeout", type=float, default=120.0, help="Ollama request timeout in seconds.")
    ask_parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_EVIDENCE_LIMIT,
        help="Maximum evidence items to retrieve.",
    )
    ask_parser.add_argument("--no-ai", action="store_true", help="Show retrieved evidence without AI generation.")
    ask_parser.add_argument("--strict", action="store_true", help="Use stricter evidence-grounding rules.")
    ask_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    ask_parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Semantic retrieval model. Defaults to {DEFAULT_EMBEDDING_MODEL}.",
    )
    ask_parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Disable semantic retrieval and use lexical evidence only.",
    )
    ask_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all retrieved evidence instead of only cited sources.",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Run a repeatable JSON evaluation suite.",
    )
    evaluate_parser.add_argument("suite", help="Path to an evaluation JSON file.")
    evaluate_parser.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Ollama answer model. Defaults to {DEFAULT_OLLAMA_MODEL}.",
    )
    evaluate_parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help=f"Semantic retrieval model. Defaults to {DEFAULT_EMBEDDING_MODEL}.",
    )
    evaluate_parser.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama host URL. Defaults to {DEFAULT_OLLAMA_HOST}.",
    )
    evaluate_parser.add_argument("--timeout", type=float, default=120.0)
    evaluate_parser.add_argument("--limit", type=int, default=DEFAULT_EVIDENCE_LIMIT)
    evaluate_parser.add_argument("--no-ai", action="store_true")
    evaluate_parser.add_argument("--no-semantic", action="store_true")

    facts_parser = subparsers.add_parser(
        "facts",
        help="Build and review structured source-backed facts.",
    )
    facts_subparsers = facts_parser.add_subparsers(dest="facts_command", required=True)

    facts_build = facts_subparsers.add_parser(
        "build",
        help="Extract facts from new or changed documents.",
    )
    facts_build.add_argument("--force", action="store_true", help="Rebuild all document facts.")

    facts_list = facts_subparsers.add_parser("list", help="List extracted facts.")
    facts_list.add_argument("--limit", type=int, default=50)
    facts_list.add_argument("--status", choices=["proposed", "confirmed", "rejected"])
    facts_list.add_argument("--type", dest="fact_type", default=None)
    facts_list.add_argument("--query", default=None)

    facts_conflicts = facts_subparsers.add_parser(
        "conflicts",
        help="List contradictory values for the same subject and predicate.",
    )
    facts_conflicts.add_argument("--limit", type=int, default=50)

    facts_subparsers.add_parser("status", help="Show fact counts by review status and type.")

    facts_review = facts_subparsers.add_parser(
        "review",
        help="Change a fact review status.",
    )
    facts_review.add_argument("fact_id", type=int)
    facts_review.add_argument("status", choices=["proposed", "confirmed", "rejected"])

    facts_review_many = facts_subparsers.add_parser(
        "review-many",
        help="Preview or apply a filtered batch fact review.",
    )
    facts_review_many.add_argument("status", choices=["confirmed", "rejected"])
    facts_review_many.add_argument(
        "--from-status",
        choices=["proposed", "confirmed", "rejected"],
        default="proposed",
    )
    facts_review_many.add_argument("--type", dest="fact_type", default=None)
    facts_review_many.add_argument("--query", default=None)
    facts_review_many.add_argument("--limit", type=int, default=100)
    facts_review_many.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. Without this flag the command is preview-only.",
    )

    knowledge_parser = subparsers.add_parser(
        "knowledge",
        help="Compile and inspect source-backed knowledge pages.",
    )
    knowledge_subparsers = knowledge_parser.add_subparsers(dest="knowledge_command", required=True)

    knowledge_discover = knowledge_subparsers.add_parser("discover", help="Discover candidate knowledge topics.")
    knowledge_discover.add_argument("--limit", type=int, default=20)

    knowledge_build = knowledge_subparsers.add_parser("build", help="Generate reviewable knowledge pages.")
    knowledge_build.add_argument("--topic", default=None, help="Build one topic instead of discovered topics.")
    knowledge_build.add_argument("--limit", type=int, default=20)

    knowledge_subparsers.add_parser("list", help="List generated knowledge pages.")

    knowledge_show = knowledge_subparsers.add_parser("show", help="Show one generated knowledge page.")
    knowledge_show.add_argument("page_id", type=int)

    knowledge_search = knowledge_subparsers.add_parser("search", help="Search generated knowledge pages.")
    knowledge_search.add_argument("query")
    knowledge_search.add_argument("--limit", type=int, default=10)

    recall_parser = subparsers.add_parser("recall", help="Recall past exposure with source-backed evidence.")
    recall_parser.add_argument("query", help="Recall query.")
    recall_parser.add_argument("--limit", type=int, default=5, help="Maximum documents to show.")
    recall_parser.add_argument(
        "--evidence-limit",
        type=int,
        default=3,
        help="Maximum evidence snippets per document.",
    )

    reference_parser = subparsers.add_parser("reference", help="Build and inspect reference cards.")
    reference_subparsers = reference_parser.add_subparsers(dest="reference_command", required=True)

    reference_build = reference_subparsers.add_parser("build", help="Generate reference cards from indexed sources.")
    reference_build.add_argument("--source-id", type=int, default=None, help="Build cards for one source id.")

    reference_subparsers.add_parser("list", help="List generated reference cards.")

    reference_search = reference_subparsers.add_parser("search", help="Search generated reference cards.")
    reference_search.add_argument("query", help="Reference search query.")
    reference_search.add_argument("--limit", type=int, default=10, help="Maximum results to show.")

    export_parser = subparsers.add_parser("export", help="Export indexed data to Markdown.")
    export_parser.add_argument("output_dir", help="Output folder for exported Markdown files.")
    export_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing export files.")

    synthesis_parser = subparsers.add_parser("synthesis", help="Build and inspect synthesis notes.")
    synthesis_subparsers = synthesis_parser.add_subparsers(dest="synthesis_command", required=True)

    synthesis_build = synthesis_subparsers.add_parser("build", help="Generate source-backed synthesis notes.")
    synthesis_build.add_argument("--source-id", type=int, default=None, help="Build notes for one source id.")
    synthesis_build.add_argument("--ai", action="store_true", help="Use local Ollama to generate synthesis notes.")
    synthesis_build.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL,
        help=f"Ollama model to use with --ai. Defaults to {DEFAULT_OLLAMA_MODEL}.",
    )
    synthesis_build.add_argument(
        "--ollama-host",
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama host URL. Defaults to {DEFAULT_OLLAMA_HOST}.",
    )
    synthesis_build.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Ollama request timeout in seconds.",
    )
    synthesis_build.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail instead of writing a rule-based fallback note if Ollama generation fails.",
    )

    synthesis_subparsers.add_parser("list", help="List generated synthesis notes.")

    synthesis_search = synthesis_subparsers.add_parser("search", help="Search generated synthesis notes.")
    synthesis_search.add_argument("query", help="Synthesis search query.")
    synthesis_search.add_argument("--limit", type=int, default=10, help="Maximum results to show.")
    return parser


def print_rows(rows: list[dict[str, object]], columns: list[str]) -> None:
    if not rows:
        print("No records found.")
        return
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  ".join(column.ljust(widths[column]) for column in columns)
    print(header)
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns))


def print_recall_results(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("No recall results found.")
        return
    for index, row in enumerate(rows, start=1):
        print(f"{index}. {row['title']} ({row['path']})")
        print(f"   source={row['source']} categories={row['categories']}")
        print(
            "   hits="
            f"chunks:{row['chunk_hits']} traces:{row['trace_hits']} "
            f"score:{row['score']}"
        )
        if row.get("technologies"):
            print(f"   technologies: {', '.join(row['technologies'])}")
        if row.get("dates"):
            print(f"   dates: {', '.join(row['dates'])}")
        if row.get("headings"):
            print(f"   headings: {', '.join(row['headings'])}")
        evidence = row.get("evidence", [])
        if evidence:
            print("   evidence:")
            for item in evidence:
                snippet = " ".join(str(item["snippet"]).split())
                print(f"   - {item['type']}: {snippet}")
        print()


def print_ask_evidence(evidence: object, answer: str = "", verbose: bool = False) -> None:
    if not evidence:
        return
    cited_ids = set(re.findall(r"\[(S\d+)\]", answer))
    selected = list(evidence) if verbose else [item for item in evidence if item.source_id in cited_ids]
    if not selected:
        selected = list(evidence)[:3]
    unique_selected = []
    seen_paths = set()
    for item in selected:
        if item.path in seen_paths:
            continue
        unique_selected.append(item)
        seen_paths.add(item.path)
    print()
    print("Sources:")
    for item in unique_selected:
        print(f"- [{item.source_id}] {item.path}")
        if verbose:
            snippet = " ".join(str(item.snippet).split())
            print(f"  {snippet}")


def print_ask_record(record: dict[str, object]) -> None:
    print(f"Ask record #{record['id']}")
    print(f"Status: {record['status']}")
    print(f"Model: {record['model']}")
    print(f"Created: {record['created_at']}")
    print()
    print("Question:")
    print(record["query"])
    print()
    print("Answer:")
    print(record["answer"])
    print_ask_evidence(record.get("evidence"), str(record["answer"]), verbose=True)


def ask_result_to_json(result: dict[str, object]) -> str:
    payload = dict(result)
    payload["evidence"] = [
        evidence_to_dict(item)
        for item in result.get("evidence", [])
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        db_path = init_db(args.db)
        print(f"Initialized ThoughtVault database: {db_path}")
        return

    if args.command == "source":
        if args.source_command == "add":
            source_id = add_source(args.path, args.category, args.name, args.db)
            print(f"Source saved: id={source_id} path={Path(args.path).resolve()}")
            return
        if args.source_command == "list":
            rows = list_sources(args.db)
            print_rows(rows, ["id", "name", "root_path", "categories", "scan_enabled", "last_scanned_at"])
            return

    if args.command == "scan":
        summary = scan(args.db, args.source_id)
        print(
            "Scan complete: "
            f"sources={summary.sources} "
            f"files={summary.scanned_files} "
            f"new={summary.new} "
            f"changed={summary.changed} "
            f"unchanged={summary.unchanged} "
            f"deleted={summary.deleted} "
            f"errors={summary.errors}"
        )
        return

    if args.command == "documents":
        rows = list_documents(args.db)
        print_rows(
            rows,
            [
                "id",
                "source",
                "path",
                "file_type",
                "size_bytes",
                "document_status",
                "chunks",
                "traces",
                "modified_at",
            ],
        )
        return

    if args.command == "search":
        rows = search(args.query, args.db, args.limit)
        print_rows(rows, ["result_type", "path", "title", "snippet"])
        return

    if args.command == "embeddings":
        if args.embeddings_command == "build":
            summary = build_embeddings(
                args.db,
                model=args.model,
                ollama_host=args.ollama_host,
                timeout=args.timeout,
                batch_size=args.batch_size,
            )
            print(
                "Embedding build complete: "
                f"model={summary.model} "
                f"total_chunks={summary.total_chunks} "
                f"embedded={summary.embedded} "
                f"unchanged={summary.unchanged} "
                f"errors={summary.errors}"
            )
            return
        if args.embeddings_command == "status":
            status = embedding_status(args.db, args.model)
            print_rows([status], ["model", "total_chunks", "embedded_chunks", "dimensions", "last_updated_at"])
            return

    if args.command == "ask":
        ask_args = list(args.query)
        if ask_args[0] == "history":
            rows = list_ask_records(args.db, args.limit)
            if args.json:
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            else:
                print_rows(rows, ["id", "query", "model", "status", "created_at"])
            return

        if ask_args[0] == "show":
            if len(ask_args) < 2:
                parser.error("ask show requires a record id")
            record = get_ask_record(int(ask_args[1]), args.db)
            if record is None:
                print("No ask record found.")
                return
            if args.json:
                payload = dict(record)
                payload["evidence"] = [
                    evidence_to_dict(item)
                    for item in record.get("evidence", [])
                ]
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_ask_record(record)
            return

        query = " ".join(ask_args)
        result = answer_question(
            query,
            args.db,
            model=args.model,
            ollama_host=args.ollama_host,
            timeout=args.timeout,
            limit=args.limit,
            use_ai=not args.no_ai,
            strict=args.strict,
            embedding_model=None if args.no_semantic else args.embedding_model,
        )
        if args.json:
            print(ask_result_to_json(result))
            return
        if result.get("record_id"):
            print(f"Ask record saved: id={result['record_id']} status={result['status']}")
            print()
        print(result["answer"])
        if not args.no_ai:
            print_ask_evidence(
                result.get("evidence"),
                str(result["answer"]),
                verbose=args.verbose,
            )
        return

    if args.command == "evaluate":
        summary = run_evaluation(
            args.suite,
            args.db,
            model=args.model,
            embedding_model=None if args.no_semantic else args.embedding_model,
            ollama_host=args.ollama_host,
            timeout=args.timeout,
            limit=args.limit,
            use_ai=not args.no_ai,
        )
        for result in summary.results:
            label = "PASS" if result.passed else "FAIL"
            print(f"[{label}] {result.case_id}: {result.query}")
            for check in result.checks:
                print(f"  - {check}")
            if not result.passed:
                print(f"  answer: {' '.join(result.answer.split())}")
                if result.source_paths:
                    print(f"  sources: {', '.join(result.source_paths)}")
        print(
            "Evaluation complete: "
            f"total={summary.total} passed={summary.passed} failed={summary.failed}"
        )
        if summary.failed:
            raise SystemExit(1)
        return

    if args.command == "facts":
        if args.facts_command == "build":
            summary = build_facts(args.db, force=args.force)
            print(
                "Fact build complete: "
                f"documents={summary.documents} "
                f"rebuilt={summary.rebuilt} "
                f"unchanged={summary.unchanged} "
                f"facts={summary.facts} "
                f"errors={summary.errors}"
            )
            return
        if args.facts_command == "list":
            rows = list_facts(
                args.db,
                limit=args.limit,
                status=args.status,
                fact_type=args.fact_type,
                query=args.query,
            )
            print_rows(
                rows,
                [
                    "id", "fact_type", "subject", "predicate", "object_value",
                    "unit", "event_date", "confidence", "status", "path",
                ],
            )
            return
        if args.facts_command == "conflicts":
            rows = list_fact_conflicts(args.db, args.limit)
            print_rows(
                rows,
                [
                    "fact_type", "subject", "predicate", "event_date",
                    "unit", "value_count", "values_text", "paths",
                ],
            )
            return
        if args.facts_command == "status":
            rows = fact_status(args.db)
            print_rows(rows, ["status", "fact_type", "fact_count"])
            return
        if args.facts_command == "review":
            row = review_fact(args.fact_id, args.status, args.db)
            if row is None:
                print("No fact found.")
            else:
                print_rows([row], ["id", "fact_type", "subject", "predicate", "object_value", "status"])
            return
        if args.facts_command == "review-many":
            summary = review_facts(
                args.status,
                args.db,
                from_status=args.from_status,
                fact_type=args.fact_type,
                query=args.query,
                limit=args.limit,
                apply=args.apply,
            )
            mode = "applied" if summary.applied else "preview"
            print(
                f"Batch review {mode}: matched={summary.matched} "
                f"updated={summary.updated} target_status={summary.target_status}"
            )
            print_rows(
                list(summary.facts),
                ["id", "fact_type", "subject", "predicate", "object_value", "status", "path"],
            )
            if not summary.applied and summary.matched:
                print("No changes written. Re-run with --apply to update these facts.")
            return

    if args.command == "knowledge":
        if args.knowledge_command == "discover":
            rows = discover_topics(args.db, args.limit)
            print_rows(rows, ["topic", "source", "document_count"])
            return
        if args.knowledge_command == "build":
            rows = build_knowledge_pages(args.db, topic=args.topic, limit=args.limit)
            print(f"Knowledge pages built: {len(rows)}")
            if rows:
                print_rows(rows, ["id", "topic", "title", "status", "updated_at"])
            return
        if args.knowledge_command == "list":
            rows = list_knowledge_pages(args.db)
            print_rows(rows, ["id", "topic", "title", "status", "generator", "updated_at"])
            return
        if args.knowledge_command == "show":
            row = get_knowledge_page(args.page_id, args.db)
            if row is None:
                print("No knowledge page found.")
            else:
                print(row["body"])
            return
        if args.knowledge_command == "search":
            rows = search_knowledge_pages(args.query, args.db, args.limit)
            print_rows(rows, ["id", "topic", "title", "status", "snippet"])
            return

    if args.command == "recall":
        rows = recall(args.query, args.db, args.limit, args.evidence_limit)
        print_recall_results(rows)
        return

    if args.command == "reference":
        if args.reference_command == "build":
            rows = build_reference_cards(args.db, args.source_id)
            print(f"Reference cards built: {len(rows)}")
            if rows:
                print_rows(rows, ["id", "title", "category", "sensitivity", "status"])
            return
        if args.reference_command == "list":
            rows = list_reference_cards(args.db)
            print_rows(rows, ["id", "title", "category", "sensitivity", "status", "source_path", "updated_at"])
            return
        if args.reference_command == "search":
            rows = search_reference_cards(args.query, args.db, args.limit)
            print_rows(rows, ["id", "title", "category", "sensitivity", "source_path", "trace_type", "value", "snippet"])
            return

    if args.command == "export":
        summary = export_markdown(args.output_dir, args.db, args.overwrite)
        print(
            "Export complete: "
            f"output={summary.output_dir} "
            f"written={summary.written} "
            f"skipped={summary.skipped}"
        )
        return

    if args.command == "synthesis":
        if args.synthesis_command == "build":
            rows = build_synthesis_notes(
                args.db,
                args.source_id,
                use_ai=args.ai,
                model=args.model,
                ollama_host=args.ollama_host,
                timeout=args.timeout,
                allow_fallback=not args.no_fallback,
            )
            print(f"Synthesis notes built: {len(rows)}")
            if rows:
                print_rows(rows, ["id", "title", "note_type", "status"])
            return
        if args.synthesis_command == "list":
            rows = list_synthesis_notes(args.db)
            print_rows(rows, ["id", "title", "note_type", "status", "source", "updated_at"])
            return
        if args.synthesis_command == "search":
            rows = search_synthesis_notes(args.query, args.db, args.limit)
            print_rows(rows, ["id", "title", "note_type", "status", "source", "snippet"])
            return

    parser.error("Unknown command")
