import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import devlog
import journal_service
import ai_service
import summary_service
import github_service
from timezone_utils import LOCAL_TZ

logger = logging.getLogger(__name__)

HELP_TEXT = """
*DayCommit* — your personal developer journal

Just send any message and it's saved as a log for today.

*Commands:*
/today — Show all logs for today
/yesterday — Show yesterday's logs
/summary — Generate AI summary of today's logs
/preview — Full DevLog preview (AI + diary)
/push — Push today's DevLog to GitHub
/delete_last — Delete the most recent log entry
/help — Show this message
""".strip()


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to *DayCommit*!\n\n"
        "Send any message to log it as a journal entry.\n"
        "Use /help to see all commands.",
        parse_mode="Markdown",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text
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

    await update.message.reply_text(
        f"Today's logs — {today_str}\n\n{devlog.format_entries(entries)}"
    )


async def cmd_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_yesterday_entries(user_id)
    yesterday_str = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for yesterday ({yesterday_str}).")
        return

    await update.message.reply_text(
        f"Yesterday's logs — {yesterday_str}\n\n{devlog.format_entries(entries)}"
    )


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


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_today_entries(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}) to summarize.")
        return

    await update.message.reply_text("Generating summary...")

    entries_text = "\n".join(
        f"{i}. {entry['message_text']}" for i, entry in enumerate(entries, 1)
    )

    try:
        summary = await ai_service.generate_summary(entries_text)
        summary_service.save_summary(user_id, summary)
        await update.message.reply_text(summary)
    except RuntimeError as e:
        await update.message.reply_text(str(e))
    except Exception:
        logger.exception("Failed to generate summary for user %s", user_id)
        await update.message.reply_text(
            "Failed to generate summary. Check your API keys and try again."
        )


async def cmd_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    summary = summary_service.get_today_summary(user_id)
    entries = journal_service.get_today_entries(user_id)

    if not summary and not entries:
        await update.message.reply_text("Nothing logged today yet.")
        return

    preview = devlog.build_markdown(today_str, summary, entries)

    if len(preview) <= 4000:
        await update.message.reply_text(preview)
    else:
        ai_block = summary if summary else "_No summary yet. Run /summary first._"
        await update.message.reply_text(
            f"# Daily DevLog — {today_str}\n\n## AI Summary\n\n{ai_block}"
        )
        await update.message.reply_text(
            f"## Rough Diary\n\n{devlog.format_entries(entries)}"
        )


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
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("yesterday", cmd_yesterday))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("preview", cmd_preview))
    app.add_handler(CommandHandler("push", cmd_push))
    app.add_handler(CommandHandler("delete_last", cmd_delete_last))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
