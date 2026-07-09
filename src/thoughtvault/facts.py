from __future__ import annotations

import re
from dataclasses import dataclass

from .db import connect, init_db

EXTRACTOR_VERSION = "facts-rule-v2"
VALID_FACT_STATUSES = {"proposed", "confirmed", "rejected"}

DATE_PATTERN = re.compile(
    r"(?<!\d)((?:19|20)\d{2})\s*[-年/.]\s*(0?[1-9]|1[0-2])"
    r"(?:\s*[-月/.]\s*(0?[1-9]|[12]\d|3[01])\s*日?)?"
)
AMOUNT_PATTERN = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*(日元|円|元|JPY|RMB|USD|美元)",
    re.IGNORECASE,
)
FIELD_PATTERN = re.compile(r"^\s*(?:[-*]\s*)?([^#|\t:：]{2,50})\s*[:：]\s*(.+?)\s*$")
MONTH_TOTAL_PATTERN = re.compile(
    r"(?:交通费|交通費|移動費|移动费|電車代|电车费)"
    r"(?:合计|合計|总计|總計|total)\s*[:：]?\s*"
    r"([\d,]+(?:\.\d+)?)\s*(日元|円|元|JPY|RMB)",
    re.IGNORECASE,
)

PREDICATE_ALIASES = {
    "常驻地": "location",
    "所在地": "location",
    "地点": "location",
    "場所": "location",
    "location": "location",
    "日期": "date",
    "日付": "date",
    "date": "date",
    "时间": "time",
    "時刻": "time",
    "参加者": "participant",
    "参与者": "participant",
    "attendees": "participant",
    "决定": "decision",
    "決定": "decision",
    "decision": "decision",
    "状态": "status",
    "状態": "status",
    "status": "status",
    "公司": "organization",
    "会社": "organization",
    "company": "organization",
}


@dataclass(frozen=True)
class ExtractedFact:
    fact_type: str
    subject: str
    predicate: str
    object_value: str
    normalized_value: str
    unit: str | None
    event_date: str | None
    confidence: float
    source_text: str
    extractor: str = EXTRACTOR_VERSION


@dataclass(frozen=True)
class FactBuildSummary:
    documents: int
    rebuilt: int
    unchanged: int
    facts: int
    errors: int


def _normalize_date(match: re.Match[str]) -> str:
    year, month, day = match.groups()
    if day:
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    return f"{int(year):04d}-{int(month):02d}"


def _normalize_unit(unit: str) -> str:
    lowered = unit.lower()
    if lowered in {"日元", "円", "jpy"}:
        return "JPY"
    if lowered in {"元", "rmb"}:
        return "RMB"
    if lowered in {"usd", "美元"}:
        return "USD"
    return unit.upper()


def _document_subject(title: str, content: str) -> str:
    heading = next(
        (
            line.lstrip("#").strip()
            for line in content.splitlines()
            if line.strip().startswith("#")
        ),
        title,
    )
    for separator in ("：", ":"):
        if separator in heading:
            candidate = heading.split(separator, 1)[1].strip()
            if candidate:
                return candidate
    return heading or title


def _month_subject(title: str, path: str, content: str) -> str | None:
    context = f"{title} {path} {content}"
    match = DATE_PATTERN.search(context)
    if match:
        return f"{int(match.group(1)):04d}-{int(match.group(2)):02d}"
    english_months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    lowered = context.lower()
    year_match = re.search(r"\b((?:19|20)\d{2})\b", context)
    for name, month in english_months.items():
        if re.search(rf"\b{name}\b", lowered) and year_match:
            return f"{int(year_match.group(1)):04d}-{month:02d}"
    return None


def _field_predicate(label: str) -> str:
    normalized = " ".join(label.strip().split()).lower()
    return PREDICATE_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _split_people(value: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[、,，;/；]", value)
        if 1 < len(item.strip()) <= 60
    ]


