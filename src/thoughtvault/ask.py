from __future__ import annotations

import re
import json
from dataclasses import dataclass
from sqlite3 import OperationalError
from typing import Callable

from .db import connect, init_db
from .search import normalize_query
from .synthesis import DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL, generate_with_ollama

AnswerGenerator = Callable[[str, str, str, float], str]

MAX_EVIDENCE_CHARS = 1400
ASK_PROMPT_VERSION = "ask-v2"
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


@dataclass(frozen=True)
class Evidence:
    source_id: str
    source: str
    path: str
    title: str
    kind: str
    snippet: str
    score: float


def evidence_to_dict(item: Evidence) -> dict[str, object]:
    return {
        "source_id": item.source_id,
        "source": item.source,
        "path": item.path,
        "title": item.title,
        "kind": item.kind,
        "snippet": item.snippet,
        "score": item.score,
    }


def evidence_from_dict(item: dict[str, object]) -> Evidence:
    return Evidence(
        source_id=str(item["source_id"]),
        source=str(item["source"]),
        path=str(item["path"]),
        title=str(item["title"]),
        kind=str(item["kind"]),
        snippet=str(item["snippet"]),
        score=float(item["score"]),
    )


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


def retrieve_evidence(query: str, db_path: str | None = None, limit: int = 8) -> list[Evidence]:
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
                        score=float(limit - index + 1) + 5.0,
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
                        score=float(limit - index + 1) + 4.0,
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
                score = float(len(matched))
                if query.lower() in haystack:
                    score += 5.0
                if score < 2.0:
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

        ranked = sorted(evidence.values(), key=lambda item: item.score, reverse=True)[:limit]
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


def build_answer_prompt(query: str, evidence: list[Evidence], strict: bool = False) -> str:
    evidence_text = "\n\n".join(
        "\n".join(
            [
                f"[{item.source_id}] source={item.source} path={item.path} kind={item.kind}",
                item.snippet,
            ]
        )
        for item in evidence
    )
    rules = [
        "You are ThoughtVault, a local-first personal knowledge and memory assistant.",
        "Answer the user's question using only the provided source-backed evidence.",
        "You may organize, summarize, infer cautiously, and extend ideas, but do not invent facts.",
        "If evidence is insufficient, say what is missing and suggest a better follow-up query.",
        "Use the same language as the user's question.",
        "Cite sources inline using [S1], [S2], etc. Do not cite sources that do not support the sentence.",
    ]
    if strict:
        rules.extend(
            [
                "Strict mode is enabled.",
                "Separate facts from cautious interpretation.",
                "Do not answer a subquestion unless at least one evidence item supports it.",
                "Use exactly these sections: Answer, Evidence Used, Missing Evidence, Suggested Next Queries.",
            ]
        )

    return "\n".join(
        rules
        + [
            "",
            f"Question: {query}",
            "",
            "Evidence:",
            evidence_text or "No relevant evidence was retrieved.",
            "",
            "Return a concise answer. If useful, include a short 'Sources' section listing the cited paths.",
        ]
    )


def save_ask_record(
    query: str,
    answer: str,
    evidence: list[Evidence],
    model: str,
    status: str,
    db_path: str | None = None,
) -> int:
    init_db(db_path)
    conn = connect(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO ask_records (query, answer, evidence_json, model, prompt_version, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                answer,
                json.dumps([evidence_to_dict(item) for item in evidence], ensure_ascii=False),
                model,
                ASK_PROMPT_VERSION,
                status,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)
    finally:
        conn.close()


def list_ask_records(db_path: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT id, query, model, status, created_at
            FROM ask_records
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_ask_record(record_id: int, db_path: str | None = None) -> dict[str, object] | None:
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT id, query, answer, evidence_json, model, prompt_version, status, created_at
            FROM ask_records
            WHERE id = ?
            """,
            (record_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["evidence"] = [evidence_from_dict(item) for item in json.loads(result.pop("evidence_json"))]
        return result
    finally:
        conn.close()


def answer_question(
    query: str,
    db_path: str | None = None,
    model: str = DEFAULT_OLLAMA_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    limit: int = 8,
    use_ai: bool = True,
    strict: bool = False,
    save: bool = True,
    generator: AnswerGenerator = generate_with_ollama,
) -> dict[str, object]:
    evidence = retrieve_evidence(query, db_path, limit)
    if not evidence:
        answer = "没有找到足够相关的本地证据。请先确认资料已 scan，或换一个更接近文件内容的关键词。"
        result: dict[str, object] = {
            "answer": "没有找到足够相关的本地证据。请先确认资料已 scan，或换一个更接近文件内容的关键词。",
            "evidence": [],
            "status": "no_evidence",
        }
        if save:
            result["record_id"] = save_ask_record(query, answer, [], "none", "no_evidence", db_path)
        return result

    if not use_ai:
        lines = ["找到这些相关证据：", ""]
        for item in evidence:
            lines.append(f"- [{item.source_id}] {item.path}: {item.snippet}")
        answer = "\n".join(lines)
        result = {"answer": answer, "evidence": evidence, "status": "evidence_only"}
        if save:
            result["record_id"] = save_ask_record(query, answer, evidence, "none", "evidence_only", db_path)
        return result

    prompt = build_answer_prompt(query, evidence, strict)
    try:
        answer = generator(prompt, model, ollama_host, timeout)
    except RuntimeError as exc:
        lines = [
            f"AI generation failed, so ThoughtVault is showing retrieved evidence instead: {exc}",
            "",
        ]
        for item in evidence:
            lines.append(f"- [{item.source_id}] {item.path}: {item.snippet}")
        answer = "\n".join(lines)
        result = {"answer": answer, "evidence": evidence, "ai_error": str(exc), "status": "ai_failed"}
        if save:
            result["record_id"] = save_ask_record(query, answer, evidence, model, "ai_failed", db_path)
        return result

    result = {"answer": answer, "evidence": evidence, "status": "answered"}
    if save:
        result["record_id"] = save_ask_record(query, answer, evidence, model, "answered", db_path)
    return result
