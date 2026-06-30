# Architecture

## High-Level Architecture

```text
Knowledge root folder
        ↓
Scanner
        ↓
Parser and extractor
        ↓
Chunker
        ↓
SQLite metadata database
        ↓
Full-text search index
        ↓
Vector index
        ↓
AI analyzer
        ↓
Markdown exporter and Web UI
```

## Components

### Scanner

Responsibilities:

- recursively scan configured folders
- calculate file hash
- detect new, changed, deleted, and unchanged files
- create document records
- enqueue changed files for extraction

### Parser and Extractor

Responsibilities:

- convert files into plain text
- keep extraction metadata
- record extraction errors
- avoid modifying source files

Parser candidates:

| File Type | Parser |
|---|---|
| Markdown | markdown parser or plain text |
| Text | built-in reader |
| PDF | pypdf or pdfplumber |
| Word | python-docx |
| Excel | openpyxl |

### Chunker

Responsibilities:

- split extracted text into chunks
- keep chunk order
- keep page, sheet, heading, or section hints when available
- avoid chunks that are too large for local models

### Metadata Store

SQLite stores:

- file records
- chunks
- tags
- entities
- relations
- processing jobs
- AI outputs
- user review decisions

### Full-Text Search

SQLite FTS5 can support:

- exact keyword search
- snippets
- ranking
- lightweight local deployment

### Vector Index

Vector index supports semantic search.

Candidate tools:

- LanceDB
- Chroma
- FAISS

The first implementation can postpone vector search until the basic full-text search is stable.

### AI Analyzer

AI should be optional and task-based.

Possible tasks:

- file summary
- folder summary
- tag suggestion
- concept extraction
- decision extraction
- open question extraction
- relation suggestion
- memo-to-note conversion

The first local model target is Ollama.

### Markdown Exporter

Responsibilities:

- generate Obsidian-compatible notes
- keep frontmatter
- keep source references
- generate index pages
- avoid overwriting user-edited notes without review

### Web UI

Responsibilities:

- browse documents
- search
- inspect summaries
- review pending suggestions
- show knowledge growth over time

## Incremental Processing

The system should process only changed files.

```text
scan file
    ↓
compare hash
    ↓
if unchanged: skip
if changed: extract text
    ↓
chunk
    ↓
update search index
    ↓
generate AI suggestions
    ↓
mark as pending review
```

## Trust Boundary

Source files are authoritative.

Generated notes are derived artifacts.

AI output is advisory unless confirmed by the user.

