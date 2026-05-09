import sys

import pytest

from note_capture import generate_slug


def test_slug_basic():
    assert generate_slug("Fix UI thing in app B") == "fix-ui-thing-in-app"

def test_slug_short_note():
    assert generate_slug("hello") == "hello"

def test_slug_strips_punctuation():
    assert generate_slug("Fix the bug! It's broken.") == "fix-the-bug-its-broken"

def test_slug_unicode_swedish():
    assert generate_slug("Ändra DNS-inställningar för hemma") == "andra-dns-installningar-for-hemma"

def test_slug_max_five_words():
    assert generate_slug("one two three four five six seven") == "one-two-three-four-five"

def test_slug_empty():
    assert generate_slug("") == "untitled"


from note_capture import infer_tag


def test_tag_fix():
    assert infer_tag("fix the login button") == "todo"

def test_tag_update():
    assert infer_tag("update the README") == "todo"

def test_tag_bug():
    assert infer_tag("bug in the checkout flow") == "todo"

def test_tag_broken():
    assert infer_tag("broken CSS on mobile") == "todo"

def test_tag_maybe():
    assert infer_tag("maybe we should use Redis") == "idea"

def test_tag_what_if():
    assert infer_tag("what if we cached this") == "idea"

def test_tag_no_match():
    assert infer_tag("DNS settings for the homelab") == ""

def test_tag_case_insensitive():
    assert infer_tag("Fix the UI") == "todo"

def test_tag_empty():
    assert infer_tag("") == ""

def test_tag_action_in_middle_no_match():
    assert infer_tag("the user wants to fix something") == ""

def test_tag_fix_with_colon():
    assert infer_tag("fix: login button not working") == "todo"

def test_tag_bug_with_em_dash():
    assert infer_tag("bug\u2014CSS is broken") == "todo"


from note_capture import resolve_context


def test_context_vscode():
    ctx = resolve_context("budget_calc.py - my-project - Visual Studio Code", "Code.exe")
    assert ctx["source"] == "vscode"
    assert ctx["project"] == "my-project"

def test_context_browser_chrome():
    ctx = resolve_context("GitHub Pull Request #42 - Google Chrome", "chrome.exe")
    assert ctx["source"] == "chrome"
    assert ctx["page"] == "GitHub Pull Request #42"

def test_context_browser_with_url():
    ctx = resolve_context("GitHub - Google Chrome", "chrome.exe", url="https://github.com/user/repo")
    assert ctx["source"] == "chrome"
    assert ctx["page"] == "GitHub"
    assert ctx["url"] == "https://github.com/user/repo"

def test_context_browser_without_url():
    ctx = resolve_context("GitHub - Google Chrome", "chrome.exe", url="")
    assert "url" not in ctx

def test_markdown_with_url():
    md = generate_markdown(
        note="interesting repo",
        tag="learning",
        context={"source": "chrome", "page": "GitHub", "url": "https://github.com/user/repo"},
        timestamp="2026-03-22T10:00:00",
    )
    assert "https://github.com/user/repo" in md
    assert "**URL**" in md

def test_context_browser_firefox():
    ctx = resolve_context("Reddit - Pair programming — Mozilla Firefox", "firefox.exe")
    assert ctx["source"] == "firefox"
    assert ctx["page"] == "Reddit - Pair programming"

def test_context_browser_edge():
    ctx = resolve_context("Bing - Microsoft Edge", "msedge.exe")
    assert ctx["source"] == "edge"
    assert ctx["page"] == "Bing"

def test_context_terminal_gitbash():
    ctx = resolve_context("MINGW64:/c/Users/youruser/Documents/github/homelab", "mintty.exe")
    assert ctx["source"] == "terminal"
    assert ctx["project"] == "homelab"

def test_context_terminal_wt():
    ctx = resolve_context("youruser@DESKTOP: ~/projects/myapp", "WindowsTerminal.exe")
    assert ctx["source"] == "terminal"
    assert ctx["project"] == "myapp"

@pytest.mark.skipif(sys.platform != "win32", reason="Windows path parsing required")
def test_context_terminal_cmd_path():
    ctx = resolve_context(r"C:\Users\youruser\Documents\github\quick-note", "WindowsTerminal.exe")
    assert ctx["source"] == "terminal"
    assert ctx["project"] == "quick-note"

def test_context_terminal_unknown_title():
    ctx = resolve_context("PowerShell", "WindowsTerminal.exe")
    assert ctx["source"] == "terminal"
    assert ctx["window"] == "PowerShell"

