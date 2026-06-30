# ThoughtVault

ThoughtVault is a local-first personal memory and knowledge system.

It helps users recall past projects, retrieve personal or work reference information, and turn scattered project materials or memos into structured knowledge notes, while keeping every generated result traceable to source files.

The project starts from a simple idea:

> Keep original files local, build a searchable memory index from them, and use AI to help recall, retrieve, synthesize, and extend what the user has touched before.

## Goals

- Build a local memory index from folders such as projects, reference documents, company records, personal files, Obsidian notes, and AI conversation memos.
- Preserve original files as the source of truth.
- Support project recall: recover project details, technologies used, decisions made, and lessons learned.
- Support reference retrieval: find and reuse information from past submissions, forms, company materials, and personal records.
- Support synthesis: organize project knowledge and scattered philosophical memos into structured notes, technical references, and thought extensions.
- Generate structured Markdown notes that remain portable and Obsidian-friendly.
- Provide a local Web UI for search, recall, browsing, synthesis, relationship discovery, and review.
- Support local AI through Ollama first, with optional cloud AI later.
- Make the memory base incremental: new files are detected, indexed, summarized, and linked to existing material.

## Non-Goals

- It is not a cloud document management platform.
- It does not upload private files by default.
- It does not let AI rewrite or replace source files automatically.
- It does not try to understand the entire folder in one large prompt.
- It does not treat every file the same way: project archives, reference materials, and personal memos require different processing.

## First Use Case

The initial target user is someone who keeps mixed local materials and wants three outcomes:

- recall past projects and recover forgotten details
- retrieve and reuse information from past reference files
- synthesize scattered notes, project materials, and philosophical memos into durable knowledge

Expected source folders include:

- project documents such as requirements, basic design, detailed design, operation manuals, source notes, and handover files
- reference materials such as attendance records, application records, company information, personal administrative documents, and reusable form data
- Obsidian notes and scattered philosophical memos
- copied AI conversations saved as Markdown or text memos

ThoughtVault should help produce:

- source-backed recall answers
- project detail pages
- project timelines
- technology and knowledge notes extracted from projects
- reusable reference cards
- classified and extended memo notes
- local AI Q&A with citations

## Product Modes

### Recall Mode

Recall Mode helps the user recover things they have touched before but no longer remember clearly.

Example questions:

- What projects did I work on that involved FastAPI?
- What technologies did this project use?
- What problem did I solve in that migration project?
- Where did I write about a specific philosophical idea?

The answer should include direct evidence, source files, dates or time hints when available, and AI-assisted summaries.

### Reference Mode

Reference Mode helps the user retrieve and reuse factual information from past files.

Example questions:

- Where is the attendance form I submitted?
- What company information did I use in a past application?
- Which file contains this personal or administrative detail?

This mode should prioritize precision, source links, and low hallucination over creative synthesis.

### Synthesis Mode

Synthesis Mode helps the user turn past exposure into structured knowledge.

For project folders, this means extracting technologies, decisions, problems, solutions, lessons, and technical notes similar to learning references or technical blog posts.

For Obsidian or memo folders, this means clustering themes, organizing philosophical ideas, finding recurring questions, and extending incomplete thoughts.

## Repository Structure

```text
thoughtvault/
|-- docs/
|   |-- 01-product-vision.md
|   |-- 02-roadmap.md
|   |-- 03-architecture.md
|   |-- 04-data-model.md
|   |-- 05-processing-pipeline.md
|   |-- 06-output-design.md
|   |-- 07-decisions-and-open-questions.md
|   `-- 08-product-modes.md
|-- examples/
|   `-- memo-example.md
`-- src/
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

Phase 2 has started. The repository now contains the product direction, architecture notes, data model draft, processing pipeline, phased roadmap, a minimal local scanner CLI, text chunking, trace extraction, and SQLite FTS search.

## Next Step

The next implementation milestone is expanding Phase 2 beyond Markdown and text files, then improving trace extraction quality.

## Phase 1 CLI

Run from the repository root.

Without installing the package:

```powershell
$env:PYTHONPATH = "src"
python -m thoughtvault init
python -m thoughtvault source add .\docs --category project --name docs
python -m thoughtvault source list
python -m thoughtvault scan
python -m thoughtvault documents
python -m thoughtvault search "SQLite FTS5"
```

Or install the local package in editable mode:

```powershell
python -m pip install -e .
thoughtvault init
thoughtvault source add .\docs --category project --name docs
thoughtvault scan
thoughtvault documents
thoughtvault search "SQLite FTS5"
```

The default database path is:

```text
.thoughtvault/thoughtvault.sqlite
```

Phase 1 supports `.md` and `.txt` files. It records source roots, categories, root-relative file paths, file type, size, content hash, modified time, and document status (`new`, `changed`, `unchanged`, `deleted`, or error states).

Phase 2 adds:

- text extraction for `.md` and `.txt`
- chunk creation
- basic trace extraction for titles, paths, headings, dates, URLs, form-like fields, and common technology names
- SQLite FTS5 indexes for chunks and traces
- `thoughtvault search <query>`
