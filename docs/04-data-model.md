# Data Model Draft

ThoughtVault should model local files as source material for recall, reference retrieval, and synthesis.

The first implementation should use SQLite for metadata, indexing state, source relationships, review state, and generated outputs.

```text
SQLite
  - sources
  - documents
  - chunks
  - traces
  - recall_items
  - reference_cards
  - synthesis_notes
  - tags
  - entities
  - relations
  - ai_outputs
  - review_decisions
  - processing_jobs

SQLite FTS5
  - chunk full-text index
  - trace full-text index

Vector DB
  - optional chunk and note embeddings
```

## sources

Represents a configured source root.

Examples:

- project archive folder
- reference materials folder
- Obsidian vault
- memo folder
- exported AI conversations folder

| Field | Meaning |
|---|---|
| id | internal source id |
| root_path | configured local folder path |
| name | user-facing source name |
| categories | project, reference, memo, conversation, personal, company, unknown |
| scan_enabled | whether this source is active |
| created_at | first configured time |
| last_scanned_at | latest scan time |

## documents

Represents a source file.

| Field | Meaning |
|---|---|
| id | internal document id |
| source_id | configured source root |
| path | root-relative file path |
| absolute_path | local absolute path, kept private |
| title | inferred or user-defined title |
| file_type | md, txt, pdf, docx, xlsx, image, other |
| source_categories | project, reference, memo, conversation, personal, company, unknown |
| size_bytes | file size |
| content_hash | hash for change detection |
| created_at | first seen time |
| modified_at | file modified time |
| indexed_at | latest indexing time |
| extraction_status | pending, success, failed |
| error_message | latest extraction error if any |

## chunks

Represents extracted text segments.

Chunks are technical retrieval units, not user-facing knowledge by themselves.

| Field | Meaning |
|---|---|
| id | internal chunk id |
| document_id | source document |
| chunk_index | order inside document |
| content | extracted text |
| token_count | estimated token count |
| location_hint | page, sheet, heading, section, or message marker |
| content_hash | chunk-level hash |

## traces

Represents searchable clues extracted from source files.

Traces are optimized for recall: they help the user find things they vaguely remember.

Examples:

- project names
- technology names
- company names
- person names
- dates
- file titles
- headings
- commands
- URLs
- error messages
- form fields
- philosophical concepts
- recurring phrases

| Field | Meaning |
|---|---|
| id | trace id |
| document_id | source document |
| chunk_id | optional source chunk |
| trace_type | project, technology, date, person, company, command, url, field, concept, phrase, unknown |
| value | normalized trace value |
| raw_text | original extracted text |
| confidence | extraction confidence |
| extractor | rule, parser, ai |

## recall_items

Represents source-backed recall material.

Recall items help answer "what did I touch, do, use, or decide before?"

| Field | Meaning |
|---|---|
| id | recall item id |
| title | readable recall title |
| summary | short description |
| recall_type | project_detail, timeline_event, technology_used, decision, problem_solution, idea, conversation, unknown |
| source_document_ids | related documents |
| source_chunk_ids | related chunks |
| time_hint | date, period, or inferred time |
| project | optional project name |
| technologies | optional technologies |
| confidence | confidence score or label |
| status | generated, accepted, rejected, stale |

## reference_cards

Represents reusable factual information from reference materials.

Reference cards should be conservative and source-backed.

| Field | Meaning |
|---|---|
| id | reference card id |
| title | readable card title |
| category | attendance, application, company_info, personal_info, contract, salary, admin, other |
| fields_json | extracted structured fields when safe |
| summary | human-readable description |
| source_document_ids | related documents |
| source_chunk_ids | evidence chunks |
| sensitivity | low, medium, high |
| status | generated, accepted, rejected, stale |

## synthesis_notes

Represents AI-assisted knowledge or thought notes.

Examples:

- technical note extracted from a project
- project lessons learned
- concept page from philosophical memos
- essay outline from recurring ideas
- comparison of related technologies

| Field | Meaning |
|---|---|
| id | synthesis note id |
| title | note title |
| note_type | technical_note, project_lesson, concept_note, thought_extension, essay_outline, comparison, other |
| body | generated Markdown content |
| source_document_ids | related source documents |
| source_chunk_ids | cited chunks |
| prompt_version | generation prompt version |
| model | AI model used |
| status | suggested, accepted, edited, rejected, stale |

## tags

Represents normalized tags.

| Field | Meaning |
|---|---|
| id | tag id |
| name | tag name |
| source | user, rule, ai |

## entities

Represents named things discovered in content.

Examples:

- project name
- system name
- company name
- person name
- technology
- process
- philosophical concept

| Field | Meaning |
|---|---|
| id | entity id |
| name | entity name |
| type | project, system, person, company, technology, process, concept, other |

## relations

Represents relationships between documents, chunks, traces, recall items, reference cards, synthesis notes, or entities.

| Field | Meaning |
|---|---|
| id | relation id |
| source_type | document, chunk, trace, recall_item, reference_card, synthesis_note, entity |
| source_id | source object |
| target_type | document, chunk, trace, recall_item, reference_card, synthesis_note, entity |
| target_id | target object |
| relation_type | references, similar_to, depends_on, updates, belongs_to, uses_technology, extends, contradicts |
| evidence_chunk_id | source evidence |
| status | suggested, accepted, rejected |

## ai_outputs

Stores generated content without confusing it with source truth.

| Field | Meaning |
|---|---|
| id | output id |
| target_type | document, folder, chunk, recall_item, reference_card, synthesis_note |
| target_id | target object |
| task_type | recall, reference_extract, project_summary, technology_extract, memo_cluster, thought_extension, qa, report |
| model | model name |
| prompt_version | prompt version |
| content | AI output |
| source_hashes | hashes of source documents or chunks |
| created_at | generation time |
| status | suggested, accepted, rejected, stale |

## processing_jobs

Tracks background work.

| Field | Meaning |
|---|---|
| id | job id |
| job_type | scan, extract, chunk, trace, recall, reference_extract, synthesize, embed, export |
| target_path | file or folder path |
| status | pending, running, success, failed |
| error_message | failure detail |
| created_at | created time |
| finished_at | completion time |

## Data Model Principle

Do not force every useful thing into one "knowledge object."

ThoughtVault should preserve the distinction between:

- source files: original evidence
- traces: recall clues
- recall items: things the user may want to remember
- reference cards: factual reusable information
- synthesis notes: AI-assisted knowledge and thought documents
