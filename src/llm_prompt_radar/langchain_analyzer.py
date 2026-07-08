"""Detects risky changes in LangChain and LlamaIndex SDK code."""
from __future__ import annotations

import re
from pathlib import Path

from llm_prompt_radar.scanner import Finding
from llm_prompt_radar.code_analyzer import _is_downgrade, MODEL_ASSIGN_RE

# ---------------------------------------------------------------------------
# LangChain patterns
# ---------------------------------------------------------------------------

# Removed SystemMessage / system_message= -> high
LANGCHAIN_SYSTEM_MSG_RE = re.compile(
    r"""(?:SystemMessage\s*\(|system_message\s*=)""",
    re.IGNORECASE,
)

# Removed memory constructs -> medium
LANGCHAIN_MEMORY_RE = re.compile(
    r"""(?:ConversationSummaryMemory|ConversationBufferMemory)""",
    re.IGNORECASE,
)

# Changed temperature in LangChain -> medium
LANGCHAIN_TEMP_RE = re.compile(
    r"""temperature\s*=""",
    re.IGNORECASE,
)

# Removed chain types -> high
LANGCHAIN_CHAIN_RE = re.compile(
    r"""(?:LLMChain|ConversationalRetrievalChain|RetrievalQA)\s*[\(\.]""",
    re.IGNORECASE,
)

