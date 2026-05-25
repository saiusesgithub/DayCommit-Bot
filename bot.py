import logging
from datetime import datetime, time, timedelta
from io import BytesIO

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import backup_service
import devlog
import journal_service
import ai_service
import summary_service
import github_service
from timezone_utils import LOCAL_TZ

logger = logging.getLogger(__name__)
TELEGRAM_TEXT_SAFE_LIMIT = 3500

HELP_TEXT = """
*DayCommit Commands*

/today — View today's logs
/status — View today's DevLog status
/history — View logs for a date
/week — Generate weekly review
/summary — Generate AI summary
/regenerate — Regenerate AI summary
/edit_summary — Edit saved summary
/preview — Preview final markdown
/push — Push to GitHub
/backup — Create database backup
/delete_last — Delete latest log
/undo — Undo latest log add/delete
/yesterday — View yesterday's logs
/cancel — Cancel current action
/help — Show this menu
""".strip()

AWAITING_EDITED_SUMMARY: set[int] = set()

BOT_COMMANDS = [
    BotCommand("start", "Start DayCommit"),
    BotCommand("help", "Show available commands"),
    BotCommand("today", "Show today's logs"),
    BotCommand("yesterday", "Show yesterday's logs"),
    BotCommand("status", "Show today's DevLog status"),
    BotCommand("history", "Show logs for a date"),
    BotCommand("week", "Generate weekly review"),
    BotCommand("summary", "Generate AI summary"),
    BotCommand("regenerate", "Regenerate AI summary"),
    BotCommand("edit_summary", "Edit saved summary"),
    BotCommand("preview", "Preview final Daily DevLog"),
    BotCommand("push", "Push today's DevLog to GitHub"),
    BotCommand("backup", "Create database backup"),
    BotCommand("delete_last", "Delete latest log entry"),
    BotCommand("undo", "Undo latest log add/delete"),
    BotCommand("cancel", "Cancel current action"),
]


async def register_bot_commands(app: Application) -> None:
    try:
        await app.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Telegram bot command menu registered.")
    except Exception as exc:
        logger.warning("Failed to register Telegram bot command menu: %s", exc.__class__.__name__)

    schedule_daily_reminder(app)


def schedule_daily_reminder(app: Application) -> None:
    if app.job_queue is None:
        logger.warning("Daily reminder not scheduled: JobQueue is unavailable.")
        return

    app.job_queue.run_daily(
        send_daily_reminders,
        time=time(hour=23, minute=0, tzinfo=LOCAL_TZ),
        name="daily_devlog_reminder",
    )
    logger.info("Daily DevLog reminder scheduled for 23:00 local time.")


async def send_daily_reminders(context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = datetime.now(LOCAL_TZ).date().isoformat()
    user_ids = journal_service.get_user_ids_with_entries_for_date(today_str)

    for user_id in user_ids:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Want to finish today's DevLog? /summary /preview /push",
            )
        except Exception as exc:
            logger.warning(
                "Failed to send daily reminder to user %s: %s",
                user_id,
                exc.__class__.__name__,
            )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to *DayCommit*!\n\n"
        "Send any message to log it as a journal entry.\n"
        "Use /help to see all commands.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def send_markdown_file(update: Update, filename: str, markdown_text: str) -> None:
    data = BytesIO(markdown_text.encode("utf-8"))
    data.name = filename
    await update.message.reply_document(document=data, filename=filename)


