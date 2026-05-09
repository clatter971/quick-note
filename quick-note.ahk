; quick-note.ahk — Quick Note Capture Tool (AutoHotkey v2)
; Hotkey: Win+Shift+N
; Captures active window context, shows note popup, saves to Obsidian Inbox

#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

; --- Auto-reload on file change ---
DebugLog("=== Script started/reloaded ===")
SetTimer(WatchForChanges, 2000)
SCRIPT_MOD_TIME := FileGetTime(A_ScriptFullPath, "M")

WatchForChanges() {
    global SCRIPT_MOD_TIME, CONFIG_MOD_TIME, CONFIG_FILE, HOTKEY_COMBO, ACTIVE_HOTKEY
    try {
        currentMod := FileGetTime(A_ScriptFullPath, "M")
        if (currentMod != SCRIPT_MOD_TIME) {
            SCRIPT_MOD_TIME := currentMod
            DebugLog("WatchForChanges: file modified, calling Reload()")
            Reload()
        }
    }
    ; Check for config file changes and re-register hotkey if it changed
    try {
        if FileExist(CONFIG_FILE) {
            currentConfigMod := FileGetTime(CONFIG_FILE, "M")
            if (CONFIG_MOD_TIME != "" && currentConfigMod != CONFIG_MOD_TIME) {
                CONFIG_MOD_TIME := currentConfigMod
                DebugLog("WatchForChanges: config changed, reloading")
                oldHotkey := ACTIVE_HOTKEY
                LoadConfig()
                if (HOTKEY_COMBO != oldHotkey) {
                    try Hotkey(oldHotkey, "Off")
                    try {
                        Hotkey(HOTKEY_COMBO, MenuNewNote)
                        ACTIVE_HOTKEY := HOTKEY_COMBO
                        DebugLog("WatchForChanges: hotkey updated to " HOTKEY_COMBO)
                    } catch as e {
                        TrayTip("New hotkey could not be registered: " HOTKEY_COMBO, "Quick Note", "0x10")
                    }
                }
            }
        }
    }
}

; --- Debug Logging ---
DebugLog(msg) {
    try {
        logFile := A_ScriptDir "\local\debug.log"
        timestamp := FormatTime(, "yyyy-MM-dd HH:mm:ss")
        FileAppend(timestamp " | " msg "`n", logFile, "UTF-8")
    }
}

; --- Configuration ---
SCRIPT_DIR := A_ScriptDir
CONFIG_FILE := SCRIPT_DIR "\local\quick-note-config.json"
if !FileExist(CONFIG_FILE)
    CONFIG_FILE := SCRIPT_DIR "\quick-note-config.json"
; Portable mode is detected by the presence of frozen .exes next to the script.
; In portable builds these sit beside quick-note.exe (renamed AutoHotkey64.exe);
; in dev mode the .py source is invoked through the configured python_path.
PORTABLE_MODE := FileExist(SCRIPT_DIR "\note_capture.exe") ? true : false
PYTHON_PATH := ""
INBOX_PATH := ""
VAULT_NAME := ""
HOTKEY_COMBO := "#+n"
WATCHER_PID := 0
CONFIG_MOD_TIME := ""
ACTIVE_HOTKEY := ""