def test_context_unknown_app():
    ctx = resolve_context("Untitled - Notepad", "notepad.exe")
    assert ctx["source"] == "notepad.exe"
    assert ctx["window"] == "Untitled - Notepad"

def test_context_empty():
    ctx = resolve_context("", "")
    assert ctx["source"] == "unknown"


from note_capture import build_filename, generate_markdown


def test_markdown_with_context():
    md = generate_markdown(
        note="Fix the login bug",
        tag="todo",
        context={"source": "vscode", "project": "my-app"},
        timestamp="2026-03-22T14:30:52",
    )
    assert "type: note" in md
    assert "tags: [quick-capture, todo]" in md
    assert 'created: "2026-03-22T14:30:52"' in md
    assert 'source: "vscode"' in md
    assert "Fix the login bug" in md
    assert "**From**: vscode -- my-app" in md

def test_markdown_no_tag():
    md = generate_markdown(
        note="some random thought",
        tag="",
        context={"source": "unknown"},
        timestamp="2026-03-22T20:00:00",
    )
    assert "tags: [quick-capture]" in md
    assert "Some random thought" in md

def test_markdown_browser_context():
    md = generate_markdown(
        note="interesting article",
        tag="learning",
        context={"source": "chrome", "page": "How DNS Works"},
        timestamp="2026-03-22T10:00:00",
    )
    assert "tags: [quick-capture, learning]" in md
    assert '**From**: chrome -- "How DNS Works"' in md

def test_build_filename():
    name = build_filename("Fix the login bug", "2026-03-22T14:30:52")
    assert name == "2026-03-22-143052-fix-the-login-bug.md"

def test_build_filename_timestamp_format():
    name = build_filename("hello world", "2026-01-05T09:05:03")
    assert name == "2026-01-05-090503-hello-world.md"


def test_setup_logging_bare_filename(tmp_path, monkeypatch):
    """Regression: setup_logging('quick-note.log') must not crash (no directory component)."""
    import logging

    from note_capture import setup_logging

    monkeypatch.chdir(tmp_path)
    logger = logging.getLogger("quick-note")
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)
    result = setup_logging("bare-regression-test.log")
    assert result is not None
    assert (tmp_path / "bare-regression-test.log").exists()


def test_save_note_creates_file(tmp_path):
    from note_capture import save_note

    result = save_note(
        note="Test note content",
        tag="idea",
        window_title="Test Window",
        process_name="notepad.exe",
        timestamp="2026-03-22T14:30:52",
        inbox_path=str(tmp_path),
    )
    assert result is True
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text(encoding="utf-8")
    assert "Test note content" in content
    assert "tags: [quick-capture, idea]" in content

def test_save_note_slug_collision(tmp_path):
    from note_capture import save_note

    save_note("hello", "", "win", "app.exe", "2026-03-22T14:30:52", str(tmp_path))
    save_note("hello", "", "win", "app.exe", "2026-03-22T14:30:52", str(tmp_path))
    files = list(tmp_path.glob("*.md"))
    assert len(files) == 2
    names = sorted(f.name for f in files)
    assert "-2" in names[1]

def test_save_note_bad_inbox(tmp_path):
    from note_capture import save_note

    result = save_note("test", "", "", "", "2026-03-22T14:30:52", str(tmp_path / "nonexistent"))
    assert result is False


def test_tag_could_we():
    assert infer_tag("could we try a different approach") == "idea"

def test_tag_should_we():
    assert infer_tag("should we refactor this module") == "idea"

def test_markdown_window_context():
    md = generate_markdown(
        note="test note",
        tag="",
        context={"source": "notepad.exe", "window": "Untitled - Notepad"},
        timestamp="2026-03-22T10:00:00",
    )
    assert "**From**: notepad.exe -- Untitled - Notepad" in md

def test_build_filename_with_microseconds():
    name = build_filename("test note", "2026-03-22T14:30:52.123456")
    assert name == "2026-03-22-143052-test-note.md"

def test_context_vscode_no_file():
    ctx = resolve_context("my-project - Visual Studio Code", "Code.exe")
    assert ctx["source"] == "vscode"
    assert ctx["project"] == "my-project"

def test_context_vscode_bare():
    ctx = resolve_context("Visual Studio Code", "Code.exe")
    assert ctx["source"] == "vscode"
    assert ctx["project"] == ""

