from __future__ import annotations

from pathlib import Path

from .db import connect, init_db

VALID_CATEGORIES = {
    "project",
    "reference",
    "memo",
    "conversation",
    "personal",
    "company",
    "unknown",
}


def normalize_categories(categories: list[str] | tuple[str, ...]) -> str:
    cleaned = []
    for category in categories:
        value = category.strip().lower()
        if not value:
            continue
        if value not in VALID_CATEGORIES:
            allowed = ", ".join(sorted(VALID_CATEGORIES))
            raise ValueError(f"Unsupported category '{category}'. Allowed: {allowed}")
        if value not in cleaned:
            cleaned.append(value)
    if not cleaned:
        cleaned.append("unknown")
    return ",".join(cleaned)


def add_source(
    root_path: str,
    categories: list[str],
    name: str | None = None,
    db_path: str | None = None,
) -> int:
    init_db(db_path)
    resolved_root = Path(root_path).expanduser().resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"Source root does not exist: {resolved_root}")
    if not resolved_root.is_dir():
        raise NotADirectoryError(f"Source root is not a directory: {resolved_root}")

    source_name = name or resolved_root.name
    category_value = normalize_categories(categories)

    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO source_roots (name, root_path, categories)
            VALUES (?, ?, ?)
            ON CONFLICT(root_path) DO UPDATE SET
                name = excluded.name,
                categories = excluded.categories,
                scan_enabled = 1
            RETURNING id
            """,
            (source_name, str(resolved_root), category_value),
        )
        source_id = int(cursor.fetchone()["id"])
        conn.commit()
        return source_id
    finally:
        conn.close()


def list_sources(db_path: str | None = None) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, name, root_path, categories, scan_enabled, last_scanned_at
            FROM source_roots
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
