"""Apply user-defined regex rules from the config file against the diff."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from llm_prompt_radar.scanner import Finding


def apply_custom_rules(
    rules: list,
    diff_text: str,
    changed_files: list,
) -> list:
    """
    Apply each rule's pattern against added lines ('+' prefix) in *diff_text*.

    Each match produces a Finding with the rule's severity, description, and
    the matched line's file/line number.

    Rules with invalid regex are skipped (warning written to stderr).

    Parameters
    ----------
    rules:
        List of rule dicts with keys: id, description, severity, pattern.
    diff_text:
        Full unified diff text.
    changed_files:
        List of changed file paths (used for context; filtering is done via diff).

    Returns
    -------
    list[Finding]
    """
    if not rules:
        return []

    # Compile rules; skip invalid patterns
    compiled_rules = []
    for rule in rules:
        rule_id = rule.get("id", "<unnamed>")
        pattern = rule.get("pattern", "")
        if not pattern:
            print(
                f"[llm-prompt-radar] Warning: custom rule '{rule_id}' has no pattern, skipping.",
                file=sys.stderr,
            )
            continue
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            print(
                f"[llm-prompt-radar] Warning: custom rule '{rule_id}' has invalid regex "
                f"'{pattern}': {exc}. Skipping.",
                file=sys.stderr,
            )
            continue
        compiled_rules.append((rule, compiled))

    if not compiled_rules:
        return []

    # Parse added lines with file + line number tracking
    findings: list[Finding] = []
    current_file: str | None = None
    new_line_no = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("--- "):
            pass  # handled below
        elif raw_line.startswith("+++ "):
            parts = raw_line[4:]
            if parts.startswith("b/"):
                parts = parts[2:]
            current_file = parts.strip()
            new_line_no = 0
        elif raw_line.startswith("@@ "):
            # e.g. "@@ -10,7 +10,6 @@"
            m = re.search(r"@@ -\d+(?:,\d+)? \+(\d+)", raw_line)
            if m:
                new_line_no = int(m.group(1)) - 1
        elif current_file is not None:
            if raw_line.startswith("+") and not raw_line.startswith("+++"):
                new_line_no += 1
                added_content = raw_line[1:]
                # Apply each compiled rule
                for rule, compiled in compiled_rules:
                    if compiled.search(added_content):
                        findings.append(Finding(
                            severity=rule.get("severity", "medium"),
                            path=current_file,
                            message=(
                                f"[{rule.get('id', 'custom')}] {rule.get('description', 'Custom rule match')}"
                            ),
                            migration_note=(
                                f"Custom rule '{rule.get('id', 'custom')}' matched line: "
                                f"{added_content.strip()!r}"
                            ),
                            line=new_line_no,
                        ))
            elif not raw_line.startswith("-"):
                # Context line
                new_line_no += 1

    return findings
