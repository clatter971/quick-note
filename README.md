# Quick Note

**Capture thoughts instantly without leaving your workflow.** One hotkey from anywhere on your desktop -- a minimal popup appears, you type, and the note lands in your Obsidian vault with full context about what you were working on. No app switching, no friction, no lost ideas.

Quick Note knows where you are. It captures the VS Code project you have open, the browser tab you're reading, or the terminal path you're working in -- and attaches that context to every note automatically.

<p align="center">
  <img src="docs/screenshots/dark-mode.png" alt="Quick Note - Dark Mode" width="460">
  &nbsp;&nbsp;
  <img src="docs/screenshots/light-mode.png" alt="Quick Note - Light Mode" width="460">
</p>

## Why Quick Note?

Your best ideas don't arrive on schedule. They hit while you're debugging, reading docs, or reviewing code -- and they vanish just as fast if you have to context-switch to write them down.

Quick Note eliminates that friction. Press **Win+Shift+N**, type your thought, and hit Enter. Your note is saved as a properly formatted Obsidian markdown file, tagged and timestamped, with a link back to exactly what you were doing. You never leave your current window for more than a few seconds.

## Features

### Instant Capture
- **Global hotkey** (`Win+Shift+N`) -- popup appears instantly from any application
- **Resizable window** with dark/light theme support that matches your system preference
- **Full keyboard control** -- Ctrl+C/V/X/A/Z all work natively in the editor

### Smart Context Detection
Every note automatically records what you were doing when inspiration struck:

| Source | What's captured |
|--------|----------------|
| **VS Code** | Project name |
| **Chrome / Edge / Firefox** | Page title + full URL (via Windows UI Automation) |
| **Windows Terminal / Git Bash** | Working directory / project path |
| **Any other app** | Window title |

### Organization
- **Tag buttons** -- one-click categorization: `project`, `idea`, `todo`, `learning`
- **Auto-tag inference** -- notes starting with action words (`fix`, `bug`, `update`, `add`, `remove`, `change`, `debug`, `broken`) are tagged `todo`; speculative phrases (`maybe`, `what if`, `could we`, `should we`) become `idea`
- **Obsidian-ready output** -- proper YAML frontmatter, kebab-case filenames, drops into your `00-Inbox/` folder

