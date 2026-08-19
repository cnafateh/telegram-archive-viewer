import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DATABASE_PATH = os.getenv("DATABASE_PATH", "/archive/data/archive.db")

def connect(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or DATABASE_PATH
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

@contextmanager
def db(db_path: str | None = None):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        source_file TEXT NOT NULL,
        sender TEXT,
        sent_at TEXT,
        date_label TEXT,
        text TEXT,
        html_text TEXT,
        reply_to INTEGER,
        forwarded_from TEXT,
        media_type TEXT,
        media_path TEXT,
        media_thumb TEXT,
        media_title TEXT,
        media_status TEXT,
        reactions_json TEXT,
        is_service INTEGER NOT NULL DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);
    CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender);
    CREATE INDEX IF NOT EXISTS idx_messages_reply_to ON messages(reply_to);

    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """)

    # FTS5 is available in normal Python/SQLite builds. We keep the app usable even if not.
    try:
        conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            text,
            sender,
            media_title,
            content='messages',
            content_rowid='id',
            tokenize='unicode61'
        )
        """)
        conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
          INSERT INTO messages_fts(rowid, text, sender, media_title)
          VALUES (new.id, new.text, new.sender, new.media_title);
        END;
        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
          INSERT INTO messages_fts(messages_fts, rowid, text, sender, media_title)
          VALUES('delete', old.id, old.text, old.sender, old.media_title);
        END;
        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
          INSERT INTO messages_fts(messages_fts, rowid, text, sender, media_title)
          VALUES('delete', old.id, old.text, old.sender, old.media_title);
          INSERT INTO messages_fts(rowid, text, sender, media_title)
          VALUES (new.id, new.text, new.sender, new.media_title);
        END;
        """)
    except sqlite3.OperationalError:
        pass

    conn.commit()

def has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='messages_fts'"
    ).fetchone()
    return bool(row)
