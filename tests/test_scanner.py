"""Comprehensive unit tests for llm-prompt-radar."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_prompt_radar.scanner import (
    Finding,
    _overall_risk,
    _semver_recommendation,
    summarize,
)
from llm_prompt_radar.prompt_analyzer import is_prompt_file, analyze_prompt_files
from llm_prompt_radar.code_analyzer import analyze_code_files, _is_downgrade
from llm_prompt_radar.reporter import (
    format_text,
    format_json,
    format_markdown,
    format_github,
    format_sarif,
    generate_badge,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SENTINEL = object()


def _make_report(risk="medium", finding_count=2, change_count=3, findings=_SENTINEL):
    if findings is _SENTINEL:
        findings = [
            {
                "severity": "medium",
                "path": "a.py",
                "message": "LLM parameter was changed: 'temperature'",
                "migration_note": "Check the temperature setting.",
                "line": 10,
            }
        ]
    return {
        "risk_level": risk,
        "finding_count": finding_count,
        "change_count": change_count,
        "changed_files": ["a.py", "b.prompt"],
        "findings": findings,
        "semver_recommendation": "minor",
    }


# ---------------------------------------------------------------------------
# is_prompt_file
# ---------------------------------------------------------------------------

class TestIsPromptFile(unittest.TestCase):

    def test_jinja_extension(self):
        self.assertTrue(is_prompt_file("system.jinja"))

    def test_jinja2_extension(self):
        self.assertTrue(is_prompt_file("templates/chat.jinja2"))

    def test_j2_extension(self):
        self.assertTrue(is_prompt_file("prompts/base.j2"))

    def test_prompt_extension(self):
        self.assertTrue(is_prompt_file("my_template.prompt"))

    def test_system_prompt_filename(self):
        self.assertTrue(is_prompt_file("system_prompt.txt"))

    def test_system_txt_filename(self):
        self.assertTrue(is_prompt_file("system.txt"))

    def test_prompt_txt_filename(self):
        self.assertTrue(is_prompt_file("some/dir/prompt.txt"))

    def test_instructions_txt_filename(self):
        self.assertTrue(is_prompt_file("instructions.txt"))

    def test_regular_python_file(self):
        self.assertFalse(is_prompt_file("main.py"))

    def test_regular_txt_file(self):
        self.assertFalse(is_prompt_file("readme.txt"))

    def test_json_file(self):
        self.assertFalse(is_prompt_file("config.json"))

    def test_case_insensitive_extension(self):
        self.assertTrue(is_prompt_file("MyTemplate.JINJA"))

    def test_case_insensitive_filename(self):
        self.assertTrue(is_prompt_file("SYSTEM_PROMPT.TXT"))


# ---------------------------------------------------------------------------
# _overall_risk
# ---------------------------------------------------------------------------

class TestOverallRisk(unittest.TestCase):

    def test_empty_findings(self):
        self.assertEqual(_overall_risk([]), "none")

    def test_single_low(self):
        findings = [Finding("low", "a.py", "msg", "note")]
        self.assertEqual(_overall_risk(findings), "low")

    def test_single_critical(self):
        findings = [Finding("critical", "a.py", "msg", "note")]
        self.assertEqual(_overall_risk(findings), "critical")

    def test_mixed_severities(self):
        findings = [
            Finding("low", "a.py", "msg", "note"),
            Finding("high", "b.py", "msg", "note"),
            Finding("medium", "c.py", "msg", "note"),
        ]
        self.assertEqual(_overall_risk(findings), "high")

    def test_critical_wins(self):
        findings = [
            Finding("high", "a.py", "msg", "note"),
            Finding("critical", "b.py", "msg", "note"),
            Finding("medium", "c.py", "msg", "note"),
        ]
        self.assertEqual(_overall_risk(findings), "critical")

    def test_all_none_equivalent(self):
        # unknown severity gets treated as none (index error safe)
        findings = [Finding("none", "a.py", "msg", "note")]
        self.assertEqual(_overall_risk(findings), "none")


# ---------------------------------------------------------------------------
# _semver_recommendation
# ---------------------------------------------------------------------------

class TestSemverRecommendation(unittest.TestCase):

    def test_none(self):
        self.assertEqual(_semver_recommendation("none"), "patch")

    def test_low(self):
        self.assertEqual(_semver_recommendation("low"), "patch")

    def test_medium(self):
        self.assertEqual(_semver_recommendation("medium"), "minor")

    def test_high(self):
        self.assertEqual(_semver_recommendation("high"), "major")

    def test_critical(self):
        self.assertEqual(_semver_recommendation("critical"), "major")

    def test_unknown(self):
        # unknown risk → patch (default)
        self.assertEqual(_semver_recommendation("unknown"), "patch")


# ---------------------------------------------------------------------------
# format_text
# ---------------------------------------------------------------------------

class TestFormatText(unittest.TestCase):

    def test_contains_risk_level(self):
        report = _make_report()
        out = format_text(report)
        self.assertIn("MEDIUM", out)

    def test_contains_finding_count(self):
        report = _make_report()
        out = format_text(report)
        self.assertIn("2", out)

    def test_no_findings_message(self):
        report = _make_report(risk="none", finding_count=0, findings=[])
        out = format_text(report)
        self.assertIn("No issues", out)

    def test_finding_details(self):
        report = _make_report()
        out = format_text(report)
        self.assertIn("a.py", out)
        self.assertIn("LLM parameter was changed", out)

    def test_semver_in_output(self):
        report = _make_report()
        out = format_text(report)
        self.assertIn("minor", out)


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------

class TestFormatJson(unittest.TestCase):

    def test_valid_json(self):
        report = _make_report()
        out = format_json(report)
        parsed = json.loads(out)
        self.assertEqual(parsed["risk_level"], "medium")

    def test_findings_present(self):
        report = _make_report()
        out = format_json(report)
        parsed = json.loads(out)
        self.assertEqual(len(parsed["findings"]), 1)

    def test_indented(self):
        report = _make_report()
        out = format_json(report)
        self.assertIn("\n", out)


# ---------------------------------------------------------------------------
# format_markdown
# ---------------------------------------------------------------------------

class TestFormatMarkdown(unittest.TestCase):

    def test_contains_heading(self):
        report = _make_report()
        out = format_markdown(report)
        self.assertIn("llm-prompt-radar Report", out)

    def test_contains_risk(self):
        report = _make_report()
        out = format_markdown(report)
        self.assertIn("MEDIUM", out)

    def test_no_issues_message(self):
        report = _make_report(risk="none", finding_count=0, findings=[])
        out = format_markdown(report)
        self.assertIn("No issues", out)

    def test_finding_in_output(self):
        report = _make_report()
        out = format_markdown(report)
        self.assertIn("a.py", out)

    def test_markdown_table(self):
        report = _make_report()
        out = format_markdown(report)
        self.assertIn("|", out)


# ---------------------------------------------------------------------------
# format_github
# ---------------------------------------------------------------------------

class TestFormatGithub(unittest.TestCase):

    def test_warning_for_medium(self):
        report = _make_report()
        out = format_github(report)
        self.assertIn("::warning", out)

    def test_error_for_critical(self):
        report = _make_report(
            risk="critical",
            finding_count=1,
            findings=[{
                "severity": "critical",
                "path": "prompt.txt",
                "message": "Safety removed",
                "migration_note": "Check safety",
                "line": 5,
            }],
        )
        out = format_github(report)
        self.assertIn("::error", out)

    def test_summary_notice(self):
        report = _make_report()
        out = format_github(report)
        self.assertIn("::notice title=llm-prompt-radar", out)


# ---------------------------------------------------------------------------
# format_sarif
# ---------------------------------------------------------------------------

class TestFormatSarif(unittest.TestCase):

    def test_valid_json(self):
        report = _make_report()
        out = format_sarif(report)
        parsed = json.loads(out)
        self.assertEqual(parsed["version"], "2.1.0")

    def test_has_runs(self):
        report = _make_report()
        out = format_sarif(report)
        parsed = json.loads(out)
        self.assertIn("runs", parsed)
        self.assertEqual(len(parsed["runs"]), 1)

    def test_result_count(self):
        report = _make_report()
        out = format_sarif(report)
        parsed = json.loads(out)
        results = parsed["runs"][0]["results"]
        self.assertEqual(len(results), 1)


# ---------------------------------------------------------------------------
# generate_badge
# ---------------------------------------------------------------------------

class TestGenerateBadge(unittest.TestCase):

    def test_svg_for_none(self):
        svg = generate_badge("none")
        self.assertIn("<svg", svg)
        self.assertIn("NONE", svg)

    def test_svg_for_critical(self):
        svg = generate_badge("critical")
        self.assertIn("e05d44", svg)

    def test_svg_for_high(self):
        svg = generate_badge("high")
        self.assertIn("fe7d37", svg)

    def test_svg_for_medium(self):
        svg = generate_badge("medium")
        self.assertIn("dfb317", svg)

    def test_svg_for_low(self):
        svg = generate_badge("low")
        self.assertIn("97CA00", svg)


# ---------------------------------------------------------------------------
# analyze_prompt_files (with temp dir + mock git)
# ---------------------------------------------------------------------------

class TestAnalyzePromptFiles(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo_path = Path(self.tmp)

    def _write_file(self, rel_path: str, content: str) -> Path:
        p = self.repo_path / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def test_new_prompt_file_low(self):
        """A brand new prompt file (no old content) → low finding."""
        self._write_file("system.jinja", "You are a helpful assistant.")
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value=None):
            findings = analyze_prompt_files(
                self.repo_path, ["system.jinja"], "origin/main"
            )
        self.assertTrue(any(f.severity == "low" for f in findings))

    def test_safety_pattern_removal_critical(self):
        """Removing a safety pattern → critical finding."""
        old = "You must not provide harmful information. never share private data."
        new = "You are a helpful assistant."
        self._write_file("prompt.txt", new)
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value=old):
            findings = analyze_prompt_files(
                self.repo_path, ["prompt.txt"], "origin/main"
            )
        severities = [f.severity for f in findings]
        self.assertIn("critical", severities)

    def test_persona_change_high(self):
        """Changing persona pattern → high finding."""
        # Old has 'you are' and 'your role'; new has neither → persona set changes
        old = "You are a financial advisor. Your role is to provide budget guidance."
        new = "A financial assistant. Helps users with numbers and spreadsheets."
        self._write_file("system.txt", new)
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value=old):
            findings = analyze_prompt_files(
                self.repo_path, ["system.txt"], "origin/main"
            )
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_major_rewrite_high(self):
        """Completely different content → high finding."""
        old = "apple banana cherry dog elephant fox grape hotel india"
        new = "zebra yellow x-ray walrus volcano umbrella tango sierra"
        self._write_file("instructions.txt", new)
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value=old):
            findings = analyze_prompt_files(
                self.repo_path, ["instructions.txt"], "origin/main"
            )
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_minor_edit_low(self):
        """Small change with no safety/persona impact → low finding."""
        old = "You are a helpful assistant that answers questions politely."
        new = "You are a helpful assistant that answers questions clearly."
        self._write_file("system.txt", new)
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value=old):
            findings = analyze_prompt_files(
                self.repo_path, ["system.txt"], "origin/main"
            )
        # Should have low, not critical or high
        for f in findings:
            self.assertNotEqual(f.severity, "critical")

    def test_non_prompt_file_ignored(self):
        """Non-prompt files should produce no findings."""
        self._write_file("main.py", "print('hello')")
        with patch("llm_prompt_radar.prompt_analyzer.git_file_at_ref", return_value="print('world')"):
            findings = analyze_prompt_files(
                self.repo_path, ["main.py"], "origin/main"
            )
        self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# Model downgrade detection
# ---------------------------------------------------------------------------

class TestModelDowngrade(unittest.TestCase):

    def test_gpt4_to_gpt35_is_downgrade(self):
        self.assertTrue(_is_downgrade("gpt-4", "gpt-3.5-turbo"))

    def test_gpt35_to_gpt4_is_not_downgrade(self):
        self.assertFalse(_is_downgrade("gpt-3.5-turbo", "gpt-4"))

    def test_claude_opus_to_haiku_is_downgrade(self):
        self.assertTrue(_is_downgrade("claude-3-opus", "claude-3-haiku"))

    def test_same_model_not_downgrade(self):
        self.assertFalse(_is_downgrade("gpt-4", "gpt-4"))

    def test_unknown_models_not_downgrade(self):
        self.assertFalse(_is_downgrade("my-custom-model", "other-custom-model"))

    def test_downgrade_detected_in_diff(self):
        diff = """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-model="gpt-4"
