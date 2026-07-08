"""Analyzes Python, JS, and TS source files for LLM API call changes."""
from __future__ import annotations

import re
from pathlib import Path

from llm_prompt_radar.scanner import Finding
from llm_prompt_radar.prompt_analyzer import SAFETY_PATTERNS

# Source file extensions to inspect
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}

# --- Model name patterns ---
MODEL_ASSIGN_RE = re.compile(
    r"""(?:model\s*=\s*|"model"\s*:\s*|'model'\s*:\s*|model\s*:\s*)['"]([^'"]+)['"]""",
    re.IGNORECASE,
)

# Model tier ordering for downgrade detection (lower index = higher capability)
MODEL_TIERS: list[list[str]] = [
    # OpenAI GPT-4 family (highest)
    ["gpt-4o", "gpt-4-turbo", "gpt-4"],
    # OpenAI GPT-3.5 family
    ["gpt-3.5-turbo", "gpt-3.5"],
    # Anthropic Claude 3 Opus
    ["claude-3-opus", "claude-3-5-sonnet", "claude-3-sonnet"],
    # Anthropic Claude 3 Haiku / lower
    ["claude-3-haiku", "claude-2", "claude-instant"],
    # Google Gemini Ultra / Pro
    ["gemini-ultra", "gemini-1.5-pro", "gemini-pro"],
    # Google Gemini Flash / Nano
    ["gemini-1.5-flash", "gemini-nano"],
    # Meta Llama large
    ["llama-3-70b", "llama-2-70b"],
    # Meta Llama small
    ["llama-3-8b", "llama-2-13b", "llama-2-7b"],
]


def _model_tier(model: str) -> int:
    """Return tier index of a model (lower = more capable). -1 if unknown."""
    lower = model.lower()
    for i, tier in enumerate(MODEL_TIERS):
        for name in tier:
            if name in lower:
                return i
    return -1


def _is_downgrade(old_model: str, new_model: str) -> bool:
    """Return True if new_model is a known downgrade from old_model."""
    old_tier = _model_tier(old_model)
    new_tier = _model_tier(new_model)
    if old_tier == -1 or new_tier == -1:
        return False
    return new_tier > old_tier


# --- System message patterns ---
SYSTEM_MSG_RE = re.compile(
    r"""(?:"role"\s*:\s*"system"|'role'\s*:\s*'system'|system_prompt\s*=|system\s*=|\.system\()""",
    re.IGNORECASE,
)

# --- Parameter patterns ---
PARAM_RE = re.compile(
    r"""(?:temperature|max_tokens|top_p|top_k|presence_penalty|frequency_penalty)\s*[=:]""",
    re.IGNORECASE,
)


def _parse_diff_sections(diff_text: str) -> dict[str, list[tuple[int, str]]]:
    """
    Parse a unified diff into a dict mapping filename -> list of (line_no, removed_line).
    """
    result: dict[str, list[tuple[int, str]]] = {}
    current_file: str | None = None
    old_line_no = 0

    for raw_line in diff_text.splitlines():
        # Detect file header
        if raw_line.startswith("--- "):
            # "--- a/path/to/file"
            parts = raw_line[4:]
            if parts.startswith("a/"):
                parts = parts[2:]
            current_file = parts.strip()
            old_line_no = 0
            if current_file not in result:
                result[current_file] = []
        elif raw_line.startswith("@@ "):
            # e.g. "@@ -10,7 +10,6 @@"
            m = re.search(r"@@ -(\d+)", raw_line)
            if m:
                old_line_no = int(m.group(1)) - 1
        elif current_file is not None:
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                old_line_no += 1
                result[current_file].append((old_line_no, raw_line[1:]))
            elif raw_line.startswith("+") and not raw_line.startswith("+++"):
                pass  # added lines don't affect old_line_no
            else:
                old_line_no += 1

    return result


