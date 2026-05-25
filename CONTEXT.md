# DayCommit — Project Context for AI Assistants

> Keep this file updated whenever the project changes. It is the single source
> of truth for any AI assistant or new developer picking up this codebase.

---

## What is DayCommit?

A personal Telegram bot that acts as a developer journal. The user sends plain
text messages throughout the day; the bot stores them as timestamped log entries
grouped by date. Think of it as a frictionless "git commit message for your day".

---

## Current Status: MVP (v0.1)

The bot is fully functional and runnable locally. No AI, no GitHub integration
yet — that is intentional for this phase.

---

## Tech Stack

| Layer        | Technology                            | Version  |
|--------------|---------------------------------------|----------|
| Language     | Python                                | 3.13     |
| Bot framework| python-telegram-bot (async, PTBv20+)  | 22.7     |
| Database     | SQLite (stdlib `sqlite3`)             | —        |
| Config       | python-dotenv                         | 1.0.1    |
| Runtime      | Local polling (no webhook)            | —        |

---

## File Structure

```
DayCommit-Bot/
├── main.py            — entry point; calls init_db() then app.run_polling()
├── bot.py             — all async Telegram handlers + build_application()
├── journal_service.py — business logic: add / get / delete entries
├── database.py        — SQLite init, schema creation, connection context manager
├── config.py          — loads .env; exposes TOKEN (str) and DB_PATH (str)
├── requirements.txt   — pinned dependencies
├── .env               — secrets (gitignored); copy from .env.example
├── .env.example       — template for .env
├── daycommit.db       — SQLite database file (auto-created on first run)
└── CLAUDE.md          — this file
```

---

## Database Schema

```sql
CREATE TABLE journal_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,       -- Telegram user ID (int64)
    message_text     TEXT    NOT NULL,       -- raw message the user sent
    entry_date       TEXT    NOT NULL,       -- YYYY-MM-DD (date of logging)
    created_at       TEXT    NOT NULL        -- UTC datetime, e.g. "2026-05-25 09:30:00"
);

CREATE INDEX idx_user_date ON journal_entries (telegram_user_id, entry_date);
```

**Notes:**
- `entry_date` is always today's date at time of insert (not editable).
- `created_at` is set via SQLite `datetime('now')` — always UTC.
- Times displayed to the user are UTC. Timezone support is a future concern.
- Multi-user safe: every query filters by `telegram_user_id`.

---

## Bot Commands

| Command        | Handler function  | Behaviour                                              |
|----------------|-------------------|--------------------------------------------------------|
| `/start`       | `cmd_start`       | Welcome message                                        |
| `/help`        | `cmd_help`        | Show command list                                      |
| `/today`       | `cmd_today`       | List all entries for today, numbered with [HH:MM]      |
| `/yesterday`   | `cmd_yesterday`   | List all entries for yesterday, numbered with [HH:MM]  |
| `/delete_last` | `cmd_delete_last` | Delete the single most recent entry (any date)         |
| *(any text)*   | `handle_message`  | Save as a new journal entry; reply "Logged."           |

**Error handling rule:** if a DB write fails, log the exception server-side and
reply with a human-readable error message. Never silently swallow errors.

---

## Key Design Decisions

1. **Polling, not webhook.** Simpler for local dev and MVP. Switch to webhook
   when deploying to a server.
2. **No ORM.** Raw `sqlite3` with a `contextmanager` for connections. Keeps the
   DB layer transparent and dependency-free.
3. **Separation of concerns.** `journal_service.py` has zero Telegram imports;
   `bot.py` has zero SQL. Easy to swap either layer later.
4. **`delete_last` is global** (not scoped to today). It deletes the most recent
   entry regardless of date. Change if needed.
5. **Markdown v1** used for bot replies (not MarkdownV2) to keep formatting
   simple and avoid excess escaping.

---

## Environment Variables

| Variable             | Required | Default        | Description              |
|----------------------|----------|----------------|--------------------------|
| `TELEGRAM_BOT_TOKEN` | Yes      | —              | From @BotFather           |
| `DB_PATH`            | No       | `daycommit.db` | Path to SQLite DB file   |

---

## How to Run Locally

```powershell
# 1. Install deps
pip install -r requirements.txt

# 2. Set up .env
copy .env.example .env
# Edit .env and paste your bot token

# 3. Start
python main.py
```

---

## What Is NOT Implemented Yet (Roadmap)

- [ ] AI summarisation of daily logs (Claude API)
- [ ] GitHub integration (auto-commit logs to a repo)
- [ ] Timezone support (currently all UTC)
- [ ] `/history` — browse logs by date
- [ ] `/week` — summary of the last 7 days
- [ ] Webhook mode for production deployment
- [ ] `/export` — export logs as markdown or JSON
- [ ] `/search` — full-text search across all entries
- [ ] Docker / deployment config

---

## Known Issues / Past Bugs Fixed

| Date       | Issue                                                                | Fix                                      |
|------------|----------------------------------------------------------------------|------------------------------------------|
| 2026-05-25 | `python-telegram-bot==21.3` crashes on Python 3.13 (`__slots__` bug) | Upgraded to 22.7                        |
| 2026-05-25 | `SyntaxWarning` from `\_` escape in HELP_TEXT string                 | Removed backslash (Markdown v1, not v2) |
