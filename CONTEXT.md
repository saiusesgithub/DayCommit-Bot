# DayCommit — Project Context for AI Assistants

> Keep this file updated whenever the project changes. It is the single source
> of truth for any AI assistant or new developer picking up this codebase.

---

## What is DayCommit?

A personal Telegram bot that acts as a developer journal. The user sends plain
text messages throughout the day; the bot stores them as timestamped log entries
grouped by date. At end of day, `/summary` calls an AI model to generate a
structured Markdown summary. `/preview` assembles the full Daily DevLog document.
`/push` publishes that DevLog to a configured GitHub repository.

---

## Current Status: MVP (v0.5)

- Journal logging, viewing, and deleting: done
- Timezone-aware dates and display: done
- AI summary (`/summary`) with OpenRouter primary, then Groq and Gemini fallbacks: done
- Full DevLog preview (`/preview`): done
- GitHub push (`/push`) via GitHub REST API: done
- Export and search: not yet implemented

---

## Tech Stack

| Layer         | Technology                            | Version  |
|---------------|---------------------------------------|----------|
| Language      | Python                                | 3.13     |
| Bot framework | python-telegram-bot (async, PTBv20+)  | 22.7     |
| Database      | SQLite (stdlib `sqlite3`)             | —        |
| Config        | python-dotenv                         | 1.0.1    |
| Timezones     | `zoneinfo` (stdlib) + `tzdata`        | 2025.2   |
| AI (primary)  | OpenRouter OpenAI-compatible chat API via `httpx` | 0.28.1 |
| AI (fallback) | Groq (llama-3.3-70b-versatile) via `groq` | 1.2.0 |
| AI (fallback) | Google Gemini via `google-generativeai` | 0.8.6 |
| GitHub API    | `httpx` async HTTP client             | 0.28.1   |
| Runtime       | Local polling (no webhook)            | —        |

---

## File Structure

```
DayCommit-Bot/
├── main.py            — entry point; calls init_db() then app.run_polling()
├── bot.py             — all async Telegram handlers + build_application()
├── journal_service.py — business logic: add / get / delete journal entries
├── summary_service.py — business logic: save / get AI summaries
├── devlog.py          — shared Daily DevLog formatting + markdown builder
├── github_service.py  — GitHub REST API push/update logic + push audit storage
├── backup_service.py  — manual SQLite backup creation
├── ai_service.py      — OpenRouter, Groq, Gemini provider fallback logic
├── prompts/
│   └── daily_summary_template.md — editable /summary prompt template
├── database.py        — SQLite init, table schemas, connection context manager
├── config.py          — loads .env; exposes all config constants
├── timezone_utils.py  — LOCAL_TZ (ZoneInfo) + utc_to_local() helper
├── requirements.txt   — pinned dependencies
├── Procfile           — Railway worker process: python main.py
├── README.md          — local run and Railway deployment notes
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

CREATE TABLE github_pushes (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    entry_date       TEXT    NOT NULL,   -- YYYY-MM-DD in LOCAL timezone
    file_path        TEXT    NOT NULL,   -- repo-relative markdown path
    commit_sha       TEXT    NOT NULL,
    pushed_at        TEXT    NOT NULL    -- UTC "YYYY-MM-DD HH:MM:SS"
);
CREATE UNIQUE INDEX idx_user_push_date ON github_pushes (telegram_user_id, entry_date);

CREATE TABLE undo_actions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_user_id INTEGER NOT NULL,
    action_type      TEXT    NOT NULL,
    entry_id         INTEGER,
    message_text     TEXT,
    entry_date       TEXT,
    created_at       TEXT    NOT NULL,
    is_used          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_user_undo_latest ON undo_actions (telegram_user_id, is_used, created_at);
```

**Notes:**
- `created_at` is always UTC via SQLite `datetime('now')`. Never touched after insert.
- `entry_date` / `summary_date` use the user's local date (configured `TIMEZONE`). This matters around midnight.
- `daily_summaries` has a UNIQUE index — calling `/summary` again on the same day upserts (overwrites) via `ON CONFLICT DO UPDATE`.
- `github_pushes` has a UNIQUE index by user/date — pushing the same day again updates the recorded path, commit SHA, and timestamp.
- `undo_actions` records the latest journal add/delete operations so `/undo` survives process restarts. It does not affect summaries or GitHub pushes.
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
       ├── try: _openrouter_summary() ← OPENROUTER_MODEL, default openai/gpt-4o-mini
       │         if any exception ↓
       ├── try: _groq_summary()       ← GROQ_MODEL, default llama-3.3-70b-versatile
       │         if any exception ↓
       └── try: _gemini_summary()     ← GEMINI_MODEL, default gemini-3.5-flash
       │
       ▼
