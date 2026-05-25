from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import TIMEZONE

LOCAL_TZ = ZoneInfo(TIMEZONE)


def utc_to_local(utc_str: str) -> datetime:
    """Convert a UTC datetime string from SQLite ('YYYY-MM-DD HH:MM:SS') to a
    timezone-aware datetime in the configured local timezone."""
    dt_utc = datetime.fromisoformat(utc_str).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ)
