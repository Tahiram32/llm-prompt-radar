"""Load optional .promptradar.yml or .promptradar.toml config from repo root."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# TOML parsing (stdlib tomllib on 3.11+, manual fallback for 3.10)
# ---------------------------------------------------------------------------

try:
    import tomllib  # Python 3.11+
    _HAS_TOMLLIB = True
except ImportError:
    _HAS_TOMLLIB = False


def _parse_toml_simple(text: str) -> dict:
    """
    Minimal TOML parser covering the subset used by .promptradar.toml.

    Supports:
    - key = "value"  (strings)
    - key = true / false  (booleans)
    - [[custom-rules]] array-of-tables
    - [ignore] section with paths = [...]
    """
    result: dict = {}
    current_section: str | None = None
    array_table_key: str | None = None
    i = 0
    lines = text.splitlines()

    while i < len(lines):
        line = lines[i].strip()

        # Skip comments and blanks
        if not line or line.startswith("#"):
            i += 1
            continue

        # Array-of-tables header: [[key]]
        m = re.match(r"^\[\[([^\]]+)\]\]$", line)
        if m:
            array_table_key = m.group(1).strip()
            current_section = None
            if array_table_key not in result:
                result[array_table_key] = []
            result[array_table_key].append({})
            i += 1
            continue

        # Section header: [key]
        m = re.match(r"^\[([^\]]+)\]$", line)
        if m:
            current_section = m.group(1).strip()
            array_table_key = None
            if current_section not in result:
                result[current_section] = {}
            i += 1
            continue

        # Key = value
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*=\s*(.+)$', line)
        if m:
            key = m.group(1).strip()
            raw_val = m.group(2).strip()

            # Multi-line array: collect until closing ]
            if raw_val.startswith("[") and "]" not in raw_val:
                arr_lines = [raw_val]
                i += 1
                while i < len(lines):
                    arr_lines.append(lines[i].strip())
                    if "]" in lines[i]:
                        break
                    i += 1
                raw_val = " ".join(arr_lines)

            value = _parse_toml_value(raw_val)

            if array_table_key is not None:
                # We're inside a [[...]] table
                result[array_table_key][-1][key] = value
            elif current_section is not None:
                result[current_section][key] = value
            else:
                result[key] = value

        i += 1

    return result


def _parse_toml_value(raw: str):
    """Parse a simple TOML scalar or inline array."""
    raw = raw.strip()
    # Boolean
    if raw == "true":
        return True
    if raw == "false":
        return False
    # String (quoted)
    m = re.match(r'^"([^"]*)"$', raw)
    if m:
        return m.group(1)
    m = re.match(r"^'([^']*)'$", raw)
    if m:
        return m.group(1)
    # Inline array: ["a", "b", ...]
    m = re.match(r"^\[(.+)\]$", raw, re.DOTALL)
    if m:
        inner = m.group(1)
        items = re.findall(r'"([^"]*)"', inner)
        return items
    # Integer
    m = re.match(r"^-?\d+$", raw)
    if m:
        return int(raw)
    # Float
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# YAML parsing (manual, no pyyaml)
# ---------------------------------------------------------------------------

def _parse_yaml_simple(text: str) -> dict:
    """
    Minimal YAML parser covering the subset used by .promptradar.yml.

    Supports:
    - key: value  (strings, booleans)
    - key:        (introduces a mapping or list block)
    - - item      (list items, indented under a key)
    - custom-rules as list of mappings
    """
    result: dict = {}
    lines = text.splitlines()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip comments and blanks
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Top-level key: value or key:
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line)
        if m and not line.startswith(" ") and not line.startswith("\t"):
            key = m.group(1).strip()
            value_str = m.group(2).strip()

            if value_str:
                result[key] = _parse_yaml_value(value_str)
                i += 1
            else:
                # Block: collect indented sub-lines
                i += 1
                sub_lines = []
                while i < len(lines):
                    sub = lines[i]
                    if sub.strip() == "" or sub.strip().startswith("#"):
                        i += 1
                        continue
                    if sub.startswith(" ") or sub.startswith("\t"):
                        sub_lines.append(sub)
                        i += 1
                    else:
                        break

                result[key] = _parse_yaml_block(sub_lines)
        else:
            i += 1

    return result


def _parse_yaml_value(raw: str):
    """Parse a simple YAML scalar."""
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() in ("null", "~"):
        return None
    # Quoted string
    m = re.match(r'^"([^"]*)"$', raw)
    if m:
        return m.group(1)
    m = re.match(r"^'([^']*)'$", raw)
    if m:
        return m.group(1)
    # Integer
    m = re.match(r"^-?\d+$", raw)
    if m:
        return int(raw)
    # Float
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_yaml_block(sub_lines: list) -> object:
    """Parse an indented YAML block as either a list or a mapping."""
    if not sub_lines:
        return {}

    # Detect if it's a list (first non-blank starts with "- ")
    first = sub_lines[0].strip() if sub_lines else ""
    if first.startswith("- "):
        return _parse_yaml_list(sub_lines)
    else:
        return _parse_yaml_mapping(sub_lines)


def _parse_yaml_list(sub_lines: list) -> list:
    """Parse an indented YAML list, possibly of mappings."""
    items = []
    current_item_lines: list = []

    for line in sub_lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_item_lines:
                items.append(_resolve_yaml_item(current_item_lines))
            # Start new item; treat the rest of the line as first entry
            rest = stripped[2:].strip()
            current_item_lines = [rest] if rest else []
        elif stripped and current_item_lines is not None:
            current_item_lines.append(stripped)

    if current_item_lines:
        items.append(_resolve_yaml_item(current_item_lines))

    return items


def _resolve_yaml_item(lines: list):
    """Resolve a single list item (scalar or mapping from sub-lines)."""
    if not lines:
        return None
    if len(lines) == 1 and ":" not in lines[0]:
        return _parse_yaml_value(lines[0])
    # It's a mapping
    mapping = {}
    for line in lines:
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line.strip())
        if m:
            mapping[m.group(1).strip()] = _parse_yaml_value(m.group(2).strip())
    return mapping


def _parse_yaml_mapping(sub_lines: list) -> dict:
    """Parse an indented YAML mapping block."""
    mapping = {}
    for line in sub_lines:
        m = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line.strip())
        if m:
            mapping[m.group(1).strip()] = _parse_yaml_value(m.group(2).strip())
    return mapping


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_YAML_NAMES = [".promptradar.yml", ".promptradar.yaml"]
_TOML_NAMES = [".promptradar.toml"]


def load_config(repo_path: Path, config_file: Path | None = None) -> dict:
    """
    Load configuration from a .promptradar.yml or .promptradar.toml file.

    If *config_file* is given, load only that file.
    Otherwise auto-detect from *repo_path*.

    Returns a (possibly empty) dict.
    """
    if config_file is not None:
        return _load_file(config_file)

    for name in _YAML_NAMES:
        candidate = repo_path / name
        if candidate.exists():
            return _load_file(candidate)

    for name in _TOML_NAMES:
        candidate = repo_path / name
        if candidate.exists():
            return _load_file(candidate)

    return {}


def _load_file(path: Path) -> dict:
    """Load and parse a single config file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[llm-prompt-radar] Warning: could not read config {path}: {exc}", file=sys.stderr)
        return {}

    suffix = path.suffix.lower()

    if suffix in {".yml", ".yaml"}:
        try:
            return _parse_yaml_simple(text)
        except Exception as exc:
            print(f"[llm-prompt-radar] Warning: failed to parse YAML config: {exc}", file=sys.stderr)
            return {}

    if suffix == ".toml":
        if _HAS_TOMLLIB:
            try:
                return tomllib.loads(text)
            except Exception as exc:
                print(f"[llm-prompt-radar] Warning: tomllib parse error: {exc}", file=sys.stderr)
                return {}
        else:
            try:
                return _parse_toml_simple(text)
            except Exception as exc:
                print(f"[llm-prompt-radar] Warning: failed to parse TOML config: {exc}", file=sys.stderr)
                return {}

    print(f"[llm-prompt-radar] Warning: unknown config file extension: {path}", file=sys.stderr)
    return {}


# ---------------------------------------------------------------------------
# Merge config with CLI args
# ---------------------------------------------------------------------------

# Mapping from config key -> (argparse dest, argparse default value).
# CLI values win when the user explicitly set them (i.e. value differs from default).
_CONFIG_KEY_MAP: dict = {
    "fail-on": ("fail_on", "high"),
    "format": ("format", "text"),
    "base-ref": ("base", "origin/main"),
    "badge": ("badge", False),
}


def merge_config_with_args(config: dict, args: argparse.Namespace) -> argparse.Namespace:
    """
    Merge config-file values into *args*.

    CLI args win when they differ from their default value.
    Config file values fill in only when the CLI arg is still at its default.
    """
    for cfg_key, (dest, default) in _CONFIG_KEY_MAP.items():
        if cfg_key not in config:
            continue
        cfg_val = config[cfg_key]
        cli_val = getattr(args, dest, default)
        # Only override if CLI arg is still at the default
        if cli_val == default:
            setattr(args, dest, cfg_val)

    return args
