from datetime import date, timedelta
from database import get_connection


def add_entry(user_id: int, text: str) -> int:
    today = date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO journal_entries (telegram_user_id, message_text, entry_date, created_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (user_id, text, today),
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
    return get_entries_for_date(user_id, date.today().isoformat())


def get_yesterday_entries(user_id: int) -> list:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return get_entries_for_date(user_id, yesterday)


def delete_last_entry(user_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM journal_entries "
            "WHERE telegram_user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM journal_entries WHERE id = ?", (row["id"],))
        conn.commit()
        return True