def test_context_empty_title_with_process():
    ctx = resolve_context("", "notepad.exe")
    assert ctx["source"] == "notepad.exe"
    assert ctx["window"] == ""

def test_markdown_yaml_escape_quotes():
    md = generate_markdown(
        note="test",
        tag="",
        context={"source": "chrome", "page": '"React" vs "Vue"'},
        timestamp="2026-03-22T10:00:00",
    )
    # Frontmatter must round-trip via a real YAML parser (CN-005)
    import yaml
    fm = md.split("---", 2)[1]
    parsed = yaml.safe_load(fm)
    assert parsed["source"] == "chrome"
    assert '"React" vs "Vue"' in parsed["context"]


def test_markdown_yaml_round_trip_metacharacters():
    """CN-005: YAML frontmatter must round-trip safely with metacharacters.

    Real-world input from `note_watcher.py` / `process_file` includes filenames
    with `:`, `#`, `[`, `]`, U+2028 etc. The hand-rolled escape in
    ``generate_markdown`` must produce parser-clean YAML for all of them.
    """
    import yaml

    nasty_titles = [
        "key: value with colon",
        "# leading hash",
        "[bracket array]",
        "trailing space ",
        "title with 'apostrophes'",
        'title with "quotes"',
        "C:\\Windows\\System32",
        "title with @at and !bang and *star",
    ]
    for window_title in nasty_titles:
        md = generate_markdown(
            note="body text",
            tag="",
            context={"source": "notepad++.exe", "window": window_title},
            timestamp="2026-03-22T14:30:52",
        )
        fm = md.split("---", 2)[1]
        parsed = yaml.safe_load(fm)
        assert parsed is not None, f"YAML parse failed for: {window_title!r}\n{fm}"
        assert parsed["source"] == "notepad++.exe"
        assert window_title.replace(" ", " ") in parsed["context"] or \
            window_title.strip() in parsed["context"], (
            f"context lost data for {window_title!r}: got {parsed['context']!r}"
        )


def test_markdown_yaml_safe_with_control_chars():
    """CN-005: control chars in frontmatter values must not break YAML parse.

    Inputs that today raise yaml.YAMLError because the double-quoted-scalar
    escape doesn't strip C0 control characters. The fix should sanitize the
    frontmatter value, not propagate raw control bytes into the YAML.
    """
    import yaml

    bad_titles = [
        "null\x00byte",
        "bell\x07char",
        "vertical\x0btab",
        "ansi\x1b[0mcolor",
        "form\x0cfeed",
    ]
    for window_title in bad_titles:
        md = generate_markdown(
            note="body",
            tag="",
            context={"source": "notepad++.exe", "window": window_title},
            timestamp="2026-03-22T14:30:52",
        )
        fm = md.split("---", 2)[1]
        parsed = yaml.safe_load(fm)
        assert isinstance(parsed, dict), (
            f"YAML did not parse to a dict for {window_title!r}: got {parsed!r}"
        )
        assert parsed.get("source") == "notepad++.exe"


def test_save_note_does_not_overwrite_concurrent_collision(tmp_path, monkeypatch):
    """CN-006: a same-name file racing in between exists()-check and write()
    must not silently overwrite. The fix uses os.O_CREAT | os.O_EXCL or an
    atomic os.replace().
    """
    from note_capture import build_filename, save_note

    # Pre-create the target so the simple non-collision filename is taken
    target_name = build_filename("hello world", "2026-03-22T14:30:52")
    (tmp_path / target_name).write_text("ORIGINAL", encoding="utf-8")

    # Simulate a race: monkeypatch Path.exists so it returns False at the
    # check, but the file is actually present on disk for the write.
    from pathlib import Path as _Path

    real_exists = _Path.exists

    def lying_exists(self):
        # Return False for the FIRST collision-check call; honest after that
        if not getattr(lying_exists, "lied", False):
            lying_exists.lied = True
            return False
        return real_exists(self)

    monkeypatch.setattr(_Path, "exists", lying_exists)

    # Even with a lying exists(), save_note must not overwrite ORIGINAL
    save_note(
        note="hello world",
        tag="",
        window_title="",
        process_name="",
        timestamp="2026-03-22T14:30:52",
        inbox_path=str(tmp_path),
    )

    # The pre-existing file with the same slug must still contain ORIGINAL
    assert (tmp_path / target_name).read_text(encoding="utf-8") == "ORIGINAL", (
        "save_note overwrote a colliding file -- TOCTOU race, see CN-006"
    )
