"""CLI entry point for llm-prompt-radar."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from llm_prompt_radar import prompt_analyzer, code_analyzer, config_analyzer, reporter, scanner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-prompt-radar",
        description="Detect risky changes to LLM prompts and AI configuration before they ship.",
    )
    parser.add_argument("--repo", default=".", help="Path to git repository.")
    parser.add_argument("--base", default="origin/main", help="Base ref to diff against.")
    parser.add_argument(
        "--format",
        choices=("text", "json", "markdown", "github", "sarif"),
        default="text",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "low", "medium", "high", "critical"),
        default="high",
    )
    parser.add_argument(
        "--badge",
        action="store_true",
        help="Write llm-radar-badge.svg to repo root.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_path = Path(args.repo).resolve()

    changed_files = scanner.git_changed_files(repo_path, args.base)
    deleted_files = scanner.git_deleted_files(repo_path, args.base)
    diff_text = scanner.git_diff(repo_path, args.base)

    findings = []
    findings.extend(prompt_analyzer.analyze_prompt_files(repo_path, changed_files, args.base))
    findings.extend(
        code_analyzer.analyze_code_files(repo_path, changed_files, args.base, diff_text)
    )
    findings.extend(
        config_analyzer.analyze_config_files(repo_path, changed_files, args.base, diff_text)
    )

    report = scanner.summarize(findings, changed_files, repo_path)

    if args.badge:
        try:
            badge = reporter.generate_badge(str(report["risk_level"]))
            (repo_path / "llm-radar-badge.svg").write_text(badge, encoding="utf-8")
        except Exception:
            pass

    if args.format == "json":
        print(reporter.format_json(report))
    elif args.format == "markdown":
        print(reporter.format_markdown(report))
    elif args.format == "github":
        print(reporter.format_github(report))
    elif args.format == "sarif":
        print(reporter.format_sarif(report))
    else:
        print(reporter.format_text(report))

    risk_order = ["none", "low", "medium", "high", "critical"]
    if risk_order.index(str(report["risk_level"])) >= risk_order.index(args.fail_on):
        if args.fail_on != "none":
            sys.exit(1)


if __name__ == "__main__":
    main()