def extract_facts(content: str, title: str, path: str) -> list[ExtractedFact]:
    subject = _document_subject(title, content)
    facts: list[ExtractedFact] = []
    chunk_date_match = DATE_PATTERN.search(content)
    chunk_date = _normalize_date(chunk_date_match) if chunk_date_match else None
    context_date = chunk_date or _month_subject(title, path, content)

    for match in MONTH_TOTAL_PATTERN.finditer(content):
        month_subject = _month_subject(title, path, content)
        if not month_subject:
            continue
        amount = match.group(1).replace(",", "")
        unit = _normalize_unit(match.group(2))
        facts.append(
            ExtractedFact(
                fact_type="amount",
                subject=month_subject,
                predicate="transport_total",
                object_value=f"{match.group(1)} {match.group(2)}",
                normalized_value=amount,
                unit=unit,
                event_date=month_subject,
                confidence=0.98,
                source_text=match.group(0),
            )
        )

    for line in content.splitlines():
        match = FIELD_PATTERN.match(line)
        if not match:
            continue
        label = " ".join(match.group(1).split())
        value = match.group(2).strip()
        predicate = _field_predicate(label)
        if MONTH_TOTAL_PATTERN.search(line):
            continue
        if predicate == "participant":
            for person in _split_people(value):
                facts.append(
                    ExtractedFact(
                        fact_type="person",
                        subject=subject,
                        predicate="participant",
                        object_value=person,
                        normalized_value=person.casefold(),
                        unit=None,
                        event_date=context_date,
                        confidence=0.92,
                        source_text=line.strip(),
                    )
                )
            continue

        date_match = DATE_PATTERN.search(value)
        amount_match = AMOUNT_PATTERN.search(value)
        if date_match and predicate in {"date", "time"}:
            normalized_date = _normalize_date(date_match)
            facts.append(
                ExtractedFact(
                    fact_type="date",
                    subject=subject,
                    predicate=predicate,
                    object_value=value,
                    normalized_value=normalized_date,
                    unit=None,
                    event_date=normalized_date,
                    confidence=0.95,
                    source_text=line.strip(),
                )
            )
        elif amount_match:
            facts.append(
                ExtractedFact(
                    fact_type="amount",
                    subject=subject,
                    predicate=predicate,
                    object_value=value,
                    normalized_value=amount_match.group(1).replace(",", ""),
                    unit=_normalize_unit(amount_match.group(2)),
                    event_date=context_date,
                    confidence=0.85,
                    source_text=line.strip(),
                )
            )
        else:
            fact_type = predicate if predicate in {
                "location", "decision", "status", "organization"
            } else "field"
            facts.append(
                ExtractedFact(
                    fact_type=fact_type,
                    subject=subject,
                    predicate=predicate,
                    object_value=value,
                    normalized_value=" ".join(value.casefold().split()),
                    unit=None,
                    event_date=context_date,
                    confidence=0.78 if fact_type == "field" else 0.9,
                    source_text=line.strip(),
                )
            )

    deduped: dict[tuple[object, ...], ExtractedFact] = {}
    for fact in facts:
        key = (
            fact.fact_type,
            fact.subject.casefold(),
            fact.predicate,
            fact.normalized_value,
            fact.event_date,
        )
        deduped.setdefault(key, fact)
    return list(deduped.values())


