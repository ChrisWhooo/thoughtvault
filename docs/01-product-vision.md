# Product Vision

## Problem

Personal memory is scattered across many local materials:

- project folders
- requirements, design documents, handover notes, and operation manuals
- Obsidian notes and philosophical memos
- copied AI conversations
- attendance forms, application records, company materials, and personal administrative files
- PDFs, Excel files, Word documents, screenshots, and loose text files

These files are not hard to store. The hard part is recovering context later.

A user may remember that they once worked on a project, used a technology, submitted a form, or wrote about an idea, but forget the details, the exact file, the surrounding context, or what could be learned from it.

ThoughtVault exists to solve that recall gap.

## Core Idea

ThoughtVault treats local files as source material for a traceable personal memory and knowledge system.

```text
Local source files
    -> scan
    -> extract text and metadata
    -> index traces
    -> support recall and retrieval
    -> generate source-backed summaries
    -> synthesize project knowledge and memo ideas
    -> export durable Markdown notes
```

The system should not ask an AI model to scan an entire folder in one request. Instead, it should split the work into small, traceable tasks:

- identify what source files exist
- extract searchable text
- preserve file, folder, time, and metadata context
- answer recall questions with source citations
- extract project timelines, technologies, decisions, problems, and lessons
- extract reusable facts from reference materials
- classify and extend memo ideas
- generate Markdown notes that point back to source files

## Product Definition

ThoughtVault is a local-first personal memory and knowledge system that helps users:

1. recall past projects and forgotten details
2. retrieve and reuse information from personal or work reference files
3. synthesize project materials and memos into structured knowledge notes

Every generated result should remain traceable to the original source file.

## Product Modes

### Recall Mode

Recall Mode is for復盤: recovering what the user has touched before but no longer remembers clearly.

Typical questions:

- What projects did I work on that involved a specific technology?
- What did this project do?
- Which documents describe the system design?
- What problem did I solve, and what decision did I make?
- Where did I write about a specific idea?

Expected outputs:

- direct answer
- relevant source files
- project details
- timeline hints
- technologies and concepts involved
- AI-assisted summary
- uncertainty notes when evidence is weak

### Reference Mode

Reference Mode is for factual lookup and reuse.

Typical sources:

- attendance records
- application forms
- company information
- personal administrative documents
- salary or contract-related documents
- reusable profile or form data

Typical questions:

- Where is the document I submitted?
- What information did I use in a past application?
- Which file contains this company or personal detail?
- What records exist for this period?

Expected outputs:

- source-backed facts
- file references
- date hints
- extracted fields when safe
- reusable reference cards

This mode should be conservative. It should prioritize precision and traceability over creative interpretation.

### Synthesis Mode

Synthesis Mode is for turning past exposure into durable learning material.

For project folders, it should extract:

- technologies used
- architecture concepts
- decisions and reasons
- problems and solutions
- lessons learned
- technical notes similar to technical blog posts or learning references

For Obsidian and memo folders, it should:

- cluster related ideas
- identify recurring philosophical themes
- organize scattered notes into concept pages
- find tensions, changes, or unresolved questions
- extend incomplete thoughts into drafts, outlines, or deeper questions

This mode can use stronger AI reasoning than Reference Mode, but generated claims still need source links.

## Source Categories

ThoughtVault should support different processing strategies for different source categories:

| Category | Primary Goal | AI Style |
|---|---|---|
| project | recall details and extract lessons | analytical synthesis |
| reference | retrieve facts and reusable information | conservative extraction |
| memo | organize and extend thought | interpretive synthesis |
| conversation | preserve raw context and extract useful ideas | structured summarization |
| personal | retrieve private information safely | conservative extraction |
| company | retrieve work-related records safely | conservative extraction |
| unknown | index first, classify later | minimal assumptions |

Categories should support multiple labels because one file can be both project-related and technical, or both personal and reference-oriented.

## Design Principles

### Local First

Original files stay on the user's machine. The default mode should not upload private data.

### Source Backed

Every AI-generated conclusion should keep a reference to the original file or chunk. If the system cannot show where a claim came from, the claim should be treated as weak.

### Different Sources Need Different Treatment

Project archives, reference documents, and philosophical memos should not be processed by one generic summarization workflow.

### Human Confirmed

AI can suggest summaries, links, classifications, concept notes, reference cards, and technical notes. The user should confirm important changes before they become durable knowledge.

### Incremental Growth

The system should detect file changes and process only new or modified files. A memory base grows through repeated small updates, not one huge import.

### Portable Output

Markdown output should remain usable even if the application disappears. Obsidian-compatible notes are the first export target.
