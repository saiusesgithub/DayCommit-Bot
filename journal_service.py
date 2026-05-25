from datetime import datetime, timedelta

from database import get_connection
from timezone_utils import LOCAL_TZ


def _local_date(offset_days: int = 0) -> str:
    """Return the current date in the configured local timezone as YYYY-MM-DD."""
    local_now = datetime.now(LOCAL_TZ)
    if offset_days:
        local_now += timedelta(days=offset_days)
    return local_now.date().isoformat()


def add_entry(user_id: int, text: str) -> int:
    entry_date = _local_date()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO journal_entries (telegram_user_id, message_text, entry_date, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (user_id, text, entry_date),
        )
        conn.commit()
        return cursor.lastrowid


def get_entries_for_date(user_id: int, target_date: str) -> list:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM journal_entries "
            "WHERE telegram_user_id = ? AND entry_date = ? "
            "ORDER BY created_at ASC",
            (user_id, target_date),
        )
        return cursor.fetchall()


def get_today_entries(user_id: int) -> list:
    return get_entries_for_date(user_id, _local_date())


def get_yesterday_entries(user_id: int) -> list:
    return get_entries_for_date(user_id, _local_date(offset_days=-1))


def delete_last_entry(user_id: int) -> str | None:
    """Delete the most recent entry and return its message_text, or None if none exist."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, message_text FROM journal_entries "
            "WHERE telegram_user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM journal_entries WHERE id = ?", (row["id"],))
        conn.commit()
        return row["message_text"]
