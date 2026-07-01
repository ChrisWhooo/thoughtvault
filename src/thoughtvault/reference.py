from __future__ import annotations

import json

from .db import connect, init_db
from .search import normalize_query

REFERENCE_CATEGORIES = {"reference", "personal", "company"}
REFERENCE_TRACE_TYPES = {"field", "date", "url", "company", "title", "path"}


def infer_card_category(categories: str, path: str) -> str:
    category_set = {item.strip() for item in categories.split(",") if item.strip()}
    lower_path = path.lower()
    if "company" in category_set:
        return "company_info"
    if "personal" in category_set:
        return "personal_info"
    if "attendance" in lower_path or "勤怠" in path:
        return "attendance"
    if "application" in lower_path or "申請" in path:
        return "application"
    return "reference"


def infer_sensitivity(categories: str) -> str:
    category_set = {item.strip() for item in categories.split(",") if item.strip()}
    if {"personal", "company"} & category_set:
        return "high"
    return "medium"


def build_reference_cards(db_path: str | None = None, source_id: int | None = None) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        source_filter = ""
        params: list[object] = []
        if source_id is not None:
            source_filter = "AND documents.source_id = ?"
            params.append(source_id)

        documents = conn.execute(
            f"""
            SELECT documents.id, documents.title, documents.path, documents.source_categories
            FROM documents
            WHERE documents.document_status != 'deleted'
              AND documents.extraction_status = 'success'
              {source_filter}
            ORDER BY documents.id
            """,
            params,
        ).fetchall()

        cards: list[dict[str, object]] = []
        for document in documents:
            categories = {
                item.strip()
                for item in document["source_categories"].split(",")
                if item.strip()
            }
            if not categories & REFERENCE_CATEGORIES:
                continue

            traces = conn.execute(
                """
                SELECT trace_type, value, raw_text, confidence
                FROM traces
                WHERE document_id = ?
                ORDER BY trace_type, value
                """,
                (document["id"],),
            ).fetchall()
            useful = [dict(row) for row in traces if row["trace_type"] in REFERENCE_TRACE_TYPES]
            if not useful:
                continue

            fields = {
                "source_path": document["path"],
                "traces": useful[:50],
            }
            card_category = infer_card_category(document["source_categories"], document["path"])
            sensitivity = infer_sensitivity(document["source_categories"])
            summary = f"Reference card generated from {document['path']} with {len(useful)} source-backed traces."

            cursor = conn.execute(
                """
                INSERT INTO reference_cards (
                    document_id, title, category, summary, fields_json, sensitivity, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'generated', CURRENT_TIMESTAMP)
                ON CONFLICT(document_id) DO UPDATE SET
                    title = excluded.title,
                    category = excluded.category,
                    summary = excluded.summary,
                    fields_json = excluded.fields_json,
                    sensitivity = excluded.sensitivity,
                    status = 'generated',
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, title, category, summary, sensitivity, status
                """,
                (
                    document["id"],
                    document["title"],
                    card_category,
                    summary,
                    json.dumps(fields, ensure_ascii=False),
                    sensitivity,
                ),
            )
            cards.append(dict(cursor.fetchone()))

        conn.commit()
        return cards
    finally:
        conn.close()


def list_reference_cards(db_path: str | None = None) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                reference_cards.id,
                reference_cards.title,
                reference_cards.category,
                reference_cards.sensitivity,
                reference_cards.status,
                documents.path AS source_path,
                reference_cards.updated_at
            FROM reference_cards
            JOIN documents ON documents.id = reference_cards.document_id
            ORDER BY reference_cards.updated_at DESC, reference_cards.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_reference_cards(query: str, db_path: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    init_db(db_path)
    fts_query = normalize_query(query)
    if fts_query == '""':
        return []
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT
                reference_cards.id,
                reference_cards.title,
                reference_cards.category,
                reference_cards.sensitivity,
                documents.path AS source_path,
                traces.trace_type,
                traces.value,
                snippet(traces_fts, 1, '[', ']', '...', 12) AS snippet,
                bm25(traces_fts) AS rank
            FROM reference_cards
            JOIN documents ON documents.id = reference_cards.document_id
            JOIN traces ON traces.document_id = documents.id
            JOIN traces_fts ON traces_fts.trace_id = traces.id
            WHERE traces_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
