# DayCommit — Project Context for AI Assistants

> Keep this file updated whenever the project changes. It is the single source
> of truth for any AI assistant or new developer picking up this codebase.

---

## What is DayCommit?

A personal Telegram bot that acts as a developer journal. The user sends plain
text messages throughout the day; the bot stores them as timestamped log entries
grouped by date. Think of it as a frictionless "git commit message for your day".

---

## Current Status: MVP (v0.2)

The bot is fully functional and runnable locally. Timezone-aware display is
implemented (default: Asia/Kolkata). No AI, no GitHub integration yet — that is
intentional for this phase.

---

## Tech Stack

| Layer         | Technology                            | Version  |
|---------------|---------------------------------------|----------|
| Language      | Python                                | 3.13     |
| Bot framework | python-telegram-bot (async, PTBv20+)  | 22.7     |
| Database      | SQLite (stdlib `sqlite3`)             | —        |
| Config        | python-dotenv                         | 1.0.1    |
| Timezones     | `zoneinfo` (stdlib) + `tzdata`        | 2025.2   |
| Runtime       | Local polling (no webhook)            | —        |

---

## File Structure

```
DayCommit-Bot/
├── main.py            — entry point; calls init_db() then app.run_polling()
├── bot.py             — all async Telegram handlers + build_application()
├── journal_service.py — business logic: add / get / delete entries
├── database.py        — SQLite init, schema creation, connection context manager
├── config.py          — loads .env; exposes TOKEN, DB_PATH, TIMEZONE
├── timezone_utils.py  — LOCAL_TZ (ZoneInfo) + utc_to_local() helper
├── requirements.txt   — pinned dependencies
├── .env               — secrets (gitignored); copy from .env.example
├── .env.example       — template for .env
├── daycommit.db       — SQLite database file (auto-created on first run)
└── CONTEXT.md         — this file
```

---

## Database Schema

```sql
CREATE TABLE journal_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,       -- Telegram user ID (int64)
    message_text     TEXT    NOT NULL,       -- raw message the user sent
    entry_date       TEXT    NOT NULL,       -- YYYY-MM-DD in LOCAL timezone
    created_at       TEXT    NOT NULL        -- UTC datetime "YYYY-MM-DD HH:MM:SS"
);

CREATE INDEX idx_user_date ON journal_entries (telegram_user_id, entry_date);
```

**Notes:**
- `created_at` is always UTC (set by SQLite `datetime('now')`). Never touched after insert.
- `entry_date` is the user's local date (in configured `TIMEZONE`) at time of insert.
  This matters around midnight: a message sent at 23:55 IST vs 00:05 IST goes to different days.
- All times displayed to the user are converted to local timezone via `utc_to_local()`.
- Multi-user safe: every query filters by `telegram_user_id`.

---

## Timezone Architecture

```
User sends message
       │
       ▼
journal_service.add_entry()
  entry_date  = _local_date()          ← datetime.now(LOCAL_TZ).date()  [local]
  created_at  = datetime('now')        ← SQLite UTC                      [UTC]
       │
       ▼
       DB stores: entry_date=local, created_at=UTC
       │
       ▼
bot.cmd_today / cmd_yesterday
  utc_to_local(entry["created_at"])    ← converts UTC → LOCAL_TZ
  .strftime("%H:%M")                   ← displayed to user in local time
```

**Rule:** store UTC, display local. Never store local, never display UTC.

### timezone_utils.py

```python
LOCAL_TZ = ZoneInfo(TIMEZONE)          # loaded once at import time

def utc_to_local(utc_str: str) -> datetime:
    dt_utc = datetime.fromisoformat(utc_str).replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(LOCAL_TZ)
```

**Why `tzdata` package?** Windows does not ship the IANA timezone database.
Python's `zoneinfo` stdlib reads from it. Without `tzdata`, any `ZoneInfo("Asia/Kolkata")`
call raises `ZoneInfoNotFoundError` on Windows.

---

## Bot Commands

| Command        | Handler function  | Behaviour                                                    |
|----------------|-------------------|--------------------------------------------------------------|
| `/start`       | `cmd_start`       | Welcome message                                              |
| `/help`        | `cmd_help`        | Show command list                                            |
| `/today`       | `cmd_today`       | List all entries for today (local date), times in local TZ   |
| `/yesterday`   | `cmd_yesterday`   | List all entries for yesterday (local date), times in local TZ|
| `/delete_last` | `cmd_delete_last` | Delete the single most recent entry (any date)               |
| *(any text)*   | `handle_message`  | Save as a new journal entry; reply "Logged."                 |

**Error handling rule:** if a DB write fails, log the exception server-side and
reply with a human-readable error message. Never silently swallow errors.

---

## Key Design Decisions

1. **Polling, not webhook.** Simpler for local dev and MVP. Switch to webhook when deploying.
2. **No ORM.** Raw `sqlite3` with a `contextmanager`. Keeps the DB layer transparent and dependency-free.
3. **Separation of concerns.** `journal_service.py` has zero Telegram imports; `bot.py` has zero SQL.
4. **`delete_last` is global** (not scoped to today). It deletes the most recent entry regardless of date.
5. **Markdown v1** used for bot replies (not MarkdownV2) to avoid excess escaping.
6. **`TIMEZONE` is the single source of truth** for all date/time logic. Change it in `.env` to relocate the bot.
7. **`LOCAL_TZ` is imported, not reconstructed.** `timezone_utils.LOCAL_TZ` is built once at startup.
   `journal_service` and `bot` both import it from there — never call `ZoneInfo()` twice.

---

## Environment Variables

| Variable             | Required | Default         | Description                              |
|----------------------|----------|-----------------|------------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Yes      | —               | From @BotFather                          |
| `DB_PATH`            | No       | `daycommit.db`  | Path to SQLite DB file                   |
| `TIMEZONE`           | No       | `Asia/Kolkata`  | IANA timezone name for display and dates |

---

## How to Run Locally

```powershell
# 1. Install deps
pip install -r requirements.txt

# 2. Set up .env
copy .env.example .env
# Edit .env — paste your bot token; optionally set TIMEZONE

# 3. Start
python main.py
```

---

## What Is NOT Implemented Yet (Roadmap)

- [ ] AI summarisation of daily logs (Claude API)
- [ ] GitHub integration (auto-commit logs to a repo)
- [ ] `/history` — browse logs by arbitrary date
- [ ] `/week` — summary of the last 7 days
- [ ] Webhook mode for production deployment
- [ ] `/export` — export logs as markdown or JSON
- [ ] `/search` — full-text search across all entries
- [ ] Docker / deployment config
- [ ] Per-user timezone setting (currently one global default)

---

## Known Issues / Past Bugs Fixed

| Date       | Issue                                                                  | Fix                                       |
|------------|------------------------------------------------------------------------|-------------------------------------------|
| 2026-05-25 | `python-telegram-bot==21.3` crashes on Python 3.13 (`__slots__` bug)  | Upgraded to 22.7                          |
| 2026-05-25 | `SyntaxWarning` from `\_` escape in HELP_TEXT string                   | Removed backslash (Markdown v1, not v2)   |
| 2026-05-25 | All timestamps displayed in UTC; `entry_date` used machine local date  | Added `timezone_utils.py`; all date/time logic now timezone-aware |
