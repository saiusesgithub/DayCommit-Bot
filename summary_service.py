from datetime import datetime

from database import get_connection
from timezone_utils import LOCAL_TZ


def _today() -> str:
    return datetime.now(LOCAL_TZ).date().isoformat()


def save_summary(user_id: int, summary_text: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_summaries (telegram_user_id, summary_date, summary_text, created_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT (telegram_user_id, summary_date)
            DO UPDATE SET summary_text = excluded.summary_text,
                          created_at   = excluded.created_at
            """,
            (user_id, _today(), summary_text),
        )
        conn.commit()


def get_today_summary(user_id: int) -> str | None:
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT summary_text FROM daily_summaries "
            "WHERE telegram_user_id = ? AND summary_date = ?",
            (user_id, _today()),
        )
        row = cursor.fetchone()
        return row["summary_text"] if row else None
