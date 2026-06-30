# Processing Pipeline

## Pipeline Overview

```text
1. Scan
2. Classify
3. Extract
4. Chunk
5. Index
6. Summarize
7. Link
8. Export
9. Review
```

## 1. Scan

The scanner walks through the configured knowledge root.

It records:

- path
- file type
- size
- modified time
- content hash

It compares the new scan with the previous scan.

Possible states:

- new
- changed
- unchanged
- deleted

## 2. Classify

The system classifies files by path and file type.

Example rules:

| Path Pattern | Category |
|---|---|
| `Projects/` | project |
| `Obsidian/` | obsidian |
| `Company/salary/` | company_salary |
| `Company/applications/` | company_application |
| `Memos/` | memo |

Classification should be configurable.

## 3. Extract

Each supported file is converted into text.

The source file is never modified.

Extraction should preserve useful hints:

- PDF page number
- Excel sheet name
- Word heading
- Markdown heading

## 4. Chunk

Long extracted text is split into smaller chunks.

Chunking strategy:

- prefer headings and section boundaries
- keep page or sheet hints
- avoid cutting tables in the middle when possible
- keep stable chunk indexes

## 5. Index

The system builds two possible indexes.

Full-text index:

- exact keyword search
- snippets
- fast local search

Vector index:

- semantic search
- related idea discovery
- RAG retrieval

Vector indexing can be optional in early versions.

## 6. Summarize

AI summarization should happen at multiple levels.

| Level | Input | Output |
|---|---|---|
| Chunk | one chunk | local key points |
| File | chunks from one file | file summary |
| Folder | files in one folder | folder summary |
| Project | project folder | project overview |

AI output should keep source references.

## 7. Link

The system suggests relationships.

Examples:

- this file belongs to this project
- this handover note updates this old design note
- this memo relates to this concept
- this project document mentions the same technology as another project

Relations are suggestions until accepted.

## 8. Export

The exporter creates Markdown output.

Possible outputs:

- raw source index
- folder overview
- project overview
- concept note
- timeline note
- AI conversation archive
- memo-derived knowledge note

Generated notes should include:

- frontmatter
- source references
- generated timestamp
- status

## 9. Review

The user reviews suggested changes.

Review actions:

- accept
- reject
- edit
- merge
- postpone

Confirmed knowledge becomes durable. Rejected suggestions should not be repeatedly suggested unless the source changes.

## Important Rule

Do not design the system as:

```text
Send entire folder to AI
```

Design it as:

```text
Break files into traceable tasks
Generate small source-backed outputs
Let the user confirm important knowledge
```

