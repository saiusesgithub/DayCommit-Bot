FALLBACK_AI_SUMMARY = "_AI summary unavailable or skipped for today._"


def format_entries(entries: list) -> str:
    """Numbered, multiline-safe plain-text block for journal entries."""
    parts = []
    for i, entry in enumerate(entries, 1):
        prefix = f"{i}. "
        indent = " " * len(prefix)
        lines = entry["message_text"].strip().split("\n")
        body = ("\n" + indent).join(line.rstrip() for line in lines)
        parts.append(prefix + body)
    return "\n".join(parts)


def format_raw_entries(entries: list) -> str:
    """Raw journal block preserving each stored message exactly."""
    return "\n\n".join(entry["message_text"] for entry in entries)


def build_raw_journal_markdown(date_str: str, entries: list) -> str:
    """Build a raw journal export preserving stored Telegram messages exactly."""
    raw_logs = "\n\n".join(entry["message_text"] for entry in entries)
    return f"# Raw Journal — {date_str}\n\n{raw_logs}"


def build_markdown(date_str: str, summary: str | None, entries: list) -> str:
    """Assemble the full Daily DevLog Markdown document."""
    ai_block = summary if summary else FALLBACK_AI_SUMMARY
    raw_block = format_raw_entries(entries) if entries else "_No entries yet._"
    return (
        f"# Daily DevLog — {date_str}\n\n"
        f"## AI Summary\n\n{ai_block}\n\n"
        f"---\n\n"
        f"# Rough Journal\n\n{raw_block}"
    )
