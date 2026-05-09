Quick Note -- Portable Build
============================

What this is
------------
A self-contained portable folder. No Python install, no AutoHotkey install,
no pip dependencies needed. Move the whole folder anywhere on Windows and
double-click quick-note.exe to launch.

Folder contents
---------------
  quick-note.exe                 - AutoHotkey64 runtime, renamed.
                                   Auto-loads quick-note.ahk on launch.
  quick-note.ahk                 - Main script. Hotkey, popup GUI, tray menu.
  popup.html                     - Note popup UI (loaded by AHK).
  note_capture.exe               - Frozen helper: writes .md to Obsidian.
  note_watcher.exe               - Frozen helper: Notepad++ folder watcher.
  claude_launcher.exe            - Frozen helper: opens Claude Code with prompt.
  quick-note-config.example.json - Template config.
  local/                         - Active config, logs, runtime state.
                                   Edit local/quick-note-config.json before
                                   first launch.

First-time setup
----------------
1. Copy quick-note-config.example.json to local/quick-note-config.json
   (the example file is a template; the real config lives in local/).
2. Open local/quick-note-config.json and set:
     - inbox_path  : your Obsidian inbox folder
     - watch_path  : folder you save Notepad++ quick notes into
     - vault_name  : Obsidian vault name (or omit to auto-derive)
   The python_path entry can stay or be removed -- portable builds use
   the bundled .exes instead.
3. Double-click quick-note.exe.
4. Press Win+Shift+N (default) to capture your first note.

How it runs
-----------
quick-note.exe (== AutoHotkey64.exe) reads quick-note.ahk from the same dir,
which:
  1. Detects portable mode (sees note_capture.exe next to itself).
  2. Loads local/quick-note-config.json.
  3. Spawns note_watcher.exe in the background.
  4. Registers the global hotkey (default Win+Shift+N).
  5. On hotkey, shows the note popup; Save calls note_capture.exe; Send to
     Claude calls claude_launcher.exe in a new Windows Terminal.

Updating
--------
Download the next release zip and copy your local/ folder into it. Your
config and theme preference are preserved.

Removing
--------
Just delete this folder. Nothing is registered system-wide.

Source
------
https://github.com/clatter971/quick-note
