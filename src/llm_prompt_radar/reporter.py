"""Output formatters for llm-prompt-radar."""
from __future__ import annotations

import json

# Severity emoji map
_EMOJI = {
    "critical": "🚨",
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
    "none": "✅",
}

_BADGE_COLORS = {
    "none": "#4c1",       # brightgreen
    "low": "#97CA00",     # green
    "medium": "#dfb317",  # yellow
    "high": "#fe7d37",    # orange
    "critical": "#e05d44",# red
}


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def format_text(report: dict) -> str:
    lines = []
    risk = report.get("risk_level", "none")
    emoji = _EMOJI.get(risk, "")
    lines.append("=" * 60)
    lines.append("  llm-prompt-radar scan report")
    lines.append("=" * 60)
    lines.append(f"  Risk level        : {emoji} {risk.upper()}")
    lines.append(f"  Findings          : {report.get('finding_count', 0)}")
    lines.append(f"  Files changed     : {report.get('change_count', 0)}")
    lines.append(f"  Semver suggestion : {report.get('semver_recommendation', 'patch')}")
    lines.append("")

    findings = report.get("findings", [])
    if not findings:
        lines.append("  No issues found. 🎉")
    else:
        for f in findings:
            sev = f.get("severity", "low")
            e = _EMOJI.get(sev, "")
            lines.append(f"  [{e} {sev.upper()}] {f.get('path', '')}:{f.get('line', 1)}")
            lines.append(f"    {f.get('message', '')}")
            lines.append(f"    → {f.get('migration_note', '')}")
            lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def format_json(report: dict) -> str:
    return json.dumps(report, indent=2)


# ---------------------------------------------------------------------------
# Markdown (GitHub PR comment style)
# ---------------------------------------------------------------------------

def format_markdown(report: dict) -> str:
    risk = report.get("risk_level", "none")
    emoji = _EMOJI.get(risk, "")
    lines = []
    lines.append(f"## {emoji} llm-prompt-radar Report")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|---|---|")
    lines.append(f"| **Risk Level** | `{risk.upper()}` |")
    lines.append(f"| **Findings** | {report.get('finding_count', 0)} |")
    lines.append(f"| **Files Changed** | {report.get('change_count', 0)} |")
    lines.append(f"| **Semver Suggestion** | `{report.get('semver_recommendation', 'patch')}` |")
    lines.append("")

    findings = report.get("findings", [])
    if not findings:
        lines.append("> ✅ No issues detected.")
    else:
        lines.append("### Findings")
        lines.append("")
        for f in findings:
            sev = f.get("severity", "low")
            e = _EMOJI.get(sev, "")
            lines.append(f"#### {e} `{sev.upper()}` — {f.get('path', '')} (line {f.get('line', 1)})")
            lines.append("")
            lines.append(f"**{f.get('message', '')}**")
            lines.append("")
            lines.append(f"> {f.get('migration_note', '')}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub Actions workflow commands
# ---------------------------------------------------------------------------

def format_github(report: dict) -> str:
    lines = []
    risk = report.get("risk_level", "none")
    findings = report.get("findings", [])

    for f in findings:
        sev = f.get("severity", "low")
        path = f.get("path", "")
        line = f.get("line", 1)
        msg = f.get("message", "")
        note = f.get("migration_note", "")
        full_msg = f"{msg} | {note}"

        if sev in ("critical", "high"):
            cmd = "error"
        elif sev == "medium":
            cmd = "warning"
        else:
            cmd = "notice"

        lines.append(f"::{cmd} file={path},line={line}::{full_msg}")

    # Summary
    lines.append(
        f"::notice title=llm-prompt-radar::Risk={risk.upper()} "
        f"Findings={report.get('finding_count', 0)} "
        f"Semver={report.get('semver_recommendation', 'patch')}"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SARIF 2.1.0
# ---------------------------------------------------------------------------

_SARIF_LEVELS = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "none": "none",
}


def format_sarif(report: dict) -> str:
    findings = report.get("findings", [])
    rules: dict[str, dict] = {}
    results = []

    for f in findings:
        sev = f.get("severity", "low")
        msg = f.get("message", "")
        rule_id = "LLM" + sev.upper()[:3] + re.sub(r"[^a-zA-Z0-9]", "", msg)[:20]

        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": msg[:64],
                "shortDescription": {"text": msg},
                "fullDescription": {"text": f.get("migration_note", msg)},
                "defaultConfiguration": {
                    "level": _SARIF_LEVELS.get(sev, "warning")
                },
            }

        results.append({
            "ruleId": rule_id,
            "level": _SARIF_LEVELS.get(sev, "warning"),
            "message": {
                "text": f"{msg}\n\n{f.get('migration_note', '')}"
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f.get("path", ""),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": {
                            "startLine": max(1, f.get("line", 1)),
                        },
                    }
                }
            ],
        })

    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "llm-prompt-radar",
                        "version": "0.1.0",
                        "informationUri": "https://github.com/example/llm-prompt-radar",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(sarif, indent=2)


# ---------------------------------------------------------------------------
# SVG Badge
# ---------------------------------------------------------------------------

def generate_badge(risk_level: str) -> str:
    """Return SVG badge content for the given risk level."""
    color = _BADGE_COLORS.get(risk_level, _BADGE_COLORS["none"])
    label = "llm-radar"
    value = risk_level.upper()
    label_width = 80
    value_width = max(60, len(value) * 8 + 10)
    total_width = label_width + value_width

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total_width}" height="20">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{value_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="{label_width // 2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_width // 2}" y="14">{label}</text>
    <text x="{label_width + value_width // 2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{label_width + value_width // 2}" y="14">{value}</text>
  </g>
</svg>"""
    return svg


# Need re for SARIF rule ID generation
import re  # noqa: E402
