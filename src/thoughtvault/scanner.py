from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import connect, init_db
from .indexer import clear_document_index, reindex_document

SUPPORTED_EXTENSIONS = {".md", ".txt"}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".thoughtvault",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}


@dataclass(frozen=True)
class ScanSummary:
    sources: int = 0
    scanned_files: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0
    deleted: int = 0
    skipped: int = 0
    errors: int = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iso_mtime(path: Path) -> str:
    timestamp = path.stat().st_mtime
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def iter_supported_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        yield path


def scan(db_path: str | None = None, source_id: int | None = None) -> ScanSummary:
    init_db(db_path)
    totals = {
        "sources": 0,
        "scanned_files": 0,
        "new": 0,
        "changed": 0,
        "unchanged": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": 0,
    }

    conn = connect(db_path)
    try:
        if source_id is None:
            sources = conn.execute(
                """
                SELECT id, root_path, categories
                FROM source_roots
                WHERE scan_enabled = 1
                ORDER BY id
                """
            ).fetchall()
        else:
            sources = conn.execute(
                """
                SELECT id, root_path, categories
                FROM source_roots
                WHERE id = ? AND scan_enabled = 1
                """,
                (source_id,),
            ).fetchall()

        for source in sources:
            totals["sources"] += 1
            root = Path(source["root_path"])
            seen_paths: set[str] = set()

            if not root.exists():
                conn.execute(
                    """
                    UPDATE documents
                    SET document_status = 'missing_source', indexed_at = CURRENT_TIMESTAMP
                    WHERE source_id = ?
                    """,
                    (source["id"],),
                )
                totals["errors"] += 1
                continue

            for path in iter_supported_files(root):
                try:
                    relative_path = path.relative_to(root).as_posix()
                    seen_paths.add(relative_path)
                    file_hash = sha256_file(path)
                    stat = path.stat()
                    modified_at = iso_mtime(path)
                    file_type = path.suffix.lower().lstrip(".")
                    title = path.stem

                    existing = conn.execute(
                        """
                        SELECT content_hash, document_status
                        FROM documents
                        WHERE source_id = ? AND path = ?
                        """,
                        (source["id"], relative_path),
                    ).fetchone()

                    if existing is None:
                        status = "new"
                        totals["new"] += 1
                    elif existing["content_hash"] != file_hash:
                        status = "changed"
                        totals["changed"] += 1
                    else:
                        status = "unchanged"
                        totals["unchanged"] += 1

                    conn.execute(
                        """
                        INSERT INTO documents (
                            source_id, path, absolute_path, title, file_type,
                            source_categories, size_bytes, content_hash,
                            modified_at, indexed_at, document_status, extraction_status,
                            error_message
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'pending', NULL)
                        ON CONFLICT(source_id, path) DO UPDATE SET
                            absolute_path = excluded.absolute_path,
                            title = excluded.title,
                            file_type = excluded.file_type,
                            source_categories = excluded.source_categories,
                            size_bytes = excluded.size_bytes,
                            content_hash = excluded.content_hash,
                            modified_at = excluded.modified_at,
                            indexed_at = CURRENT_TIMESTAMP,
                            document_status = excluded.document_status,
                            error_message = NULL
                        """,
                        (
                            source["id"],
                            relative_path,
                            str(path.resolve()),
                            title,
                            file_type,
                            source["categories"],
                            stat.st_size,
                            file_hash,
                            modified_at,
                            status,
                        ),
                    )
                    document = conn.execute(
                        """
                        SELECT id
                        FROM documents
                        WHERE source_id = ? AND path = ?
                        """,
                        (source["id"], relative_path),
                    ).fetchone()
                    document_id = int(document["id"])
                    chunk_count = conn.execute(
                        "SELECT COUNT(*) AS count FROM chunks WHERE document_id = ?",
                        (document_id,),
                    ).fetchone()["count"]
                    if status in {"new", "changed"} or chunk_count == 0:
                        try:
                            reindex_document(
                                conn,
                                document_id,
                                str(path.resolve()),
                                title,
                                relative_path,
                            )
                        except UnicodeError as exc:
                            totals["errors"] += 1
                            conn.execute(
                                """
                                UPDATE documents
                                SET extraction_status = 'failed', error_message = ?
                                WHERE id = ?
                                """,
                                (str(exc), document_id),
                            )
                    totals["scanned_files"] += 1
                except OSError as exc:
                    totals["errors"] += 1
                    conn.execute(
                        """
                        INSERT INTO documents (
                            source_id, path, absolute_path, title, file_type,
                            source_categories, size_bytes, content_hash,
                            modified_at, indexed_at, document_status, extraction_status,
                            error_message
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 0, '', '', CURRENT_TIMESTAMP, 'error', 'failed', ?)
                        ON CONFLICT(source_id, path) DO UPDATE SET
                            indexed_at = CURRENT_TIMESTAMP,
                            document_status = 'error',
                            extraction_status = 'failed',
                            error_message = excluded.error_message
                        """,
                        (
                            source["id"],
                            path.name,
                            str(path),
                            path.stem,
                            path.suffix.lower().lstrip("."),
                            source["categories"],
                            str(exc),
                        ),
                    )

            existing_paths = conn.execute(
                "SELECT path FROM documents WHERE source_id = ?",
                (source["id"],),
            ).fetchall()
            for row in existing_paths:
                if row["path"] not in seen_paths:
                    current = conn.execute(
                        """
                        SELECT document_status
                        FROM documents
                        WHERE source_id = ? AND path = ?
                        """,
                        (source["id"], row["path"]),
                    ).fetchone()
                    if current and current["document_status"] != "deleted":
                        totals["deleted"] += 1
                    document = conn.execute(
                        """
                        SELECT id
                        FROM documents
                        WHERE source_id = ? AND path = ?
                        """,
                        (source["id"], row["path"]),
                    ).fetchone()
                    if document:
                        clear_document_index(conn, int(document["id"]))
                    conn.execute(
                        """
                        UPDATE documents
                        SET document_status = 'deleted', indexed_at = CURRENT_TIMESTAMP
                        WHERE source_id = ? AND path = ?
                        """,
                        (source["id"], row["path"]),
                    )

            conn.execute(
                """
                UPDATE source_roots
                SET last_scanned_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (source["id"],),
            )

        conn.commit()
    finally:
        conn.close()

    return ScanSummary(**totals)


def list_documents(db_path: str | None = None) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                documents.id,
                source_roots.name AS source,
                documents.path,
                documents.file_type,
                documents.size_bytes,
                documents.document_status,
                documents.modified_at,
                COUNT(DISTINCT chunks.id) AS chunks,
                COUNT(DISTINCT traces.id) AS traces
            FROM documents
            JOIN source_roots ON source_roots.id = documents.source_id
            LEFT JOIN chunks ON chunks.document_id = documents.id
            LEFT JOIN traces ON traces.document_id = documents.id
            GROUP BY documents.id
            ORDER BY documents.indexed_at DESC, documents.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
