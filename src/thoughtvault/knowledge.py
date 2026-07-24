from __future__ import annotations

import json
from collections import defaultdict

from .db import connect, init_db

KNOWLEDGE_GENERATOR = "knowledge-rule-v1"
TOPIC_TRACE_TYPES = {"technology", "heading"}
VALID_KNOWLEDGE_STATUSES = {"generated", "accepted", "rejected", "stale"}


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


def _json_id_set(value: object) -> set[int]:
    if not value:
        return set()
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, list):
        return set()
    return {int(item) for item in parsed if isinstance(item, int) or str(item).isdigit()}


def _json_id_union(*values: object) -> str:
    merged: set[int] = set()
    for value in values:
        merged.update(_json_id_set(value))
    return json.dumps(sorted(merged))


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
            existing = conn.execute(
                """
                SELECT id, topic, title, status, updated_at
                FROM knowledge_pages
                WHERE topic = ?
                """,
                (topic_value,),
            ).fetchone()
            if existing and existing["status"] == "accepted":
                row = conn.execute(
                    """
                    UPDATE knowledge_pages
                    SET status = 'stale', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    RETURNING id, topic, title, status, updated_at
                    """,
                    (existing["id"],),
                ).fetchone()
                pages.append(dict(row))
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
                    status = 'generated',
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
        _rebuild_knowledge_links(conn)
        conn.commit()
        return pages
    finally:
        conn.close()