def build_facts(db_path: str | None = None, force: bool = False) -> FactBuildSummary:
    init_db(db_path)
    conn = connect(db_path)
    totals = {"documents": 0, "rebuilt": 0, "unchanged": 0, "facts": 0, "errors": 0}
    try:
        documents = conn.execute(
            """
            SELECT documents.id, documents.title, documents.path, documents.content_hash,
                   fact_build_state.content_hash AS built_hash,
                   fact_build_state.extractor_version AS built_version
            FROM documents
            LEFT JOIN fact_build_state ON fact_build_state.document_id = documents.id
            WHERE documents.document_status != 'deleted'
              AND documents.extraction_status = 'success'
            ORDER BY documents.id
            """
        ).fetchall()
        totals["documents"] = len(documents)
        for document in documents:
            if (
                not force
                and document["built_hash"] == document["content_hash"]
                and document["built_version"] == EXTRACTOR_VERSION
            ):
                totals["unchanged"] += 1
                continue
            try:
                chunks = conn.execute(
                    """
                    SELECT id, content
                    FROM chunks
                    WHERE document_id = ?
                    ORDER BY chunk_index
                    """,
                    (document["id"],),
                ).fetchall()
                reviewed_rows = conn.execute(
                    """
                    SELECT fact_type, subject, predicate, normalized_value,
                           COALESCE(event_date, '') AS event_date, status
                    FROM facts
                    WHERE document_id = ? AND status != 'proposed'
                    """,
                    (document["id"],),
                ).fetchall()
                reviewed_status = {
                    (
                        row["fact_type"],
                        row["subject"].casefold(),
                        row["predicate"],
                        row["normalized_value"],
                        row["event_date"],
                    ): row["status"]
                    for row in reviewed_rows
                }
                conn.execute("DELETE FROM facts WHERE document_id = ?", (document["id"],))
                for chunk in chunks:
                    for fact in extract_facts(
                        chunk["content"],
                        document["title"],
                        document["path"],
                    ):
                        fact_key = (
                            fact.fact_type,
                            fact.subject.casefold(),
                            fact.predicate,
                            fact.normalized_value,
                            fact.event_date or "",
                        )
                        status = reviewed_status.get(fact_key, "proposed")
                        cursor = conn.execute(
                            """
                            INSERT OR IGNORE INTO facts (
                                document_id, chunk_id, fact_type, subject, predicate,
                                object_value, normalized_value, unit, event_date,
                                confidence, extractor, status, source_text
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                document["id"],
                                chunk["id"],
                                fact.fact_type,
                                fact.subject,
                                fact.predicate,
                                fact.object_value,
                                fact.normalized_value,
                                fact.unit,
                                fact.event_date,
                                fact.confidence,
                                fact.extractor,
                                status,
                                fact.source_text,
                            ),
                        )
                        totals["facts"] += max(cursor.rowcount, 0)
                conn.execute(
                    """
                    INSERT INTO fact_build_state (
                        document_id, content_hash, extractor_version, updated_at
                    )
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(document_id) DO UPDATE SET
                        content_hash = excluded.content_hash,
                        extractor_version = excluded.extractor_version,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (document["id"], document["content_hash"], EXTRACTOR_VERSION),
                )
                totals["rebuilt"] += 1
                conn.commit()
            except (OSError, ValueError):
                totals["errors"] += 1
                conn.rollback()
        return FactBuildSummary(**totals)
    finally:
        conn.close()


def list_facts(
    db_path: str | None = None,
    limit: int = 50,
    status: str | None = None,
    fact_type: str | None = None,
    query: str | None = None,
) -> list[dict[str, object]]:
    init_db(db_path)
    clauses = []
    params: list[object] = []
    if status:
        clauses.append("facts.status = ?")
        params.append(status)
    if fact_type:
        clauses.append("facts.fact_type = ?")
        params.append(fact_type)
    if query:
        clauses.append(
            """
            (facts.subject LIKE ? OR facts.predicate LIKE ?
             OR facts.object_value LIKE ? OR facts.normalized_value LIKE ?
             OR facts.source_text LIKE ? OR documents.path LIKE ?)
            """
        )
        pattern = f"%{query}%"
        params.extend([pattern] * 6)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            f"""
            SELECT facts.id, facts.fact_type, facts.subject, facts.predicate,
                   facts.object_value, facts.normalized_value, facts.unit,
                   facts.event_date, facts.confidence, facts.status,
                   source_roots.name AS source, documents.path
            FROM facts
            JOIN documents ON documents.id = facts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            {where}
            ORDER BY facts.id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_confirmed_facts(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT facts.id, facts.fact_type, facts.subject, facts.predicate,
                   facts.object_value, facts.normalized_value, facts.unit,
                   facts.event_date, facts.confidence, facts.source_text,
                   source_roots.name AS source, documents.path, documents.title
            FROM facts
            JOIN documents ON documents.id = facts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE facts.status = 'confirmed'
              AND documents.document_status != 'deleted'
            ORDER BY facts.confidence DESC, facts.id DESC
            LIMIT 500
            """
        ).fetchall()
        lowered_query = query.casefold()
        requested_months = {
            int(value)
            for value in re.findall(r"(?<!\d)(1[0-2]|0?[1-9])\s*月", query)
        }
        concept_predicates = set()
        if any(term in lowered_query for term in ("交通费", "交通費", "移動費", "电车费", "電車代")):
            concept_predicates.add("transport_total")
        if any(term in lowered_query for term in ("地点", "地方", "哪里", "哪儿", "場所", "どこ", "location")):
            concept_predicates.add("location")
        if any(term in lowered_query for term in ("决定", "決定", "decision")):
            concept_predicates.add("decision")
        if any(term in lowered_query for term in ("参加", "参与", "誰", "谁", "participant")):
            concept_predicates.add("participant")

        terms = [
            term.casefold()
            for term in re.findall(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u9fff]{2,}", query)
        ]
        matches = []
        for row in rows:
            haystack = " ".join(
                str(row[key])
                for key in (
                    "subject", "predicate", "object_value", "normalized_value",
                    "event_date", "source_text", "path",
                )
                if row[key] is not None
            ).casefold()
            score = 0.0
            score += sum(1.0 for term in terms if term in haystack)
            if row["predicate"] in concept_predicates:
                score += 6.0
            if requested_months and row["event_date"]:
                try:
                    fact_month = int(str(row["event_date"])[5:7])
                except (ValueError, IndexError):
                    fact_month = 0
                if fact_month in requested_months:
                    score += 8.0
            if str(row["subject"]).casefold() in lowered_query:
                score += 4.0
            if score <= 0.0:
                continue
            result = dict(row)
            result["match_score"] = score + float(row["confidence"])
            matches.append(result)
        return sorted(
            matches,
            key=lambda item: float(item["match_score"]),
            reverse=True,
        )[:limit]
    finally:
        conn.close()