def analyze_code_files(
    repo_path: Path,
    changed_files: list[str],
    base_ref: str,
    diff_text: str,
) -> list[Finding]:
    """Analyze code files for LLM API changes using the diff."""
    findings: list[Finding] = []

    removed_by_file = _parse_diff_sections(diff_text)

    # Collect added lines per file for model comparison
    added_by_file: dict[str, list[str]] = {}
    current_file: str | None = None
    for raw_line in diff_text.splitlines():
        if raw_line.startswith("--- "):
            parts = raw_line[4:]
            if parts.startswith("a/"):
                parts = parts[2:]
            current_file = parts.strip()
            if current_file not in added_by_file:
                added_by_file[current_file] = []
        elif current_file is not None and raw_line.startswith("+") and not raw_line.startswith("+++"):
            added_by_file[current_file].append(raw_line[1:])

    code_files_in_diff = {
        f for f in removed_by_file if Path(f).suffix.lower() in CODE_EXTENSIONS
    }

    for rel_path in code_files_in_diff:
        removed_lines = removed_by_file.get(rel_path, [])
        added_lines = added_by_file.get(rel_path, [])

        # Collect removed and added model names
        removed_models = []
        added_models_set: set[str] = set()

        for line_no, line in removed_lines:
            m = MODEL_ASSIGN_RE.search(line)
            if m:
                removed_models.append((line_no, m.group(1)))

        for line in added_lines:
            m = MODEL_ASSIGN_RE.search(line)
            if m:
                added_models_set.add(m.group(1))

        for line_no, old_model in removed_models:
            if added_models_set:
                for new_model in added_models_set:
                    if old_model.lower() != new_model.lower():
                        if _is_downgrade(old_model, new_model):
                            findings.append(
                                Finding(
                                    severity="critical",
                                    path=rel_path,
                                    message=f"Model may have been downgraded: '{old_model}' → '{new_model}'",
                                    migration_note=(
                                        f"The model was changed from '{old_model}' to '{new_model}'. "
                                        "This may result in degraded quality, capability, or safety. "
                                        "Verify this downgrade is intentional."
                                    ),
                                    line=line_no,
                                )
                            )
                        else:
                            findings.append(
                                Finding(
                                    severity="high",
                                    path=rel_path,
                                    message=f"LLM model name was changed: '{old_model}' → '{new_model}'",
                                    migration_note=(
                                        f"The model was changed from '{old_model}' to '{new_model}'. "
                                        "Verify the new model meets your quality and safety requirements."
                                    ),
                                    line=line_no,
                                )
                            )
            else:
                # model was removed, no replacement found
                findings.append(
                    Finding(
                        severity="high",
                        path=rel_path,
                        message=f"LLM model reference removed: '{old_model}'",
                        migration_note=(
                            "A model assignment was removed. Verify the model is still configured correctly."
                        ),
                        line=line_no,
                    )
                )

        # --- System message changes ---
        for line_no, line in removed_lines:
            if SYSTEM_MSG_RE.search(line):
                findings.append(
                    Finding(
                        severity="high",
                        path=rel_path,
                        message="System message in code was modified",
                        migration_note=(
                            "A system message or system prompt assignment was removed or changed. "
                            "Verify the system message is still correctly set in the new code."
                        ),
                        line=line_no,
                    )
                )

        # --- Parameter changes ---
        param_seen: set[str] = set()
        for line_no, line in removed_lines:
            m = PARAM_RE.search(line)
            if m:
                param_name = m.group(0).rstrip("=: ").strip().lower()
                if param_name not in param_seen:
                    param_seen.add(param_name)
                    findings.append(
                        Finding(
                            severity="medium",
                            path=rel_path,
                            message=f"LLM parameter was changed: '{param_name}'",
                            migration_note=(
                                f"The parameter '{param_name}' was modified. "
                                "Changing LLM parameters can affect output quality, length, and behaviour."
                            ),
                            line=line_no,
                        )
                    )

        # --- Safety/guardrail removal in code strings ---
        for line_no, line in removed_lines:
            lower_line = line.lower()
            # Only check lines that look like string content (contain quotes)
            if '"' in line or "'" in line:
                for pat in SAFETY_PATTERNS:
                    if re.search(pat, lower_line):
                        findings.append(
                            Finding(
                                severity="critical",
                                path=rel_path,
                                message="Safety instruction in code may have been removed",
                                migration_note=(
                                    f"A line containing the safety pattern '{pat}' was removed. "
                                    "Verify that safety instructions are still enforced."
                                ),
                                line=line_no,
                            )
                        )
                        break  # one finding per line is enough

    return findings