async def send_summary_result(update: Update, date_str: str, summary: str) -> None:
    if len(summary) > TELEGRAM_TEXT_SAFE_LIMIT:
        await send_markdown_file(update, f"summary_{date_str}.md", summary)
    else:
        await update.message.reply_text(summary)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if user_id in AWAITING_EDITED_SUMMARY:
        try:
            summary_service.save_summary(user_id, text)
            AWAITING_EDITED_SUMMARY.discard(user_id)
            await update.message.reply_text("Summary updated ✅")
        except Exception:
            logger.exception("Failed to update summary for user %s", user_id)
            await update.message.reply_text("Failed to update summary. Please try again.")
        return

    try:
        journal_service.add_entry(user_id, text)
        await update.message.reply_text("Logged.")
    except Exception:
        logger.exception("Failed to save entry for user %s", user_id)
        await update.message.reply_text("Failed to save your log. Please try again.")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_today_entries(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}) yet.")
        return

    raw_journal = devlog.build_raw_journal_markdown(today_str, entries)
    await send_markdown_file(update, f"raw_journal_{today_str}.md", raw_journal)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today_str = datetime.now(LOCAL_TZ).date().isoformat()

    log_count = journal_service.count_entries_for_date(user_id, today_str)
    has_summary = summary_service.summary_exists(user_id, today_str)
    push = github_service.get_push_for_date(user_id, today_str)
    streak = journal_service.calculate_streak(user_id)

    await update.message.reply_text(
        f"Logs: {log_count}\n"
        f"Summary: {'Generated' if has_summary else 'Not generated'}\n"
        f"GitHub: {'Pushed' if push else 'Not pushed'}\n"
        f"Last push: {push['pushed_at'] if push else '—'}\n"
        f"Streak: {streak} {'day' if streak == 1 else 'days'}"
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Usage: /history 2026-05-24")
        return

    date_arg = context.args[0]
    try:
        parsed_date = datetime.strptime(date_arg, "%Y-%m-%d").date()
    except ValueError:
        await update.message.reply_text(
            "Invalid date. Use YYYY-MM-DD, for example: /history 2026-05-24"
        )
        return

    if parsed_date.isoformat() != date_arg:
        await update.message.reply_text(
            "Invalid date. Use YYYY-MM-DD, for example: /history 2026-05-24"
        )
        return

    entries = journal_service.get_entries_for_date(user_id, date_arg)
    if not entries:
        await update.message.reply_text(f"No logs found for {date_arg}.")
        return

    raw_journal = devlog.build_raw_journal_markdown(date_arg, entries)
    await send_markdown_file(update, f"raw_journal_{date_arg}.md", raw_journal)


async def cmd_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_yesterday_entries(user_id)
    yesterday_str = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for yesterday ({yesterday_str}).")
        return

    raw_journal = devlog.build_raw_journal_markdown(yesterday_str, entries)
    await send_markdown_file(update, f"raw_journal_{yesterday_str}.md", raw_journal)


async def cmd_delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        deleted_text = journal_service.delete_last_entry(user_id)
        if deleted_text is not None:
            await update.message.reply_text(f"Deleted last log:\n{deleted_text}")
        else:
            await update.message.reply_text("No log entries to delete.")
    except Exception:
        logger.exception("Failed to delete entry for user %s", user_id)
        await update.message.reply_text("Failed to delete the last entry. Please try again.")


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        reply = journal_service.undo_last_action(user_id)
        await update.message.reply_text(reply if reply else "Nothing to undo.")
    except Exception:
        logger.exception("Failed to undo last action for user %s", user_id)
        await update.message.reply_text("Failed to undo last action. Please try again.")


async def _generate_today_summary(user_id: int) -> str:
    entries = journal_service.get_today_entries(user_id)
    entries_text = "\n".join(
        f"{i}. {entry['message_text']}" for i, entry in enumerate(entries, 1)
    )
    summary = await ai_service.generate_summary(entries_text)
    summary_service.save_summary(user_id, summary)
    return summary


def _weekly_review_prompt(grouped_entries: dict[str, list]) -> str:
    sections = []
    for date_str, entries in grouped_entries.items():
        sections.append(f"## {date_str}\n{devlog.format_entries(entries)}")
    diary_text = "\n\n".join(sections)

    return f"""\
You are DayCommit, an AI assistant creating a concise weekly developer review.

Review these journal entries from the last 7 local dates including today.

Weekly diary:
{diary_text}

Return only Markdown with these sections:

## What I Worked On
Summarize the main work areas.

## Strong Days
Identify the strongest days and why.

## Weak Days
Identify weaker days and why.

## Main Distractions
List recurring distractions or wasted time.

## Main Wins
List the biggest wins.

## Next Week Focus
List practical focus areas for next week.

## Suggested Improvements
Give specific, actionable improvements.
"""


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today = datetime.now(LOCAL_TZ).date()
    grouped_entries = {}

    for offset in range(6, -1, -1):
        date_str = (today - timedelta(days=offset)).isoformat()
        entries = journal_service.get_entries_for_date(user_id, date_str)
        if entries:
            grouped_entries[date_str] = entries

    if not grouped_entries:
        await update.message.reply_text("No logs found for the last 7 days.")
        return

    await update.message.reply_text("Generating weekly review...")

    try:
        review = await ai_service.generate_from_prompt(_weekly_review_prompt(grouped_entries))
        if len(review) > TELEGRAM_TEXT_SAFE_LIMIT:
            await send_markdown_file(update, "weekly_review.md", review)
        else:
            await update.message.reply_text(review)
    except RuntimeError as e:
        await update.message.reply_text(str(e))
    except Exception:
        logger.exception("Failed to generate weekly review for user %s", user_id)
        await update.message.reply_text(
            "Failed to generate weekly review. Check your API keys and try again."
        )


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_today_entries(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}) to summarize.")
        return

    if summary_service.get_today_summary(user_id):
        await update.message.reply_text(
            "Today's summary already exists. Use /regenerate to overwrite it or /edit_summary to edit it."
        )
        return

    await update.message.reply_text("Generating summary...")

    try:
        summary = await _generate_today_summary(user_id)
        await send_summary_result(update, today_str, summary)
    except RuntimeError as e:
        await update.message.reply_text(str(e))
    except Exception:
        logger.exception("Failed to generate summary for user %s", user_id)
        await update.message.reply_text(
            "Failed to generate summary. Check your API keys and try again."
        )


