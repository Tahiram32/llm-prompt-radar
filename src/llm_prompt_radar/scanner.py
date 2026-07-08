"""Core git utilities and Finding dataclass for llm-prompt-radar."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Finding:
    severity: str
    path: str
    message: str
    migration_note: str
    line: int = 1


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _run_git(repo_path: Path, args: list[str]) -> str:
    """Run a git command and return stdout. Returns '' on failure."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
    except Exception:
        return ""


def git_changed_files(repo_path: Path, base_ref: str) -> list[str]:
    """Return list of changed file paths relative to repo root."""
    out = _run_git(repo_path, ["diff", "--name-only", f"{base_ref}...HEAD"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def git_deleted_files(repo_path: Path, base_ref: str) -> list[str]:
    """Return list of deleted file paths (status D) relative to repo root."""
    out = _run_git(repo_path, ["diff", "--name-status", f"{base_ref}...HEAD"])
    deleted = []
    for line in out.splitlines():
        parts = line.split("\t", 1)
        if len(parts) == 2 and parts[0].strip().upper() == "D":
            deleted.append(parts[1].strip())
    return deleted


def git_diff(repo_path: Path, base_ref: str) -> str:
    """Return the full unified diff between base_ref and HEAD."""
    return _run_git(repo_path, ["diff", f"{base_ref}...HEAD"])


def git_file_at_ref(repo_path: Path, ref: str, path: str) -> Optional[str]:
    """Return file content at the given ref, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Risk helpers
# ---------------------------------------------------------------------------

_RISK_ORDER = ["none", "low", "medium", "high", "critical"]


def _overall_risk(findings: list[Finding]) -> str:
    """Return the highest severity level present in findings."""
    if not findings:
        return "none"
    max_idx = 0
    for f in findings:
        try:
            idx = _RISK_ORDER.index(f.severity)
            if idx > max_idx:
                max_idx = idx
        except ValueError:
            pass
    return _RISK_ORDER[max_idx]


def _semver_recommendation(risk_level: str) -> str:
    """Map a risk level to a semver bump recommendation."""
    mapping = {
        "none": "patch",
        "low": "patch",
        "medium": "minor",
        "high": "major",
        "critical": "major",
    }
    return mapping.get(risk_level, "patch")


# ---------------------------------------------------------------------------
# Summarize
# ---------------------------------------------------------------------------

def summarize(findings: list[Finding], changed_files: list[str], repo_path: Path) -> dict:
    """Produce a summary report dict."""
    risk_level = _overall_risk(findings)
    return {
        "risk_level": risk_level,
        "finding_count": len(findings),
        "change_count": len(changed_files),
        "changed_files": changed_files,
        "findings": [asdict(f) for f in findings],
        "semver_recommendation": _semver_recommendation(risk_level),
    }
