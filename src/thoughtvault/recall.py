from __future__ import annotations

from collections import defaultdict

from .db import connect, init_db
from .search import normalize_query


def recall(
    query: str,
    db_path: str | None = None,
    limit: int = 5,
    evidence_limit: int = 3,
) -> list[dict[str, object]]:
    init_db(db_path)
    fts_query = normalize_query(query)
    if fts_query == '""':
        return []

    conn = connect(db_path)
    try:
        row_limit = max(limit * evidence_limit * 3, 20)
        chunk_rows = conn.execute(
            """
            SELECT
                documents.id AS document_id,
                source_roots.name AS source,
                documents.path AS path,
                documents.title AS title,
                documents.source_categories AS categories,
                snippet(chunks_fts, 0, '[', ']', '...', 18) AS snippet,
                bm25(chunks_fts) AS rank
            FROM chunks_fts
            JOIN documents ON documents.id = chunks_fts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, row_limit),
        ).fetchall()

        trace_rows = conn.execute(
            """
            SELECT
                documents.id AS document_id,
                source_roots.name AS source,
                documents.path AS path,
                documents.title AS title,
                documents.source_categories AS categories,
                traces.trace_type AS trace_type,
                traces.value AS trace_value,
                snippet(traces_fts, 1, '[', ']', '...', 12) AS snippet,
                bm25(traces_fts) AS rank
            FROM traces_fts
            JOIN traces ON traces.id = traces_fts.trace_id
            JOIN documents ON documents.id = traces_fts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE traces_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, row_limit),
        ).fetchall()

        grouped: dict[int, dict[str, object]] = {}
        evidence: dict[int, list[dict[str, object]]] = defaultdict(list)
        trace_values: dict[int, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        def ensure_doc(row) -> dict[str, object]:
            document_id = int(row["document_id"])
            if document_id not in grouped:
                grouped[document_id] = {
                    "document_id": document_id,
                    "source": row["source"],
                    "path": row["path"],
                    "title": row["title"],
                    "categories": row["categories"],
                    "chunk_hits": 0,
                    "trace_hits": 0,
                    "score": 0.0,
                }
            return grouped[document_id]

        for row in chunk_rows:
            doc = ensure_doc(row)
            doc["chunk_hits"] = int(doc["chunk_hits"]) + 1
            doc["score"] = float(doc["score"]) + 1.0
            document_id = int(row["document_id"])
            if len(evidence[document_id]) < evidence_limit:
                evidence[document_id].append({"type": "chunk", "snippet": row["snippet"]})

        for row in trace_rows:
            doc = ensure_doc(row)
            doc["trace_hits"] = int(doc["trace_hits"]) + 1
            doc["score"] = float(doc["score"]) + 1.5
            document_id = int(row["document_id"])
            trace_values[document_id][row["trace_type"]].add(row["trace_value"])
            if len(evidence[document_id]) < evidence_limit:
                evidence[document_id].append(
                    {"type": f"trace:{row['trace_type']}", "snippet": row["snippet"]}
                )

        results = sorted(
            grouped.values(),
            key=lambda item: (
                float(item["score"]),
                int(item["chunk_hits"]) + int(item["trace_hits"]),
            ),
            reverse=True,
        )[:limit]

        for result in results:
            document_id = int(result["document_id"])
            result["evidence"] = evidence[document_id]
            result["technologies"] = sorted(trace_values[document_id].get("technology", set()))
            result["dates"] = sorted(trace_values[document_id].get("date", set()))
            result["headings"] = sorted(trace_values[document_id].get("heading", set()))[:5]

        return results
    finally:
        conn.close()
