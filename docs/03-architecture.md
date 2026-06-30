# Architecture

## High-Level Architecture

```text
Source roots
        -> Scanner
        -> Parser and extractor
        -> Chunker
        -> Trace extractor
        -> SQLite metadata database
        -> Full-text search index
        -> Recall engine
        -> Reference extractor
        -> Synthesis engine
        -> Markdown exporter and Web UI
```

## Source Roots

A source root is a configured local folder.

Each source root can have one or more categories:

- project
- reference
- memo
- conversation
- personal
- company
- unknown

The category does not only label the folder. It controls which processing tasks are appropriate.

## Components

### Scanner

Responsibilities:

- recursively scan configured folders
- calculate file hash
- detect new, changed, deleted, and unchanged files
- create document records
- preserve root-relative paths
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
| Image | OCR later |

### Chunker

Responsibilities:

- split extracted text into chunks
- keep chunk order
- keep page, sheet, heading, section, or message hints when available
- avoid chunks that are too large for local models

### Trace Extractor

Responsibilities:

- extract recall clues from chunks and metadata
- identify technologies, project names, companies, dates, commands, URLs, form fields, and concepts
- store both normalized values and raw text
- support rule-based extraction first, AI extraction later

Traces are important because users often remember only fragments.

### Metadata Store

SQLite stores:

- source roots
- file records
- chunks
- traces
- recall items
- reference cards
- synthesis notes
- tags
- entities
- relations
- processing jobs
- AI outputs
- user review decisions

### Full-Text Search

SQLite FTS5 supports:

- exact keyword search
- snippets
- ranking
- trace search
- lightweight local deployment

### Recall Engine

Responsibilities:

- answer "what did I touch before?" questions
- combine file metadata, chunks, traces, and accepted/generated recall items
- return evidence before synthesis
- generate project summaries, timelines, technology lists, decisions, and problem-solution notes

### Reference Extractor

Responsibilities:

- extract conservative facts from reference materials
- generate source-backed reference cards
- identify dates, organizations, form fields, and reusable facts
- mark sensitive information
- avoid unsupported interpretation

### Synthesis Engine

Responsibilities:

- generate technical notes from project materials
- generate lessons learned
- cluster memo themes
- organize philosophical concepts
- extend incomplete thoughts
- cite source chunks for generated claims

### Vector Index

Vector index supports semantic search.

Candidate tools:

- LanceDB
- Chroma
- FAISS

The first implementation can postpone vector search until the basic full-text and trace search is stable.

### Markdown Exporter

Responsibilities:

- generate Obsidian-compatible notes
- keep frontmatter
- keep source references
- generate index pages, project recall pages, reference cards, and synthesis notes
- avoid overwriting user-edited notes without review

### Web UI

Responsibilities:

- browse sources and documents
- search
- inspect recall answers
- retrieve reference cards
- review synthesis notes
- show memory growth over time

## Incremental Processing

The system should process only changed files.

```text
scan file
    -> compare hash
    -> if unchanged: skip
if changed: extract text
    -> chunk
    -> extract traces
    -> update search index
    -> run category-specific jobs
    -> mark AI outputs stale when source changes
```

## Trust Boundary

Source files are authoritative.

Generated notes, recall items, reference cards, and synthesis notes are derived artifacts.

AI output is advisory unless confirmed by the user.

Reference Mode should be more conservative than Synthesis Mode.