### AI Integration
- **Send to Claude** (`Ctrl+Shift+Enter`) -- opens an interactive [Claude Code](https://docs.anthropic.com/en/docs/claude-code) session pre-loaded with your question and the URL you were viewing

### Notepad++ Watcher
A background file watcher monitors a folder for `.txt` files saved from Notepad++ (or any editor). Multi-note files are automatically split on `---` separators or two or more blank lines, and each chunk becomes its own Inbox entry. Great for brain-dump sessions.

## Example Output

A note captured while working in VS Code:

```markdown
---
type: note
tags: [quick-capture, todo]
created: "2026-03-22T14:30:52"
source: "vscode"
context: "project: homelab-dashboard"
---

# Fix the sidebar alignment

## Captured Context
- **From**: vscode -- homelab-dashboard
- **When**: 2026-03-22 14:30
```

A note captured while reading in Chrome:

```markdown
---
type: note
tags: [quick-capture, learning]
created: "2026-03-22T15:10:00"
source: "chrome"
context: "page: How DNS Works | url: https://example.com/dns-guide"
---

# Interesting DNS article

## Captured Context
- **From**: chrome -- "How DNS Works"
- **URL**: https://example.com/dns-guide
- **When**: 2026-03-22 15:10
```

## Requirements

- **Windows 10 or 11**
- [AutoHotkey v2](https://www.autohotkey.com/)
- Python 3.12+ with [watchdog](https://pypi.org/project/watchdog/)
- An [Obsidian](https://obsidian.md/) vault with an `00-Inbox/` folder
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI (optional, for the Send to Claude feature)

## Installation

Two options:

- **Portable (easy)** -- one zip, no Python or AutoHotkey install needed. Best for end users.
- **From source** -- clone the repo, run from your own Python. Best for hacking on it.

### Option A: Portable (recommended)

1. Download the latest `quick-note-portable-<version>.zip` from the [Releases page](https://github.com/clatter971/quick-note/releases).
2. Extract the folder anywhere -- e.g. `C:\Tools\quick-note\`.
3. Copy `quick-note-config.example.json` to `local\quick-note-config.json` and edit the paths (see the [Config table](#config)).
4. Double-click `quick-note.exe`. Press **Win+Shift+N** to capture your first note.

The zip bundles AutoHotkey v2 (renamed to `quick-note.exe`) and PyInstaller-frozen helpers, so nothing is registered system-wide. Delete the folder to uninstall. To upgrade, download the next zip and copy your `local/` folder into it -- your config and preferences carry over.

### Option B: From source

1. **Install AutoHotkey**

   ```
   winget install AutoHotkey.AutoHotkey
   ```

2. **Clone the repo**

   ```
   git clone https://github.com/clatter971/quick-note.git
   cd quick-note
   ```

3. **Install Python dependencies**

   ```
   pip install -r requirements.txt
   ```

4. **Create your config** (see [Config](#config) below)

   ```
   mkdir local
   cp quick-note-config.example.json local/quick-note-config.json
   ```

5. **Run it**

   Double-click `quick-note.ahk` or run from a terminal:

   ```
   "%LocalAppData%\Programs\AutoHotkey\v2\AutoHotkey64.exe" "quick-note.ahk"
   ```

6. **Auto-start on login** (optional)

   Create a shortcut in your Startup folder:

   ```powershell
   $WshShell = New-Object -ComObject WScript.Shell
   $Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\QuickNote.lnk")
   $Shortcut.TargetPath = "$env:LocalAppData\Programs\AutoHotkey\v2\AutoHotkey64.exe"
   $Shortcut.Arguments = '"C:\path\to\quick-note.ahk"'
   $Shortcut.WorkingDirectory = "C:\path\to\quick-note"
   $Shortcut.Save()
   ```

   For the portable build, point `TargetPath` at `quick-note.exe` instead and drop the `Arguments` line.

### Config

Edit `local/quick-note-config.json`:

| Key | Required | Description |
|-----|----------|-------------|
| `inbox_path` | Yes | Your Obsidian vault's inbox folder (e.g. `C:/Users/you/Vault/00-Inbox`) |
| `python_path` | Source build only | Path to your Python executable. Ignored by the portable build. |
| `watch_path` | Yes | Folder where Notepad++ saves quick notes |
| `vault_name` | No | Your Obsidian vault name for the "Open Inbox" tray action. Auto-derived from `inbox_path` parent folder if omitted. |
| `log_path` | No | Where to write logs (defaults to `local/quick-note.log`) |
| `hotkey` | No | Global keyboard shortcut (default: `#+n` = Win+Shift+N). See [Changing the keyboard shortcut](#changing-the-keyboard-shortcut). |

The `local/` folder is gitignored -- your config, logs, and runtime files stay private.

### Building a portable release yourself

Maintainers and contributors can produce the portable zip locally:

```powershell
.\build_portable.ps1 -Zip
```

This script creates a build venv, runs PyInstaller on each helper, copies `AutoHotkey64.exe` to `quick-note.exe`, and assembles the distribution under `dist\quick-note-portable\` plus a versioned zip in `dist\`. The same steps run automatically in CI on tag push (see `.github/workflows/release.yml`).

## Usage

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Win+Shift+N` | Open note popup |
| `Ctrl+Enter` | Save note to Obsidian |
| `Ctrl+Shift+Enter` | Send to Claude |
| `Ctrl+C / V / X` | Copy / Paste / Cut |
| `Ctrl+A` | Select all |
| `Ctrl+Z` | Undo |
| `Escape` | Cancel |

### Tag Buttons

Click a tag to categorize your note. Click again to deselect. If you skip tagging, the auto-tagger will infer one from the note text when possible.

### System Tray

Right-click the Quick Note icon in the system tray for:

- **New Note** -- same as Win+Shift+N
- **Open Inbox** -- opens the inbox folder in Obsidian
- **Pause/Resume Watcher** -- toggle the Notepad++ file watcher
- **Dark Mode** -- toggle between dark and light themes
- **Exit** -- stop Quick Note and the file watcher

### Changing the keyboard shortcut

The default shortcut is **Win + Shift + N**. To change it, add a `hotkey` entry to `quick-note-config.json` (in your `local/` folder) using these modifier codes:

| Code | Key     |
|------|---------|
| `#`  | Win     |
| `+`  | Shift   |
| `^`  | Ctrl    |
| `!`  | Alt     |

Combine the codes with a letter. Examples:

| Config value | Shortcut                  |
|--------------|---------------------------|
| `"#+n"`      | Win + Shift + N (default) |
| `"^+n"`      | Ctrl + Shift + N          |
| `"#n"`       | Win + N                   |
| `"!+n"`      | Alt + Shift + N           |

Add it to your config file like this:

```json
{
    "hotkey": "^+n"
}
```

The change takes effect automatically within a few seconds (the script watches for config changes).

## Architecture

```
Win+Shift+N
    |
    +-- AHK captures: window title, process name, browser URL (via UI Automation)
    +-- Shows popup GUI (embedded HTML/CSS via WebBrowser control)
    |
    +-- [Save]   --> JSON temp file --> Python enriches context --> .md in Inbox
    +-- [Claude]  --> prompt temp file --> Python launches Claude Code session
```

The Notepad++ watcher runs as a background process alongside the main AHK script, monitoring for new or changed `.txt` files. It splits multi-note files on `---` separators or two or more blank lines and creates individual Obsidian Inbox entries. A content-hash database prevents duplicate processing.

## Project Structure

| File | Purpose |
|------|---------|
| `quick-note.ahk` | AutoHotkey v2 script: hotkey, popup GUI, system tray, browser URL capture |
| `popup.html` | HTML/CSS/JS for the note popup UI (rendered in embedded browser control) |
| `note_capture.py` | Context enrichment, markdown generation, file writing |
| `note_watcher.py` | Notepad++ folder monitor with debounce and note splitting |
| `claude_launcher.py` | Launches interactive Claude Code session with prompt context |
| `quick-note-config.example.json` | Template config -- copy to `local/` and edit |
| `test_note_capture.py` | Tests for note capture (45 tests) |
| `test_note_watcher.py` | Tests for note watcher (8 tests) |

## Running Tests

```
pip install pytest
python -m pytest test_note_capture.py test_note_watcher.py -v
```

## License

[MIT](LICENSE)