def fact_evidence_text(fact: dict[str, object]) -> str:
    if fact["predicate"] == "transport_total":
        return (
            f"{fact['subject']} 交通费合计：{fact['object_value']}；"
            "审核状态：confirmed"
        )
    date_part = f"；日期：{fact['event_date']}" if fact.get("event_date") else ""
    return (
        f"{fact['subject']} | {fact['predicate']}：{fact['object_value']}"
        f"{date_part}；审核状态：confirmed"
    )


def search_confirmed_fact_conflicts(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
) -> list[dict[str, object]]:
    facts = search_confirmed_facts(query, db_path, limit=100)
    grouped: dict[tuple[object, ...], dict[str, object]] = {}
    for fact in facts:
        if fact["fact_type"] in {"person", "decision"} or fact["predicate"] == "participant":
            continue
        key = (
            fact["fact_type"],
            fact["subject"],
            fact["predicate"],
            fact["event_date"] or "",
            fact["unit"] or "",
        )
        group = grouped.setdefault(
            key,
            {
                "fact_type": fact["fact_type"],
                "subject": fact["subject"],
                "predicate": fact["predicate"],
                "event_date": fact["event_date"] or "",
                "unit": fact["unit"] or "",
                "values": {},
            },
        )
        group["values"].setdefault(
            fact["normalized_value"],
            {
                "object_value": fact["object_value"],
                "path": fact["path"],
            },
        )
    conflicts = []
    for group in grouped.values():
        values = group.pop("values")
        if len(values) <= 1:
            continue
        group["value_count"] = len(values)
        group["values"] = list(values.values())
        conflicts.append(group)
    return conflicts[:limit]


def list_fact_conflicts(
    db_path: str | None = None,
    limit: int = 50,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                facts.fact_type,
                facts.subject,
                facts.predicate,
                COALESCE(facts.event_date, '') AS event_date,
                COALESCE(facts.unit, '') AS unit,
                COUNT(DISTINCT facts.normalized_value) AS value_count,
                GROUP_CONCAT(DISTINCT facts.object_value) AS values_text,
                GROUP_CONCAT(DISTINCT documents.path) AS paths
            FROM facts
            JOIN documents ON documents.id = facts.document_id
            WHERE facts.status != 'rejected'
              AND facts.fact_type NOT IN ('person', 'decision')
              AND facts.predicate != 'participant'
            GROUP BY facts.fact_type, facts.subject, facts.predicate,
                     COALESCE(facts.event_date, ''), COALESCE(facts.unit, '')
            HAVING COUNT(DISTINCT facts.normalized_value) > 1
            ORDER BY value_count DESC, facts.subject, facts.predicate
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def review_fact(
    fact_id: int,
    status: str,
    db_path: str | None = None,
) -> dict[str, object] | None:
    if status not in VALID_FACT_STATUSES:
        raise ValueError(f"Unsupported fact status: {status}")
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            UPDATE facts
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            RETURNING id, fact_type, subject, predicate, object_value, status
            """,
            (status, fact_id),
        ).fetchone()
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()
