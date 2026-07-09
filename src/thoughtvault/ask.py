from __future__ import annotations

import re
from dataclasses import dataclass
from sqlite3 import OperationalError
from typing import Callable

from .db import connect, init_db
from .embeddings import (
    DEFAULT_EMBEDDING_MODEL,
    Embedder,
    generate_embeddings_with_ollama,
    semantic_search,
)
from .search import normalize_query
from .synthesis import DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL, generate_with_ollama

AnswerGenerator = Callable[[str, str, str, float], str]

MAX_EVIDENCE_CHARS = 1400
DEFAULT_EVIDENCE_LIMIT = 5
MAX_EVIDENCE_PER_PATH = 2
STOP_TERMS = {
    "什么",
    "哪些",
    "内容",
    "关于",
    "里面",
    "我的",
    "知识",
    "知识库",
    "资料",
    "可以",
    "怎么",
    "如何",
    "the",
    "and",
    "for",
    "with",
}

QUERY_ALIASES = {
    "交通费": ("交通費", "移動費", "电车费", "電車代"),
    "交通費": ("交通费", "移動費", "电车费", "電車代"),
    "移动费": ("交通费", "交通費", "移動費", "電車代"),
    "移動費": ("交通费", "交通費", "移动费", "電車代"),
    "电车费": ("交通费", "交通費", "移動費", "電車代"),
    "電車代": ("交通费", "交通費", "移動費", "电车费"),
    "下一次": ("下次", "次回"),
    "下次": ("下一次", "次回"),
    "次回": ("下一次", "下次"),
    "评审": ("評審", "レビュー"),
    "評審": ("评审", "レビュー"),
    "レビュー": ("评审", "評審"),
    "什么时候": ("何时", "いつ", "日時"),
    "何时": ("什么时候", "いつ", "日時"),
    "电话": ("電話", "phone"),
    "電話": ("电话", "phone"),
}


@dataclass(frozen=True)
class Evidence:
    source_id: str
    source: str
    path: str
    title: str
    kind: str
    snippet: str
    score: float


def query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9_]+|[\u3040-\u30ff\u3400-\u9fff]+", query.lower()):
        if token in STOP_TERMS:
            continue
        if token not in terms:
            terms.append(token)
        if re.search(r"[\u3040-\u30ff\u3400-\u9fff]", token):
            for size in (2, 3):
                for index in range(0, max(len(token) - size + 1, 0)):
                    ngram = token[index : index + size]
                    if ngram not in STOP_TERMS and ngram not in terms:
                        terms.append(ngram)
    normalized = query.lower()
    for key, aliases in QUERY_ALIASES.items():
        if key.lower() not in normalized:
            continue
        for alias in aliases:
            lowered = alias.lower()
            if lowered not in terms:
                terms.append(lowered)
    return terms


