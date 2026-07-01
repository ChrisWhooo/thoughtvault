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

Phase 4 has started. The repository now contains the product direction, architecture notes, data model draft, processing pipeline, phased roadmap, a minimal local scanner CLI, text chunking, trace extraction, SQLite FTS search, a first source-backed Recall Mode command, and generated Reference Cards.

## Next Step

The next implementation milestone is improving Reference Mode and Recall Mode quality, then expanding beyond Markdown and text files.

## Usage

Run commands from the repository root.

### Option A: Run Without Installing

```powershell
$env:PYTHONPATH = "src"
python -m thoughtvault init
```

When using this mode, keep `$env:PYTHONPATH = "src"` in the current PowerShell session before running ThoughtVault commands.

### Option B: Install Locally

```powershell
python -m pip install -e .
thoughtvault init
```

After editable install, use `thoughtvault` directly instead of `python -m thoughtvault`.

## Quickstart

This example indexes the repository's own documentation folder.

Using `python -m`:

```powershell
$env:PYTHONPATH = "src"
python -m thoughtvault init
python -m thoughtvault source add .\docs --category project --name docs
python -m thoughtvault source list
python -m thoughtvault scan
python -m thoughtvault documents
python -m thoughtvault search "SQLite FTS5"
python -m thoughtvault recall "FastAPI"
python -m thoughtvault reference build
python -m thoughtvault reference list
```

Using the installed command:

```powershell
thoughtvault init
thoughtvault source add .\docs --category project --name docs
thoughtvault source list
thoughtvault scan
thoughtvault documents
thoughtvault search "SQLite FTS5"
thoughtvault recall "FastAPI"
thoughtvault reference build
thoughtvault reference list
```

## Command Reference

### Initialize Database

```powershell
python -m thoughtvault init
```

Creates the local SQLite database if it does not already exist.

The default database path is:

```text
.thoughtvault/thoughtvault.sqlite
```

Use a custom database path with `--db`:

```powershell
python -m thoughtvault --db .thoughtvault\dev.sqlite init
```

### Add A Source Folder

```powershell
python -m thoughtvault source add <folder> --category <category> --name <display-name>
```

Example:

```powershell
python -m thoughtvault source add .\docs --category project --name docs
```

This registers a local folder as a source root. It does not scan files immediately. Run `scan` after adding sources.

Supported categories:

```text
project
reference
memo
conversation
personal
company
unknown
```

You can pass multiple categories:

```powershell
python -m thoughtvault source add "D:\Notes" --category memo --category personal --name personal-notes
```

### List Source Folders

```powershell
python -m thoughtvault source list
```

Shows registered source ids, names, paths, categories, enabled state, and last scan time.

### Scan Sources

```powershell
python -m thoughtvault scan
```

Scans all enabled source folders.

Scan only one source:

```powershell
python -m thoughtvault scan --source-id 1
```

Scan records file status:

```text
new
changed
unchanged
deleted
error
missing_source
```

### List Indexed Documents

```powershell
python -m thoughtvault documents
```

Shows indexed documents with source name, path, file type, size, status, chunk count, trace count, and modified time.

### Search

```powershell
python -m thoughtvault search "<query>"
```

Examples:

```powershell
python -m thoughtvault search "FastAPI"
python -m thoughtvault search "SQLite FTS5"
python -m thoughtvault search "personal memory"
```

Search currently checks both:

- extracted text chunks
- extracted traces such as titles, paths, headings, dates, URLs, fields, and common technology names

Limit result count:

```powershell
python -m thoughtvault search "SQLite" --limit 5
```

### Recall

```powershell
python -m thoughtvault recall "<query>"
```

Examples:

```powershell
python -m thoughtvault recall "FastAPI"
python -m thoughtvault recall "SQLite FTS5"
python -m thoughtvault recall "personal memory"
```

Recall Mode groups matching chunks and traces by source document. It shows:

- source path
- source category
- chunk hit count
- trace hit count
- technologies detected from matching traces
- dates detected from matching traces
- relevant headings
- evidence snippets

Limit document count:

```powershell
python -m thoughtvault recall "SQLite" --limit 3
```

Limit evidence snippets per document:

```powershell
python -m thoughtvault recall "SQLite" --evidence-limit 2
```

Current Recall Mode is source-backed retrieval and aggregation. It does not use AI yet.

### Reference Cards

```powershell
python -m thoughtvault reference build
```

Builds conservative reference cards from indexed sources categorized as `reference`, `personal`, or `company`.

List generated cards:

```powershell
python -m thoughtvault reference list
```

Search generated cards through their source-backed traces:

```powershell
python -m thoughtvault reference search "Example"
```

Build cards for one source:

```powershell
python -m thoughtvault reference build --source-id 1
```

Reference Cards currently include:

- source document path
- inferred card category
- sensitivity label
- source-backed traces such as fields, dates, URLs, title, and path

Reference Mode is intentionally conservative. It does not infer facts beyond extracted traces.

## Current Capabilities

Phase 1 supports `.md` and `.txt` files. It records source roots, categories, root-relative file paths, file type, size, content hash, modified time, and document status (`new`, `changed`, `unchanged`, `deleted`, or error states).

Phase 2 adds:

- text extraction for `.md` and `.txt`
- chunk creation
- basic trace extraction for titles, paths, headings, dates, URLs, form-like fields, and common technology names
- SQLite FTS5 indexes for chunks and traces
- `thoughtvault search <query>`

Phase 3 adds:

- `thoughtvault recall <query>`
- document-level grouping of matching chunks and traces
- source-backed evidence snippets for recall
- extracted technologies, dates, and headings in recall output

Phase 4 adds:

- `thoughtvault reference build`
- `thoughtvault reference list`
- `thoughtvault reference search <query>`
- generated reference cards for `reference`, `personal`, and `company` sources
- sensitivity labels for personal/company reference cards

## Current Limits

Not implemented yet:

- PDF, Word, Excel, and image/OCR extraction
- AI summarization
- AI-generated natural-language Recall Mode answers
- advanced Reference Cards with user review and masking
- Memo clustering and thought extension
- Markdown export
- Web UI
- semantic search or vector database
