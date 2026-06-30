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
