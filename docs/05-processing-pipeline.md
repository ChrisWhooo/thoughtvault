# Processing Pipeline

## Pipeline Overview

```text
1. Configure sources
2. Scan
3. Classify
4. Extract
5. Chunk
6. Extract traces
7. Index
8. Run mode-specific processing
9. Export
10. Review
```

## 1. Configure Sources

The user selects local folders and assigns one or more categories.

Examples:

| Folder | Categories |
|---|---|
| `Projects/` | project |
| `Work/Forms/` | reference, company |
| `Personal/Admin/` | reference, personal |
| `Obsidian/` | memo |
| `AI-Conversations/` | conversation, memo |

Categories guide later processing. A project folder should produce recall and knowledge notes. A reference folder should prioritize accurate retrieval. A memo folder should support clustering and thought extension.

## 2. Scan

The scanner walks through configured source roots.

It records:

- root-relative path
- file type
- size
- modified time
- content hash
- source category

It compares the new scan with the previous scan.

Possible states:

- new
- changed
- unchanged
- deleted

## 3. Classify

The system classifies files by source root, path, file type, and optional rules.

Example rules:

| Path Pattern | Category |
|---|---|
| `Projects/` | project |
| `Obsidian/` | memo |
| `Company/salary/` | reference, company |
| `Company/applications/` | reference, company |
| `Personal/forms/` | reference, personal |
| `Memos/` | memo |

Classification should be configurable and reversible.

## 4. Extract

Each supported file is converted into text.

The source file is never modified.

Extraction should preserve useful hints:

- PDF page number
- Excel sheet name
- Word heading
- Markdown heading
- AI conversation speaker marker
- file modified time

Failures should be recorded, not hidden.

## 5. Chunk

Long extracted text is split into smaller chunks.

Chunking strategy:

- prefer headings and section boundaries
- keep page or sheet hints
- keep speaker markers in conversation files
- avoid cutting tables in the middle when possible
- keep stable chunk indexes

Chunks are technical retrieval units. They are not automatically user-facing knowledge.

## 6. Extract Traces

Traces are searchable clues that help future recall.

Trace extraction should identify:

- project names
- technology names
- company names
- dates
- people
- commands
- URLs
- file titles
- headings
- form fields
- error messages
- philosophical concepts
- recurring phrases

Trace extraction can begin with simple rules and expand to AI-assisted extraction later.

## 7. Index

The system builds multiple indexes.

Full-text index:

- exact keyword search
- snippets
- fast local search

Trace index:

- technology names
- project names
- dates
- fields
- concepts

Vector index:

- semantic search
- related idea discovery
- RAG retrieval

Vector indexing can be optional in early versions.

## 8. Run Mode-Specific Processing

### Recall Processing

Used for project archives, memos, and conversations.

Possible outputs:

- project summary
- project timeline
- technologies used
- decisions
- problems and solutions
- "things I touched before" recall items

Recall answers must include source evidence.

### Reference Processing

Used for personal, company, administrative, and form-like materials.

Possible outputs:

- reference cards
- extracted dates
- extracted fields
- source-backed factual answers

Reference processing should avoid creative interpretation. It should say when evidence is missing or uncertain.

### Synthesis Processing

Used for project learning and memo organization.

Project synthesis outputs:

- technical notes
- architecture explanations
- lessons learned
- reusable knowledge pages

Memo synthesis outputs:

- theme clusters
- concept notes
- thought extensions
- essay outlines
- contradictions or open questions

Synthesis can be more interpretive, but important claims still need source links.

## 9. Export

The exporter creates Markdown output.

Possible outputs:

- source index
- project recall page
- project timeline
- technology note
- reference card
- concept note
- thought extension
- AI conversation archive
- memo-derived knowledge note

Generated notes should include:

- frontmatter
- source references
- source hashes
- generated timestamp
- status

## 10. Review

The user reviews suggested changes.

Review actions:

- accept
- reject
- edit
- merge
- postpone

Confirmed outputs become durable. Rejected suggestions should not be repeatedly suggested unless the source changes.

## Important Rule

Do not design the system as:

```text
Send entire folder to AI
```

Design it as:

```text
Extract source-backed evidence
Build searchable traces
Generate mode-specific outputs
Let the user confirm important knowledge
```
