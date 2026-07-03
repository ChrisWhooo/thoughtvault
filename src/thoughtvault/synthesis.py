from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Callable

from .db import connect, init_db
from .search import normalize_query

SYNTHESIS_CATEGORIES = {"project", "memo", "conversation"}
DEFAULT_OLLAMA_HOST = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"
AI_PROMPT_VERSION = "ollama-v1"

Generator = Callable[[str, str, str, float], str]


def _split_categories(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def _bullet_list(items: list[str], empty: str = "No extracted evidence yet.") -> str:
    if not items:
        return f"- {empty}"
    return "\n".join(f"- {item}" for item in items)


def generate_with_ollama(prompt: str, model: str, host: str, timeout: float = 120.0) -> str:
    url = host.rstrip("/") + "/api/generate"
    payload = json.dumps(
        {"model": model, "prompt": prompt, "stream": False},
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
        raise RuntimeError(f"Ollama generation failed: {exc}") from exc

    generated = str(data.get("response", "")).strip()
    if not generated:
        raise RuntimeError("Ollama generation returned an empty response.")
    return generated


def _build_rule_body(
    title: str,
    categories: set[str],
    document_paths: list[str],
    technologies: list[str],
    headings: list[str],
    dates: list[str],
    urls: list[str],
) -> tuple[str, str]:
    if "project" in categories:
        note_type = "project_synthesis"
        body = "\n".join(
            [
                f"# {title}",
                "",
                "## Source Documents",
                "",
                _bullet_list(document_paths),
                "",
                "## Technologies Detected",
                "",
                _bullet_list(technologies),
                "",
                "## Important Headings",
                "",
                _bullet_list(headings),
                "",
                "## Dates Detected",
                "",
                _bullet_list(dates),
                "",
                "## Source-Backed Draft Notes",
                "",
                "This note is generated from extracted traces. It is not an AI interpretation yet.",
            ]
        )
        return note_type, body

    note_type = "memo_synthesis"
    body = "\n".join(
        [
            f"# {title}",
            "",
            "## Source Documents",
            "",
            _bullet_list(document_paths),
            "",
            "## Themes And Headings",
            "",
            _bullet_list(headings),
            "",
            "## URLs",
            "",
            _bullet_list(urls),
            "",
            "## Source-Backed Draft Notes",
            "",
            "This note is generated from extracted traces. It is a starting point for later AI-assisted synthesis.",
        ]
    )
    return note_type, body


def _build_ai_prompt(
    title: str,
    categories: set[str],
    document_paths: list[str],
    technologies: list[str],
    headings: list[str],
    dates: list[str],
    urls: list[str],
    chunks: list[object],
) -> str:
    chunk_text = "\n\n".join(
        f"[{index}] {str(chunk['content']).strip()[:900]}"
        for index, chunk in enumerate(chunks, start=1)
        if str(chunk["content"]).strip()
    )
    return "\n".join(
        [
            "You are ThoughtVault, a local-first personal memory and knowledge assistant.",
            "Create a concise Markdown synthesis note from the provided source-backed evidence.",
            "Do not invent facts. If evidence is weak, say what is missing.",
            "Write in the same language as the source material when possible.",
            "",
            f"Title: {title}",
            f"Source categories: {', '.join(sorted(categories))}",
            "",
            "Source documents:",
            _bullet_list(document_paths),
            "",
            "Detected technologies:",
            _bullet_list(technologies),
            "",
            "Detected headings:",
            _bullet_list(headings),
            "",
            "Detected dates:",
            _bullet_list(dates),
            "",
            "Detected URLs:",
            _bullet_list(urls),
            "",
            "Evidence snippets:",
            chunk_text or "- No chunk evidence available.",
            "",
            "Return Markdown with these sections:",
            "# <title>",
            "## What This Is",
            "## Key Details To Recall",
            "## Technologies / Knowledge Points",
            "## Reusable Notes",
            "## Open Questions",
        ]
    )


def build_synthesis_notes(
    db_path: str | None = None,
    source_id: int | None = None,
    use_ai: bool = False,
    model: str = DEFAULT_OLLAMA_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    allow_fallback: bool = True,
    generator: Generator = generate_with_ollama,
) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        source_filter = ""
        params: list[object] = []
        if source_id is not None:
            source_filter = "AND source_roots.id = ?"
            params.append(source_id)

        sources = conn.execute(
            f"""
            SELECT id, name, categories
            FROM source_roots
            WHERE scan_enabled = 1 {source_filter}
            ORDER BY id
            """,
            params,
        ).fetchall()

        notes: list[dict[str, object]] = []
        for source in sources:
            categories = _split_categories(source["categories"])
            if not categories & SYNTHESIS_CATEGORIES:
                continue

            documents = conn.execute(
                """
                SELECT id, path, title
                FROM documents
                WHERE source_id = ?
                  AND document_status != 'deleted'
                  AND extraction_status = 'success'
                ORDER BY path
                """,
                (source["id"],),
            ).fetchall()
            if not documents:
                continue

            document_ids = [int(row["id"]) for row in documents]
            placeholders = ",".join("?" for _ in document_ids)
            traces = conn.execute(
                f"""
                SELECT trace_type, value
                FROM traces
                WHERE document_id IN ({placeholders})
                ORDER BY trace_type, value
                """,
                document_ids,
            ).fetchall()
            chunks = conn.execute(
                f"""
                SELECT id, content, location_hint
                FROM chunks
                WHERE document_id IN ({placeholders})
                ORDER BY document_id, chunk_index
                LIMIT 8
                """,
                document_ids,
            ).fetchall()

            trace_map: dict[str, set[str]] = defaultdict(set)
            for trace in traces:
                trace_map[trace["trace_type"]].add(trace["value"])

            technologies = sorted(trace_map.get("technology", set()))
            headings = sorted(trace_map.get("heading", set()))[:20]
            dates = sorted(trace_map.get("date", set()))
            urls = sorted(trace_map.get("url", set()))[:10]
            document_paths = [row["path"] for row in documents]
            chunk_ids = [int(row["id"]) for row in chunks]

            title = (
                f"{source['name']} Project Synthesis"
                if "project" in categories
                else f"{source['name']} Memo Synthesis"
            )
            note_type, body = _build_rule_body(
                title,
                categories,
                document_paths,
                technologies,
                headings,
                dates,
                urls,
            )
            prompt_version = "rule-v1"
            stored_model = "none"
            status = "suggested"

            if use_ai:
                prompt = _build_ai_prompt(
                    title,
                    categories,
                    document_paths,
                    technologies,
                    headings,
                    dates,
                    urls,
                    chunks,
                )
                try:
                    body = generator(prompt, model, ollama_host, timeout)
                    prompt_version = AI_PROMPT_VERSION
                    stored_model = model
                    status = "ai_suggested"
                except RuntimeError as exc:
                    if not allow_fallback:
                        raise
                    body = "\n".join(
                        [
                            body,
                            "",
                            "## AI Generation Status",
                            "",
                            f"- AI generation failed, so this note used the rule-based fallback: {exc}",
                        ]
                    )
                    status = "ai_failed"

            cursor = conn.execute(
                """
                INSERT INTO synthesis_notes (
                    source_id, title, note_type, body, source_document_ids, source_chunk_ids,
                    prompt_version, model, status, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_id, note_type, title) DO UPDATE SET
                    body = excluded.body,
                    source_document_ids = excluded.source_document_ids,
                    source_chunk_ids = excluded.source_chunk_ids,
                    prompt_version = excluded.prompt_version,
                    model = excluded.model,
                    status = excluded.status,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id, title, note_type, status
                """,
                (
                    source["id"],
                    title,
                    note_type,
                    body,
                    json.dumps(document_ids),
                    json.dumps(chunk_ids),
                    prompt_version,
                    stored_model,
                    status,
                ),
            )
            notes.append(dict(cursor.fetchone()))

        conn.commit()
        return notes
    finally:
        conn.close()


def list_synthesis_notes(db_path: str | None = None) -> list[dict[str, object]]:
    init_db(db_path)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                synthesis_notes.id,
                synthesis_notes.title,
                synthesis_notes.note_type,
                synthesis_notes.status,
                source_roots.name AS source,
                synthesis_notes.updated_at
            FROM synthesis_notes
            JOIN source_roots ON source_roots.id = synthesis_notes.source_id
            ORDER BY synthesis_notes.updated_at DESC, synthesis_notes.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_synthesis_notes(query: str, db_path: str | None = None, limit: int = 10) -> list[dict[str, object]]:
    init_db(db_path)
    tokens = normalize_query(query).replace(" OR ", " ").replace('"', "").lower().split()
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT
                synthesis_notes.id,
                synthesis_notes.title,
                synthesis_notes.note_type,
                synthesis_notes.status,
                source_roots.name AS source,
                synthesis_notes.body
            FROM synthesis_notes
            JOIN source_roots ON source_roots.id = synthesis_notes.source_id
            ORDER BY synthesis_notes.updated_at DESC, synthesis_notes.id DESC
            """
        ).fetchall()
        results = []
        for row in rows:
            haystack = f"{row['title']}\n{row['note_type']}\n{row['body']}".lower()
            if all(token in haystack for token in tokens):
                snippet = " ".join(str(row["body"]).split())[:240]
                result = dict(row)
                result.pop("body", None)
                result["snippet"] = snippet
                results.append(result)
            if len(results) >= limit:
                break
        return results
    finally:
        conn.close()
