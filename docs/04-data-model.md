# Data Model Draft

The system should not rely on a traditional relational database alone, but SQLite is still useful for metadata, indexing state, user review state, and relationships.

The recommended first design is:

```text
SQLite
  - documents
  - chunks
  - tags
  - relations
  - ai_outputs
  - processing_jobs

SQLite FTS5
  - chunk full-text index

Vector DB
  - chunk embeddings
```

## documents

Represents a source file.

| Field | Meaning |
|---|---|
| id | internal document id |
| path | absolute or root-relative file path |
| title | inferred or user-defined title |
| file_type | md, txt, pdf, docx, xlsx |
| source_category | project, obsidian, company, memo, other |
| size_bytes | file size |
| content_hash | hash for change detection |
| created_at | first seen time |
| modified_at | file modified time |
| indexed_at | latest indexing time |
| extraction_status | pending, success, failed |
| summary | latest accepted summary |

## chunks

Represents extracted text segments.

| Field | Meaning |
|---|---|
| id | internal chunk id |
| document_id | source document |
| chunk_index | order inside document |
| content | extracted text |
| token_count | estimated token count |
| location_hint | page, sheet, heading, or section |
| content_hash | chunk-level hash |

## tags

Represents normalized tags.

| Field | Meaning |
|---|---|
| id | tag id |
| name | tag name |
| source | user, rule, ai |

## document_tags

Connects documents and tags.

| Field | Meaning |
|---|---|
| document_id | source document |
| tag_id | tag |
| confidence | optional AI confidence |
| status | suggested, accepted, rejected |

## entities

Represents named things discovered in content.

Examples:

- project name
- system name
- company name
- person name
- technology
- process
- server name

| Field | Meaning |
|---|---|
| id | entity id |
| name | entity name |
| type | project, system, person, company, technology, process, other |

## relations

Represents relationships between documents, chunks, or entities.

| Field | Meaning |
|---|---|
| id | relation id |
| source_type | document, chunk, entity |
| source_id | source object |
| target_type | document, chunk, entity |
| target_id | target object |
| relation_type | references, similar_to, depends_on, contradicts, updates, belongs_to |
| evidence_chunk_id | source evidence |
| status | suggested, accepted, rejected |

## ai_outputs

Stores generated content without confusing it with source truth.

| Field | Meaning |
|---|---|
| id | output id |
| target_type | document, folder, chunk, memo |
| target_id | target object |
| task_type | summary, tags, concepts, decisions, open_questions, report |
| model | model name |
| prompt_version | prompt version |
| content | AI output |
| created_at | generation time |
| status | suggested, accepted, rejected |

## processing_jobs

Tracks background work.

| Field | Meaning |
|---|---|
| id | job id |
| job_type | scan, extract, chunk, summarize, embed, export |
| target_path | file or folder path |
| status | pending, running, success, failed |
| error_message | failure detail |
| created_at | created time |
| finished_at | completion time |

## Why Not Only MongoDB?

MongoDB can store flexible documents, but local-first desktop tools benefit from SQLite because:

- it is embedded
- it is easy to back up
- it is easy to inspect
- it supports FTS5
- it has no server process

The source files are already the document store. The database mainly tracks structure, search, state, and derived knowledge.