+model="gpt-3.5-turbo"
 other_code()
"""
        findings = analyze_code_files(Path("/tmp"), ["app.py"], "origin/main", diff)
        self.assertTrue(any("downgraded" in f.message.lower() or f.severity == "critical" for f in findings))


# ---------------------------------------------------------------------------
# Safety pattern removal in code
# ---------------------------------------------------------------------------

class TestSafetyPatternInCode(unittest.TestCase):

    def test_safety_removal_in_code_critical(self):
        diff = """--- a/llm_client.py
+++ b/llm_client.py
@@ -5,7 +5,6 @@
-    system_msg = "You must never provide harmful information or illegal advice."
+    system_msg = "You are a helpful assistant."
     response = client.chat(messages)
"""
        findings = analyze_code_files(Path("/tmp"), ["llm_client.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("critical", severities)

    def test_system_message_change_high(self):
        diff = """--- a/client.py
+++ b/client.py
@@ -2,7 +2,7 @@
-    {"role": "system", "content": "Be helpful."}
+    {"role": "user", "content": "Be helpful."}
"""
        findings = analyze_code_files(Path("/tmp"), ["client.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_temperature_change_medium(self):
        diff = """--- a/app.py
+++ b/app.py
@@ -1,3 +1,3 @@
-temperature=0.2
+temperature=1.0
"""
        findings = analyze_code_files(Path("/tmp"), ["app.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("medium", severities)

    def test_non_code_file_ignored(self):
        diff = """--- a/README.md
