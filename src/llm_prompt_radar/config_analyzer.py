"""Analyzes JSON, YAML, and TOML config files for LLM configuration changes."""
from __future__ import annotations

import re
from pathlib import Path

from llm_prompt_radar.scanner import Finding

CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml"}

# Keys that indicate LLM configuration
LLM_KEY_RE = re.compile(
    r"""(?:model|temperature|max_tokens|top_p|top_k|system_prompt|llm|openai|anthropic|
        gemini|gpt|claude|palm|cohere|mistral|ollama|presence_penalty|frequency_penalty)""",
    re.IGNORECASE | re.VERBOSE,
)

MODEL_VALUE_RE = re.compile(
    r"""(?:model|llm_model|model_name)\s*[=:]\s*['"]?([a-zA-Z0-9._:/-]+)['"]?""",
    re.IGNORECASE,
)

PARAM_VALUE_RE = re.compile(
    r"""(temperature|max_tokens|top_p|top_k|presence_penalty|frequency_penalty)\s*[=:]\s*([\d.]+)""",
    re.IGNORECASE,
)


def _is_llm_config_file(rel_path: str, content_sample: str) -> bool:
    """Heuristic: does this config file contain LLM-related keys?"""
    if LLM_KEY_RE.search(rel_path):
        return True
    if LLM_KEY_RE.search(content_sample):
        return True
    return False


def _parse_diff_removed(diff_text: str, target_file: str) -> list[tuple[int, str]]:
    """Extract removed lines for a specific file from a unified diff."""
    removed: list[tuple[int, str]] = []
    in_file = False
    old_line_no = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("--- "):
            parts = raw_line[4:]
            if parts.startswith("a/"):
                parts = parts[2:]
            in_file = parts.strip() == target_file
            old_line_no = 0
        elif raw_line.startswith("@@ ") and in_file:
            m = re.search(r"@@ -(\d+)", raw_line)
            if m:
                old_line_no = int(m.group(1)) - 1
        elif in_file:
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                old_line_no += 1
                removed.append((old_line_no, raw_line[1:]))
            elif not raw_line.startswith("+"):
                old_line_no += 1

    return removed


def _parse_diff_added(diff_text: str, target_file: str) -> list[str]:
    """Extract added lines for a specific file from a unified diff."""
    added: list[str] = []
    in_file = False

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("--- "):
            parts = raw_line[4:]
            if parts.startswith("a/"):
                parts = parts[2:]
            in_file = parts.strip() == target_file
        elif in_file and raw_line.startswith("+") and not raw_line.startswith("+++"):
            added.append(raw_line[1:])

    return added


def analyze_config_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze config files for LLM-related changes."""
    findings: list[Finding] = []

    for rel_path in changed_files:
        p = Path(rel_path)
        if p.suffix.lower() not in CONFIG_EXTENSIONS:
            continue

        # Read new content to check if it's an LLM config file
        abs_path = repo_path / rel_path
        new_content = ""
        try:
            new_content = abs_path.read_text(encoding="utf-8", errors="replace")
        except (FileNotFoundError, OSError):
            pass

        # Sample from diff too
        diff_sample = ""
        for raw_line in diff_text.splitlines():
            if rel_path in raw_line or p.name in raw_line:
                diff_sample = raw_line
                break

        if not _is_llm_config_file(rel_path, new_content + diff_sample):
            continue

        removed_lines = _parse_diff_removed(diff_text, rel_path)
        added_lines = _parse_diff_added(diff_text, rel_path)

        if not removed_lines:
            continue

        # --- Model name changes ---
        removed_models: list[tuple[int, str]] = []
        added_models: set[str] = set()

        for line_no, line in removed_lines:
            m = MODEL_VALUE_RE.search(line)
            if m:
                removed_models.append((line_no, m.group(1)))

        for line in added_lines:
            m = MODEL_VALUE_RE.search(line)
            if m:
                added_models.add(m.group(1))

        for line_no, old_model in removed_models:
            if added_models:
                for new_model in added_models:
                    if old_model.lower() != new_model.lower():
                        findings.append(
                            Finding(
                                severity="high",
                                path=rel_path,
                                message=f"LLM model changed in config: '{old_model}' → '{new_model}'",
                                migration_note=(
                                    f"The model was changed from '{old_model}' to '{new_model}' in config. "
                                    "Verify the new model is appropriate for your use case."
                                ),
                                line=line_no,
                            )
                        )
            else:
                findings.append(
                    Finding(
                        severity="medium",
                        path=rel_path,
                        message=f"LLM model reference removed from config: '{old_model}'",
                        migration_note=(
                            "A model configuration was removed. Ensure the model is still configured correctly."
                        ),
                        line=line_no,
                    )
                )

        # --- Parameter changes ---
        param_seen: set[str] = set()
        for line_no, line in removed_lines:
            m = PARAM_VALUE_RE.search(line)
            if m:
                param_name = m.group(1).lower()
                old_val = m.group(2)
                if param_name not in param_seen:
                    param_seen.add(param_name)
                    # Find new value
                    new_val = None
                    for added_line in added_lines:
                        am = PARAM_VALUE_RE.search(added_line)
                        if am and am.group(1).lower() == param_name:
                            new_val = am.group(2)
                            break
                    if new_val and new_val != old_val:
                        findings.append(
                            Finding(
                                severity="medium",
                                path=rel_path,
                                message=f"LLM parameter changed in config: '{param_name}' {old_val} → {new_val}",
                                migration_note=(
                                    f"The '{param_name}' parameter changed from {old_val} to {new_val}. "
                                    "Parameter changes can affect model output quality and behaviour."
                                ),
                                line=line_no,
                            )
                        )
                    elif not new_val:
                        findings.append(
                            Finding(
                                severity="low",
                                path=rel_path,
                                message=f"LLM parameter removed from config: '{param_name}'",
                                migration_note=(
                                    f"The '{param_name}' config key was removed. "
                                    "Verify the model will use an appropriate default."
                                ),
                                line=line_no,
                            )
                        )

    return findings