def term_matches(haystack: str, term: str) -> bool:
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9_]+", term):
        if len(term) < 3:
            return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", haystack) is not None
        return re.search(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", haystack) is not None
    return term in haystack


def _compact(text: str, limit: int = MAX_EVIDENCE_CHARS) -> str:
    compacted = " ".join(text.split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."


def _term_weight(term: str) -> float:
    if re.fullmatch(r"[a-z0-9_]+", term):
        return 2.0
    if len(term) >= 4:
        return 3.0
    if len(term) == 3:
        return 1.25
    return 0.4


def _intent_bonus(query: str, text: str) -> float:
    lowered_query = query.lower()
    lowered_text = text.lower()
    bonus = 0.0
    asks_for_quantity = any(
        marker in lowered_query
        for marker in ("多少", "合计", "总计", "高", "低", "相差", "比較", "いくら", "how much")
    )
    if asks_for_quantity:
        if re.search(r"\d[\d,]*(?:\.\d+)?\s*(?:日元|円|元|usd|rmb)", lowered_text):
            bonus += 6.0
        if any(marker in lowered_text for marker in ("合计", "總計", "总计", "計：", "total")):
            bonus += 3.0
    asks_for_time = any(
        marker in lowered_query
        for marker in ("什么时候", "何时", "日期", "时间", "いつ", "次回", "when")
    )
    if asks_for_time and re.search(r"\b20\d{2}[-年/]\d{1,2}(?:[-月/]\d{1,2})?", lowered_text):
        bonus += 5.0
    return bonus


def retrieve_evidence(
    query: str,
    db_path: str | None = None,
    limit: int = DEFAULT_EVIDENCE_LIMIT,
    embedding_model: str | None = None,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    embedder: Embedder = generate_embeddings_with_ollama,
) -> list[Evidence]:
    init_db(db_path)
    fts_query = normalize_query(query)
    conn = connect(db_path)
    evidence: dict[tuple[str, str, str], Evidence] = {}
    try:
        if fts_query != '""':
            try:
                rows = conn.execute(
                    """
                    SELECT
                        source_roots.name AS source,
                        documents.path AS path,
                        documents.title AS title,
                        'chunk' AS kind,
                        snippet(chunks_fts, 0, '[', ']', '...', 28) AS snippet,
                        bm25(chunks_fts) AS rank
                    FROM chunks_fts
                    JOIN documents ON documents.id = chunks_fts.document_id
                    JOIN source_roots ON source_roots.id = documents.source_id
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                for index, row in enumerate(rows, start=1):
                    key = (row["path"], row["kind"], row["snippet"])
                    evidence[key] = Evidence(
                        source_id=f"S{len(evidence) + 1}",
                        source=row["source"],
                        path=row["path"],
                        title=row["title"],
                        kind=row["kind"],
                        snippet=_compact(row["snippet"]),
                        score=float(limit - index + 1)
                        + 5.0
                        + _intent_bonus(query, f"{row['path']} {row['snippet']}"),
                    )
            except OperationalError:
                pass

            try:
                rows = conn.execute(
                    """
                    SELECT
                        source_roots.name AS source,
                        documents.path AS path,
                        documents.title AS title,
                        traces.trace_type AS trace_type,
                        traces.value AS trace_value,
                        snippet(traces_fts, 1, '[', ']', '...', 18) AS snippet,
                        bm25(traces_fts) AS rank
                    FROM traces_fts
                    JOIN traces ON traces.id = traces_fts.trace_id
                    JOIN documents ON documents.id = traces_fts.document_id
                    JOIN source_roots ON source_roots.id = documents.source_id
                    WHERE traces_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                for index, row in enumerate(rows, start=1):
                    kind = f"trace:{row['trace_type']}"
                    snippet = row["snippet"] or row["trace_value"]
                    key = (row["path"], kind, snippet)
                    evidence[key] = Evidence(
                        source_id=f"S{len(evidence) + 1}",
                        source=row["source"],
                        path=row["path"],
                        title=row["title"],
                        kind=kind,
                        snippet=_compact(snippet),
                        score=float(limit - index + 1)
                        + 4.0
                        + _intent_bonus(query, f"{row['path']} {snippet}"),
                    )
            except OperationalError:
                pass

        terms = query_terms(query)
        if terms:
            rows = conn.execute(
                """
                SELECT
                    source_roots.name AS source,
                    documents.path AS path,
                    documents.title AS title,
                    chunks.content AS content
                FROM chunks
                JOIN documents ON documents.id = chunks.document_id
                JOIN source_roots ON source_roots.id = documents.source_id
                WHERE documents.document_status != 'deleted'
                  AND documents.extraction_status = 'success'
                ORDER BY documents.indexed_at DESC, chunks.id DESC
                LIMIT 300
                """
            ).fetchall()
            for row in rows:
                haystack = f"{row['title']} {row['path']} {row['content']}".lower()
                matched = [term for term in terms if term_matches(haystack, term)]
                if not matched:
                    continue
                strong_score = sum(
                    _term_weight(term)
                    for term in matched
                    if re.fullmatch(r"[a-z0-9_]+", term) or len(term) >= 4
                )
                short_score = sum(
                    _term_weight(term)
                    for term in matched
                    if not re.fullmatch(r"[a-z0-9_]+", term) and len(term) < 4
                )
                score = strong_score + min(short_score, 3.0)
                if query.lower() in haystack:
                    score += 8.0
                score += _intent_bonus(query, haystack)
                if score < 2.5:
                    continue
                key = (row["path"], "chunk", row["content"])
                existing = evidence.get(key)
                if existing and existing.score >= score:
                    continue
                evidence[key] = Evidence(
                    source_id=f"S{len(evidence) + 1}",
                    source=row["source"],
                    path=row["path"],
                    title=row["title"],
                    kind="chunk",
                    snippet=_compact(row["content"]),
                    score=score,
                )

        if embedding_model:
            try:
                semantic_matches = semantic_search(
                    query,
                    db_path,
                    model=embedding_model,
                    ollama_host=ollama_host,
                    timeout=timeout,
                    limit=max(limit * 2, 10),
                    embedder=embedder,
                )
            except RuntimeError:
                semantic_matches = []
            for index, match in enumerate(semantic_matches, start=1):
                key = (match.path, "chunk", match.content)
                semantic_score = 10.0 + (match.score * 10.0) - (index * 0.05)
                existing = evidence.get(key)
                if existing:
                    semantic_score += min(existing.score, 8.0)
                evidence[key] = Evidence(
                    source_id=f"S{len(evidence) + 1}",
                    source=match.source,
                    path=match.path,
                    title=match.title,
                    kind="chunk",
                    snippet=_compact(match.content),
                    score=semantic_score,
                )

            document_scores: dict[tuple[str, str], float] = {}
            for match in semantic_matches:
                key = (match.source, match.path)
                document_scores[key] = max(document_scores.get(key, -1.0), match.score)
            for (source_name, path), document_score in sorted(
                document_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]:
                sibling_rows = conn.execute(
                    """
                    SELECT
                        source_roots.name AS source,
                        documents.path,
                        documents.title,
                        chunks.content
                    FROM chunks
                    JOIN documents ON documents.id = chunks.document_id
                    JOIN source_roots ON source_roots.id = documents.source_id
                    WHERE source_roots.name = ?
                      AND documents.path = ?
                      AND documents.document_status != 'deleted'
                    ORDER BY chunks.chunk_index
                    """,
                    (source_name, path),
                ).fetchall()
                for row in sibling_rows:
                    intent_score = _intent_bonus(query, row["content"])
                    if intent_score <= 0.0:
                        continue
                    sibling_score = 9.0 + (document_score * 5.0) + intent_score
                    key = (row["path"], "chunk", row["content"])
                    existing = evidence.get(key)
                    if existing and existing.score >= sibling_score:
                        continue
                    evidence[key] = Evidence(
                        source_id=f"S{len(evidence) + 1}",
                        source=row["source"],
                        path=row["path"],
                        title=row["title"],
                        kind="chunk",
                        snippet=_compact(row["content"]),
                        score=sibling_score,
                    )

        ranked_candidates = sorted(evidence.values(), key=lambda item: item.score, reverse=True)
        ranked: list[Evidence] = []
        path_counts: dict[str, int] = {}
        seen_snippets: set[tuple[str, str]] = set()
        for item in ranked_candidates:
            normalized_snippet = re.sub(r"\W+", "", item.snippet.lower())[:240]
            snippet_key = (item.path, normalized_snippet)
            if snippet_key in seen_snippets:
                continue
            if path_counts.get(item.path, 0) >= MAX_EVIDENCE_PER_PATH:
                continue
            ranked.append(item)
            seen_snippets.add(snippet_key)
            path_counts[item.path] = path_counts.get(item.path, 0) + 1
            if len(ranked) >= limit:
                break
        return [
            Evidence(
                source_id=f"S{index}",
                source=item.source,
                path=item.path,
                title=item.title,
                kind=item.kind,
                snippet=item.snippet,
                score=item.score,
            )
            for index, item in enumerate(ranked, start=1)
        ]
    finally:
        conn.close()


def build_answer_prompt(query: str, evidence: list[Evidence]) -> str:
    evidence_text = "\n\n".join(
        "\n".join(
            [
                f"[{item.source_id}] source={item.source} path={item.path} kind={item.kind}",
                item.snippet,
            ]
        )
        for item in evidence
    )
    return "\n".join(
        [
            "You are ThoughtVault, a local-first personal knowledge and memory assistant.",
            "Answer using only facts explicitly present in the provided evidence.",
            "Treat dates, months, names, places, and amounts as strict constraints.",
            "Never copy a value from a different date or month to fill a missing answer.",
            "For comparisons, read every relevant value, calculate the difference, and state the calculation.",
            "Do not infer a cause merely because one evidence item says something did not occur.",
            "If the requested fact is not explicit, say it cannot be confirmed from the local sources.",
            "Do not suggest web searches, public profiles, or outside sources.",
            "Use the same language as the user's question.",
            "Cite sources inline using [S1], [S2], etc. Do not cite sources that do not support the sentence.",
            "",
            f"Question: {query}",
            "",
            "Evidence:",
            evidence_text or "No relevant evidence was retrieved.",
            "",
            "Return only a concise answer with inline citations. Do not add a Sources or Evidence section.",
        ]
    )


def _month_totals(evidence: list[Evidence]) -> dict[int, tuple[int, str]]:
    candidates: dict[int, dict[int, str]] = {}
    by_path: dict[str, list[Evidence]] = {}
    for item in evidence:
        by_path.setdefault(item.path, []).append(item)

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for items in by_path.values():
        context = " ".join(
            f"{item.title} {item.path} {item.snippet}"
            for item in items
        )
        month_match = re.search(
            r"20\d{2}\s*[-年_/]\s*(1[0-2]|0?[1-9])\s*月?",
            context,
        )
        month = int(month_match.group(1)) if month_match else None
        if month is None:
            lowered = context.lower()
            month = next(
                (value for name, value in month_names.items() if re.search(rf"\b{name}\b", lowered)),
                None,
            )
        if month is None:
            continue
        for item in items:
            total_match = re.search(
                r"(?:交通费|交通費|移動費|移动费|電車代|电车费)"
                r"(?:合计|合計|总计|總計|total)?\s*[:：]?\s*"
                r"([\d,]+)(?:\.\d+)?\s*(?:日元|円|元|rmb|jpy)",
                item.snippet,
                re.IGNORECASE,
            )
            if not total_match:
                continue
            amount = int(total_match.group(1).replace(",", ""))
            candidates.setdefault(month, {})[amount] = item.source_id
    return {
        month: (next(iter(values)), next(iter(values.values())))
        for month, values in candidates.items()
        if len(values) == 1
    }


def verified_numeric_answer(query: str, evidence: list[Evidence]) -> str | None:
    if not any(
        marker in query.lower()
        for marker in ("交通费", "交通費", "移動費", "移动费", "電車代", "电车费")
    ):
        return None
    if not any(
        marker in query.lower()
        for marker in ("多少", "合计", "总计", "高", "低", "相差", "比較", "いくら", "how much")
    ):
        return None

    requested_months = {
        int(value)
        for value in re.findall(r"(?<!\d)(1[0-2]|0?[1-9])\s*月", query)
    }
    if not requested_months:
        return None

    totals = _month_totals(evidence)
    missing = sorted(requested_months - totals.keys())
    if missing:
        labels = "、".join(f"{month} 月" for month in missing)
        return f"现有本地资料中没有找到 {labels}的明确交通费合计，因此无法可靠确认。"

    ordered = sorted(requested_months)
    if len(ordered) == 1:
        month = ordered[0]
        amount, source_id = totals[month]
        return f"{month} 月交通费合计为 {amount:,} 日元 [{source_id}]。"

    if len(ordered) == 2:
        first_month, second_month = ordered
        first_amount, first_source = totals[first_month]
        second_amount, second_source = totals[second_month]
        difference = abs(first_amount - second_amount)
        if first_amount == second_amount:
            return (
                f"{first_month} 月和 {second_month} 月交通费相同，"
                f"均为 {first_amount:,} 日元 [{first_source}][{second_source}]。"
            )
        higher_month = first_month if first_amount > second_amount else second_month
        return (
            f"{first_month} 月为 {first_amount:,} 日元 [{first_source}]，"
            f"{second_month} 月为 {second_amount:,} 日元 [{second_source}]。"
            f"因此 {higher_month} 月更高，相差 {difference:,} 日元。"
        )
    return None


def verified_direct_answer(query: str, evidence: list[Evidence]) -> str | None:
    lowered_query = query.lower()
    asks_for_contact = any(marker in lowered_query for marker in ("电话", "電話", "手机号", "phone"))
    if asks_for_contact:
        phone_pattern = re.compile(
            r"(?<!\d)(?:"
            r"\+\d{10,15}"
            r"|0\d{1,4}-\d{1,4}-\d{3,4}"
            r"|1[3-9]\d{9}"
            r")(?!\d)"
        )
        supporting = [
            item
            for item in evidence
            if phone_pattern.search(item.snippet)
        ]
        if not supporting:
            return "现有本地资料中没有找到该电话号码，因此无法确认。"

    asks_for_next_time = (
        any(marker in lowered_query for marker in ("下一次", "下次", "次回"))
        and any(marker in lowered_query for marker in ("什么时候", "何时", "时间", "日期", "いつ", "when"))
    )
    if asks_for_next_time:
        for item in evidence:
            if not any(marker in item.snippet for marker in ("下一次", "下次", "次回")):
                continue
            date_match = re.search(
                r"(20\d{2})\s*[-年/]\s*(\d{1,2})\s*[-月/]\s*(\d{1,2})\s*日?",
                item.snippet,
            )
            time_match = re.search(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)", item.snippet)
            if not date_match:
                continue
            year, month, day = (int(value) for value in date_match.groups())
            date_text = f"{year} 年 {month} 月 {day} 日"
            time_text = ""
            if time_match:
                time_text = f" {int(time_match.group(1)):02d}:{time_match.group(2)}"
            return f"下一次安排是 {date_text}{time_text} [{item.source_id}]。"
    return None


def answer_question(
    query: str,
    db_path: str | None = None,
    model: str = DEFAULT_OLLAMA_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    limit: int = DEFAULT_EVIDENCE_LIMIT,
    use_ai: bool = True,
    generator: AnswerGenerator = generate_with_ollama,
    embedding_model: str | None = None,
    embedder: Embedder = generate_embeddings_with_ollama,
) -> dict[str, object]:
    evidence = retrieve_evidence(
        query,
        db_path,
        limit,
        embedding_model=embedding_model,
        ollama_host=ollama_host,
        timeout=timeout,
        embedder=embedder,
    )
    if not evidence:
        return {
            "answer": "没有找到足够相关的本地证据。请先确认资料已 scan，或换一个更接近文件内容的关键词。",
            "evidence": [],
        }

    if not use_ai:
        lines = ["找到这些相关证据：", ""]
        for item in evidence:
            lines.append(f"- [{item.source_id}] {item.path}: {item.snippet}")
        return {"answer": "\n".join(lines), "evidence": evidence}

    numeric_answer = verified_numeric_answer(query, evidence)
    if numeric_answer is not None:
        return {
            "answer": numeric_answer,
            "evidence": evidence,
            "answer_mode": "verified_numeric",
        }

    direct_answer = verified_direct_answer(query, evidence)
    if direct_answer is not None:
        return {
            "answer": direct_answer,
            "evidence": evidence,
            "answer_mode": "verified_direct",
        }

    prompt = build_answer_prompt(query, evidence)
    try:
        answer = generator(prompt, model, ollama_host, timeout)
    except RuntimeError as exc:
        lines = [
            f"AI generation failed, so ThoughtVault is showing retrieved evidence instead: {exc}",
            "",
        ]
        for item in evidence:
            lines.append(f"- [{item.source_id}] {item.path}: {item.snippet}")
        return {"answer": "\n".join(lines), "evidence": evidence, "ai_error": str(exc)}
    return {"answer": answer, "evidence": evidence}