async def cmd_regenerate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_today_entries(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}) to summarize.")
        return

    await update.message.reply_text("Regenerating summary...")

    try:
        summary = await _generate_today_summary(user_id)
        await send_summary_result(update, today_str, summary)
    except RuntimeError as e:
        await update.message.reply_text(str(e))
    except Exception:
        logger.exception("Failed to regenerate summary for user %s", user_id)
        await update.message.reply_text(
            "Failed to regenerate summary. Check your API keys and try again."
        )


async def cmd_edit_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    summary = summary_service.get_today_summary(user_id)

    if not summary:
        await update.message.reply_text("No AI summary found. Run /summary first.")
        return

    AWAITING_EDITED_SUMMARY.add(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")
    if len(summary) > TELEGRAM_TEXT_SAFE_LIMIT:
        await send_markdown_file(update, f"summary_{today_str}.md", summary)
        await update.message.reply_text(
            "Send the edited summary as your next message, or use /cancel."
        )
    else:
        await update.message.reply_text(
            f"Current summary:\n\n{summary}\n\nSend the edited summary as your next message, or use /cancel."
        )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in AWAITING_EDITED_SUMMARY:
        AWAITING_EDITED_SUMMARY.discard(user_id)
        await update.message.reply_text("Cancelled.")
    else:
        await update.message.reply_text("Nothing to cancel.")


async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        backup_path = backup_service.create_backup()
        await update.message.reply_text(f"Backup created ✅ {backup_path.name}")
    except Exception:
        logger.exception("Failed to create database backup")
        await update.message.reply_text("Failed to create backup. Check bot logs for details.")


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    summary = summary_service.get_today_summary(user_id)
    entries = journal_service.get_today_entries(user_id)

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}). Nothing to preview.")
        return

    if not summary:
        await update.message.reply_text("No AI summary found. Run /summary first.")
        return

    preview = devlog.build_markdown(today_str, summary, entries)
    await send_markdown_file(update, f"devlog_{today_str}.md", preview)


async def cmd_push(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    entries = journal_service.get_today_entries(user_id)
    if not entries:
        await update.message.reply_text(
            f"No logs for today ({today_str}). Nothing to push."
        )
        return

    ai_summary = summary_service.get_today_summary(user_id)
    if not ai_summary:
        await update.message.reply_text(
            "No AI summary found. Run /summary first, then /push."
        )
        return

    await update.message.reply_text("Pushing to GitHub...")

    markdown = devlog.build_markdown(today_str, ai_summary, entries)

    try:
        result = await github_service.push_devlog(user_id, today_str, markdown)
        action = result["action"].capitalize()
        short_sha = result["sha"][:7]
        await update.message.reply_text(
            f"{action} successfully.\n\n"
            f"Commit: {short_sha}\n"
            f"Path: {result['path']}\n"
            f"{result['url']}"
        )
    except RuntimeError as e:
        await update.message.reply_text(str(e))
    except Exception:
        logger.exception("GitHub push failed for user %s", user_id)
        await update.message.reply_text(
            "GitHub push failed. Your local data is safe. Check bot logs for details."
        )


def build_application(token: str) -> Application:
    app = Application.builder().token(token).post_init(register_bot_commands).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("yesterday", cmd_yesterday))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("week", cmd_week))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("regenerate", cmd_regenerate))
    app.add_handler(CommandHandler("edit_summary", cmd_edit_summary))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("push", cmd_push))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("delete_last", cmd_delete_last))
    app.add_handler(CommandHandler("undo", cmd_undo))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
