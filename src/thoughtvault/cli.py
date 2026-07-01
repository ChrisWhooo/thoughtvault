from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import init_db
from .exporter import export_markdown
from .recall import recall
from .reference import build_reference_cards, list_reference_cards, search_reference_cards
from .scanner import list_documents, scan
from .search import search
from .sources import add_source, list_sources


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


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
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

    parser.error("Unknown command")
