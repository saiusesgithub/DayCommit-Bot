import sqlite3
from datetime import datetime
from pathlib import Path

from config import BACKUP_DIR, DB_PATH
from timezone_utils import LOCAL_TZ


def create_backup() -> Path:
    backup_dir = Path(BACKUP_DIR).expanduser()
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d_%H-%M-%S")
    backup_path = backup_dir / f"daycommit_{timestamp}.db"

    source = sqlite3.connect(DB_PATH)
    try:
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    return backup_path
