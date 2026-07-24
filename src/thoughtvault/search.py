from __future__ import annotations

import re
from typing import Callable

from .db import connect, init_db


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
VALID_SEARCH_MODES = {"lexical", "semantic", "hybrid"}
DEFAULT_SEARCH_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
DEFAULT_SEARCH_OLLAMA_HOST = "http://localhost:11434"
Embedder = Callable[[list[str], str, str, float], list[list[float]]]


def normalize_query(query: str) -> str:
    tokens = TOKEN_RE.findall(query)
    if not tokens:
        return '""'
    return " OR ".join(tokens)


def _metadata_clause(
    table_alias: str = "documents",
    source_alias: str = "source_roots",
    category: str | None = None,
    source: str | None = None,
    path: str | None = None,
) -> tuple[str, list[object]]:
    clauses = [
        f"{table_alias}.document_status != 'deleted'",
        f"{table_alias}.extraction_status = 'success'",
    ]
    params: list[object] = []
    if category:
        clauses.append(f"(',' || {table_alias}.source_categories || ',') LIKE ?")
        params.append(f"%,{category.strip().lower()},%")
    if source:
        clauses.append(f"{source_alias}.name = ?")
        params.append(source)
    if path:
        clauses.append(f"{table_alias}.path LIKE ?")
        params.append(f"%{path}%")
    return " AND ".join(clauses), params


def _compact(text: str, limit: int = 360) -> str:
    compacted = " ".join(str(text).split())
    if len(compacted) <= limit:
        return compacted
    return compacted[: limit - 3].rstrip() + "..."


def _lexical_search(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
    category: str | None = None,
    source: str | None = None,
    path: str | None = None,
) -> list[dict[str, object]]:
    init_db(db_path)
    fts_query = normalize_query(query)
    if fts_query == '""':
        return []
    where, metadata_params = _metadata_clause(category=category, source=source, path=path)
    conn = connect(db_path)
    try:
        chunk_rows = conn.execute(
            f"""
            SELECT
                'chunk' AS result_type,
                documents.path AS path,
                documents.title AS title,
                snippet(chunks_fts, 0, '[', ']', '...', 12) AS snippet,
                bm25(chunks_fts) AS rank,
                source_roots.name AS source,
                documents.source_categories AS categories
            FROM chunks_fts
            JOIN documents ON documents.id = chunks_fts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE chunks_fts MATCH ?
              AND {where}
            ORDER BY rank
            LIMIT ?
            """,
            [fts_query, *metadata_params, limit],
        ).fetchall()
        trace_rows = conn.execute(
            f"""
            SELECT
                'trace' AS result_type,
                documents.path AS path,
                traces.trace_type || ': ' || traces.value AS title,
                snippet(traces_fts, 1, '[', ']', '...', 12) AS snippet,
                bm25(traces_fts) AS rank,
                source_roots.name AS source,
                documents.source_categories AS categories
            FROM traces_fts
            JOIN traces ON traces.id = traces_fts.trace_id
            JOIN documents ON documents.id = traces_fts.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE traces_fts MATCH ?
              AND {where}
            ORDER BY rank
            LIMIT ?
            """,
            [fts_query, *metadata_params, limit],
        ).fetchall()

        results = []
        for row in [*chunk_rows, *trace_rows]:
            item = dict(row)
            item["snippet"] = _compact(str(item["snippet"]))
            item["match_mode"] = "lexical"
            item["score"] = 1.0 / (1.0 + abs(float(item.pop("rank"))))
            results.append(item)
        return sorted(results, key=lambda item: float(item["score"]), reverse=True)[:limit]
    finally:
        conn.close()


def _semantic_search_results(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
    category: str | None = None,
    source: str | None = None,
    path: str | None = None,
    embedding_model: str = DEFAULT_SEARCH_EMBEDDING_MODEL,
    ollama_host: str = DEFAULT_SEARCH_OLLAMA_HOST,
    timeout: float = 120.0,
    embedder: Embedder | None = None,
) -> list[dict[str, object]]:
    from .embeddings import generate_embeddings_with_ollama, semantic_search

    active_embedder = embedder or generate_embeddings_with_ollama
    try:
        matches = semantic_search(
            query,
            db_path,
            model=embedding_model,
            ollama_host=ollama_host,
            timeout=timeout,
            limit=limit,
            embedder=active_embedder,
            category=category,
            source=source,
            path=path,
        )
    except RuntimeError:
        return []
    return [
        {
            "result_type": "chunk",
            "path": match.path,
            "title": match.title,
            "snippet": _compact(match.content),
            "source": match.source,
            "categories": match.categories,
            "match_mode": "semantic",
            "score": match.score,
        }
        for match in matches
    ]


def _merge_ranked_results(
    lexical_rows: list[dict[str, object]],
    semantic_rows: list[dict[str, object]],
    limit: int,
) -> list[dict[str, object]]:
    merged: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in lexical_rows:
        key = (str(row["result_type"]), str(row["path"]), str(row["snippet"]))
        item = dict(row)
        item["score"] = float(item["score"]) * 10.0
        merged[key] = item
    for row in semantic_rows:
        key = (str(row["result_type"]), str(row["path"]), str(row["snippet"]))
        semantic_score = 10.0 + float(row["score"]) * 10.0
        if key in merged:
            merged[key]["score"] = float(merged[key]["score"]) + semantic_score
            merged[key]["match_mode"] = "hybrid"
        else:
            item = dict(row)
            item["score"] = semantic_score
            merged[key] = item
    return sorted(merged.values(), key=lambda item: float(item["score"]), reverse=True)[:limit]


def search(
    query: str,
    db_path: str | None = None,
    limit: int = 10,
    mode: str = "lexical",
    category: str | None = None,
    source: str | None = None,
    path: str | None = None,
    embedding_model: str = DEFAULT_SEARCH_EMBEDDING_MODEL,
    ollama_host: str = DEFAULT_SEARCH_OLLAMA_HOST,
    timeout: float = 120.0,
    embedder: Embedder | None = None,
) -> list[dict[str, object]]:
    if mode not in VALID_SEARCH_MODES:
        raise ValueError(f"Unsupported search mode: {mode}")

    lexical_rows: list[dict[str, object]] = []
    semantic_rows: list[dict[str, object]] = []
    if mode in {"lexical", "hybrid"}:
        lexical_rows = _lexical_search(query, db_path, limit, category, source, path)
    if mode in {"semantic", "hybrid"}:
        semantic_rows = _semantic_search_results(
            query,
            db_path,
            limit,
            category,
            source,
            path,
            embedding_model,
            ollama_host,
            timeout,
            embedder,
        )

    if mode == "lexical":
        return lexical_rows
    if mode == "semantic":
        return semantic_rows
    return _merge_ranked_results(lexical_rows, semantic_rows, limit)
