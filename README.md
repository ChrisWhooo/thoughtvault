# ThoughtVault

ThoughtVault is a local-first personal knowledge system for turning local files, AI conversation memos, project documents, and personal records into a structured, searchable, self-growing knowledge base.

The project starts from a simple idea:

> Keep the original files local, let the system parse and index them, then use local AI to summarize, connect, and organize knowledge over time.

## Goals

- Build a local knowledge base from folders such as projects, Obsidian notes, company records, and personal memos.
- Preserve original files as the source of truth.
- Generate structured Markdown notes that remain portable and Obsidian-friendly.
- Provide a local Web UI for search, browsing, relationship discovery, and review.
- Support local AI through Ollama first, with optional cloud AI later.
- Make knowledge growth incremental: new files are detected, indexed, summarized, and linked to existing knowledge.

## Non-Goals

- It is not a cloud document management platform.
- It does not upload private files by default.
- It does not let AI rewrite or replace source files automatically.
- It does not try to understand the entire folder in one large prompt.

## First Use Case

The initial target user is someone who keeps mixed local materials:

- project documents such as requirements, basic design, detailed design, and operation manuals
- Obsidian notes and scattered raw thoughts
- company-related files such as salary slips, application records, and personal administrative documents
- copied AI conversations saved as Markdown or text memos

ThoughtVault should help convert these materials into:

- source-backed summaries
- project overview pages
- concept notes
- timelines
- tags
- search index
- local AI Q&A with citations

## Repository Structure

```text
thoughtvault/
├─ docs/
│  ├─ 01-product-vision.md
│  ├─ 02-roadmap.md
│  ├─ 03-architecture.md
│  ├─ 04-data-model.md
│  ├─ 05-processing-pipeline.md
│  ├─ 06-output-design.md
│  └─ 07-decisions-and-open-questions.md
├─ examples/
│  └─ memo-example.md
└─ src/
```

## Planned Tech Stack

| Layer | Candidate |
|---|---|
| Backend | Python, FastAPI |
| Frontend | React or Next.js |
| Metadata DB | SQLite |
| Full-text search | SQLite FTS5 |
| Vector index | LanceDB or Chroma |
| Local AI | Ollama |
| Markdown output | Obsidian-compatible Markdown |
| Parsers | python-docx, openpyxl, pypdf, markdown parser |

## Current Status

Planning stage. The current repository contains the product direction, architecture notes, data model draft, processing pipeline, and phased roadmap.

## Next Step

The next implementation milestone is Phase 1: local scanner and basic SQLite metadata index.