# Removed guardrail/parser constructs -> high
LANGCHAIN_GUARDRAIL_RE = re.compile(
    r"""(?:guardrails?|output_parser|PydanticOutputParser)\s*[\(=\.]""",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# LlamaIndex patterns
# ---------------------------------------------------------------------------

# Changed llm= or LLM( in index context -> high
LLAMA_LLM_RE = re.compile(
    r"""(?:llm\s*=|LLM\s*\()""",
    re.IGNORECASE,
)

# Removed system_prompt= from ServiceContext or Settings -> critical
LLAMA_SYSTEM_PROMPT_RE = re.compile(
    r"""system_prompt\s*=""",
    re.IGNORECASE,
)

# Changed similarity_top_k= to lower value -> low
LLAMA_TOPK_RE = re.compile(
    r"""similarity_top_k\s*=\s*(\d+)""",
    re.IGNORECASE,
)

# Removed response_mode= -> medium
LLAMA_RESPONSE_MODE_RE = re.compile(
    r"""response_mode\s*=""",
    re.IGNORECASE,
)

# Removed node_postprocessors= (guardrail filtering) -> high
LLAMA_POSTPROCESSORS_RE = re.compile(
    r"""node_postprocessors\s*=""",
    re.IGNORECASE,
)

# File extensions to inspect for LangChain / LlamaIndex usage
_LC_EXTENSIONS = {".py", ".ipynb"}

# Keywords indicating a file uses LangChain or LlamaIndex
_LC_IMPORT_HINTS = re.compile(
    r"""(?:from\s+langchain|import\s+langchain|from\s+llama_index|import\s+llama_index
         |from\s+llama|llama[-_]index
         |SystemMessage|LLMChain|ConversationalRetrievalChain|RetrievalQA
         |ChatOpenAI|ChatAnthropic|AzureChatOpenAI
         |ConversationSummaryMemory|ConversationBufferMemory
         |PydanticOutputParser|guardrails?
         |ServiceContext|VectorStoreIndex|QueryEngine
         |similarity_top_k|node_postprocessors|response_mode)""",
    re.IGNORECASE | re.VERBOSE,
)


def _is_langchain_file(content: str) -> bool:
    """Heuristic: does the file import LangChain or LlamaIndex?"""
    return bool(_LC_IMPORT_HINTS.search(content))


def _parse_diff_for_file(
    diff_text: str,
) -> dict:
    """
    Parse unified diff -> {filename: {
        'removed': [(lineno, text), ...],
        'added': [text, ...],
        'context': [text, ...],   # context/unchanged lines
    }}.
    """
    result: dict = {}
    current_file: str | None = None
    old_line_no = 0

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("--- "):
            parts = raw_line[4:]
            if parts.startswith("a/"):
                parts = parts[2:]
            current_file = parts.strip()
            old_line_no = 0
            if current_file not in result:
                result[current_file] = {"removed": [], "added": [], "context": []}
        elif raw_line.startswith("+++ "):
            pass
        elif raw_line.startswith("@@ "):
            m = re.search(r"@@ -(\d+)", raw_line)
            if m:
                old_line_no = int(m.group(1)) - 1
        elif current_file is not None:
            if raw_line.startswith("-") and not raw_line.startswith("---"):
                old_line_no += 1
                result[current_file]["removed"].append((old_line_no, raw_line[1:]))
            elif raw_line.startswith("+") and not raw_line.startswith("+++"):
                result[current_file]["added"].append(raw_line[1:])
            else:
                old_line_no += 1
                result[current_file]["context"].append(raw_line.lstrip(" "))

    return result


def analyze_langchain_files(
    repo_path: Path,
    changed_files: list,
    base_ref: str,
    diff_text: str,
) -> list:
    """
    Analyze changed files for risky LangChain / LlamaIndex changes.

    Returns a list of Finding objects.
    """
    findings: list[Finding] = []

    file_diffs = _parse_diff_for_file(diff_text)

    for rel_path in changed_files:
        if Path(rel_path).suffix.lower() not in _LC_EXTENSIONS:
            continue

        entry = file_diffs.get(rel_path)
        if entry is None:
            continue

        removed = entry["removed"]
        added = entry["added"]
        context = entry["context"]

        # Heuristic: any line in the diff (removed, added, or context) suggests LC/LlamaIndex
        all_lines = [t for _, t in removed] + list(added) + list(context)
        all_text = "\n".join(all_lines)

        if not _LC_IMPORT_HINTS.search(all_text):
            # Fall back: read file from disk
            abs_path = repo_path / rel_path
            try:
                disk_text = abs_path.read_text(encoding="utf-8", errors="replace")
                if not _is_langchain_file(disk_text):
                    continue
            except OSError:
                continue

        # ---- LangChain checks on removed lines ----
        for line_no, line in removed:

            # SystemMessage / system_message removed -> high
            if LANGCHAIN_SYSTEM_MSG_RE.search(line):
                findings.append(Finding(
                    severity="high",
                    path=rel_path,
                    message="LangChain SystemMessage or system_message removed",
                    migration_note=(
                        "Removing SystemMessage or system_message= may strip the system "
                        "prompt from the LangChain chain. Verify the system context is "
                        "preserved in the updated code."
                    ),
                    line=line_no,
                ))

            # Memory constructs removed -> medium
            if LANGCHAIN_MEMORY_RE.search(line):
                findings.append(Finding(
                    severity="medium",
                    path=rel_path,
                    message="LangChain memory construct removed (potential memory loss)",
                    migration_note=(
                        "ConversationSummaryMemory or ConversationBufferMemory was removed. "
                        "Ensure conversation history is still managed appropriately."
                    ),
                    line=line_no,
                ))

            # Temperature changed -> medium
            if LANGCHAIN_TEMP_RE.search(line):
                findings.append(Finding(
                    severity="medium",
                    path=rel_path,
                    message="LangChain chain temperature parameter changed",
                    migration_note=(
                        "Changing temperature= affects the randomness of model outputs. "
                        "Verify the new value is appropriate for your use case."
                    ),
                    line=line_no,
                ))

            # Chain types removed -> high
            if LANGCHAIN_CHAIN_RE.search(line):
                findings.append(Finding(
                    severity="high",
                    path=rel_path,
                    message="LangChain chain class removed (LLMChain / ConversationalRetrievalChain / RetrievalQA)",
                    migration_note=(
                        "A core LangChain chain class was removed. Ensure the functionality "
                        "has been migrated to an equivalent component."
                    ),
                    line=line_no,
                ))

            # Guardrail / output parser removed -> high
            if LANGCHAIN_GUARDRAIL_RE.search(line):
                findings.append(Finding(
                    severity="high",
                    path=rel_path,
                    message="LangChain guardrail or output parser removed",
                    migration_note=(
                        "Removing guardrails, output_parser, or PydanticOutputParser may "
                        "expose the application to unvalidated model output. Review the change."
                    ),
                    line=line_no,
                ))

        # ---- LangChain model downgrade check ----
        removed_models = []
        added_models = []
        for line_no, line in removed:
            m = MODEL_ASSIGN_RE.search(line)
            if m:
                removed_models.append((line_no, m.group(1)))
        for line in added:
            m = MODEL_ASSIGN_RE.search(line)
            if m:
                added_models.append(m.group(1))

        for line_no, old_model in removed_models:
            for new_model in added_models:
                if old_model.lower() != new_model.lower():
                    if _is_downgrade(old_model, new_model):
                        findings.append(Finding(
                            severity="high",
                            path=rel_path,
                            message=f"LangChain model downgrade detected: '{old_model}' -> '{new_model}'",
                            migration_note=(
                                f"The model changed from '{old_model}' to '{new_model}' which "
                                "appears to be a capability downgrade. Verify this is intentional."
                            ),
                            line=line_no,
                        ))

        # ---- LlamaIndex checks on removed lines ----
        for line_no, line in removed:

            # llm= or LLM( changed -> high
            if LLAMA_LLM_RE.search(line):
                findings.append(Finding(
                    severity="high",
                    path=rel_path,
                    message="LlamaIndex LLM assignment changed",
                    migration_note=(
                        "The llm= or LLM( parameter in a LlamaIndex context was removed/changed. "
                        "Verify the new LLM configuration is correct."
                    ),
                    line=line_no,
                ))

            # system_prompt= removed from ServiceContext / Settings -> critical
            if LLAMA_SYSTEM_PROMPT_RE.search(line):
                findings.append(Finding(
                    severity="critical",
                    path=rel_path,
                    message="LlamaIndex system_prompt removed from ServiceContext or Settings",
                    migration_note=(
                        "Removing system_prompt= from ServiceContext or Settings eliminates the "
                        "system-level instructions. Confirm this is intentional."
                    ),
                    line=line_no,
                ))

            # similarity_top_k= changed to lower value -> low
            m_old = LLAMA_TOPK_RE.search(line)
            if m_old:
                old_k = int(m_old.group(1))
                for added_line in added:
                    m_new = LLAMA_TOPK_RE.search(added_line)
                    if m_new:
                        new_k = int(m_new.group(1))
                        if new_k < old_k:
                            findings.append(Finding(
                                severity="low",
                                path=rel_path,
                                message=f"LlamaIndex similarity_top_k reduced: {old_k} -> {new_k}",
                                migration_note=(
                                    "Reducing similarity_top_k may lower retrieval quality. "
                                    "Verify the new value suits your use case."
                                ),
                                line=line_no,
                            ))

            # response_mode= removed -> medium
            if LLAMA_RESPONSE_MODE_RE.search(line):
                findings.append(Finding(
                    severity="medium",
                    path=rel_path,
                    message="LlamaIndex response_mode parameter removed",
                    migration_note=(
                        "Removing response_mode= may change how LlamaIndex synthesizes "
                        "responses. Review the updated query engine configuration."
                    ),
                    line=line_no,
                ))

            # node_postprocessors= removed -> high
            if LLAMA_POSTPROCESSORS_RE.search(line):
                findings.append(Finding(
                    severity="high",
                    path=rel_path,
                    message="LlamaIndex node_postprocessors removed (guardrail removal)",
                    migration_note=(
                        "Removing node_postprocessors= disables filtering/re-ranking of "
                        "retrieved nodes, which may act as a guardrail. Review the change."
                    ),
                    line=line_no,
                ))

    return findings
