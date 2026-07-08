"""Analyzes prompt template files for risky changes."""
from __future__ import annotations

import re
from pathlib import Path

from llm_prompt_radar.scanner import Finding, git_file_at_ref

PROMPT_EXTENSIONS = {".prompt", ".jinja", ".jinja2", ".j2"}
PROMPT_FILENAMES = {"system_prompt.txt", "system.txt", "prompt.txt", "instructions.txt"}

SAFETY_PATTERNS = [
    r"do not",
    r"don't",
    r"never",
    r"must not",
    r"cannot",
    r"forbidden",
    r"unsafe",
    r"harmful",
    r"illegal",
    r"refuse",
    r"guardrail",
    r"safety",
    r"only respond",
    r"do not reveal",
    r"confidential",
    r"do not discuss",
]

PERSONA_PATTERNS = [
    r"you are",
    r"your name is",
    r"act as",
    r"you're a",
    r"you are an",
    r"your role",
    r"your job is",
    r"your purpose",
]


def is_prompt_file(path: str) -> bool:
    """Return True if the path is a recognised prompt template file."""
    p = Path(path)
    if p.suffix.lower() in PROMPT_EXTENSIONS:
        return True
    if p.name.lower() in PROMPT_FILENAMES:
        return True
    return False


def _word_set(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def _similarity(a: str, b: str) -> float:
    """Simple Jaccard-like word-overlap similarity between two texts."""
    ws_a = _word_set(a)
    ws_b = _word_set(b)
    if not ws_a and not ws_b:
        return 1.0
    if not ws_a or not ws_b:
        return 0.0
    intersection = ws_a & ws_b
    union = ws_a | ws_b
    return len(intersection) / len(union)


def _patterns_present(text: str, patterns: list[str]) -> set[str]:
    """Return the subset of patterns found in text (case-insensitive)."""
    found = set()
    lower = text.lower()
    for pat in patterns:
        if re.search(pat, lower):
            found.add(pat)
    return found


def analyze_prompt_files(
    repo_path: Path, changed_files: list[str], base_ref: str
) -> list[Finding]:
    """Analyze prompt template files and return a list of Findings."""
    findings: list[Finding] = []

    for rel_path in changed_files:
        if not is_prompt_file(rel_path):
            continue

        abs_path = repo_path / rel_path

        # Retrieve old content from git
        old_content: str = git_file_at_ref(repo_path, base_ref, rel_path) or ""

        # Read new content from disk (file might have been deleted)
        new_content: str = ""
        try:
            new_content = abs_path.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, OSError):
            new_content = ""

        # If no old content at all, it's a new file — low finding only
        if not old_content:
            findings.append(
                Finding(
                    severity="low",
                    path=rel_path,
                    message="New prompt file was added",
                    migration_note=(
                        "Review the new prompt file to ensure it meets safety and content guidelines."
                    ),
                )
            )
            continue

        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        # --- Safety pattern removal (Critical) ---
        old_safety = _patterns_present(old_content, SAFETY_PATTERNS)
        new_safety = _patterns_present(new_content, SAFETY_PATTERNS)
        removed_safety = old_safety - new_safety
        for pat in removed_safety:
            findings.append(
                Finding(
                    severity="critical",
                    path=rel_path,
                    message="Safety/guardrail instruction may have been removed",
                    migration_note=(
                        f"The safety pattern '{pat}' was present in the old prompt but is "
                        "no longer found in the new version. Verify that safety guardrails "
                        "are intentionally removed or replaced with equivalent protections."
                    ),
                )
            )

        # --- Persona change (High) ---
        old_persona = _patterns_present(old_content, PERSONA_PATTERNS)
        new_persona = _patterns_present(new_content, PERSONA_PATTERNS)
        if old_persona != new_persona:
            findings.append(
                Finding(
                    severity="high",
                    path=rel_path,
                    message="Persona/role definition was modified",
                    migration_note=(
                        "The persona or role patterns in the prompt changed. "
                        "Ensure the updated persona is intentional and appropriate."
                    ),
                )
            )

        # --- Major rewrite (High) ---
        sim = _similarity(old_content, new_content)
        if sim < 0.40:
            findings.append(
                Finding(
                    severity="high",
                    path=rel_path,
                    message="Prompt was substantially rewritten",
                    migration_note=(
                        f"Word-overlap similarity dropped to {sim:.0%}. "
                        "Conduct a full review of the rewritten prompt for safety and alignment."
                    ),
                )
            )
        else:
            # Major line-count reduction (High)
            if old_lines and len(new_lines) < len(old_lines) * 0.5:
                findings.append(
                    Finding(
                        severity="high",
                        path=rel_path,
                        message="Prompt file had a major reduction in content",
                        migration_note=(
                            f"Line count dropped from {len(old_lines)} to {len(new_lines)}. "
                            "Verify that important instructions were not accidentally removed."
                        ),
                    )
                )
            elif old_content != new_content and not removed_safety and old_persona == new_persona:
                # Minor edit
                findings.append(
                    Finding(
                        severity="low",
                        path=rel_path,
                        message="Prompt file was modified",
                        migration_note=(
                            "Review the prompt changes to confirm they are intentional "
                            "and do not affect model behaviour in undesirable ways."
                        ),
                    )
                )

    return findings
