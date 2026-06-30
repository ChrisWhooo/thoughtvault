# Roadmap

## Phase 0: Project Foundation

Goal: define the product clearly before writing code.

Deliverables:

- README
- product vision
- architecture draft
- data model draft
- processing pipeline
- output design
- example memo format

Exit criteria:

- project scope is understandable from the repository alone
- MVP boundary is clear
- major technical choices are recorded

## Phase 1: Local Scanner and Basic Index

Goal: scan a local folder and build a stable file inventory.

Features:

- configure knowledge root folder
- recursively scan files
- record file path, type, size, hash, modified time
- detect added, changed, and deleted files
- store metadata in SQLite

Supported file types:

- `.md`
- `.txt`
- `.pdf`
- `.docx`
- `.xlsx`

Exit criteria:

- user can run one command to scan a folder
- repeated scans only mark changed files
- SQLite database can show current file inventory

## Phase 2: Text Extraction and Full-Text Search

Goal: convert supported files into searchable text.

Features:

- extract text from Markdown and text files
- extract text from PDF
- extract text from Word
- extract text from Excel sheets
- split extracted text into chunks
- build SQLite FTS5 index
- provide CLI search command

Exit criteria:

- user can search across all supported files
- search results show file path and matching snippet
- extraction errors are recorded instead of crashing the scan

## Phase 3: Markdown Export

Goal: generate durable Obsidian-friendly output.

Features:

- generate raw file summary placeholders
- generate index pages
- generate folder overview pages
- export tags and frontmatter
- preserve source references

Exit criteria:

- user can open the exported folder in Obsidian
- generated notes link back to original source paths

## Phase 4: Local AI Summarization

Goal: add optional local AI through Ollama.

Features:

- configure Ollama model
- summarize one file
- summarize one folder
- extract tags
- extract action items, decisions, concepts, and open questions
- mark AI outputs as generated and source-backed

Exit criteria:

- AI can summarize documents without cloud API
- summaries include source references
- AI failure does not block basic indexing

## Phase 5: Semantic Search

Goal: search by meaning, not only exact words.

Features:

- generate embeddings for chunks
- store embeddings in LanceDB or Chroma
- semantic search command
- combine keyword search and vector search

Exit criteria:

- user can search for related ideas even when exact keywords differ
- search results keep source file and chunk references

## Phase 6: Local Web UI

Goal: make the system easier to inspect and review.

Features:

- dashboard
- file browser
- search page
- document detail page
- summary page
- growth review page
- pending suggestions page

Exit criteria:

- user can browse and search the knowledge base without CLI
- new summaries and tags can be reviewed in the UI

## Phase 7: Memo-to-Knowledge Workflow

Goal: support copied AI conversations and personal notes as first-class input.

Features:

- parse memo files
- detect user and assistant messages
- keep raw conversation archives
- generate knowledge notes from selected conversations
- separate user original statements from AI-generated summaries

Exit criteria:

- user can copy a whole AI conversation into a memo file
- tool can produce raw archive, summary, and knowledge notes

## Phase 8: Playful Conversation Report

Goal: add a shareable, lightweight demo mode.

Features:

- paste conversation text
- generate conversation summary
- infer user interaction style
- generate Markdown or HTML report
- do not store raw conversation by default

Exit criteria:

- user can generate a report from pasted conversation text
- report is useful as a demo but clearly separated from the serious knowledge base workflow

## Suggested MVP

The first real MVP should include only:

- folder scan
- SQLite metadata
- text extraction for md/txt/pdf/docx/xlsx
- chunking
- full-text search
- Markdown export
- optional Ollama file summary

Everything else can wait.

