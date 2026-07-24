from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(".thoughtvault") / "thoughtvault.sqlite"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL UNIQUE,
    categories TEXT NOT NULL,
    scan_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES source_roots(id) ON DELETE CASCADE,
    path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    title TEXT NOT NULL,
    file_type TEXT NOT NULL,
    source_categories TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    document_status TEXT NOT NULL,
    extraction_status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    UNIQUE(source_id, path)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(document_status);
CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    location_hint TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    vector BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chunk_id, model)
);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk_id ON chunk_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_model ON chunk_embeddings(model);

CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    trace_type TEXT NOT NULL,
    value TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    confidence REAL NOT NULL,
    extractor TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_traces_document_id ON traces(document_id);
CREATE INDEX IF NOT EXISTS idx_traces_type ON traces(trace_type);
CREATE INDEX IF NOT EXISTS idx_traces_value ON traces(value);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    title,
    path,
    document_id UNINDEXED,
    chunk_id UNINDEXED
);

CREATE VIRTUAL TABLE IF NOT EXISTS traces_fts USING fts5(
    value,
    raw_text,
    trace_type,
    path,
    document_id UNINDEXED,
    trace_id UNINDEXED
);

CREATE TABLE IF NOT EXISTS reference_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'generated',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id)
);

CREATE INDEX IF NOT EXISTS idx_reference_cards_document_id ON reference_cards(document_id);
CREATE INDEX IF NOT EXISTS idx_reference_cards_category ON reference_cards(category);
CREATE INDEX IF NOT EXISTS idx_reference_cards_status ON reference_cards(status);

CREATE TABLE IF NOT EXISTS synthesis_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES source_roots(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    note_type TEXT NOT NULL,
    body TEXT NOT NULL,
    source_document_ids TEXT NOT NULL,
    source_chunk_ids TEXT NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT 'rule-v1',
    model TEXT NOT NULL DEFAULT 'none',
    status TEXT NOT NULL DEFAULT 'suggested',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, note_type, title)
);

CREATE INDEX IF NOT EXISTS idx_synthesis_notes_source_id ON synthesis_notes(source_id);
CREATE INDEX IF NOT EXISTS idx_synthesis_notes_type ON synthesis_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_synthesis_notes_status ON synthesis_notes(status);

CREATE TABLE IF NOT EXISTS ask_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    model TEXT NOT NULL DEFAULT 'none',
    prompt_version TEXT NOT NULL DEFAULT 'ask-v1',
    status TEXT NOT NULL DEFAULT 'answered',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ask_records_created_at ON ask_records(created_at);
CREATE INDEX IF NOT EXISTS idx_ask_records_status ON ask_records(status);

CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id INTEGER REFERENCES chunks(id) ON DELETE CASCADE,
    fact_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    unit TEXT,
    event_date TEXT,
    confidence REAL NOT NULL,
    extractor TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'proposed',
    source_text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chunk_id, fact_type, subject, predicate, normalized_value, event_date)
);

CREATE INDEX IF NOT EXISTS idx_facts_document_id ON facts(document_id);
CREATE INDEX IF NOT EXISTS idx_facts_chunk_id ON facts(chunk_id);
CREATE INDEX IF NOT EXISTS idx_facts_subject_predicate ON facts(subject, predicate);
CREATE INDEX IF NOT EXISTS idx_facts_type ON facts(fact_type);
CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);

CREATE TABLE IF NOT EXISTS fact_build_state (
    document_id INTEGER PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    extractor_version TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    source_document_ids TEXT NOT NULL,
    source_chunk_ids TEXT NOT NULL,
    source_fact_ids TEXT NOT NULL,
    generator TEXT NOT NULL DEFAULT 'rule-v1',
    status TEXT NOT NULL DEFAULT 'generated',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_knowledge_pages_topic ON knowledge_pages(topic);
CREATE INDEX IF NOT EXISTS idx_knowledge_pages_status ON knowledge_pages(status);

CREATE TABLE IF NOT EXISTS knowledge_page_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_page_id INTEGER NOT NULL REFERENCES knowledge_pages(id) ON DELETE CASCADE,
    target_page_id INTEGER NOT NULL REFERENCES knowledge_pages(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    score REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_page_id, target_page_id, relation_type)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_page_links_source ON knowledge_page_links(source_page_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_page_links_target ON knowledge_page_links(target_page_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_page_links_type ON knowledge_page_links(relation_type);
"""


def resolve_db_path(path: str | Path | None = None) -> Path:
    db_path = Path(path) if path else DEFAULT_DB_PATH
    return db_path.expanduser().resolve()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = resolve_db_path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | Path | None = None) -> Path:
    db_path = resolve_db_path(path)
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    return db_path