LoadConfig() {
    global CONFIG_FILE, PYTHON_PATH, INBOX_PATH, VAULT_NAME, HOTKEY_COMBO
    if !FileExist(CONFIG_FILE) {
        TrayTip("Config not found: " CONFIG_FILE, "Quick Note", "0x10")
        return false
    }
    try {
        configText := FileRead(CONFIG_FILE, "UTF-8")
        if RegExMatch(configText, '"python_path"\s*:\s*"([^"]+)"', &m)
            PYTHON_PATH := m[1]
        if RegExMatch(configText, '"inbox_path"\s*:\s*"([^"]+)"', &m)
            INBOX_PATH := m[1]
        if RegExMatch(configText, '"vault_name"\s*:\s*"([^"]+)"', &m)
            VAULT_NAME := m[1]
        if RegExMatch(configText, '"hotkey"\s*:\s*"([^"]+)"', &m)
            HOTKEY_COMBO := m[1]
        ; Derive vault name from inbox_path parent if not configured
        if !VAULT_NAME && INBOX_PATH {
            normalized := StrReplace(INBOX_PATH, "/", "\")
            SplitPath(normalized, , &parentDir)
            SplitPath(parentDir, &derivedName)
            VAULT_NAME := derivedName
        }
        return true
    } catch as e {
        TrayTip("Config error: " e.Message, "Quick Note", "0x10")
        return false
    }
}

ValidateRequiredConfig() {
    global PYTHON_PATH, INBOX_PATH, SCRIPT_DIR, PORTABLE_MODE
    if PORTABLE_MODE {
        ; Portable build: bundled .exes replace python_path
        for exe in ["note_capture.exe", "note_watcher.exe", "claude_launcher.exe"] {
            if !FileExist(SCRIPT_DIR "\" exe) {
                MsgBox("Missing portable component: " exe "`nExpected next to quick-note.exe.", "Quick Note Error")
                return false
            }
        }
    } else {
        if !PYTHON_PATH {
            MsgBox("Config missing required key: python_path", "Quick Note Error")
            return false
        }
        if !FileExist(PYTHON_PATH) {
            MsgBox("Configured Python executable not found:`n" PYTHON_PATH, "Quick Note Error")
            return false
        }
    }
    if !INBOX_PATH {
        MsgBox("Config missing required key: inbox_path", "Quick Note Error")
        return false
    }
    if !DirExist(INBOX_PATH) {
        MsgBox("Configured inbox_path not found:`n" INBOX_PATH, "Quick Note Error")
        return false
    }
    return true
}

; --- Theme ---
GetSystemThemePref() {
    try {
        appsUseLightTheme := RegRead(
            "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            "AppsUseLightTheme"
        )
        return appsUseLightTheme ? "light" : "dark"
    }
    return "dark"
}

LoadThemePref() {
    global SCRIPT_DIR
    prefFile := SCRIPT_DIR "\local\theme-pref.txt"
    if FileExist(prefFile) {
        try {
            pref := Trim(FileRead(prefFile, "UTF-8"))
            if (pref = "dark" || pref = "light")
                return pref
        }
    }
    return GetSystemThemePref()
}

SaveThemePref(pref) {
    global SCRIPT_DIR
    if !(pref = "light" || pref = "dark")
        return
    localDir := SCRIPT_DIR "\local"
    if !FileExist(localDir)
        DirCreate(localDir)
    prefFile := localDir "\theme-pref.txt"
    try {
        f := FileOpen(prefFile, "w", "UTF-8")
        f.Write(pref)
        f.Close()
    } catch as e {
        TrayTip("Could not save theme preference: " e.Message, "Quick Note", "0x10")
    }
}

SetDarkTitleBar(hWnd, dark) {
    darkVal := dark ? 1 : 0
    DllCall("dwmapi\DwmSetWindowAttribute", "Ptr", hWnd, "Int", 20, "Int*", darkVal, "Int", 4)
}

HotkeyToDisplay(hk) {
    display := ""
    if InStr(hk, "#")
        display .= "Win+"
    if InStr(hk, "^")
        display .= "Ctrl+"
    if InStr(hk, "!")
        display .= "Alt+"
    if InStr(hk, "+")
        display .= "Shift+"
    key := RegExReplace(hk, "[#^!+]", "")
    display .= StrUpper(key)
    return display
}

UriEncode(str) {
    size := StrPut(str, "UTF-8")
    buf := Buffer(size)
    StrPut(str, buf, "UTF-8")
    encoded := ""
    Loop size - 1 {
        byte := NumGet(buf, A_Index - 1, "UChar")
        if ((byte >= 0x30 && byte <= 0x39)
            || (byte >= 0x41 && byte <= 0x5A)
            || (byte >= 0x61 && byte <= 0x7A)
            || byte = 0x2D
            || byte = 0x2E
            || byte = 0x5F
            || byte = 0x7E) {
            encoded .= Chr(byte)
        } else {
            encoded .= "%" Format("{:02X}", byte)
        }
    }
    return encoded
}

; --- Startup ---
if !LoadConfig() {
    MsgBox("Failed to load config. Exiting.", "Quick Note Error")
    ExitApp
}
if !ValidateRequiredConfig() {
    ExitApp
}

LaunchWatcher() {
    global WATCHER_PID, PYTHON_PATH, SCRIPT_DIR, PORTABLE_MODE
    if PORTABLE_MODE {
        watcherExe := SCRIPT_DIR "\note_watcher.exe"
        if FileExist(watcherExe) {
            Run('"' watcherExe '"', SCRIPT_DIR, "Hide", &pid)
            WATCHER_PID := pid
        }
    } else {
        watcherScript := SCRIPT_DIR "\note_watcher.py"
        if FileExist(watcherScript) && FileExist(PYTHON_PATH) {
            Run('"' PYTHON_PATH '" "' watcherScript '"', SCRIPT_DIR, "Hide", &pid)
            WATCHER_PID := pid
        }
    }
}
LaunchWatcher()
CONFIG_MOD_TIME := FileExist(CONFIG_FILE) ? FileGetTime(CONFIG_FILE, "M") : "0"

; --- System Tray ---
A_IconTip := "Quick Note Capture"
TraySetIcon("Shell32.dll", 70)

hotkeyDisplay := HotkeyToDisplay(HOTKEY_COMBO)
tray := A_TrayMenu
tray.Delete()
tray.Add("New Note`t" hotkeyDisplay, MenuNewNote)
tray.Add("Open Inbox", MenuOpenInbox)
tray.Add()
tray.Add("Pause Watcher", MenuTogglePause)
if FileExist(A_Temp "\quick-note-watcher-paused")
    tray.Check("Pause Watcher")
tray.Add()
tray.Add("Dark Mode", MenuToggleDarkMode)
if (LoadThemePref() = "dark")
    tray.Check("Dark Mode")
tray.Add()
tray.Add("Exit", MenuExit)
tray.Default := "New Note`t" hotkeyDisplay

MenuNewNote(*) {
    ShowNoteGUI()
}
MenuOpenInbox(*) {
    global VAULT_NAME, INBOX_PATH
    normalized := StrReplace(INBOX_PATH, "/", "\")
    SplitPath(normalized, &inboxFolder)
    Run("obsidian://open?vault=" UriEncode(VAULT_NAME) "&file=" UriEncode(inboxFolder))
}
MenuTogglePause(*) {
    global tray
    pauseFile := A_Temp "\quick-note-watcher-paused"
    if FileExist(pauseFile) {
        FileDelete(pauseFile)
        tray.Uncheck("Pause Watcher")
        TrayTip("Watcher resumed", "Quick Note", "0x1")
    } else {
        FileAppend("", pauseFile)
        tray.Check("Pause Watcher")
        TrayTip("Watcher paused", "Quick Note", "0x1")
    }
}
MenuToggleDarkMode(*) {
    global tray
    if (LoadThemePref() = "dark") {
        SaveThemePref("light")
        tray.Uncheck("Dark Mode")
        TrayTip("Light mode enabled", "Quick Note", "0x1")
    } else {
        SaveThemePref("dark")
        tray.Check("Dark Mode")
        TrayTip("Dark mode enabled", "Quick Note", "0x1")
    }
}
MenuExit(*) {
    global WATCHER_PID
    if WATCHER_PID
        try ProcessClose(WATCHER_PID)
    ExitApp
}

OnExit(CleanupOnExit)
CleanupOnExit(reason, code) {
    DebugLog("OnExit triggered: reason=" reason " code=" code)
    global WATCHER_PID
    if WATCHER_PID
        try ProcessClose(WATCHER_PID)
}

; --- Hotkey ---
try {
    Hotkey HOTKEY_COMBO, MenuNewNote
    ACTIVE_HOTKEY := HOTKEY_COMBO
} catch {
    TrayTip("Hotkey " hotkeyDisplay " could not be registered", "Quick Note", "0x10")
}

; --- GUI ---
ShowNoteGUI() {
    global PYTHON_PATH, SCRIPT_DIR

    ; Capture active window context immediately
    prevTitle := ""
    prevProcess := ""
    prevUrl := ""
    try {
        prevHwnd := WinGetID("A")
        prevTitle := WinGetTitle("ahk_id " prevHwnd)
        prevProcess := WinGetProcessName("ahk_id " prevHwnd)
        DebugLog("ShowNoteGUI: captured context, process=" prevProcess " hwnd=" prevHwnd)
        DebugLog("ShowNoteGUI: calling GetBrowserUrl...")
        prevUrl := GetBrowserUrl(prevHwnd, prevProcess)
        DebugLog("ShowNoteGUI: GetBrowserUrl completed, hasUrl=" (prevUrl ? "yes" : "no"))
    }

    ; Resolve theme
    theme := LoadThemePref()
    isDark := (theme = "dark")

    ; Read HTML template and inject theme
    htmlPath := SCRIPT_DIR "\popup.html"
    if !FileExist(htmlPath) {
        TrayTip("popup.html not found", "Quick Note", "0x10")
        return
    }
    htmlContent := FileRead(htmlPath, "UTF-8")
    htmlContent := StrReplace(htmlContent, '<body class="dark">', '<body class="' theme '">')

    ; Write themed HTML to temp file (needed for IE11 edge mode via meta tag)
    tempHtml := A_Temp "\quick-note-popup.html"
    try FileDelete(tempHtml)
    f := FileOpen(tempHtml, "w", "UTF-8")
    f.Write(htmlContent)
    f.Close()

    ; Build resizable GUI with embedded browser
    noteGui := Gui("+AlwaysOnTop -MinimizeBox +Resize +MinSize450x200", "Quick Note")
    noteGui.MarginX := 0
    noteGui.MarginY := 0
    SetDarkTitleBar(noteGui.Hwnd, isDark)

    try {
        wb := noteGui.AddActiveX("w450 h270", "Shell.Explorer")
    } catch as e {
        TrayTip("Browser control not available: " e.Message, "Quick Note", "0x10")
        noteGui.Destroy()
        return
    }
    wbCtrl := wb.Value
    wbCtrl.Silent := true
    wbCtrl.Navigate(tempHtml)
    startTime := A_TickCount
    while (wbCtrl.ReadyState != 4) && ((A_TickCount - startTime) < 10000)
        Sleep(10)
    if (wbCtrl.ReadyState != 4) {
        TrayTip("Browser failed to load note editor within 10 seconds.", "Quick Note", "0x10")
        noteGui.Destroy()
        return
    }

    ; Register keyboard shortcuts via low-level hook (AHK Hotkey)
    ; AHK's GUI message loop swallows Ctrl+key before the browser sees them,
    ; so we intercept at hook level and call COM methods directly.
    WB_Paste(*) {
        try wbCtrl.Document.parentWindow.doPaste()
    }
    WB_Copy(*) {
        try wbCtrl.Document.parentWindow.doCopy()
    }
    WB_Cut(*) {
        try wbCtrl.Document.parentWindow.doCut()
    }
    WB_SelAll(*) {
        try wbCtrl.Document.parentWindow.doSelectAll()
    }
    WB_Undo(*) {
        try wbCtrl.Document.parentWindow.doUndo()
    }
    WB_Save(*) {
        try wbCtrl.Document.parentWindow.doSave()
    }
    WB_Claude(*) {
        try wbCtrl.Document.parentWindow.doClaude()
    }

    HotIfWinActive("ahk_id " noteGui.Hwnd)
    Hotkey("^v", WB_Paste)
    Hotkey("^c", WB_Copy)
    Hotkey("^x", WB_Cut)
    Hotkey("^a", WB_SelAll)
    Hotkey("^z", WB_Undo)
    Hotkey("^Enter", WB_Save)
    Hotkey("^+Enter", WB_Claude)
    HotIfWinActive()

    ; Resize ActiveX control to fill window when resized
    noteGui.OnEvent("Size", OnResize)
    OnResize(thisGui, minMax, width, height) {
        if minMax != -1
            wb.Move(0, 0, width, height)
    }

    ; Poll for user action via document.title
    actionDone := false
    CheckAction() {
        if actionDone
            return
        try {
            doc := wbCtrl.Document
            docTitle := doc.title
            if (docTitle = "CANCEL") {
                actionDone := true
                SetTimer(CheckAction, 0)
                noteGui.Destroy()
            } else if (docTitle = "SAVE") {
                actionDone := true
                SetTimer(CheckAction, 0)
                noteText := doc.getElementById("resultNote").value
                selectedTag := doc.getElementById("resultTag").value
                noteGui.Destroy()
                DoSaveNote(noteText, selectedTag, prevTitle, prevProcess, prevUrl)
            } else if (docTitle = "CLAUDE") {
                actionDone := true
                SetTimer(CheckAction, 0)
                noteText := doc.getElementById("resultNote").value
                noteGui.Destroy()
                DoSendToClaude(noteText, prevTitle, prevUrl)
            }
        }
    }
    SetTimer(CheckAction, 100)

    noteGui.OnEvent("Close", (*) => (actionDone := true, SetTimer(CheckAction, 0), noteGui.Destroy()))
    noteGui.Show()
}

DoSaveNote(noteText, tag, windowTitle, processName, url) {
    global PYTHON_PATH, SCRIPT_DIR, PORTABLE_MODE
    noteText := Trim(noteText)
    if !noteText
        return

    timestamp := FormatTime(, "yyyy-MM-ddTHH:mm:ss")
    tempFile := A_Temp "\quick-note-" A_Now A_MSec ".json"

    jsonContent := '{"note":' JsonEscape(noteText)
        . ',"tag":' JsonEscape(tag)
        . ',"window_title":' JsonEscape(windowTitle)
        . ',"process_name":' JsonEscape(processName)
        . ',"url":' JsonEscape(url)
        . ',"timestamp":' JsonEscape(timestamp) '}'

    f := FileOpen(tempFile, "w", "UTF-8")
    f.Write(jsonContent)
    f.Close()

    if PORTABLE_MODE
        cmd := '"' SCRIPT_DIR '\note_capture.exe" "' tempFile '"'
    else
        cmd := '"' PYTHON_PATH '" "' SCRIPT_DIR '\note_capture.py" "' tempFile '"'
    try {
        exitCode := RunWait(cmd, SCRIPT_DIR, "Hide")
    } catch {
        TrayTip("Failed to run capture script. Raw note preserved in TEMP: " tempFile, "Quick Note", "0x10")
        return
    }

    if exitCode = 0 {
        try FileDelete(tempFile)
        TrayTip("Note saved!", "Quick Note", "0x1")
    } else {
        TrayTip("Note save failed -- raw note preserved in TEMP: " tempFile, "Quick Note", "0x10")
    }
}

DoSendToClaude(noteText, windowTitle, url) {
    global PYTHON_PATH, SCRIPT_DIR, PORTABLE_MODE
    noteText := Trim(noteText)
    if !noteText
        return

    prompt := noteText
    if url {
        prompt := "URL: " url "`n`nIMPORTANT: If fetching the URL fails (403, 451, etc.), tell me and I will paste the content. Do NOT give up or apologize repeatedly -- just ask me to paste it.`n`n" prompt
    } else if windowTitle {
        prompt := "Context: " windowTitle "`n`n" prompt
    }

    tempPrompt := A_Temp "\claude-prompt-" A_Now A_MSec ".txt"
    f := FileOpen(tempPrompt, "w", "UTF-8-RAW")
    f.Write(prompt)
    f.Close()

    if PORTABLE_MODE
        launchCmd := 'wt.exe "' SCRIPT_DIR '\claude_launcher.exe" "' tempPrompt '"'
    else
        launchCmd := 'wt.exe "' PYTHON_PATH '" "' SCRIPT_DIR '\claude_launcher.py" "' tempPrompt '"'
    try Run(launchCmd)
    catch
        TrayTip("Failed to launch Claude. Prompt preserved in TEMP: " tempPrompt, "Quick Note", "0x10")
}

GetBrowserUrl(hWnd, processName) {
    static S_OK := 0
        , TreeScope_Descendants := 4
        , UIA_ControlTypePropertyId := 30003
        , UIA_DocumentControlTypeId := 50030
        , UIA_EditControlTypeId := 50004
        , UIA_ValueValuePropertyId := 30045

    ; Only attempt for known browsers
    exe := StrLower(processName)
    if !(exe = "chrome.exe" || exe = "msedge.exe" || exe = "firefox.exe")
        return ""

    DebugLog("GetBrowserUrl: enter, exe=" exe " hwnd=" hWnd)

    try winClass := WinGetClass("ahk_id " hWnd)
    catch
        return ""
    ctrlTypeId := (winClass ~= "Chrome") ? UIA_DocumentControlTypeId : UIA_EditControlTypeId
    DebugLog("GetBrowserUrl: winClass=" winClass " ctrlTypeId=" ctrlTypeId)

    try {
        IUIAutomation := ComObject("{FF48DBA4-60EF-4201-AA87-54103EEF594E}"
            , "{30CBE57D-D9D0-452A-AB13-7AC5AC4825EE}")
    } catch {
        DebugLog("GetBrowserUrl: failed to create IUIAutomation")
        return ""
    }
    DebugLog("GetBrowserUrl: IUIAutomation created")

    eRoot := ComValue(13, 0)
    hr := ComCall(6, IUIAutomation, "Ptr", hWnd, "Ptr*", eRoot)
    if (hr != S_OK || !eRoot.Ptr) {
        DebugLog("GetBrowserUrl: ElementFromHandle failed hr=" hr)
        return ""
    }
    DebugLog("GetBrowserUrl: ElementFromHandle OK")

    variant := Buffer(8 + 2 * A_PtrSize, 0)
    NumPut("UShort", 3, variant, 0)
    NumPut("Ptr", ctrlTypeId, variant, 8)

    condition := ComValue(13, 0)
    if (A_PtrSize = 8)
        hr := ComCall(23, IUIAutomation, "UInt", UIA_ControlTypePropertyId
            , "Ptr", variant, "Ptr*", condition)
    else
        hr := ComCall(23, IUIAutomation, "UInt", UIA_ControlTypePropertyId
            , "UInt64", NumGet(variant, 0, "UInt64")
            , "UInt64", NumGet(variant, 8, "UInt64")
            , "Ptr*", condition)

    if (hr != S_OK || !condition.Ptr) {
        DebugLog("GetBrowserUrl: CreatePropertyCondition failed hr=" hr)
        return ""
    }
    DebugLog("GetBrowserUrl: condition created, calling FindFirst...")

    eFound := ComValue(13, 0)
    hr := ComCall(5, eRoot, "UInt", TreeScope_Descendants, "Ptr", condition, "Ptr*", eFound)
    if (hr != S_OK || !eFound.Ptr) {
        DebugLog("GetBrowserUrl: FindFirst failed hr=" hr)
        return ""
    }
    DebugLog("GetBrowserUrl: FindFirst OK, getting value...")

    propVal := Buffer(8 + 2 * A_PtrSize, 0)
    hr := ComCall(10, eFound, "UInt", UIA_ValueValuePropertyId, "Ptr", propVal)

    ; COM pointers are auto-released by ComValue(13, ...) when they go out of scope.
    ; Do NOT manually call ObjRelease -- that causes double-free crashes.

    if (hr != S_OK) {
        DebugLog("GetBrowserUrl: GetPropertyValue failed hr=" hr)
        return ""
    }

    try {
        pBstr := NumGet(propVal, 8, "Ptr")
        if !pBstr {
            DebugLog("GetBrowserUrl: pBstr is null")
            return ""
        }
        url := StrGet(pBstr, "UTF-16")
        DllCall("OleAut32\SysFreeString", "Ptr", pBstr)
        DebugLog("GetBrowserUrl: success")
        return url
    } catch {
        DebugLog("GetBrowserUrl: exception reading BSTR")
        return ""
    }
}

JsonEscape(str) {
    str := StrReplace(str, "\", "\\")
    str := StrReplace(str, '"', '\"')
    str := StrReplace(str, "`n", "\n")
    str := StrReplace(str, "`r", "\r")
    str := StrReplace(str, "`t", "\t")
    ; Escape remaining ASCII control characters (0x00–0x1F) as \uXXXX
    out := ""
    Loop Parse, str {
        code := Ord(A_LoopField)
        out .= (code <= 0x1F) ? "\u" Format("{:04X}", code) : A_LoopField
    }
    return '"' out '"'
}
