"""CI policy tests for .github/workflows/*.yml.

Static text-grep checks that enforce supply-chain integrity properties.
Avoids taking on a YAML parser dep just to assert workflow hygiene.
Each test maps to a Cyber Neo finding ID.
"""
import re
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
WORKFLOW = WORKFLOWS_DIR / "release.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_ahk_zip_is_sha256_verified():
    """CN-001: the AHK zip must be SHA-256 verified before extraction."""
    text = _workflow()
    assert "Download AutoHotkey" in text, "AHK download step missing"
    assert "Get-FileHash" in text and "SHA256" in text, (
        "AHK download is not SHA-256 verified -- see CN-001"
    )
    assert re.search(r"throw\s+['\"][^'\"]*hecksum[^'\"]*['\"]", text), (
        "Checksum mismatch must abort the workflow -- see CN-001"
    )


def test_ci_build_deps_are_version_pinned():
    """CN-002: pyinstaller and watchdog must be pinned to exact versions in CI."""
    text = _workflow()
    install_lines = [
        ln for ln in text.splitlines() if "pip install" in ln and "--upgrade pip" not in ln
    ]
    assert install_lines, "No pip install line found for build deps"
    joined = "\n".join(install_lines)
    assert re.search(r"pyinstaller==\d+\.\d+", joined), (
        "pyinstaller must be pinned with == in CI -- see CN-002"
    )
    assert re.search(r"watchdog==\d+\.\d+", joined), (
        "watchdog must be pinned with == in CI -- see CN-002"
    )


def test_actions_pinned_to_commit_sha():
    """CN-003: every `uses:` action ref must be a 40-char commit SHA."""
    sha_re = re.compile(r"[0-9a-f]{40}")
    uses_re = re.compile(r"^\s*-?\s*uses:\s*(\S+)")
    for wf in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = wf.read_text(encoding="utf-8")
        for ln in text.splitlines():
            m = uses_re.match(ln)
            if not m:
                continue
            ref = m.group(1)
            assert "@" in ref, f"{wf.name}: no ref pin on `{ref}`"
            sha = ref.rsplit("@", 1)[1]
            assert sha_re.fullmatch(sha), (
                f"{wf.name}: `{ref}` must be pinned to a 40-char commit SHA -- "
                f"see CN-003"
            )


def test_requirements_txt_pins_exact_versions():
    """CN-004: requirements.txt must use == pins, not >= or unconstrained."""
    req = WORKFLOWS_DIR.parents[1] / "requirements.txt"
    for raw in req.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        assert "==" in line, (
            f"requirements.txt line `{raw}` is not pinned with == -- see CN-004"
        )
