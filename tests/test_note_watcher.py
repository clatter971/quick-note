import json
import logging

from note_watcher import process_existing_backlog, split_notes


def test_split_double_blank_lines():
    text = "First note here\n\n\nSecond note here"
    chunks = split_notes(text)
    assert len(chunks) == 2
    assert chunks[0] == "First note here"
    assert chunks[1] == "Second note here"

def test_split_separator_dashes():
    text = "First note\n---\nSecond note"
    chunks = split_notes(text)
    assert len(chunks) == 2
    assert chunks[0] == "First note"
    assert chunks[1] == "Second note"

def test_split_single_note():
    text = "Just one note"
    chunks = split_notes(text)
    assert len(chunks) == 1
    assert chunks[0] == "Just one note"

def test_split_empty_chunks_removed():
    text = "Note one\n\n\n\n\n\nNote two"
    chunks = split_notes(text)
    assert len(chunks) == 2

def test_split_whitespace_only_chunks_removed():
    text = "Note one\n---\n   \n---\nNote two"
    chunks = split_notes(text)
    assert len(chunks) == 2

def test_process_file_creates_inbox_notes(tmp_path, monkeypatch):
    from note_watcher import process_file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("First note\n\n\nSecond note", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}

    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    logger = logging.getLogger("test-watcher")
    process_file(str(txt_file), config, logger)

    md_files = list(inbox.glob("*.md"))
    assert len(md_files) == 2

def test_process_file_skips_already_processed(tmp_path, monkeypatch):
    from note_watcher import process_file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Only one note", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    logger = logging.getLogger("test-watcher")
    process_file(str(txt_file), config, logger)
    process_file(str(txt_file), config, logger)

    md_files = list(inbox.glob("*.md"))
    assert len(md_files) == 1

def test_process_file_paused(tmp_path, monkeypatch):
    from note_watcher import process_file
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("A note", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    # Create pause flag
    pause_file = tmp_path / "paused"
    pause_file.touch()
    monkeypatch.setattr("note_watcher.PAUSE_FLAG", str(pause_file))

    logger = logging.getLogger("test-watcher")
    process_file(str(txt_file), config, logger)

    md_files = list(inbox.glob("*.md"))
    assert len(md_files) == 0  # paused, nothing created


def test_process_file_no_duplicate_on_append(tmp_path, monkeypatch):
    """Appending a new note to a processed file must import only the new chunk."""
    from note_watcher import process_file

    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("First note", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    logger = logging.getLogger("test-dedup")
    process_file(str(txt_file), config, logger)
    assert len(list(inbox.glob("*.md"))) == 1

    # Append a second note — only the new chunk should be imported
    txt_file.write_text("First note\n\n\nSecond note", encoding="utf-8")
    process_file(str(txt_file), config, logger)

    files = list(inbox.glob("*.md"))
    assert len(files) == 2, "First note must not be re-created on append"


def test_startup_backlog_is_processed(tmp_path, monkeypatch):
    """Files already in the watch folder at startup must be imported, not skipped."""
    watch_path = tmp_path / "watch"
    watch_path.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    # Create a file as if it arrived while the watcher was down
    (watch_path / "backlog.txt").write_text("Backlog note", encoding="utf-8")

    logger = logging.getLogger("test-backlog")
    process_existing_backlog(str(watch_path), config, logger)

    md_files = list(inbox.glob("*.md"))
    assert len(md_files) == 1, "Backlog note must be imported at startup"


def test_process_file_retries_after_failed_save(tmp_path, monkeypatch):
    from note_watcher import process_file

    txt_file = tmp_path / "test.txt"
    txt_file.write_text("Retry me", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    processed_db = tmp_path / "processed.json"
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(processed_db))

    calls = {"count": 0}

    def fake_save_note(**kwargs):
        calls["count"] += 1
        return calls["count"] > 1

    monkeypatch.setattr("note_watcher.save_note", fake_save_note)

    logger = logging.getLogger("test-watcher")

    process_file(str(txt_file), config, logger)
    assert calls["count"] == 1
    if processed_db.exists():
        db = json.loads(processed_db.read_text(encoding="utf-8"))
        assert str(txt_file) not in db

    process_file(str(txt_file), config, logger)
    assert calls["count"] == 2
    db = json.loads(processed_db.read_text(encoding="utf-8"))
    assert str(txt_file) in db


def test_process_file_skips_oversized_file(tmp_path, monkeypatch, caplog):
    """CN-007: process_file must refuse to load multi-MB+ files into memory."""
    import logging

    from note_watcher import process_file

    txt_file = tmp_path / "big.txt"
    txt_file.write_text("First note", encoding="utf-8")

    inbox = tmp_path / "inbox"
    inbox.mkdir()
    config = {"inbox_path": str(inbox), "log_path": str(tmp_path / "test.log")}
    monkeypatch.setattr("note_watcher.PROCESSED_DB", str(tmp_path / "processed.json"))

    # Pretend the file is 50 MB without actually allocating it
    monkeypatch.setattr("os.path.getsize", lambda p: 50 * 1024 * 1024)

    logger = logging.getLogger("test-oversized")
    with caplog.at_level(logging.WARNING, logger="test-oversized"):
        process_file(str(txt_file), config, logger)

    md_files = list(inbox.glob("*.md"))
    assert md_files == [], "Oversized file must not be processed -- see CN-007"


def test_processed_db_lives_under_home():
    """CN-008: PROCESSED_DB must default to a per-user HOME path, not TEMP."""
    from pathlib import Path

    from note_watcher import PROCESSED_DB

    home = str(Path.home().resolve())
    assert PROCESSED_DB.startswith(home), (
        f"PROCESSED_DB should live under HOME ({home}), got "
        f"{PROCESSED_DB!r} -- see CN-008"
    )
    assert "/tmp" not in PROCESSED_DB and "Temp" not in PROCESSED_DB, (
        f"PROCESSED_DB still references TEMP: {PROCESSED_DB!r}"
    )