+++ b/README.md
@@ -1,2 +1,2 @@
-model="gpt-4"
+model="gpt-3.5-turbo"
"""
        findings = analyze_code_files(Path("/tmp"), ["README.md"], "origin/main", diff)
        self.assertEqual(findings, [])


# ---------------------------------------------------------------------------
# summarize
# ---------------------------------------------------------------------------

class TestSummarize(unittest.TestCase):

    def test_empty(self):
        report = summarize([], [], Path("/tmp"))
        self.assertEqual(report["risk_level"], "none")
        self.assertEqual(report["finding_count"], 0)
        self.assertEqual(report["semver_recommendation"], "patch")

    def test_with_findings(self):
        findings = [
            Finding("high", "a.py", "msg", "note"),
            Finding("medium", "b.py", "msg", "note"),
        ]
        report = summarize(findings, ["a.py", "b.py"], Path("/tmp"))
        self.assertEqual(report["risk_level"], "high")
        self.assertEqual(report["finding_count"], 2)
        self.assertEqual(report["change_count"], 2)
        self.assertEqual(report["semver_recommendation"], "major")

    def test_findings_as_dicts(self):
        findings = [Finding("low", "x.py", "msg", "note", line=5)]
        report = summarize(findings, ["x.py"], Path("/tmp"))
        self.assertIsInstance(report["findings"], list)
        self.assertIsInstance(report["findings"][0], dict)
        self.assertEqual(report["findings"][0]["line"], 5)


if __name__ == "__main__":
    unittest.main()
