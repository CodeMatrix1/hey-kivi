"""Unit tests — ops shell scripts stay bash-safe on Windows checkouts."""

from __future__ import annotations

from pathlib import Path

OPS_SCRIPTS = Path(__file__).resolve().parents[3] / "ops" / "scripts"


def test_shell_scripts_use_lf_line_endings():
    """CRLF breaks ``set -o pipefail`` when Git Bash runs scripts on Windows."""
    for path in sorted(OPS_SCRIPTS.glob("*.sh")):
        data = path.read_bytes()
        assert b"\r" not in data, f"{path.name} must use LF line endings (found CR)"


def test_restore_baseline_script_declares_bash_and_pipefail():
    text = (OPS_SCRIPTS / "restore_baseline.sh").read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash")
    assert "set -euo pipefail" in text
    assert "golden_goose_eval_user" in text or "baseline" in text.lower()


def test_restore_baseline_powershell_script_exists():
    ps1 = OPS_SCRIPTS / "restore_baseline.ps1"
    assert ps1.is_file()
    text = ps1.read_text(encoding="utf-8")
    assert "hey-kivi_hindsight_pg0" in text
    assert "hey-kivi_kivi2_sqlite" in text
