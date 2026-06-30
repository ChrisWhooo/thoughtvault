# Output Design

ThoughtVault should produce two types of output:

1. portable Markdown notes
2. local Web UI views

Markdown is the durable artifact. The Web UI is the convenient interface.

## Markdown Output

Suggested structure:

```text
Vault/
|-- _Index.md
|-- Sources/
|-- Recall/
|   |-- Projects/
|   |-- Timelines/
|   `-- Technologies/
|-- References/
|-- Knowledge/
|   |-- Technical/
|   |-- Concepts/
|   `-- Lessons/
|-- Memos/
|   |-- Themes/
|   |-- Thoughts/
|   `-- Extensions/
`-- Reviews/
```

## Source Archive Note

Generated from one source file.

```markdown
---
type: source
source_path: Projects/Migration/basic-design.xlsx
source_hash: ...
generated_by: thoughtvault
status: generated
---

# basic-design.xlsx

## Summary

This file describes...

## Extracted Traces

- project: ...
- technologies: ...
- dates: ...

## Source

- Projects/Migration/basic-design.xlsx
```

## Project Recall Page

Generated from a project folder.

```markdown
---
type: project_recall
project: Migration Project
generated_by: thoughtvault
status: generated
---

# Migration Project

## What This Project Was

...

## Timeline

- ...

## Technologies Used

- ...

## Decisions

- ...

## Problems and Solutions

- ...

## Source Documents

- [[Sources/basic-design]]
- [[Sources/operation-manual]]
```

## Technical Knowledge Note

Generated from project materials when there is reusable learning value.

```markdown
---
type: technical_note
topic: SQLite FTS5
derived_from:
  - Projects/ThoughtVault/docs/03-architecture.md
generated_by: thoughtvault
status: suggested
---

# SQLite FTS5 for Local Knowledge Search

## Context

This note was derived from project materials where SQLite FTS5 was considered for local full-text search.

## Explanation

...

## When To Use

...

## Source Evidence

- Projects/ThoughtVault/docs/03-architecture.md
```

## Reference Card

Generated from factual reference materials.

```markdown
---
type: reference_card
category: application
sensitivity: medium
generated_by: thoughtvault
status: generated
---

# Application Record - 2026-06

## Key Facts

| Field | Value | Source |
|---|---|---|
| submitted_date | ... | ... |
| organization | ... | ... |

## Source

- Company/applications/...
```

Reference cards should avoid unsupported inference. If a field is uncertain, mark it uncertain.

## Memo Concept Note

Generated from Obsidian notes or loose memos.

```markdown
---
type: concept_note
topic: Personal Memory
generated_by: thoughtvault
status: suggested
---

# Personal Memory

## Core Idea

...

## Related Notes

- [[Memos/2026-06-30-memory-system]]

## Open Questions

- ...

## Thought Extension

...
```

## Web UI Views

### Dashboard

Shows:

- total sources
- total files
- indexed files
- failed files
- recently changed files
- pending review items

### Search

Supports:

- keyword search
- trace search
- semantic search
- filter by source category
- filter by file type
- filter by tag

### Recall

Supports:

- project recall
- technology recall
- timeline recall
- "where did I touch this before?" questions

### Reference

Supports:

- factual lookup
- reference cards
- sensitive information warnings
- source-backed answers

### Synthesis

Supports:

- technical notes
- project lessons
- memo clustering
- philosophical concept pages
- thought extensions

### Review

Shows:

- newly generated recall items
- reference cards
- synthesis notes
- stale outputs after source file changes

## Output Rule

Markdown must be useful even without the Web UI.

Web UI must never be the only place where important memory, reference, or knowledge exists.

Generated outputs must keep source references.