summary_service.save_summary()    ← upsert into daily_summaries
       │
       ▼
bot sends summary text to user
```

- Both AI clients are lazy-initialized (only created on first `/summary` call).
- Model names are configurable via `.env` so provider deprecations do not require code edits.
- Summary style is configurable by editing `prompts/daily_summary_template.md`.
- The template must contain `{{DIARY_TEXT}}`; `ai_service.py` replaces it with combined journal entries at runtime.
- If the template file is missing or does not contain the placeholder, `ai_service.py` falls back to a built-in safe prompt.
- If a provider fails, the next provider takes over silently — user just gets their summary.
- Provider failure logs include only provider name and a sanitized error string, never API keys or full request URLs.
- If all providers fail, the exception bubbles up and the bot replies with a clear error message.
- `google-generativeai` shows a FutureWarning about deprecation; it is suppressed via `warnings.catch_warnings()`. Migrate to `google-genai` SDK when ready.

---

## GitHub Push Architecture

```
/push command
       │
       ▼
bot.cmd_push
  get today's journal entries
  get today's saved AI summary
  require entries + saved summary
       │
       ▼
devlog.build_markdown()           ← same final Markdown as /preview
       │
       ▼
github_service.push_devlog()
  path = YYYY/MM-Month/YYYY-MM-DD.md
  GET /repos/{owner}/{repo}/contents/{path}?ref={branch}
  PUT /repos/{owner}/{repo}/contents/{path}
       │
       ▼
record commit SHA in github_pushes after successful API response
```

- GitHub config comes from `.env`: `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_BRANCH`.
- `GITHUB_BRANCH` defaults to `main`.
- File path example: `2026/05-May/2026-05-25.md`.
- Commit message is `Add devlog for YYYY-MM-DD` for new files and `Update devlog for YYYY-MM-DD` for existing files.
- Existing files are detected first; updates include the current GitHub file `sha`.
- Content is sent as base64, per GitHub Contents API requirements.
- The bot only writes to `github_pushes` after GitHub returns success. Journal entries and summaries are never modified by `/push`.
- Known GitHub config/auth/permission failures are converted to clear user-facing messages.

---

## Bot Commands

| Command        | Handler          | Behaviour                                                          |
|----------------|------------------|--------------------------------------------------------------------|
| `/start`       | `cmd_start`      | Welcome message                                                    |
| `/help`        | `cmd_help`       | Show all commands                                                  |
| `/today`       | `cmd_today`      | Send today's raw logs as `raw_journal_YYYY-MM-DD.md`               |
| `/status`      | `cmd_status`     | Show logs, summary, push state, last push, and streak for today    |
| `/history`     | `cmd_history`    | Send raw logs for a given date as `raw_journal_YYYY-MM-DD.md`      |
| `/week`        | `cmd_week`       | Generate a send-only weekly AI review for the last 7 local dates   |
| `/yesterday`   | `cmd_yesterday`  | Send yesterday's raw logs as `raw_journal_YYYY-MM-DD.md`           |
| `/summary`     | `cmd_summary`    | Generate AI summary of today's logs; stores in DB; sends to user  |
| `/regenerate`  | `cmd_regenerate` | Regenerate and overwrite today's AI summary                        |
| `/edit_summary`| `cmd_edit_summary`| Start manual edit flow for today's saved summary                  |
| `/preview`     | `cmd_preview`    | Send full Daily DevLog markdown as `devlog_YYYY-MM-DD.md`          |
| `/push`        | `cmd_push`       | Push today's saved-summary DevLog to GitHub                        |
| `/backup`      | `cmd_backup`     | Create a manual SQLite backup                                      |
| `/delete_last` | `cmd_delete_last`| Delete most recent entry; echoes the deleted text                  |
| `/undo`        | `cmd_undo`       | Undo latest journal add/delete action                              |
| `/cancel`      | `cmd_cancel`     | Cancel summary editing mode                                       |
| *(any text)*   | `handle_message` | Save as journal entry; reply "Logged."                             |

Telegram's slash-command menu is registered on startup via `set_my_commands()` in the application `post_init` hook. If registration fails, the bot logs a warning and continues polling.

Manual summary editing uses in-memory per-user state in `bot.py`. While a user is awaiting an edited summary, their next normal text message is saved through `summary_service.save_summary()` instead of being logged as a journal entry. `/cancel` clears that state.

Daily reminders use python-telegram-bot `JobQueue`. At 23:00 in the configured `TIMEZONE`, the bot sends `Want to finish today's DevLog? /summary /preview /push` only to users who have at least one journal entry for the current local date.

