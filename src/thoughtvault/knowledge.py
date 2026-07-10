from __future__ import annotations

import json
from collections import defaultdict

from .db import connect, init_db

KNOWLEDGE_GENERATOR = "knowledge-rule-v1"
TOPIC_TRACE_TYPES = {"technology", "heading"}


def _bullet_list(items: list[str], empty: str = "No source-backed items yet.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def _compact(text: str, limit: int = 360) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."


def _topic_title(topic: str) -> str:
    return " ".join(part for part in topic.replace("_", " ").split()) or "Untitled"


def discover_topics(db_path: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        topics: dict[str, dict[str, object]] = {}

        trace_rows = conn.execute(
            """
            SELECT traces.value, traces.trace_type, COUNT(DISTINCT documents.id) AS document_count
            FROM traces
            JOIN documents ON documents.id = traces.document_id
            WHERE traces.trace_type IN ('technology', 'heading')
              AND documents.document_status != 'deleted'
            GROUP BY LOWER(traces.value), traces.trace_type
            ORDER BY document_count DESC, traces.value
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in trace_rows:
            topic = str(row["value"]).strip()
            if len(topic) < 2:
                continue
            key = topic.casefold()
            topics.setdefault(
                key,
                {
                    "topic": topic,
                    "source": f"trace:{row['trace_type']}",
                    "document_count": int(row["document_count"]),
                },
            )

        fact_rows = conn.execute(
            """
            SELECT subject, COUNT(*) AS fact_count
            FROM facts
            WHERE status = 'confirmed'
            GROUP BY subject
            ORDER BY fact_count DESC, subject
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        for row in fact_rows:
            topic = str(row["subject"]).strip()
            if len(topic) < 2:
                continue
            key = topic.casefold()
            topics.setdefault(
                key,
                {
                    "topic": topic,
                    "source": "fact:confirmed",
                    "document_count": int(row["fact_count"]),
                },
            )

        return sorted(
            topics.values(),
            key=lambda item: (-int(item["document_count"]), str(item["topic"]).casefold()),
        )[:limit]
    finally:
        conn.close()


def _load_topic_material(conn, topic: str) -> dict[str, object]:
    like = f"%{topic}%"
    traces = conn.execute(
        """
        SELECT traces.id, traces.trace_type, traces.value, documents.id AS document_id,
               documents.path, documents.title
        FROM traces
        JOIN documents ON documents.id = traces.document_id
        WHERE documents.document_status != 'deleted'
          AND (traces.value LIKE ? OR traces.raw_text LIKE ? OR documents.title LIKE ? OR documents.path LIKE ?)
        ORDER BY traces.trace_type, documents.path, traces.value
        LIMIT 80
        """,
        (like, like, like, like),
    ).fetchall()
    facts = conn.execute(
        """
        SELECT facts.id, facts.fact_type, facts.subject, facts.predicate,
               facts.object_value, facts.event_date, facts.confidence,
               facts.document_id, facts.chunk_id, facts.source_text,
               documents.path, documents.title
        FROM facts
        JOIN documents ON documents.id = facts.document_id
        WHERE facts.status = 'confirmed'
          AND (facts.subject LIKE ? OR facts.predicate LIKE ? OR facts.object_value LIKE ? OR facts.source_text LIKE ?)
        ORDER BY facts.subject, facts.predicate, facts.id
        LIMIT 80
        """,
        (like, like, like, like),
    ).fetchall()
    chunks = conn.execute(
        """
        SELECT chunks.id, chunks.content, chunks.document_id,
               documents.path, documents.title
        FROM chunks
        JOIN documents ON documents.id = chunks.document_id
        WHERE documents.document_status != 'deleted'
          AND (chunks.content LIKE ? OR documents.title LIKE ? OR documents.path LIKE ?)
        ORDER BY documents.path, chunks.chunk_index
        LIMIT 12
        """,
        (like, like, like),
    ).fetchall()
    return {"traces": traces, "facts": facts, "chunks": chunks}


def build_knowledge_page_body(topic: str, material: dict[str, object]) -> tuple[str, list[int], list[int], list[int]]:
    traces = list(material["traces"])
    facts = list(material["facts"])
    chunks = list(material["chunks"])

    document_ids = sorted({
        int(row["document_id"])
        for row in [*traces, *facts, *chunks]
        if row["document_id"] is not None
    })
    chunk_ids = sorted({
        int(row["id"])
        for row in chunks
        if row["id"] is not None
    } | {
        int(row["chunk_id"])
        for row in facts
        if row["chunk_id"] is not None
    })
    fact_ids = sorted(int(row["id"]) for row in facts)

    facts_by_type: dict[str, list[str]] = defaultdict(list)
    for fact in facts:
        value = f"{fact['subject']} | {fact['predicate']}: {fact['object_value']}"
        if fact["event_date"]:
            value += f" ({fact['event_date']})"
        value += f" [{fact['path']}]"
        facts_by_type[str(fact["fact_type"])].append(value)

    trace_lines = [
        f"{trace['trace_type']}: {trace['value']} [{trace['path']}]"
        for trace in traces[:20]
    ]
    chunk_lines = [
        f"{_compact(chunk['content'])} [{chunk['path']}]"
        for chunk in chunks[:8]
    ]
    source_paths = sorted({
        str(row["path"])
        for row in [*traces, *facts, *chunks]
        if row["path"]
    })

    lines = [
        f"# {_topic_title(topic)}",
        "",
        "## What This Page Is",
        "",
        "This is a generated, source-backed knowledge page. It should be reviewed before being treated as durable knowledge.",
        "",
        "## Confirmed Facts",
        "",
    ]
    if facts_by_type:
        for fact_type, values in sorted(facts_by_type.items()):
            lines.extend([f"### {fact_type}", "", _bullet_list(values[:20]), ""])
    else:
        lines.extend(["- No confirmed facts linked to this topic yet.", ""])

    lines.extend(
        [
            "## Detected Trace Evidence",
            "",
            _bullet_list(trace_lines),
            "",
            "## Source Excerpts",
            "",
            _bullet_list(chunk_lines),
            "",
            "## Source Documents",
            "",
            _bullet_list(source_paths),
            "",
            "## Review Notes",
            "",
            "- Status: generated",
            "- Review needed: confirm whether the topic page is useful, merge duplicates, and remove weak evidence.",
        ]
    )
    return "\n".join(lines), document_ids, chunk_ids, fact_ids


def build_knowledge_pages(
    db_path: str | None = None,
    topic: str | None = None,
    limit: int = 20,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        topics = [{"topic": topic}] if topic else discover_topics(db_path, limit)
        pages: list[dict[str, object]] = []
        for topic_row in topics:
            topic_value = str(topic_row["topic"]).strip()
            if not topic_value:
                continue
            material = _load_topic_material(conn, topic_value)
            body, document_ids, chunk_ids, fact_ids = build_knowledge_page_body(topic_value, material)
            if not document_ids and not fact_ids:
                continue
            row = conn.execute(
                """
                INSERT INTO knowledge_pages (
                    topic, title, body, source_document_ids, source_chunk_ids,
                    source_fact_ids, generator, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'generated', CURRENT_TIMESTAMP)
                ON CONFLICT(topic) DO UPDATE SET
                    title = excluded.title,
                    body = excluded.body,
                    source_document_ids = excluded.source_document_ids,
                    source_chunk_ids = excluded.source_chunk_ids,
                    source_fact_ids = excluded.source_fact_ids,
                    generator = excluded.generator,
                    status = CASE
                        WHEN knowledge_pages.status = 'accepted' THEN 'stale'
                        ELSE 'generated'
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, topic, title, status, updated_at
                """,
                (
                    topic_value,
                    _topic_title(topic_value),
                    body,
                    json.dumps(document_ids),
                    json.dumps(chunk_ids),
                    json.dumps(fact_ids),
                    KNOWLEDGE_GENERATOR,
                ),
            ).fetchone()
            pages.append(dict(row))
        conn.commit()
        return pages
    finally:
        conn.close()


def list_knowledge_pages(db_path: str | None = None, limit: int = 50) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, topic, title, status, generator, updated_at
            FROM knowledge_pages
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_knowledge_page(page_id: int, db_path: str | None = None) -> dict[str, object] | None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, topic, title, body, source_document_ids, source_chunk_ids,
                   source_fact_ids, generator, status, created_at, updated_at
            FROM knowledge_pages
            WHERE id = ?
            """,
            (page_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def search_knowledge_pages(query: str, db_path: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    tokens = [token.casefold() for token in query.split() if token.strip()]
    try:
        rows = conn.execute(
            """
            SELECT id, topic, title, body, status, updated_at
            FROM knowledge_pages
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        results = []
        for row in rows:
            haystack = f"{row['topic']} {row['title']} {row['body']}".casefold()
            if tokens and not all(token in haystack for token in tokens):
                continue
            snippet = _compact(str(row["body"]), 240)
            item = dict(row)
            item.pop("body", None)
            item["snippet"] = snippet
            results.append(item)
            if len(results) >= limit:
                break
        return results
    finally:
        conn.close()
