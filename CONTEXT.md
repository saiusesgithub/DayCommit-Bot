# DayCommit — Project Context for AI Assistants

> Keep this file updated whenever the project changes. It is the single source
> of truth for any AI assistant or new developer picking up this codebase.

---

## What is DayCommit?

A personal Telegram bot that acts as a developer journal. The user sends plain
text messages throughout the day; the bot stores them as timestamped log entries
grouped by date. At end of day, `/summary` calls an AI model to generate a
structured Markdown summary. `/preview` assembles the full Daily DevLog document.

---

## Current Status: MVP (v0.4)

- Journal logging, viewing, and deleting: done
- Timezone-aware dates and display: done
- AI summary (`/summary`) with Gemini primary + Groq fallback: done
- Full DevLog preview (`/preview`): done
- GitHub push, export, search: not yet implemented

---

## Tech Stack

| Layer         | Technology                            | Version  |
|---------------|---------------------------------------|----------|
| Language      | Python                                | 3.13     |
| Bot framework | python-telegram-bot (async, PTBv20+)  | 22.7     |
| Database      | SQLite (stdlib `sqlite3`)             | —        |
| Config        | python-dotenv                         | 1.0.1    |
| Timezones     | `zoneinfo` (stdlib) + `tzdata`        | 2025.2   |
| AI (primary)  | Google Gemini via `google-generativeai` | 0.8.6  |
| AI (fallback) | Groq (llama3-70b-8192) via `groq`    | 0.9.0    |
| Runtime       | Local polling (no webhook)            | —        |

---

## File Structure

```
DayCommit-Bot/
├── main.py            — entry point; calls init_db() then app.run_polling()
├── bot.py             — all async Telegram handlers + build_application()
├── journal_service.py — business logic: add / get / delete journal entries
├── summary_service.py — business logic: save / get AI summaries
├── ai_service.py      — Gemini + Groq AI calls; fallback logic
├── database.py        — SQLite init, both table schemas, connection context manager
├── config.py          — loads .env; exposes all config constants
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
    telegram_user_id INTEGER NOT NULL,
    message_text     TEXT    NOT NULL,
    entry_date       TEXT    NOT NULL,   -- YYYY-MM-DD in LOCAL timezone
    created_at       TEXT    NOT NULL    -- UTC "YYYY-MM-DD HH:MM:SS"
);
CREATE INDEX idx_user_date ON journal_entries (telegram_user_id, entry_date);

CREATE TABLE daily_summaries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    summary_date     TEXT    NOT NULL,   -- YYYY-MM-DD in LOCAL timezone
    summary_text     TEXT    NOT NULL,   -- full Markdown from AI
    created_at       TEXT    NOT NULL    -- UTC "YYYY-MM-DD HH:MM:SS"
);
CREATE UNIQUE INDEX idx_user_summary_date ON daily_summaries (telegram_user_id, summary_date);
```

**Notes:**
- `created_at` is always UTC via SQLite `datetime('now')`. Never touched after insert.
- `entry_date` / `summary_date` use the user's local date (configured `TIMEZONE`). This matters around midnight.
- `daily_summaries` has a UNIQUE index — calling `/summary` again on the same day upserts (overwrites) via `ON CONFLICT DO UPDATE`.
- Multi-user safe: every query filters by `telegram_user_id`.

---

## Timezone Architecture

```
User sends message
       │
       ▼
journal_service.add_entry()
  entry_date  = _local_date()     ← datetime.now(LOCAL_TZ).date()  [local]
  created_at  = datetime('now')   ← SQLite UTC                      [UTC]
       │
       ▼
bot.cmd_today / cmd_yesterday
  timestamps no longer displayed  ← clean numbered list only
```

**Rule:** store UTC, display local. `entry_date` is always the user's local date.

**Why `tzdata`?** Windows has no IANA timezone database. `zoneinfo` reads from it.
Without `tzdata`, `ZoneInfo("Asia/Kolkata")` raises `ZoneInfoNotFoundError` on Windows.

---

## AI Summary Architecture

```
/summary command
       │
       ▼
ai_service.generate_summary(entries_text)
       │
       ├── try: _gemini_summary()   ← gemini-1.5-flash (google-generativeai)
       │         if any exception ↓
       └── fallback: _groq_summary() ← llama3-70b-8192 (groq)
       │
       ▼
summary_service.save_summary()    ← upsert into daily_summaries
       │
       ▼
bot sends summary text to user
```

- Both AI clients are lazy-initialized (only created on first `/summary` call).
- If Gemini fails for any reason, Groq takes over silently — user just gets their summary.
- If both fail, the exception bubbles up and the bot replies with a clear error message.
- `google-generativeai` shows a FutureWarning about deprecation; it is suppressed via `warnings.catch_warnings()`. Migrate to `google-genai` SDK when ready.

---

## Bot Commands

