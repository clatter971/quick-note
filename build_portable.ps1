#Requires -Version 7
<#
.SYNOPSIS
    Build a portable Quick Note distribution.

.DESCRIPTION
    Produces a self-contained folder (and optional zip) under .\dist\ that
    bundles AutoHotkey, the Quick Note script, and PyInstaller-frozen helpers.
    End users can drop the folder anywhere on Windows and double-click
    quick-note.exe -- no Python or AutoHotkey install required.

.PARAMETER OutputDir
    Where to assemble the portable build. Default: .\dist\quick-note-portable

.PARAMETER AhkExe
    Path to AutoHotkey64.exe to ship as quick-note.exe.
    Default: $env:LocalAppData\Programs\AutoHotkey\v2\AutoHotkey64.exe

.PARAMETER Zip
    If set, also produce dist\quick-note-portable-<version>.zip.

.PARAMETER SkipBuild
    Reuse existing dist\_pyinstaller artifacts (faster reruns while iterating
    on the AHK or HTML).

.EXAMPLE
    .\build_portable.ps1 -Zip

.NOTES
    Requires Python 3.12+ on PATH and AutoHotkey v2 installed locally.
#>
[CmdletBinding()]
param(
    [string]$OutputDir = (Join-Path $PSScriptRoot 'dist\quick-note-portable'),
    [string]$AhkExe   = (Join-Path $env:LocalAppData 'Programs\AutoHotkey\v2\AutoHotkey64.exe'),
    [switch]$Zip,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$repoRoot   = $PSScriptRoot
$distRoot   = Join-Path $repoRoot 'dist'
$buildWork  = Join-Path $distRoot '_pyinstaller'
$venvDir    = Join-Path $repoRoot '.venv-build'
$version    = (Get-Content (Join-Path $repoRoot 'VERSION')).Trim()

# --- Sanity checks -----------------------------------------------------------
if (-not (Test-Path $AhkExe)) {
    throw "AutoHotkey64.exe not found at: $AhkExe`nInstall AutoHotkey v2 or pass -AhkExe <path>."
}

$python = (Get-Command python -ErrorAction SilentlyContinue) ?? (Get-Command py -ErrorAction SilentlyContinue)
if (-not $python) {
    throw 'Python 3.12+ not found on PATH.'
}

# --- Build venv --------------------------------------------------------------
if (-not (Test-Path $venvDir)) {
    Write-Host "Creating build venv at $venvDir"
    & $python.Source -m venv $venvDir
}
$venvPython    = Join-Path $venvDir 'Scripts\python.exe'
$venvPyInstall = Join-Path $venvDir 'Scripts\pyinstaller.exe'

if (-not (Test-Path $venvPyInstall)) {
    Write-Host 'Installing PyInstaller and runtime deps into build venv'
    & $venvPython -m pip install --upgrade pip --quiet
    # Keep these versions in sync with .github/workflows/release.yml
    & $venvPython -m pip install --quiet pyinstaller==6.20.0 watchdog==6.0.0
}

# --- Build .exes -------------------------------------------------------------
$specRoot = Join-Path $distRoot '_pyinstaller'
$workPath = Join-Path $specRoot 'work'
$distPath = Join-Path $specRoot 'dist'

if (-not $SkipBuild) {
    if (Test-Path $specRoot) { Remove-Item $specRoot -Recurse -Force }
    New-Item -ItemType Directory -Path $specRoot | Out-Null

    foreach ($script in @('note_capture.py', 'note_watcher.py', 'claude_launcher.py')) {
        Write-Host "Building $script"
        & $venvPyInstall --onefile --clean --noconfirm `
            --distpath $distPath `
            --workpath $workPath `
            --specpath $specRoot `
            (Join-Path $repoRoot $script)
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed on $script" }
    }
}

# --- Assemble portable folder ------------------------------------------------
if (Test-Path $OutputDir) { Remove-Item $OutputDir -Recurse -Force }
New-Item -ItemType Directory -Path $OutputDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $OutputDir 'local') | Out-Null

# AutoHotkey runtime, renamed so users can double-click it
Copy-Item $AhkExe (Join-Path $OutputDir 'quick-note.exe')

# Frozen helpers
foreach ($exe in @('note_capture.exe', 'note_watcher.exe', 'claude_launcher.exe')) {
    $src = Join-Path $distPath $exe
    if (-not (Test-Path $src)) { throw "Missing build artifact: $src" }
    Copy-Item $src (Join-Path $OutputDir $exe)
}

# Source files shipped as-is
foreach ($f in @('quick-note.ahk', 'popup.html', 'quick-note-config.example.json', 'LICENSE', 'VERSION', 'README.md')) {
    Copy-Item (Join-Path $repoRoot $f) (Join-Path $OutputDir $f)
}

# Portable-specific README
Copy-Item (Join-Path $repoRoot 'docs\README-portable.txt') (Join-Path $OutputDir 'README-portable.txt')

Write-Host "Portable folder ready: $OutputDir"

# --- Optional zip ------------------------------------------------------------
if ($Zip) {
    $zipName = "quick-note-portable-$version.zip"
    $zipPath = Join-Path $distRoot $zipName
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path "$OutputDir\*" -DestinationPath $zipPath
    Write-Host "Zip: $zipPath"
}
