# Decisions and Open Questions

This document records early product and technical decisions. It should be updated whenever the project direction changes.

## Confirmed Decisions

### Local-first by default

The default workflow should run locally and should not upload private files.

Reason:

- the knowledge base may contain company documents, salary slips, personal records, and private AI conversations
- privacy is part of the product value
- local-first makes the project more suitable for open source users

### Source files remain authoritative

ThoughtVault should not edit original source files automatically.

Reason:

- project documents and company records should remain unchanged
- generated knowledge should be traceable
- AI output may be wrong and should not overwrite source truth

### Markdown is the durable output

The system should export Obsidian-compatible Markdown.

Reason:

- portable
- easy to inspect
- easy to version with Git
- useful even without the Web UI

### AI is optional

Basic scanning, metadata, extraction, and full-text search should work without AI.

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

### Vector index choice

Candidates:

- LanceDB
- Chroma
- FAISS

Current preference:

- LanceDB or Chroma

Decision timing:

- Phase 5

### Frontend framework

Candidates:

- React
- Next.js
- simple static frontend with API backend

Current preference:

- React first, Next.js only if routing and app structure become important

Decision timing:

- Phase 6

### Local model baseline

Candidates:

- Ollama with Qwen
- Ollama with Llama
- Ollama with Gemma
- no default model, user config required

Current preference:

- support Ollama through configuration, do not hardcode one model

Decision timing:

- Phase 4

### Desktop app or local web app

Candidates:

- local Web app
- Electron desktop app
- Tauri desktop app

Current preference:

- local Web app first

Reason:

- easier to build
- easier to debug
- can become desktop later

Decision timing:

- after MVP proves useful

## Open Product Questions

### How much should the system auto-organize?

Possible rule:

- AI can suggest
- user confirms
- confirmed knowledge becomes durable

### Should generated Markdown be overwritten?

Possible rule:

- generated files can be regenerated
- user-edited files should not be overwritten without explicit confirmation

### How should company documents be handled?

Possible rule:

- company-related files should be indexed locally
- sensitive folders can be excluded
- generated summaries should not expose raw salary or personal identifiers in shareable views

### How should memo files be formatted?

Possible rule:

- support loose formats first
- optionally support structured markers later

Examples:

- `User:`
- `Assistant:`
- `我:`
- `ChatGPT:`
- `[User]`
- `[Assistant]`

## Next Documentation Tasks

- define CLI command examples
- define prompt templates for local AI tasks
- define folder configuration file format
- define export conflict handling
- define privacy and sensitive data policy