def _knowledge_page_rows(conn, page_id: int | None = None) -> list[dict[str, object]]:
    params: list[object] = []
    where = "WHERE status != 'rejected'"
    if page_id is not None:
        where += " AND id = ?"
        params.append(page_id)
    rows = conn.execute(
        f"""
        SELECT id, topic, title, body, status,
               source_document_ids, source_chunk_ids, source_fact_ids
        FROM knowledge_pages
        {where}
        ORDER BY id
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _link_evidence(left: dict[str, object], right: dict[str, object]) -> tuple[str, dict[str, object], float]:
    left_docs = _json_id_set(left["source_document_ids"])
    right_docs = _json_id_set(right["source_document_ids"])
    left_chunks = _json_id_set(left["source_chunk_ids"])
    right_chunks = _json_id_set(right["source_chunk_ids"])
    left_facts = _json_id_set(left["source_fact_ids"])
    right_facts = _json_id_set(right["source_fact_ids"])

    shared_documents = sorted(left_docs & right_docs)
    shared_chunks = sorted(left_chunks & right_chunks)
    shared_facts = sorted(left_facts & right_facts)
    left_topic = str(left["topic"]).casefold()
    right_topic = str(right["topic"]).casefold()
    left_body = str(left["body"]).casefold()
    right_body = str(right["body"]).casefold()
    topic_mentions = []
    if left_topic and left_topic in right_body:
        topic_mentions.append(str(left["topic"]))
    if right_topic and right_topic in left_body:
        topic_mentions.append(str(right["topic"]))

    score = float(len(shared_documents) + len(shared_chunks) * 2 + len(shared_facts) * 3 + len(topic_mentions))
    relation_type = "mentions_topic" if topic_mentions and not shared_facts else "shared_evidence"
    evidence = {
        "shared_document_ids": shared_documents,
        "shared_chunk_ids": shared_chunks,
        "shared_fact_ids": shared_facts,
        "topic_mentions": topic_mentions,
    }
    return relation_type, evidence, score


def _upsert_link(
    conn,
    source_page_id: int,
    target_page_id: int,
    relation_type: str,
    evidence: dict[str, object],
    score: float,
) -> None:
    conn.execute(
        """
        INSERT INTO knowledge_page_links (
            source_page_id, target_page_id, relation_type, evidence_json, score, updated_at
        )
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(source_page_id, target_page_id, relation_type) DO UPDATE SET
            evidence_json = excluded.evidence_json,
            score = excluded.score,
            updated_at = CURRENT_TIMESTAMP
        """,
        (source_page_id, target_page_id, relation_type, json.dumps(evidence), score),
    )


def _rebuild_knowledge_links(conn, page_id: int | None = None, min_score: float = 1.0) -> list[dict[str, object]]:
    if page_id is None:
        conn.execute("DELETE FROM knowledge_page_links")
    else:
        conn.execute(
            """
            DELETE FROM knowledge_page_links
            WHERE source_page_id = ? OR target_page_id = ?
            """,
            (page_id, page_id),
        )

    pages = _knowledge_page_rows(conn)
    if page_id is None:
        pairs = [
            (left, right)
            for index, left in enumerate(pages)
            for right in pages[index + 1:]
        ]
    else:
        selected = next((page for page in pages if int(page["id"]) == page_id), None)
        pairs = [] if selected is None else [
            (selected, page)
            for page in pages
            if int(page["id"]) != page_id
        ]
    for left, right in pairs:
        relation_type, evidence, score = _link_evidence(left, right)
        if score < min_score:
            continue
        left_id = int(left["id"])
        right_id = int(right["id"])
        source_id, target_id = sorted([left_id, right_id])
        _upsert_link(conn, source_id, target_id, relation_type, evidence, score)
    params: list[object] = []
    where = ""
    if page_id is not None:
        where = "WHERE links.source_page_id = ? OR links.target_page_id = ?"
        params.extend([page_id, page_id])
    rows = conn.execute(
        f"""
        SELECT links.id, links.source_page_id, source.topic AS source_topic,
               links.target_page_id, target.topic AS target_topic,
               links.relation_type, links.evidence_json, links.score, links.updated_at
        FROM knowledge_page_links AS links
        JOIN knowledge_pages AS source ON source.id = links.source_page_id
        JOIN knowledge_pages AS target ON target.id = links.target_page_id
        {where}
        ORDER BY links.score DESC, links.updated_at DESC, links.id DESC
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def build_knowledge_links(
    db_path: str | None = None,
    page_id: int | None = None,
    min_score: float = 1.0,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = _rebuild_knowledge_links(conn, page_id=page_id, min_score=min_score)
        conn.commit()
        return rows
    finally:
        conn.close()


def list_knowledge_links(
    db_path: str | None = None,
    page_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        params: list[object] = []
        where = ""
        if page_id is not None:
            where = "WHERE links.source_page_id = ? OR links.target_page_id = ?"
            params.extend([page_id, page_id])
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT links.id, links.source_page_id, source.topic AS source_topic,
                   links.target_page_id, target.topic AS target_topic,
                   links.relation_type, links.evidence_json, links.score, links.updated_at
            FROM knowledge_page_links AS links
            JOIN knowledge_pages AS source ON source.id = links.source_page_id
            JOIN knowledge_pages AS target ON target.id = links.target_page_id
            {where}
            ORDER BY links.score DESC, links.updated_at DESC, links.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def merge_knowledge_pages(
    target_page_id: int,
    source_page_id: int,
    db_path: str | None = None,
) -> dict[str, object] | None:
    if target_page_id == source_page_id:
        raise ValueError("Cannot merge a knowledge page into itself")
    init_db(db_path)
    conn = connect(db_path)
    try:
        target = get_knowledge_page(target_page_id, db_path)
        source = get_knowledge_page(source_page_id, db_path)
        if target is None or source is None:
            return None

        merged_body = "\n\n".join([
            str(target["body"]).rstrip(),
            f"## Merged From: {source['title']}",
            str(source["body"]).strip(),
        ])
        target_status = "stale" if target["status"] in {"accepted", "stale"} else "generated"
        row = conn.execute(
            """
            UPDATE knowledge_pages
            SET body = ?,
                source_document_ids = ?,
                source_chunk_ids = ?,
                source_fact_ids = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING id, topic, title, status, updated_at
            """,
            (
                merged_body,
                _json_id_union(target["source_document_ids"], source["source_document_ids"]),
                _json_id_union(target["source_chunk_ids"], source["source_chunk_ids"]),
                _json_id_union(target["source_fact_ids"], source["source_fact_ids"]),
                target_status,
                target_page_id,
            ),
        ).fetchone()
        source_row = conn.execute(
            """
            UPDATE knowledge_pages
            SET status = 'rejected', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING id, topic, title, status, updated_at
            """,
            (source_page_id,),
        ).fetchone()
        _rebuild_knowledge_links(conn)
        conn.commit()
        return {"target": dict(row), "source": dict(source_row)}
    finally:
        conn.close()


def list_knowledge_pages(
    db_path: str | None = None,
    limit: int = 50,
    status: str | None = None,
) -> list[dict[str, object]]:
    if status is not None and status not in VALID_KNOWLEDGE_STATUSES:
        raise ValueError(f"Unsupported knowledge page status: {status}")
    init_db(db_path)
    conn = connect(db_path)
    try:
        params: list[object] = []
        where = ""
        if status is not None:
            where = "WHERE status = ?"
            params.append(status)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT id, topic, title, status, generator, updated_at
            FROM knowledge_pages
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            params,
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


def review_knowledge_page(
    page_id: int,
    status: str,
    db_path: str | None = None,
) -> dict[str, object] | None:
    if status not in VALID_KNOWLEDGE_STATUSES:
        raise ValueError(f"Unsupported knowledge page status: {status}")
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            UPDATE knowledge_pages
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING id, topic, title, status, updated_at
            """,
            (status, page_id),
        ).fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


def search_knowledge_pages(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
    status: str | None = None,
) -> list[dict[str, object]]:
    if status is not None and status not in VALID_KNOWLEDGE_STATUSES:
        raise ValueError(f"Unsupported knowledge page status: {status}")
    init_db(db_path)
    conn = connect(db_path)
    tokens = [token.casefold() for token in query.split() if token.strip()]
    try:
        params: list[object] = []
        where = ""
        if status is not None:
            where = "WHERE status = ?"
            params.append(status)
        rows = conn.execute(
            f"""
            SELECT id, topic, title, body, status, updated_at
            FROM knowledge_pages
            {where}
            ORDER BY updated_at DESC, id DESC
            """,
            params,
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
