import sqlite3
from contextlib import contextmanager
from config import DB_PATH


def init_db() -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                message_text  TEXT    NOT NULL,
                entry_date    TEXT    NOT NULL,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_date "
            "ON journal_entries (telegram_user_id, entry_date)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_summaries (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                summary_date     TEXT    NOT NULL,
                summary_text     TEXT    NOT NULL,
                created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_user_summary_date "
            "ON daily_summaries (telegram_user_id, summary_date)"
        )
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
