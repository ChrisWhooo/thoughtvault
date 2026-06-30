# Product Modes

ThoughtVault has three main product modes:

1. Recall Mode
2. Reference Mode
3. Synthesis Mode

The modes share the same source files, scanner, indexes, and evidence model, but they produce different kinds of answers.

## Recall Mode

Recall Mode is for復盤.

It helps the user recover past exposure:

- projects they worked on
- technologies they touched
- problems they solved
- decisions they made
- documents they once read or created
- ideas they wrote about but no longer remember clearly

### Input Examples

- Did I ever work with FastAPI?
- What did the migration project involve?
- Which project used SQLite FTS?
- What documents mention this system?
- What did I write about memory and knowledge?

### Expected Answer Shape

```text
Answer
Relevant source files
Evidence snippets
Timeline hints
Technologies or concepts
AI-assisted summary
Uncertainty notes
```

### Quality Bar

Recall Mode can synthesize, but it must preserve evidence.

If evidence is weak, the answer should say so.

## Reference Mode

Reference Mode is for factual lookup and reuse.

It helps the user find information from:

- attendance records
- application records
- company information
- personal information
- contracts
- administrative documents
- submitted forms

### Input Examples

- Where is the attendance sheet I submitted?
- What company information did I use in that application?
- Which file contains this address or identifier?
- What records do I have for this month?

### Expected Answer Shape

```text
Direct fact or file location
Source document
Evidence snippet or field
Date hint
Sensitivity warning when relevant
```

### Quality Bar

Reference Mode should be conservative.

It should not infer beyond the evidence. It should mark uncertain fields and prefer saying "not found" over guessing.

## Synthesis Mode

Synthesis Mode is for turning past exposure into structured knowledge.

It has two major branches:

1. project synthesis
2. memo and thought synthesis

## Project Synthesis

Project synthesis turns project archives into learning material.

Expected outputs:

- technical notes
- project lessons
- architecture explanations
- technology summaries
- problem-solution writeups
- decision records

Example:

```text
Create a technical note from the project files about how SQLite FTS5 is used for local search.
```

## Memo and Thought Synthesis

Memo synthesis turns scattered notes into organized thought.

Expected outputs:

- theme clusters
- concept notes
- thought extensions
- essay outlines
- recurring questions
- contradictions or changes in thinking

Example:

```text
Organize my notes about personal memory into concepts and open questions.
```

### Quality Bar

Synthesis Mode can be more interpretive than Reference Mode, but it should separate:

- source-backed summary
- AI-generated interpretation
- AI-generated extension

Generated claims should cite source files or chunks whenever possible.

## Mode Selection

The system can infer mode from the user's question:

| User Intent | Mode |
|---|---|
| "What did I work on?" | Recall |
| "Where is this file or fact?" | Reference |
| "Turn this into a technical note" | Synthesis |
| "Organize my thoughts" | Synthesis |
| "What technologies did this project involve?" | Recall, then Synthesis |

When uncertain, the system should default to Recall Mode because it surfaces evidence without forcing interpretation.
