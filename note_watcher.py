"""Notepad++ file watcher -- monitors a folder and creates Obsidian Inbox notes."""

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from note_capture import load_config, save_note, setup_logging

# Per-user state directory.  PROCESSED_DB lives here (not %TEMP%) so the
# dedup state is not vulnerable to tampering by other processes that share
# the temp dir on multi-user or misconfigured systems.
_STATE_DIR = Path.home() / ".quick-note"
_STATE_DIR.mkdir(parents=True, exist_ok=True)

PROCESSED_DB = str(_STATE_DIR / "processed.json")
# PAUSE_FLAG stays in %TEMP% because quick-note.ahk writes it there for IPC;
# moving it requires a coordinated AHK change.
PAUSE_FLAG = os.path.join(os.environ.get("TEMP", "/tmp"), "quick-note-watcher-paused")

# Cap on the size of a single .txt file we'll load into memory.
# A runaway log file accidentally placed in the watch folder would
# otherwise OOM the watcher silently.
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB


_SPLIT_RE = re.compile(r"\n{3,}|(?:^|\n)---(?:\n|$)")


def split_notes(text: str) -> list[str]:
    """Split text into separate notes on triple newlines or --- separators."""
    chunks = _SPLIT_RE.split(text)
    return [c.strip() for c in chunks if c.strip()]


def _load_processed_db() -> dict[str, str]:
    if os.path.exists(PROCESSED_DB):
        try:
            with open(PROCESSED_DB, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_processed_db(db: dict[str, str]) -> None:
    with open(PROCESSED_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def process_file(filepath: str, config: dict, logger: logging.Logger):
    """Process a single text file into Inbox notes, tracking per-chunk imports.

    Deduplication is keyed on per-chunk content hashes rather than a whole-file
    hash.  This means appending a new note to a file only imports the new chunk,
    and a partial-batch failure on retry only re-attempts unimported chunks.

    Args:
        filepath: Path to the ``.txt`` file to process.
        config: Loaded quick-note config dict; must contain ``inbox_path``.
        logger: Logger instance for progress and error reporting.
    """
    if os.path.exists(PAUSE_FLAG):
        logger.info("Watcher paused, skipping: %s", filepath)
        return

    try:
        size = os.path.getsize(filepath)
    except OSError as e:
        logger.warning("Could not stat %s: %s", filepath, e)
        return
    if size > MAX_FILE_BYTES:
        logger.warning(
            "Skipping oversized file (%d bytes > %d): %s",
            size, MAX_FILE_BYTES, filepath,
        )
        return

    db = _load_processed_db()
    raw = db.get(filepath, [])
    # Migrate from old whole-file-hash format (string) to chunk-hash list
    imported_chunks: set[str] = set(raw) if isinstance(raw, list) else set()

    with open(filepath, "rb") as f:
        content = f.read().decode("utf-8", errors="replace")

    chunks = split_notes(content)
    timestamp = datetime.now().isoformat(timespec="seconds")
    source_name = Path(filepath).stem

    for i, chunk in enumerate(chunks):
        chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
        if chunk_hash in imported_chunks:
            continue
        chunk_ts = datetime.now().isoformat(timespec="seconds") if i > 0 else timestamp
        if not save_note(
            note=chunk,
            tag="",
            window_title=f"Notepad++ -- {source_name}",
            process_name="notepad++.exe",
            timestamp=chunk_ts,
            inbox_path=config["inbox_path"],
            log_path=config.get("log_path", ""),
        ):
            logger.error("Failed to create inbox note from: %s", filepath)
            if imported_chunks:
                # Persist progress so successful chunks aren't re-imported on retry
                db[filepath] = list(imported_chunks)
                _save_processed_db(db)
            else:
                logger.warning("Leaving file unmarked for retry: %s", filepath)
            return
        imported_chunks.add(chunk_hash)
        logger.info("Created inbox note from: %s", filepath)

    db[filepath] = list(imported_chunks)
    _save_processed_db(db)


class NoteHandler(FileSystemEventHandler):
    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_modified(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith(".txt"):
            return
        with self._lock:
            self._pending[event.src_path] = time.time()

    def on_created(self, event):
        self.on_modified(event)

    def check_pending(self):
        """Call periodically to process debounced files."""
        now = time.time()
        with self._lock:
            ready = [p for p, t in self._pending.items() if now - t >= 2.0]
            for filepath in ready:
                del self._pending[filepath]
        for filepath in ready:
            try:
                process_file(filepath, self.config, self.logger)
            except Exception as e:
                self.logger.error("Error processing %s: %s", filepath, e)


def process_existing_backlog(watch_path: str, config: dict, logger: logging.Logger) -> None:
    """Process any .txt files already in the watch folder at startup.

    Prunes stale DB entries, then imports any chunks not yet seen from existing
    files.  Notes captured while the watcher was down are imported here rather
    than silently skipped.

    Args:
        watch_path: Directory to scan for ``.txt`` files.
        config: Loaded quick-note config dict.
        logger: Logger instance.
    """
    db = _load_processed_db()
    db = {k: v for k, v in db.items() if os.path.exists(k)}
    _save_processed_db(db)

    for f in Path(watch_path).glob("*.txt"):
        process_file(str(f), config, logger)


def main():
    config = load_config()
    logger = setup_logging(config.get("log_path", "quick-note.log"))

    watch_path = config.get("watch_path")
    if not watch_path:
        logger.error("'watch_path' missing from config")
        return
    if not config.get("inbox_path"):
        logger.error("'inbox_path' missing from config")
        return

    max_retries = 10
    retries = 0
    while not os.path.isdir(watch_path):
        retries += 1
        if retries > max_retries:
            logger.error("Watch path not found after %d retries, exiting: %s", max_retries, watch_path)
            return
        logger.warning("Watch path not found, retrying in 30s (%d/%d): %s", retries, max_retries, watch_path)
        time.sleep(30)

    process_existing_backlog(watch_path, config, logger)
    logger.info("Watcher started, monitoring: %s", watch_path)

    handler = NoteHandler(config, logger)
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
            handler.check_pending()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
