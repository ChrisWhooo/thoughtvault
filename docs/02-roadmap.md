# Roadmap

## Phase 0: Project Foundation

Goal: define ThoughtVault as a personal memory and knowledge system, not only a generic document index.

Deliverables:

- README
- product vision
- architecture draft
- data model draft
- processing pipeline
- output design
- example memo format
- clarified product modes: Recall, Reference, Synthesis

Exit criteria:

- project scope is understandable from the repository alone
- MVP boundary is clear
- major technical choices are recorded
- project, reference, and memo materials have distinct handling strategies

## Phase 1: Local Scanner and Basic Index

Goal: scan a local folder and build a stable file inventory.

Features:

- configure one or more source roots
- assign source categories such as project, reference, memo, personal, company, or unknown
- recursively scan files
- record file path, type, size, hash, modified time
- detect added, changed, and deleted files
- store metadata in SQLite

Supported file types:

- `.md`
- `.txt`

Later in this phase or immediately after:

- `.pdf`
- `.docx`
- `.xlsx`

Exit criteria:

- user can run one command to scan a folder
- repeated scans only mark changed files
- SQLite database can show current file inventory
- each source root has a category that can guide later processing

## Phase 2: Text Extraction, Chunks, and Trace Index

Goal: convert supported files into searchable text and recall clues.

Features:

- extract text from Markdown and text files
- extract text from PDF, Word, and Excel when parsers are available
- split extracted text into chunks
- extract trace clues such as titles, dates, technologies, project names, company names, form fields, URLs, and key phrases
- build SQLite FTS5 index for chunks and traces
- provide CLI search command

Exit criteria:

- user can search across supported files
- search results show source file path and matching snippet
- trace search can find vague clues such as technologies, dates, or concept names
- extraction errors are recorded instead of crashing the scan

## Phase 3: Recall Mode MVP

Goal: answer "what did I touch before?" questions with source-backed results.

Features:

- search across projects, memos, and reference materials
- return source files, snippets, and time hints
- identify project-related files
- extract basic project recall items:
  - project summary
  - technologies used
  - timeline events
  - decisions
  - problems and solutions
- provide CLI recall command

Exit criteria:

- user can ask for past exposure to a technology or project
- answers include source citations
- generated recall items can be marked accepted, rejected, or stale

## Phase 4: Reference Mode MVP

Goal: retrieve and reuse factual information from personal or work reference files.

Features:

- identify reference-oriented source folders
- extract conservative facts, dates, and form-like fields
- generate reference cards
- mark sensitive cards
- answer factual lookup questions with citations

Exit criteria:

- user can retrieve where a past form, application, company document, or personal record lives
- extracted facts point back to source chunks
- Reference Mode avoids unsupported interpretation

## Phase 5: Markdown Export

Goal: generate durable Obsidian-friendly output.

Features:

- generate source index pages
- generate project recall pages
- generate project timelines
- generate reference cards
- generate synthesis note placeholders
- preserve source references and source hashes
- avoid overwriting user-edited notes without review

Exit criteria:

- user can open the exported folder in Obsidian
- generated notes link back to original source paths or source ids
- export conflict behavior is explicit

## Phase 6: Local AI Synthesis

Goal: use local AI to turn source-backed recall into structured knowledge.

Project synthesis features:

- generate technical notes from project materials
- summarize lessons learned
- extract architecture concepts
- compare technologies used in past projects

Memo synthesis features:

- cluster philosophical themes
- extract concept notes
- identify recurring questions
- find contradictions or changes in thinking
- extend incomplete thoughts into outlines or essays

Exit criteria:

- AI-generated synthesis notes cite source chunks
- summaries include source references
- AI failure does not block indexing, recall, or reference lookup

## Phase 7: Semantic Search

Goal: search by meaning, not only exact words.

Features:

- generate embeddings for chunks, traces, recall items, and synthesis notes
- store embeddings in LanceDB or Chroma
- semantic search command
- combine keyword search, trace search, and vector search

Exit criteria:

- user can search for related ideas even when exact keywords differ
- search results keep source file and chunk references

## Phase 8: Local Web UI

Goal: make recall, reference lookup, and synthesis easier to inspect and review.

Views:

- dashboard
- source browser
- search page
- Recall Mode page
- Reference Mode page
- Synthesis Mode page
- document detail page
- review queue

Exit criteria:

- user can browse, search, and review generated outputs without CLI
- new summaries, cards, and synthesis notes can be accepted or rejected in the UI

## Suggested MVP

The first real MVP should include only:

- source root configuration
- folder scan
- SQLite metadata
- text extraction for md/txt
- chunking
- trace extraction
- full-text search
- source-backed search results
- minimal Recall Mode CLI

PDF, docx, xlsx, AI synthesis, semantic search, and Web UI can wait until the core memory index is stable.
