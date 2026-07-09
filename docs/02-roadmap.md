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

## Phase 7: Local Knowledge Ask

Goal: let users ask natural-language questions over indexed local files with source-backed answers.

Features:

- `thoughtvault ask <question>`
- retrieve evidence from chunks and traces
- call local Ollama for source-backed answers
- print evidence after AI answers
- support `--no-ai` for evidence inspection
- extract text from Excel and text-based PDF files

Exit criteria:

- users can ask questions without manually opening source files
- answers include source-backed evidence
- AI failure falls back to evidence retrieval

## Phase 8: Reliable Hybrid Knowledge Q&A (Complete)

Goal: make local knowledge answers semantic, stable, reviewable, and reusable enough for productization.

Features:

- generate and incrementally refresh local chunk embeddings
- combine keyword, trace, and vector evidence ranking
- support multilingual and cross-language retrieval
- save Ask Records in SQLite
- list and show past Ask Records
- export Ask Records to Markdown
- support stricter evidence-grounded answering
- support JSON output for future UI/API integration
- keep answers traceable even when model citations are imperfect
- run repeatable JSON evaluation suites

Exit criteria:

- fuzzy questions can retrieve relevant material across Chinese and Japanese
- users can review what they asked and which sources supported the answer
- exported Q&A history can be opened in Obsidian or another Markdown tool
- unsupported answers degrade to evidence-only output
- automated retrieval and answer checks pass against a fixed evaluation suite

## Phase 9: Structured Facts And Conflict Detection (In Progress)

Goal: turn retrieved text into reviewable facts without losing source provenance.

Features:

- extract people, organizations, dates, places, amounts, events, and relationships
- keep source location, confidence, and extraction method for every fact
- detect conflicting values across files and dates
- calculate supported totals and comparisons through deterministic tools
- add a review state before inferred facts become durable knowledge
- prioritize confirmed facts during answers and exclude rejected facts
- refuse to arbitrate conflicting confirmed values

Exit criteria:

- factual answers can point to normalized, source-backed records
- conflicting facts are shown rather than silently merged
- unsupported calculations are refused instead of guessed

## Phase 10: Local Web UI

Goal: make recall, reference lookup, Q&A, and synthesis easier to inspect and review.

Views:

- dashboard
- source browser
- search and ask page
- Recall Mode page
- Reference Mode page
- Synthesis Mode page
- Ask history page
- document detail page
- review queue

Exit criteria:

- users can browse, search, ask, and review generated outputs without CLI
- new summaries, cards, answers, and synthesis notes can be accepted or rejected in the UI

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