Manual backups use SQLite's `.backup()` API and write files named `daycommit_YYYY-MM-DD_HH-MM-SS.db` into `BACKUP_DIR`, which defaults to `daycommit-backups`.

Weekly reviews use the existing AI provider fallback system directly with a weekly prompt. Reviews are send-only for now and are not stored in SQLite.

Undo is intentionally scoped to journal add/delete actions only. It does not roll back summaries, GitHub pushes, backups, or AI generations.

### /preview output format

`/preview` requires both today's journal entries and a saved AI summary. It builds the final document with `devlog.build_markdown()` and sends it as `devlog_YYYY-MM-DD.md` instead of a large Telegram text message.

```
# Daily DevLog — YYYY-MM-DD

## AI Summary

**One-line summary:** ...

### Detailed Summary
...

### Timeline / Time Allocation / Wins / Wasted Time / Improvements / Tags
...

---

## Rough Journal (Raw Logs)

1.
first log

2.
second log

3.
multiline log title
continuation line
```

Long `/summary`, `/regenerate`, and `/edit_summary` summary text is sent as `summary_YYYY-MM-DD.md` when it exceeds 3500 characters. Raw diary output is sent as plain text, never parsed as Telegram Markdown.

`/today`, `/yesterday`, and `/history` send raw journal exports as `.md` documents to avoid Telegram message length limits. These exports use `# Raw Journal — YYYY-MM-DD` and append stored `message_text` values directly in original order.

---

## Key Design Decisions

1. **Polling, not webhook.** Simpler for local dev. Switch to webhook for production.
2. **No ORM.** Raw `sqlite3` with a `contextmanager`. Transparent and dependency-free.
3. **Separation of concerns.** `journal_service` and `summary_service` have zero Telegram imports. `bot.py` has zero SQL.
4. **`delete_last` is global** (not scoped to today). Deletes the single most recent entry regardless of date.
5. **No `parse_mode` on diary output.** User text may contain `*`, `_`, `` ` `` which break Markdown parsing. Only `/help` and `/start` use `parse_mode="Markdown"`.
6. **`TIMEZONE` is the single source of truth.** Change it in `.env` to relocate the bot. `LOCAL_TZ` is built once in `timezone_utils.py` and imported everywhere.
7. **AI fallback is silent.** The user never sees provider fallback details — they just get a summary. Sanitized failures are logged server-side only.
8. **Preview and push share one markdown builder.** `devlog.build_markdown()` is the source of truth for final Daily DevLog output.
9. **GitHub logic stays outside `bot.py`.** The Telegram handler only validates local prerequisites, builds markdown, calls `github_service`, and formats the reply.
10. **Summary edit state is in-memory.** If the process restarts during `/edit_summary`, the user must run `/edit_summary` again.
11. **Raw logs never pass through AI in final DevLogs.** AI generates only the summary. `devlog.build_markdown()` appends raw `journal_entries.message_text` from SQLite directly under `# Rough Journal (Raw Logs)`.

---

## Environment Variables

