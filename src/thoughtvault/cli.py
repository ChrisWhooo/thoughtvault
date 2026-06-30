from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import init_db
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

    parser.error("Unknown command")
