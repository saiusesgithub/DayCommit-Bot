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


def build_markdown(date_str: str, summary: str | None, entries: list) -> str:
    """Assemble the full Daily DevLog Markdown document."""
    ai_block = summary if summary else "_No summary yet. Run /summary first._"
    diary_block = format_entries(entries) if entries else "_No entries yet._"
    return (
        f"# Daily DevLog — {date_str}\n\n"
        f"## AI Summary\n\n{ai_block}\n\n"
        f"---\n\n"
        f"## Rough Diary\n\n{diary_block}"
    )
