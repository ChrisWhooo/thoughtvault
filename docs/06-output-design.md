# Output Design

ThoughtVault should produce two types of output:

1. portable Markdown notes
2. local Web UI views

Markdown is the durable artifact. The Web UI is the convenient interface.

## Markdown Output

Suggested structure:

```text
Vault/
├─ _Index.md
├─ Projects/
├─ Concepts/
├─ Sources/
├─ Memos/
├─ Timelines/
└─ Reviews/
```

## Source Archive Note

Generated from one source file.

```markdown
---
type: source
source_path: Projects/vMotion/基本設計書.xlsx
generated_by: thoughtvault
status: generated
---

# 基本設計書

## Summary

This file describes...

## Key Points

- ...

## Source

- Projects/vMotion/基本設計書.xlsx
```

## Project Overview Note

Generated from a project folder.

```markdown
---
type: project
project: vMotion Migration
generated_by: thoughtvault
status: generated
---

# vMotion Migration

## Overview

...

## Documents

- [[Sources/要件定義書]]
- [[Sources/基本設計書]]
- [[Sources/手順書]]

## Decisions

- ...

## Open Questions

- ...
```

## Concept Note

Generated from repeated themes across files.

```markdown
---
type: concept
tags:
  - VMware
  - vMotion
generated_by: thoughtvault
status: suggested
---

# Cross-Cluster Migration

## Definition

...

## Related Sources

- Projects/vMotion/...

## Related Concepts

- [[EVC]]
- [[vGPU]]
- [[Offline Migration]]
```

## Memo-Derived Note

Used when the user copies AI conversation content into a memo file.

```markdown
---
type: memo_note
source: Memos/2026-06-30_knowledge-base.md
generated_by: thoughtvault
status: suggested
---

# Memo-first Knowledge Workflow

## User Original Thought

> ...

## AI-Assisted Summary

...

## Durable Knowledge

...

## Source

- [[Memos/2026-06-30_knowledge-base_raw]]
```

## Web UI Views

### Dashboard

Shows:

- total files
- indexed files
- failed files
- recently changed files
- pending review items

### Search

Supports:

- keyword search
- semantic search
- filter by category
- filter by file type
- filter by tag

### Document Detail

Shows:

- original metadata
- extracted text preview
- chunks
- summary
- tags
- related files

### Growth Review

Shows:

- newly found files
- changed files
- suggested summaries
- suggested tags
- suggested relations

### Project Page

Shows:

- project overview
- source documents
- decisions
- open questions
- timeline
- related concepts

## Output Rule

Markdown must be useful even without the Web UI.

Web UI must never be the only place where important knowledge exists.

