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

import journal_service
from timezone_utils import LOCAL_TZ, utc_to_local

logger = logging.getLogger(__name__)

HELP_TEXT = """
*DayCommit* — your personal developer journal

Just send any message and it's saved as a log for today.

*Commands:*
/today — Show all logs for today
/yesterday — Show yesterday's logs
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
        await update.message.reply_text(
            "Failed to save your log. Please try again."
        )


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_today_entries(user_id)
    today_str = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for today ({today_str}) yet.")
        return

    lines = [f"*Today's logs — {today_str}*\n"]
    for i, entry in enumerate(entries, 1):
        time_part = utc_to_local(entry["created_at"]).strftime("%H:%M")
        lines.append(f"{i}. `[{time_part}]` {entry['message_text']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_yesterday(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    entries = journal_service.get_yesterday_entries(user_id)
    yesterday_str = (datetime.now(LOCAL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    if not entries:
        await update.message.reply_text(f"No logs for yesterday ({yesterday_str}).")
        return

    lines = [f"*Yesterday's logs — {yesterday_str}*\n"]
    for i, entry in enumerate(entries, 1):
        time_part = utc_to_local(entry["created_at"]).strftime("%H:%M")
        lines.append(f"{i}. `[{time_part}]` {entry['message_text']}")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_delete_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        deleted = journal_service.delete_last_entry(user_id)
        if deleted:
            await update.message.reply_text("Last log entry deleted.")
        else:
            await update.message.reply_text("No log entries to delete.")
    except Exception:
        logger.exception("Failed to delete entry for user %s", user_id)
        await update.message.reply_text(
            "Failed to delete the last entry. Please try again."
        )


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("today", cmd_today))
    app.add_handler(CommandHandler("yesterday", cmd_yesterday))
    app.add_handler(CommandHandler("delete_last", cmd_delete_last))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
