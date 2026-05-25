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
        entry_id = cursor.lastrowid
        conn.execute(
            """
            INSERT INTO undo_actions
                (telegram_user_id, action_type, entry_id, message_text, entry_date, created_at)
            VALUES (?, 'add_entry', ?, ?, ?, datetime('now'))
            """,
            (user_id, entry_id, text, entry_date),
        )
        conn.commit()
        return entry_id


def get_entries_for_date(user_id: int, target_date: str) -> list:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM journal_entries "
            "WHERE telegram_user_id = ? AND entry_date = ? "
            "ORDER BY created_at ASC",
            (user_id, target_date),
        )
        return cursor.fetchall()


def count_entries_for_date(user_id: int, target_date: str) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) AS count FROM journal_entries "
            "WHERE telegram_user_id = ? AND entry_date = ?",
            (user_id, target_date),
        )
        row = cursor.fetchone()
        return int(row["count"])


def get_user_ids_with_entries_for_date(target_date: str) -> list[int]:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT telegram_user_id FROM journal_entries "
            "WHERE entry_date = ?",
            (target_date,),
        )
        return [int(row["telegram_user_id"]) for row in cursor.fetchall()]


def calculate_streak(user_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT DISTINCT entry_date FROM journal_entries "
            "WHERE telegram_user_id = ?",
            (user_id,),
        )
        logged_dates = {row["entry_date"] for row in cursor.fetchall()}

    streak = 0
    current = datetime.now(LOCAL_TZ).date()
    while current.isoformat() in logged_dates:
        streak += 1
        current -= timedelta(days=1)
    return streak


def get_today_entries(user_id: int) -> list:
    return get_entries_for_date(user_id, _local_date())


def get_yesterday_entries(user_id: int) -> list:
    return get_entries_for_date(user_id, _local_date(offset_days=-1))


def delete_last_entry(user_id: int) -> str | None:
    """Delete the most recent entry and return its message_text, or None if none exist."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM journal_entries "
            "WHERE telegram_user_id = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        conn.execute(
            """
            INSERT INTO undo_actions
                (telegram_user_id, action_type, entry_id, message_text, entry_date, created_at)
            VALUES (?, 'delete_entry', ?, ?, ?, datetime('now'))
            """,
            (user_id, row["id"], row["message_text"], row["entry_date"]),
        )
        conn.execute("DELETE FROM journal_entries WHERE id = ?", (row["id"],))
        conn.commit()
        return row["message_text"]


def undo_last_action(user_id: int) -> str | None:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM undo_actions "
            "WHERE telegram_user_id = ? AND is_used = 0 "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (user_id,),
        )
        action = cursor.fetchone()
        if not action:
            return None

        if action["action_type"] == "add_entry":
            conn.execute(
                "DELETE FROM journal_entries "
                "WHERE id = ? AND telegram_user_id = ?",
                (action["entry_id"], user_id),
            )
            reply = "Undid last added log ✅"
        elif action["action_type"] == "delete_entry":
            conn.execute(
                "INSERT INTO journal_entries (telegram_user_id, message_text, entry_date, created_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                (user_id, action["message_text"], action["entry_date"]),
            )
            reply = "Restored deleted log ✅"
        else:
            reply = None

        conn.execute(
            "UPDATE undo_actions SET is_used = 1 WHERE id = ?",
            (action["id"],),
        )
        conn.commit()
        return reply
