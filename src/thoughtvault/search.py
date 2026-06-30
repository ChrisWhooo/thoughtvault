from __future__ import annotations

import re

from .db import connect, init_db


TOKEN_RE = re.compile(r"[\w一-龥ぁ-んァ-ンー]+", re.UNICODE)


def normalize_query(query: str) -> str:
    tokens = TOKEN_RE.findall(query)
    if not tokens:
        return '""'
    return " OR ".join(tokens)


def search(query: str, db_path: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    init_db(db_path)
    fts_query = normalize_query(query)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                'chunk' AS result_type,
                documents.path AS path,
                documents.title AS title,
                snippet(chunks_fts, 0, '[', ']', '...', 12) AS snippet,
                bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN documents ON documents.id = chunks_fts.document_id
            WHERE chunks_fts MATCH ?

            UNION ALL

            SELECT
                'trace' AS result_type,
                documents.path AS path,
                traces.trace_type || ': ' || traces.value AS title,
                snippet(traces_fts, 1, '[', ']', '...', 12) AS snippet,
                bm25(traces_fts) AS rank
            FROM traces_fts
            JOIN traces ON traces.id = traces_fts.trace_id
            JOIN documents ON documents.id = traces_fts.document_id
            WHERE traces_fts MATCH ?

            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, fts_query, limit),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
