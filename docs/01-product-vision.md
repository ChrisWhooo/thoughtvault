# Product Vision

## Problem

Personal knowledge is usually scattered across many places:

- formal project documents
- raw Obsidian notes
- copied AI conversations
- work records
- salary slips and administrative files
- screenshots, PDFs, Excel files, and Word documents

These files are not difficult to store, but they are difficult to continuously organize. Search can find text, but it cannot explain relationships, extract long-term themes, or show how knowledge has changed.

The real problem is not file storage. The real problem is knowledge digestion.

## Core Idea

ThoughtVault treats local files as raw material and turns them into structured knowledge objects.

```text
Local files
    ↓
Parsing
    ↓
Metadata
    ↓
Chunks
    ↓
Search index and vector index
    ↓
AI summaries and relationships
    ↓
Markdown notes and local Web UI
```

The system should not ask an AI model to scan an entire folder in one request. Instead, it should split the work into small, traceable tasks:

- summarize one file
- summarize one folder
- extract concepts from one chunk
- connect a new file to existing topics
- answer a user question with cited sources

## Design Principles

### Local First

Original files stay on the user's machine. The default mode should not upload private data.

### Source Backed

Every AI-generated conclusion should keep a reference to the original file or chunk. If the system cannot show where a claim came from, the claim should be treated as weak.

### Human Confirmed

AI can suggest tags, links, summaries, and knowledge notes. The user should confirm important changes before they become durable knowledge.

### Incremental Growth

The system should detect file changes and process only new or modified files. A knowledge base grows through repeated small updates, not one huge import.

### Portable Output

Markdown output should remain usable even if the application disappears. Obsidian-compatible notes are the first export target.

## Product Modes

### Library Mode

Used for browsing, searching, and asking questions.

Expected features:

- file browser
- full-text search
- semantic search
- source-backed AI Q&A
- project overview pages
- concept pages
- timeline views

### Growth Mode

Used for reviewing newly discovered changes.

Expected features:

- newly added files
- changed files
- suggested summaries
- suggested tags
- suggested links to existing notes
- pending user confirmation

### Memo Mode

Used for copied AI conversations or personal notes.

Expected features:

- parse copied user and assistant messages
- keep raw conversation archive
- extract useful ideas
- generate structured knowledge notes
- separate user original statements from AI-assisted summaries

## First Product Definition

ThoughtVault is a local-first knowledge system that scans a user-selected folder, indexes mixed document files, uses local AI to summarize and connect them, and exports source-backed knowledge notes to Markdown while offering a local Web UI for search and review.