| Command        | Handler          | Behaviour                                                          |
|----------------|------------------|--------------------------------------------------------------------|
| `/start`       | `cmd_start`      | Welcome message                                                    |
| `/help`        | `cmd_help`       | Show all commands                                                  |
| `/today`       | `cmd_today`      | Numbered list of today's entries (no timestamps)                   |
| `/yesterday`   | `cmd_yesterday`  | Numbered list of yesterday's entries                               |
| `/summary`     | `cmd_summary`    | Generate AI summary of today's logs; stores in DB; sends to user  |
| `/preview`     | `cmd_preview`    | Full Daily DevLog markdown: AI summary + raw diary                 |
| `/delete_last` | `cmd_delete_last`| Delete most recent entry; echoes the deleted text                  |
| *(any text)*   | `handle_message` | Save as journal entry; reply "Logged."                             |

### /preview output format

```
# Daily DevLog — YYYY-MM-DD

## AI Summary

**One-line summary:** ...

### Detailed Summary
...

### Timeline / Time Allocation / Wins / Wasted Time / Improvements / Tags
...

---

## Rough Diary

1. first log
2. second log
3. multiline log title
   continuation line
```

If the full preview exceeds 4000 characters, it is split into two messages (AI summary first, diary second).

---

## Key Design Decisions

1. **Polling, not webhook.** Simpler for local dev. Switch to webhook for production.
2. **No ORM.** Raw `sqlite3` with a `contextmanager`. Transparent and dependency-free.
3. **Separation of concerns.** `journal_service` and `summary_service` have zero Telegram imports. `bot.py` has zero SQL.
4. **`delete_last` is global** (not scoped to today). Deletes the single most recent entry regardless of date.
5. **No `parse_mode` on diary output.** User text may contain `*`, `_`, `` ` `` which break Markdown parsing. Only `/help` and `/start` use `parse_mode="Markdown"`.
6. **`TIMEZONE` is the single source of truth.** Change it in `.env` to relocate the bot. `LOCAL_TZ` is built once in `timezone_utils.py` and imported everywhere.
7. **AI fallback is silent.** The user never sees "Gemini failed, using Groq" — they just get a summary. Failures are logged server-side only.

---

## Environment Variables

| Variable             | Required | Default         | Description                                    |
|----------------------|----------|-----------------|------------------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Yes      | —               | From @BotFather                                |
| `GEMINI_API_KEY`     | Yes*     | —               | Google AI Studio — primary AI model            |
| `GROQ_API_KEY`       | Yes*     | —               | Groq Cloud — fallback AI if Gemini unavailable |
| `DB_PATH`            | No       | `daycommit.db`  | Path to SQLite DB file                         |
| `TIMEZONE`           | No       | `Asia/Kolkata`  | IANA timezone name for display and dates       |

\* At least one of `GEMINI_API_KEY` or `GROQ_API_KEY` must be set to use `/summary`.

---

## How to Run Locally

```powershell
# 1. Install deps
pip install -r requirements.txt

# 2. Set up .env
copy .env.example .env
# Edit .env — fill in bot token + API keys

# 3. Start
python main.py
```

---

## What Is NOT Implemented Yet (Roadmap)

- [ ] GitHub integration — push daily DevLog as a markdown file commit
- [ ] `/history` — view logs for an arbitrary past date
- [ ] `/week` — AI summary of the past 7 days
- [ ] `/export` — download today's DevLog as a `.md` file
- [ ] `/search` — full-text search across all entries
- [ ] Webhook mode for production deployment
- [ ] Docker / deployment config
- [ ] Per-user timezone setting (currently one global default)
- [ ] Migrate `google-generativeai` → `google-genai` SDK (deprecated warning)

---

## Known Issues / Past Bugs Fixed

| Date       | Issue                                                                         | Fix                                                                 |
|------------|-------------------------------------------------------------------------------|---------------------------------------------------------------------|
| 2026-05-25 | `python-telegram-bot==21.3` crashes on Python 3.13 (`__slots__` bug)         | Upgraded to 22.7                                                    |
| 2026-05-25 | `SyntaxWarning` from `\_` escape in HELP_TEXT                                 | Removed backslash (Markdown v1, not v2)                             |
| 2026-05-25 | Timestamps displayed in UTC; `entry_date` used naive machine date             | Added `timezone_utils.py`; all date/time logic is now TZ-aware     |
| 2026-05-25 | `/today`/`/yesterday` showed `[HH:MM]` clutter; no multiline indent          | `_format_entries()`: numbered, no timestamps, continuation indented |
| 2026-05-25 | `/delete_last` replied generic "deleted" with no content                      | Returns `message_text` from service and echoes it in reply          |
| 2026-05-25 | `google-generativeai` deprecated; `google-genai` failed to install on Windows | Using `google-generativeai` 0.8.6 with FutureWarning suppressed; Groq added as fallback |
