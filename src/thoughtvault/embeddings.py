from __future__ import annotations

import json
import math
import struct
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable

from .db import connect, init_db
from .synthesis import DEFAULT_OLLAMA_HOST

DEFAULT_EMBEDDING_MODEL = "qwen3-embedding:0.6b"
Embedder = Callable[[list[str], str, str, float], list[list[float]]]


@dataclass(frozen=True)
class EmbeddingBuildSummary:
    model: str
    total_chunks: int
    embedded: int
    unchanged: int
    errors: int


@dataclass(frozen=True)
class SemanticMatch:
    chunk_id: int
    source: str
    path: str
    title: str
    content: str
    score: float


def generate_embeddings_with_ollama(
    texts: list[str],
    model: str,
    host: str,
    timeout: float = 120.0,
) -> list[list[float]]:
    if not texts:
        return []
    url = host.rstrip("/") + "/api/embed"
    payload = json.dumps(
        {"model": model, "input": texts},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama embedding failed: {exc}") from exc

    vectors = data.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("Ollama embedding returned an unexpected response.")
    parsed = [[float(value) for value in vector] for vector in vectors]
    if any(not vector for vector in parsed):
        raise RuntimeError("Ollama embedding returned an empty vector.")
    return parsed


def _batches(items: list[object], size: int) -> Iterable[list[object]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{len(vector)}f", *vector)


def _unpack_vector(payload: bytes, dimensions: int) -> tuple[float, ...]:
    return struct.unpack(f"<{dimensions}f", payload)


def _cosine_similarity(left: list[float], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return -1.0
    return dot / (left_norm * right_norm)


def build_embeddings(
    db_path: str | None = None,
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    batch_size: int = 16,
    embedder: Embedder = generate_embeddings_with_ollama,
) -> EmbeddingBuildSummary:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                chunks.id,
                chunks.content,
                chunks.content_hash,
                documents.title,
                documents.path,
                chunk_embeddings.content_hash AS embedded_hash
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            LEFT JOIN chunk_embeddings
              ON chunk_embeddings.chunk_id = chunks.id
             AND chunk_embeddings.model = ?
            WHERE documents.document_status != 'deleted'
              AND documents.extraction_status = 'success'
            ORDER BY chunks.id
            """,
            (model,),
        ).fetchall()
        pending = [row for row in rows if row["embedded_hash"] != row["content_hash"]]
        errors = 0
        embedded = 0
        for batch in _batches(pending, batch_size):
            texts = [
                f"Title: {row['title']}\nPath: {row['path']}\n\n{row['content']}"
                for row in batch
            ]
            try:
                vectors = embedder(texts, model, ollama_host, timeout)
                if len(vectors) != len(batch):
                    raise RuntimeError("Embedding count did not match the requested batch.")
                for row, vector in zip(batch, vectors):
                    conn.execute(
                        """
                        INSERT INTO chunk_embeddings (
                            chunk_id, model, dimensions, vector, content_hash, updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(chunk_id, model) DO UPDATE SET
                            dimensions = excluded.dimensions,
                            vector = excluded.vector,
                            content_hash = excluded.content_hash,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            row["id"],
                            model,
                            len(vector),
                            _pack_vector(vector),
                            row["content_hash"],
                        ),
                    )
                    embedded += 1
                conn.commit()
            except RuntimeError:
                errors += len(batch)
        return EmbeddingBuildSummary(
            model=model,
            total_chunks=len(rows),
            embedded=embedded,
            unchanged=len(rows) - len(pending),
            errors=errors,
        )
    finally:
        conn.close()


def embedding_status(
    db_path: str | None = None,
    model: str = DEFAULT_EMBEDDING_MODEL,
) -> dict[str, object]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT
                (SELECT COUNT(*)
                 FROM chunks
                 JOIN documents ON documents.id = chunks.document_id
                 WHERE documents.document_status != 'deleted'
                   AND documents.extraction_status = 'success') AS total_chunks,
                COUNT(chunk_embeddings.id) AS embedded_chunks,
                MIN(chunk_embeddings.dimensions) AS min_dimensions,
                MAX(chunk_embeddings.dimensions) AS max_dimensions,
                MAX(chunk_embeddings.updated_at) AS last_updated_at
            FROM chunk_embeddings
            WHERE chunk_embeddings.model = ?
            """,
            (model,),
        ).fetchone()
        return {
            "model": model,
            "total_chunks": int(row["total_chunks"] or 0),
            "embedded_chunks": int(row["embedded_chunks"] or 0),
            "dimensions": (
                int(row["min_dimensions"])
                if row["min_dimensions"] == row["max_dimensions"] and row["min_dimensions"] is not None
                else None
            ),
            "last_updated_at": row["last_updated_at"],
        }
    finally:
        conn.close()


def semantic_search(
    query: str,
    db_path: str | None = None,
    model: str = DEFAULT_EMBEDDING_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    limit: int = 10,
    min_score: float = 0.25,
    embedder: Embedder = generate_embeddings_with_ollama,
) -> list[SemanticMatch]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                chunks.id AS chunk_id,
                chunks.content,
                source_roots.name AS source,
                documents.path,
                documents.title,
                chunk_embeddings.dimensions,
                chunk_embeddings.vector
            FROM chunk_embeddings
            JOIN chunks ON chunks.id = chunk_embeddings.chunk_id
            JOIN documents ON documents.id = chunks.document_id
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE chunk_embeddings.model = ?
              AND chunk_embeddings.content_hash = chunks.content_hash
              AND documents.document_status != 'deleted'
              AND documents.extraction_status = 'success'
            """,
            (model,),
        ).fetchall()
        if not rows:
            return []
        query_vectors = embedder([query], model, ollama_host, timeout)
        if not query_vectors:
            return []
        query_vector = query_vectors[0]
        matches = []
        for row in rows:
            vector = _unpack_vector(row["vector"], int(row["dimensions"]))
            score = _cosine_similarity(query_vector, vector)
            if score < min_score:
                continue
            matches.append(
                SemanticMatch(
                    chunk_id=int(row["chunk_id"]),
                    source=row["source"],
                    path=row["path"],
                    title=row["title"],
                    content=row["content"],
                    score=score,
                )
            )
        return sorted(matches, key=lambda item: item.score, reverse=True)[:limit]
    finally:
        conn.close()