| Variable             | Required | Default         | Description                                    |
|----------------------|----------|-----------------|------------------------------------------------|
| `TELEGRAM_BOT_TOKEN` | Yes      | —               | From @BotFather                                |
| `OPENROUTER_API_KEY` | Yes*     | —               | OpenRouter primary AI provider                 |
| `OPENROUTER_MODEL`   | No       | `openai/gpt-4o-mini` | OpenRouter model used by `/summary`       |
| `GROQ_API_KEY`       | Yes*     | —               | Groq fallback AI provider                      |
| `GEMINI_MODEL`       | No       | `gemini-3.5-flash` | Gemini model used by `/summary`             |
| `GROQ_MODEL`         | No       | `llama-3.3-70b-versatile` | Groq fallback model used by `/summary` |
| `GEMINI_API_KEY`     | Yes*     | —               | Google AI Studio fallback AI provider          |
| `GITHUB_TOKEN`       | Yes**    | —               | GitHub token with repo contents write access   |
| `GITHUB_OWNER`       | Yes**    | —               | GitHub username or organization                |
| `GITHUB_REPO`        | Yes**    | —               | Repository name                                |
| `GITHUB_BRANCH`      | No       | `main`          | Branch to create/update DevLog files on        |
| `DB_PATH`            | No       | `daycommit.db`  | Path to SQLite DB file                         |
| `BACKUP_DIR`         | No       | `daycommit-backups` | Directory for manual SQLite backups       |
| `TIMEZONE`           | No       | `Asia/Kolkata`  | IANA timezone name for display and dates       |

\* At least one of `OPENROUTER_API_KEY`, `GROQ_API_KEY`, or `GEMINI_API_KEY` must be set to use `/summary`.
\** Required only for `/push`.

---

## Railway Deployment

- Deployment uses polling mode, not webhooks.
- `main.py` is the entrypoint and must run with `python main.py`.
- `Procfile` defines the Railway worker process: `worker: python main.py`.
- Use a Railway volume mounted at `/data`.
- Recommended Railway database path: `DB_PATH=/data/daycommit.db`.
- Keep `.env` and SQLite database files out of git; `.gitignore` excludes `.env`, `*.db`, `*.sqlite`, `*.sqlite3`, and `data/`.
- Manual backups go to `BACKUP_DIR`; `daycommit-backups/` is ignored by git.

---

## How to Run Locally

```powershell
# 1. Install deps
pip install -r requirements.txt

# 2. Set up .env
copy .env.example .env
# Edit .env — fill in bot token, API keys, and optional GitHub settings

# 3. Start
python main.py
```

---

## What Is NOT Implemented Yet (Roadmap)

- [x] GitHub integration — push daily DevLog as a markdown file commit
- [x] `/history` — view logs for an arbitrary past date
- [x] `/week` — AI summary of the past 7 days
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
| 2026-05-25 | `/summary` failed because `gemini-1.5-flash` was unavailable and old Groq SDK crashed with `httpx 0.28` | Added configurable model names, defaulted to current Gemini/Groq models, and upgraded `groq` to 1.2.0 |
| 2026-05-25 | AI fallback was hardcoded around Gemini first, then Groq | Refactored `ai_service.py` into OpenRouter → Groq → Gemini provider fallback with sanitized provider logs |
| 2026-05-25 | `/summary` prompt was hardcoded in `ai_service.py` | Moved editable prompt style to `prompts/daily_summary_template.md` with `{{DIARY_TEXT}}` runtime replacement |
| 2026-05-25 | Telegram slash-command menu was not populated | Added startup `set_my_commands()` registration and cleaner `/help` text |
| 2026-05-25 | Saved AI summaries could not be manually edited or regenerated explicitly | Added `/edit_summary`, `/regenerate`, and `/cancel` with in-memory edit state |
| 2026-05-25 | No quick state check, historical date view, manual backup, or close-of-day reminder | Added `/status`, `/history`, `/backup`, and a 23:00 local JobQueue reminder |
| 2026-05-25 | No weekly review or persistent undo for journal edits | Added `/week` and `/undo` backed by `undo_actions` |
| 2026-05-25 | Large previews and summaries could hit Telegram message length limits | `/preview` now sends a `.md` file; long summaries/edit summaries are sent as files |
| 2026-05-25 | Final raw journal section used a formatter that trimmed and indented user messages | Added raw-log final formatter so final DevLogs append exact stored messages under `# Rough Journal (Raw Logs)` |
| 2026-05-25 | Long `/today` responses could exceed Telegram message limits | `/today`, `/yesterday`, and `/history` now send raw journal `.md` files |
