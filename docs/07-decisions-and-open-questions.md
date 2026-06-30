# Decisions and Open Questions

This document records early product and technical decisions. It should be updated whenever the project direction changes.

## Confirmed Decisions

### ThoughtVault is a personal memory and knowledge system

ThoughtVault should not be framed only as a knowledge base.

It has three first-class goals:

- recall past projects and forgotten details
- retrieve and reuse personal or work reference information
- synthesize project materials and memos into durable knowledge notes

Reason:

- the user may remember only fragments of past exposure
- project archives need復盤, not only search
- reference materials need accurate lookup, not creative summarization
- Obsidian and philosophical memos need classification, synthesis, and thought extension

### Local-first by default

The default workflow should run locally and should not upload private files.

Reason:

- the memory base may contain company documents, salary slips, personal records, and private AI conversations
- privacy is part of the product value
- local-first makes the project more suitable for open source users

### Source files remain authoritative

ThoughtVault should not edit original source files automatically.

Reason:

- project documents and company records should remain unchanged
- generated memory and knowledge should be traceable
- AI output may be wrong and should not overwrite source truth

### Source categories drive processing

Project, reference, memo, conversation, personal, and company sources should not be processed the same way.

Reason:

- project folders need recall and technical synthesis
- reference folders need conservative factual retrieval
- memo folders need clustering, interpretation, and thought extension

### Recall, Reference, and Synthesis are separate modes

The product should expose three main modes:

- Recall Mode: recover what the user touched before
- Reference Mode: retrieve and reuse factual information
- Synthesis Mode: organize and extend project knowledge or memo ideas

Reason:

- the same search engine can support all three, but the expected answer style is different
- Reference Mode should avoid unsupported interpretation
- Synthesis Mode needs stronger AI reasoning and can be more exploratory

### Markdown is the durable output

The system should export Obsidian-compatible Markdown.

Reason:

- portable
- easy to inspect
- easy to version with Git
- useful even without the Web UI

### AI is optional for indexing and retrieval

Basic scanning, metadata, extraction, trace indexing, and full-text search should work without AI.

Reason:

- some users may not have a strong local model
- indexing should remain deterministic
- AI should enhance the system, not become a hard dependency

### First database choice: SQLite

SQLite should be used for the first metadata store.

Reason:

- embedded
- local
- easy to back up
- supports FTS5
- enough for MVP

## Pending Decisions

### Source category configuration format

Possible options:

- a `thoughtvault.yaml` config file
- CLI commands that write to SQLite
- both

Decision timing:

- Phase 1

### Export conflict behavior

Possible rule:

- generated files can be regenerated
- user-edited files should not be overwritten without explicit confirmation
- source hashes should be stored in frontmatter

Decision timing:

- before Markdown export

### Sensitive information handling

Questions:

- should personal and company reference cards be excluded from some exports?
- should sensitive fields be masked by default?
- should absolute source paths be hidden in shareable Markdown?

Decision timing:

- before Reference Mode MVP

### Vector index choice

Candidates:

- LanceDB
- Chroma
- FAISS

Current preference:

- LanceDB or Chroma

Decision timing:

- semantic search phase

### Frontend framework

Candidates:

- React
- Next.js
- simple static frontend with API backend

Current preference:

- React first, Next.js only if routing and app structure become important

Decision timing:

- Web UI phase

### Local model baseline

Candidates:

- Ollama with Qwen
- Ollama with Llama
- Ollama with Gemma
- no default model, user config required

Current preference:

- support Ollama through configuration, do not hardcode one model

Decision timing:

- Synthesis Mode phase

## Open Product Questions

### How should project recall be structured?

Possible sections:

- what this project was
- my role or exposure
- timeline
- technologies
- documents
- decisions
- problems and solutions
- lessons learned
- reusable knowledge notes

### How should reference facts be reviewed?

Possible rule:

- low-risk facts can be generated as suggested cards
- sensitive facts require explicit review before export
- uncertain fields must be labeled uncertain

### How should memo synthesis avoid over-interpreting?

Possible rule:

- separate direct memo summary from AI thought extension
- preserve original note links
- mark extension as generated interpretation

### How should generated Markdown be overwritten?

Possible rule:

- generated files can be regenerated
- user-edited files should not be overwritten without explicit confirmation
- stale generated files should be marked rather than silently replaced

## Next Documentation Tasks

- define CLI command examples
- define source configuration file format
- define export conflict handling
- define privacy and sensitive data policy
- define prompt templates for Recall Mode, Reference Mode, and Synthesis Mode
