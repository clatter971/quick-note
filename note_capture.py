"""Quick Note Capture -- context enrichment and markdown file creation."""

import json
import logging
import os
import re
import sys
import unicodedata
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_path: str) -> logging.Logger:
    """Configure rotating file logging for quick-note.

    Idempotent: subsequent calls with a different log_path are ignored; the
    first caller's path wins. Document this at the call site if the path must
    match a runtime config value.

    Args:
        log_path: Path to the log file.  A bare filename (no directory
            component) is valid and writes to the current working directory.

    Returns:
        The configured ``quick-note`` logger.
    """
    logger = logging.getLogger("quick-note")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_dir = os.path.dirname(log_path)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    handler = RotatingFileHandler(
        log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


def load_config() -> dict:
    # When frozen by PyInstaller, __file__ points inside the bundle's temp
    # extraction dir; the user's config sits next to the .exe.
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    config_path = base / "local" / "quick-note-config.json"
    if not config_path.exists():
        config_path = base / "quick-note-config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


_SLUG_CLEAN_RE = re.compile(r"[^a-zA-Z0-9\s-]")


def generate_slug(text: str) -> str:
    if not text.strip():
        return "untitled"
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = _SLUG_CLEAN_RE.sub("", ascii_text)
    words = cleaned.lower().split()[:5]
    slug = "-".join(words)
    return slug or "untitled"


_TODO_VERBS = {"fix", "update", "change", "add", "remove", "debug"}
_TODO_STARTS = {"bug", "broken"}
_IDEA_STARTS = {"maybe", "what if", "could we", "should we"}


def infer_tag(note_text: str) -> str:
    if not note_text.strip():
        return ""
    lower = note_text.strip().lower()
    words = lower.split()
    # Strip trailing punctuation and split on em-dash to handle "fix:" and "bug—text"
    first_word = words[0].split("\u2014")[0].rstrip(":,.!?-") if words else ""
    if first_word in _TODO_VERBS or first_word in _TODO_STARTS:
        return "todo"
    for phrase in _IDEA_STARTS:
        if lower.startswith(phrase):
            return "idea"
    return ""


_BROWSERS = {
    "chrome.exe": "chrome",
    "firefox.exe": "firefox",
    "msedge.exe": "edge",
}

_BROWSER_SUFFIXES = [
    " - Google Chrome",
    " \u2014 Mozilla Firefox",
    " - Mozilla Firefox",
    " - Microsoft Edge",
]

_TERMINALS = {"WindowsTerminal.exe", "git-bash.exe", "mintty.exe", "bash.exe", "cmd.exe", "powershell.exe", "pwsh.exe"}


def resolve_context(window_title: str, process_name: str, url: str = "") -> dict:
    """Enrich a captured window title and process name into a structured context dict.

    Args:
        window_title: The title of the active window at capture time.
        process_name: The executable name of the active process (e.g. ``chrome.exe``).
        url: Optional URL from the browser's address bar.

    Returns:
        Dict with at least a ``source`` key.  Browser contexts include ``page``
        (and optionally ``url``).  VS Code contexts include ``project``.
        Terminal contexts include ``project`` or ``window``.
    """
    if not window_title and not process_name:
        return {"source": "unknown"}

    if process_name == "Code.exe":
        parts = window_title.rsplit(" - ", 2)
        if len(parts) >= 3:
            project = parts[-2].strip()
        elif len(parts) == 2:
            project = parts[0].strip()
        else:
            project = ""
        return {"source": "vscode", "project": project}

    if process_name in _BROWSERS:
        page_title = window_title
        for suffix in _BROWSER_SUFFIXES:
            if page_title.endswith(suffix):
                page_title = page_title[: -len(suffix)]
                break
        ctx = {"source": _BROWSERS[process_name], "page": page_title.strip()}
        if url:
            ctx["url"] = url
        return ctx

    if process_name in _TERMINALS:
        project = _parse_terminal_project(window_title)
        return {"source": "terminal", "project": project} if project else {"source": "terminal", "window": window_title}

    return {"source": process_name or "unknown", "window": window_title}


_MINGW_RE = re.compile(r"MINGW\d*:(.+)")
_WSL_RE = re.compile(r"\w+@[\w.-]+:\s*~?/(.+)")
_WINPATH_RE = re.compile(r"[A-Z]:\\")


def _parse_terminal_project(title: str) -> str:
    # Git Bash: "MINGW64:/c/Users/youruser/Documents/github/homelab"
    m = _MINGW_RE.search(title)
    if m:
        return Path(m.group(1).strip()).name

    # WSL-style: "user@host: ~/projects/myapp"
    m = _WSL_RE.match(title)
    if m:
        return Path(m.group(1).strip()).name

    # Windows path: "C:\Users\youruser\Documents\github\quick-note"
    m = _WINPATH_RE.match(title)
    if m:
        return Path(title.strip()).name

    return ""


def build_filename(note_text: str, timestamp: str) -> str:
    """Build a kebab-case filename from the first five words of a note and its timestamp.

    Args:
        note_text: The raw note content; slug is derived from its first line.
        timestamp: ISO-8601 timestamp string (microseconds are stripped).

    Returns:
        A filename of the form ``YYYY-MM-DD-HHmmss-slug.md``.
    """
    slug = generate_slug(note_text)
    # Truncate to seconds (remove microseconds if present)
    ts_clean = timestamp[:19]  # "2026-03-22T14:30:52"
    ts = ts_clean.replace("T", "-").replace(":", "")
    return f"{ts}-{slug}.md"


def _format_context_line(context: dict) -> str:
    source = context.get("source", "unknown")
    if "project" in context:
        branch = context.get("branch", "")
        suffix = f" (branch: {branch})" if branch else ""
        return f"**From**: {source} -- {context['project']}{suffix}"
    if "page" in context:
        url = context.get("url", "")
        url_suffix = f"\n- **URL**: {url}" if url else ""
        return f'**From**: {source} -- "{context["page"]}"{url_suffix}'
    if "window" in context:
        return f"**From**: {source} -- {context['window']}"
    return ""


def _format_context_frontmatter(context: dict) -> str:
    parts = []
    if "project" in context:
        parts.append(f"project: {context['project']}")
        if "branch" in context:
            parts.append(f"branch: {context['branch']}")
    elif "page" in context:
        parts.append(f'page: {context["page"]}')
        if "url" in context:
            parts.append(f'url: {context["url"]}')
    elif "window" in context:
        parts.append(f"window: {context['window']}")
    return " | ".join(parts)


def generate_markdown(note: str, tag: str, context: dict, timestamp: str) -> str:
    """Render a note as Obsidian-ready markdown with YAML frontmatter.

    Args:
        note: Raw note text.  First line becomes the title; remaining lines
            become the body.
        tag: User-selected or inferred tag (e.g. ``"todo"``).  Empty string
            means no secondary tag.
        context: Structured context dict from :func:`resolve_context`.
        timestamp: ISO-8601 timestamp for the ``created`` frontmatter field.

    Returns:
        Complete markdown string ready to be written to the inbox.
    """
    tags = ["quick-capture"]
    if tag:
        tags.append(tag)
    tags_str = ", ".join(tags)

    source = context.get("source", "unknown")
    context_fm = _format_context_frontmatter(context)
    safe_context_fm = (
        context_fm.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", "")
    )
    safe_source = source.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")

    # First line = title, rest = body (if multi-line)
    lines = note.split("\n", 1)
    first_line = lines[0].strip()
    title = (first_line[0].upper() + first_line[1:]) if first_line else "Untitled"
    body = lines[1].strip() if len(lines) > 1 else ""

    display_time = timestamp[:16].replace("T", " ")

    context_line = _format_context_line(context)
    context_section = "## Captured Context\n"
    if context_line:
        context_section += f"- {context_line}\n"
    context_section += f"- **When**: {display_time}"

    body_section = f"\n{body}\n" if body else ""

    return f"""---
type: note
tags: [{tags_str}]
created: "{timestamp}"
source: "{safe_source}"
context: "{safe_context_fm}"
---

{title}
{body_section}
{context_section}
"""


def save_note(
    note: str,
    tag: str,
    window_title: str,
    process_name: str,
    timestamp: str,
    inbox_path: str,
    log_path: str = "",
    url: str = "",
) -> bool:
    """Enrich and persist a captured note to the Obsidian inbox as a markdown file.

    Args:
        note: Raw note text to save.
        tag: Explicit tag (e.g. ``"todo"``).  Empty string triggers auto-inference.
        window_title: Title of the active window when the note was captured.
        process_name: Executable name of the active process.
        timestamp: ISO-8601 capture timestamp.
        inbox_path: Absolute path to the Obsidian inbox directory.
        log_path: Optional path to the rotating log file.  Falls back to
            ``NullHandler`` if omitted.
        url: Optional browser URL to embed in the context.

    Returns:
        ``True`` on success, ``False`` if ``inbox_path`` does not exist or
        the file cannot be written.
    """
    if log_path:
        logger = setup_logging(log_path)
    else:
        logger = logging.getLogger("quick-note")
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())

    if not os.path.isdir(inbox_path):
        logger.error("Inbox path does not exist: %s", inbox_path)
        return False

    context = resolve_context(window_title, process_name, url)

    if not tag:
        tag = infer_tag(note)

    md = generate_markdown(note, tag, context, timestamp)

    filename = build_filename(note, timestamp)
    filepath = Path(inbox_path) / filename
    counter = 2
    while filepath.exists():
        stem = filename.rsplit(".", 1)[0]
        filepath = Path(inbox_path) / f"{stem}-{counter}.md"
        counter += 1

    filepath.write_text(md, encoding="utf-8")
    logger.info("Saved note: %s", filepath.name)
    return True


def main():
    """CLI entry point: python note_capture.py <temp_json_path>"""
    if len(sys.argv) != 2:
        print("Usage: python note_capture.py <temp_json_path>", file=sys.stderr)
        sys.exit(1)

    json_path = sys.argv[1]
    try:
        with open(json_path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)

    note = data.get("note", "")
    if not note.strip():
        print("Error: 'note' field is missing or empty", file=sys.stderr)
        sys.exit(1)

    inbox_path = config.get("inbox_path")
    if not inbox_path:
        print("Error: 'inbox_path' missing from config", file=sys.stderr)
        sys.exit(1)

    success = save_note(
        note=note,
        tag=data.get("tag", ""),
        window_title=data.get("window_title", ""),
        process_name=data.get("process_name", ""),
        timestamp=data.get("timestamp", datetime.now().isoformat()),
        inbox_path=inbox_path,
        log_path=config.get("log_path", ""),
        url=data.get("url", ""),
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
