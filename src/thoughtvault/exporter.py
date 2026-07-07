from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .db import connect, init_db


@dataclass(frozen=True)
class ExportSummary:
    output_dir: Path
    written: int = 0
    skipped: int = 0


SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slugify(value: str, fallback: str = "untitled") -> str:
    slug = SLUG_RE.sub("-", value).strip("-._")
    return slug or fallback


def write_text(path: Path, content: str, overwrite: bool) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return False
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def frontmatter(items: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in items.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            escaped = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{escaped}"')
    lines.append("---")
    return "\n".join(lines)


def export_markdown(
    output_dir: str | Path,
    db_path: str | None = None,
    overwrite: bool = False,
) -> ExportSummary:
    init_db(db_path)
    output = Path(output_dir).expanduser().resolve()
    written = 0
    skipped = 0

    conn = connect(db_path)
    try:
        sources = conn.execute(
            """
            SELECT id, name, root_path, categories, last_scanned_at
            FROM source_roots
            ORDER BY id
            """
        ).fetchall()
        documents = conn.execute(
            """
            SELECT
                documents.id,
                source_roots.name AS source,
                documents.path,
                documents.title,
                documents.file_type,
                documents.source_categories,
                documents.size_bytes,
                documents.content_hash,
                documents.modified_at,
                documents.document_status,
                documents.extraction_status
            FROM documents
            JOIN source_roots ON source_roots.id = documents.source_id
            WHERE documents.document_status != 'deleted'
            ORDER BY source_roots.name, documents.path
            """
        ).fetchall()
        reference_cards = conn.execute(
            """
            SELECT
                reference_cards.id,
                reference_cards.title,
                reference_cards.category,
                reference_cards.summary,
                reference_cards.fields_json,
                reference_cards.sensitivity,
                reference_cards.status,
                documents.path AS source_path
            FROM reference_cards
            JOIN documents ON documents.id = reference_cards.document_id
            ORDER BY reference_cards.category, reference_cards.title
            """
        ).fetchall()
        synthesis_notes = conn.execute(
            """
            SELECT
                synthesis_notes.id,
                synthesis_notes.title,
                synthesis_notes.note_type,
                synthesis_notes.body,
                synthesis_notes.source_document_ids,
                synthesis_notes.source_chunk_ids,
                synthesis_notes.status,
                synthesis_notes.model,
                synthesis_notes.prompt_version,
                source_roots.name AS source
            FROM synthesis_notes
            JOIN source_roots ON source_roots.id = synthesis_notes.source_id
            ORDER BY synthesis_notes.note_type, synthesis_notes.title
            """
        ).fetchall()
        ask_records = conn.execute(
            """
            SELECT id, query, answer, evidence_json, model, prompt_version, status, created_at
            FROM ask_records
            ORDER BY id DESC
            """
        ).fetchall()

        index_lines = [
            frontmatter({"type": "index", "generated_by": "thoughtvault"}),
            "",
            "# ThoughtVault Index",
            "",
            "## Sources",
            "",
        ]
        for source in sources:
            index_lines.append(
                f"- {source['name']} (`{source['categories']}`): `{source['root_path']}`"
            )
        index_lines.extend(["", "## Documents", ""])
        for document in documents:
            note_name = f"{document['id']}-{slugify(document['title'])}.md"
            index_lines.append(f"- [[Sources/{note_name[:-3]}|{document['path']}]]")
        index_lines.extend(["", "## Reference Cards", ""])
        for card in reference_cards:
            note_name = f"{card['id']}-{slugify(card['title'])}.md"
            index_lines.append(f"- [[References/{note_name[:-3]}|{card['title']}]]")
        index_lines.extend(["", "## Synthesis Notes", ""])
        for note in synthesis_notes:
            note_name = f"{note['id']}-{slugify(note['title'])}.md"
            index_lines.append(f"- [[Knowledge/{note_name[:-3]}|{note['title']}]]")
        index_lines.extend(["", "## Ask Records", ""])
        for record in ask_records:
            note_name = f"{record['id']}-{slugify(record['query'])}.md"
            index_lines.append(f"- [[Ask/{note_name[:-3]}|{record['query']}]]")

        if write_text(output / "_Index.md", "\n".join(index_lines) + "\n", overwrite):
            written += 1
        else:
            skipped += 1

        for document in documents:
            traces = conn.execute(
                """
                SELECT trace_type, value, raw_text, confidence
                FROM traces
                WHERE document_id = ?
                ORDER BY trace_type, value
                LIMIT 100
                """,
                (document["id"],),
            ).fetchall()
            chunks = conn.execute(
                """
                SELECT chunk_index, location_hint, content
                FROM chunks
                WHERE document_id = ?
                ORDER BY chunk_index
                LIMIT 5
                """,
                (document["id"],),
            ).fetchall()

            lines = [
                frontmatter(
                    {
                        "type": "source",
                        "generated_by": "thoughtvault",
                        "source_path": document["path"],
                        "source": document["source"],
                        "categories": document["source_categories"].split(","),
                        "source_hash": document["content_hash"],
                        "status": document["document_status"],
                    }
                ),
                "",
                f"# {document['title']}",
                "",
                "## Metadata",
                "",
                f"- Source: `{document['source']}`",
                f"- Path: `{document['path']}`",
                f"- File type: `{document['file_type']}`",
                f"- Size: `{document['size_bytes']}` bytes",
                f"- Modified: `{document['modified_at']}`",
                f"- Extraction: `{document['extraction_status']}`",
                "",
                "## Traces",
                "",
            ]
            if traces:
                for trace in traces:
                    lines.append(f"- **{trace['trace_type']}**: {trace['value']}")
            else:
                lines.append("- No traces extracted.")
            lines.extend(["", "## Chunk Preview", ""])
            if chunks:
                for chunk in chunks:
                    hint = f" ({chunk['location_hint']})" if chunk["location_hint"] else ""
                    preview = str(chunk["content"]).strip()
                    if len(preview) > 700:
                        preview = preview[:700].rstrip() + "..."
                    lines.extend([f"### Chunk {chunk['chunk_index']}{hint}", "", preview, ""])
            else:
                lines.append("No chunks extracted.")

            path = output / "Sources" / f"{document['id']}-{slugify(document['title'])}.md"
            if write_text(path, "\n".join(lines).rstrip() + "\n", overwrite):
                written += 1
            else:
                skipped += 1

        for card in reference_cards:
            fields = json.loads(card["fields_json"])
            lines = [
                frontmatter(
                    {
                        "type": "reference_card",
                        "generated_by": "thoughtvault",
                        "category": card["category"],
                        "sensitivity": card["sensitivity"],
                        "status": card["status"],
                        "source_path": card["source_path"],
                    }
                ),
                "",
                f"# {card['title']}",
                "",
                "## Summary",
                "",
                card["summary"],
                "",
                "## Source",
                "",
                f"- `{card['source_path']}`",
                "",
                "## Source-Backed Traces",
                "",
            ]
            for trace in fields.get("traces", []):
                lines.append(f"- **{trace['trace_type']}**: {trace['value']}")
            path = output / "References" / f"{card['id']}-{slugify(card['title'])}.md"
            if write_text(path, "\n".join(lines).rstrip() + "\n", overwrite):
                written += 1
            else:
                skipped += 1

        for note in synthesis_notes:
            lines = [
                frontmatter(
                    {
                        "type": "synthesis_note",
                        "generated_by": "thoughtvault",
                        "note_type": note["note_type"],
                        "source": note["source"],
                        "status": note["status"],
                        "model": note["model"],
                        "prompt_version": note["prompt_version"],
                    }
                ),
                "",
                note["body"],
                "",
                "## Provenance",
                "",
                f"- Source document ids: `{note['source_document_ids']}`",
                f"- Source chunk ids: `{note['source_chunk_ids']}`",
            ]
            path = output / "Knowledge" / f"{note['id']}-{slugify(note['title'])}.md"
            if write_text(path, "\n".join(lines).rstrip() + "\n", overwrite):
                written += 1
            else:
                skipped += 1

        for record in ask_records:
            evidence = json.loads(record["evidence_json"])
            lines = [
                frontmatter(
                    {
                        "type": "ask_record",
                        "generated_by": "thoughtvault",
                        "status": record["status"],
                        "model": record["model"],
                        "prompt_version": record["prompt_version"],
                        "created_at": record["created_at"],
                    }
                ),
                "",
                f"# Ask {record['id']}: {record['query']}",
                "",
                "## Question",
                "",
                record["query"],
                "",
                "## Answer",
                "",
                record["answer"],
                "",
                "## Evidence",
                "",
            ]
            if evidence:
                for item in evidence:
                    lines.append(
                        f"- **[{item['source_id']}] {item['path']}** ({item['kind']}): {item['snippet']}"
                    )
            else:
                lines.append("- No evidence retrieved.")
            path = output / "Ask" / f"{record['id']}-{slugify(record['query'])}.md"
            if write_text(path, "\n".join(lines).rstrip() + "\n", overwrite):
                written += 1
            else:
                skipped += 1
    finally:
        conn.close()

    return ExportSummary(output, written, skipped)
