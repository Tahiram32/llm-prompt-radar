"""New tests for config_loader, langchain_analyzer, and custom_rules."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from llm_prompt_radar.config_loader import (
    _parse_yaml_simple,
    _parse_toml_simple,
    load_config,
    merge_config_with_args,
)
from llm_prompt_radar.custom_rules import apply_custom_rules
from llm_prompt_radar.langchain_analyzer import analyze_langchain_files
import argparse
import tempfile


# ---------------------------------------------------------------------------
# config_loader — YAML
# ---------------------------------------------------------------------------

class TestConfigLoaderYaml(unittest.TestCase):

    def test_config_loader_yaml_basic(self):
        """Parses a minimal YAML string correctly."""
        yaml = (
            "fail-on: high\n"
            "format: github\n"
            "base-ref: origin/main\n"
            "badge: false\n"
        )
        result = _parse_yaml_simple(yaml)
        self.assertEqual(result["fail-on"], "high")
        self.assertEqual(result["format"], "github")
        self.assertEqual(result["base-ref"], "origin/main")
        self.assertEqual(result["badge"], False)

    def test_config_loader_yaml_custom_rules(self):
        """Parses YAML custom-rules list of mappings."""
        yaml = (
            "custom-rules:\n"
            "  - id: my-rule\n"
            "    description: Catches leaking of API keys\n"
            "    severity: critical\n"
            "    pattern: (sk-[a-zA-Z0-9]{32,})\n"
        )
        result = _parse_yaml_simple(yaml)
        self.assertIn("custom-rules", result)
        rules = result["custom-rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "my-rule")
        self.assertEqual(rules[0]["severity"], "critical")

    def test_config_loader_yaml_ignore(self):
        """Parses YAML ignore list."""
        yaml = (
            "ignore:\n"
            "  - tests/fixtures/**\n"
            "  - docs/**\n"
        )
        result = _parse_yaml_simple(yaml)
        self.assertIn("ignore", result)
        self.assertIsInstance(result["ignore"], list)
        self.assertIn("tests/fixtures/**", result["ignore"])

    def test_config_loader_yaml_from_file(self):
        """load_config reads a .promptradar.yml from repo root."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".promptradar.yml"
            p.write_text("fail-on: medium\nformat: json\n", encoding="utf-8")
            cfg = load_config(Path(tmp))
        self.assertEqual(cfg.get("fail-on"), "medium")
        self.assertEqual(cfg.get("format"), "json")

    def test_config_loader_yaml_missing_file(self):
        """load_config returns empty dict when no config file exists."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = load_config(Path(tmp))
        self.assertEqual(cfg, {})


# ---------------------------------------------------------------------------
# config_loader — TOML
# ---------------------------------------------------------------------------

class TestConfigLoaderToml(unittest.TestCase):

    def test_config_loader_toml_basic(self):
        """Parses a minimal TOML string correctly."""
        toml = (
            'fail-on = "high"\n'
            'format = "github"\n'
            'base-ref = "origin/main"\n'
            "badge = false\n"
        )
        result = _parse_toml_simple(toml)
        self.assertEqual(result["fail-on"], "high")
        self.assertEqual(result["format"], "github")
        self.assertEqual(result["base-ref"], "origin/main")
        self.assertEqual(result["badge"], False)

    def test_config_loader_toml_custom_rules(self):
        """Parses TOML [[custom-rules]] array-of-tables."""
        toml = (
            "[[custom-rules]]\n"
            'id = "my-rule"\n'
            'description = "Catches leaking of API keys"\n'
            'severity = "critical"\n'
            'pattern = "(sk-[a-zA-Z0-9]{32,})"\n'
        )
        result = _parse_toml_simple(toml)
        self.assertIn("custom-rules", result)
        rules = result["custom-rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["id"], "my-rule")
        self.assertEqual(rules[0]["severity"], "critical")

    def test_config_loader_toml_ignore_section(self):
        """Parses TOML [ignore] section with paths array."""
        toml = (
            "[ignore]\n"
            'paths = ["tests/fixtures/**", "docs/**"]\n'
        )
        result = _parse_toml_simple(toml)
        self.assertIn("ignore", result)
        self.assertIn("paths", result["ignore"])
        self.assertIn("tests/fixtures/**", result["ignore"]["paths"])

    def test_config_loader_toml_from_file(self):
        """load_config reads a .promptradar.toml from repo root."""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / ".promptradar.toml"
            p.write_text('fail-on = "medium"\nformat = "json"\n', encoding="utf-8")
            cfg = load_config(Path(tmp))
        self.assertEqual(cfg.get("fail-on"), "medium")
        self.assertEqual(cfg.get("format"), "json")

    def test_config_loader_yaml_preferred_over_toml(self):
        """When both .yml and .toml exist, YAML is preferred."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".promptradar.yml").write_text(
                "fail-on: critical\n", encoding="utf-8"
            )
            (Path(tmp) / ".promptradar.toml").write_text(
                'fail-on = "none"\n', encoding="utf-8"
            )
            cfg = load_config(Path(tmp))
        self.assertEqual(cfg.get("fail-on"), "critical")


# ---------------------------------------------------------------------------
# merge_config_with_args
# ---------------------------------------------------------------------------

class TestMergeConfigWithArgs(unittest.TestCase):

    def _make_args(self, **kwargs):
        defaults = {
            "fail_on": "high",
            "format": "text",
            "base": "origin/main",
            "badge": False,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_config_fills_defaults(self):
        """Config values fill in when CLI args are at defaults."""
        config = {"fail-on": "medium", "format": "github"}
        args = self._make_args()
        result = merge_config_with_args(config, args)
        self.assertEqual(result.fail_on, "medium")
        self.assertEqual(result.format, "github")

    def test_cli_wins_over_config(self):
        """CLI args win when they differ from the default."""
        config = {"fail-on": "medium"}
        args = self._make_args(fail_on="critical")  # user explicitly passed --fail-on critical
        result = merge_config_with_args(config, args)
        self.assertEqual(result.fail_on, "critical")

    def test_empty_config_no_change(self):
        """Empty config leaves args unchanged."""
        args = self._make_args()
        result = merge_config_with_args({}, args)
        self.assertEqual(result.fail_on, "high")
        self.assertEqual(result.format, "text")


# ---------------------------------------------------------------------------
# custom_rules
# ---------------------------------------------------------------------------

class TestCustomRulesMatch(unittest.TestCase):

    def _rule(self, pattern, severity="critical", rule_id="test-rule"):
        return {
            "id": rule_id,
            "description": "Test rule",
            "severity": severity,
            "pattern": pattern,
        }

    def test_custom_rules_match(self):
        """A rule that matches an added line produces a Finding."""
        diff = (
            "--- a/secrets.py\n"
            "+++ b/secrets.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing = 'x'\n"
            "+api_key = 'sk-abcdefghijklmnopqrstuvwxyz1234567890'\n"
        )
        rules = [self._rule(r"sk-[a-zA-Z0-9]{32,}")]
        findings = apply_custom_rules(rules, diff, ["secrets.py"])
        self.assertTrue(len(findings) > 0)
        self.assertEqual(findings[0].severity, "critical")

    def test_custom_rules_no_match(self):
        """A rule that doesn't match produces no findings."""
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,1 +1,2 @@\n"
            " existing = 'x'\n"
            "+safe_change = True\n"
        )
        rules = [self._rule(r"sk-[a-zA-Z0-9]{32,}")]
        findings = apply_custom_rules(rules, diff, ["app.py"])
        self.assertEqual(findings, [])

    def test_custom_rules_only_added_lines(self):
        """Rules should only match added lines, not removed lines."""
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,2 +1,1 @@\n"
            "-api_key = 'sk-abcdefghijklmnopqrstuvwxyz1234567890'\n"
            " safe_change = True\n"
        )
        rules = [self._rule(r"sk-[a-zA-Z0-9]{32,}")]
        findings = apply_custom_rules(rules, diff, ["app.py"])
        self.assertEqual(findings, [])

    def test_custom_rules_invalid_regex_skipped(self):
        """Rules with invalid regex are gracefully skipped."""
        diff = (
            "+++ b/app.py\n"
            "@@ -1,1 +1,2 @@\n"
            "+something\n"
        )
        rules = [
            self._rule(r"[invalid regex(", rule_id="bad-rule"),
            self._rule(r"something", rule_id="good-rule"),
        ]
        # Should not raise; bad-rule is skipped
        findings = apply_custom_rules(rules, diff, ["app.py"])
        self.assertTrue(all(f.message and "good-rule" in f.message for f in findings))

    def test_custom_rules_empty_rules(self):
        """Empty rules list returns empty findings."""
        diff = "+some_added_line\n"
        findings = apply_custom_rules([], diff, [])
        self.assertEqual(findings, [])

    def test_custom_rules_finding_has_correct_file(self):
        """Finding path matches the file in which the match was found."""
        diff = (
            "--- a/config.py\n"
            "+++ b/config.py\n"
            "@@ -1,1 +1,2 @@\n"
            " x = 1\n"
            "+SECRET = 'sk-abcdefghijklmnopqrstuvwxyz1234567890'\n"
        )
        rules = [self._rule(r"sk-[a-zA-Z0-9]{32,}")]
        findings = apply_custom_rules(rules, diff, ["config.py"])
        self.assertEqual(findings[0].path, "config.py")


# ---------------------------------------------------------------------------
# langchain_analyzer
# ---------------------------------------------------------------------------

class TestLangchainSystemMessageRemoved(unittest.TestCase):

    def _diff_with_langchain_import(self, removed_line: str) -> str:
        return (
            "--- a/chain.py\n"
            "+++ b/chain.py\n"
            "@@ -1,5 +1,4 @@\n"
            " from langchain.schema import SystemMessage\n"
            f"-{removed_line}\n"
            " chain = LLMChain(llm=llm)\n"
        )

    def test_langchain_system_message_removed(self):
        """Detects removed SystemMessage(...) → high finding."""
        diff = self._diff_with_langchain_import('msg = SystemMessage(content="Be safe.")')
        findings = analyze_langchain_files(Path("/tmp"), ["chain.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)
        msgs = [f.message for f in findings]
        self.assertTrue(any("SystemMessage" in m for m in msgs))

    def test_langchain_system_message_param_removed(self):
        """Detects removed system_message= parameter → high finding."""
        diff = (
            "--- a/chain.py\n"
            "+++ b/chain.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from langchain.chat_models import ChatOpenAI\n"
            "-chain = ConversationChain(system_message='Be helpful.')\n"
            " chain2 = ConversationChain()\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["chain.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_langchain_memory_removed(self):
        """Detects removed ConversationBufferMemory → medium finding."""
        diff = (
            "--- a/bot.py\n"
            "+++ b/bot.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from langchain.memory import ConversationBufferMemory\n"
            "-memory = ConversationBufferMemory()\n"
            " chain = LLMChain(llm=llm)\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["bot.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("medium", severities)

    def test_langchain_chain_removed(self):
        """Detects removed LLMChain → high finding."""
        diff = (
            "--- a/app.py\n"
            "+++ b/app.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from langchain.chains import LLMChain\n"
            "-chain = LLMChain(llm=llm, prompt=prompt)\n"
            " result = chain.run(input='hello')\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["app.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_langchain_guardrail_removed(self):
        """Detects removed PydanticOutputParser → high finding."""
        diff = (
            "--- a/parser.py\n"
            "+++ b/parser.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from langchain.output_parsers import PydanticOutputParser\n"
            "-output_parser = PydanticOutputParser(pydantic_object=MyModel)\n"
            " result = chain.run(input='test')\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["parser.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)


class TestLangchainModelChanged(unittest.TestCase):

    def test_langchain_model_changed_downgrade(self):
        """Detects model downgrade in ChatOpenAI → high finding."""
        diff = (
            "--- a/llm.py\n"
            "+++ b/llm.py\n"
            "@@ -1,4 +1,4 @@\n"
            " from langchain.chat_models import ChatOpenAI\n"
            "-llm = ChatOpenAI(model='gpt-4')\n"
            "+llm = ChatOpenAI(model='gpt-3.5-turbo')\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["llm.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        # Should detect a downgrade (high) or model change
        self.assertTrue(any(s in ("high", "critical") for s in severities))

    def test_langchain_temperature_changed(self):
        """Detects temperature= change in LangChain file → medium finding."""
        diff = (
            "--- a/chain.py\n"
            "+++ b/chain.py\n"
            "@@ -1,4 +1,4 @@\n"
            " from langchain.chat_models import ChatOpenAI\n"
            "-llm = ChatOpenAI(temperature=0.2)\n"
            "+llm = ChatOpenAI(temperature=1.0)\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["chain.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("medium", severities)


class TestLlamaIndexSystemPromptRemoved(unittest.TestCase):

    def test_llamaindex_system_prompt_removed(self):
        """Detects removed system_prompt= in LlamaIndex file → critical finding."""
        diff = (
            "--- a/index.py\n"
            "+++ b/index.py\n"
            "@@ -1,5 +1,4 @@\n"
            " from llama_index import ServiceContext\n"
            "-ctx = ServiceContext.from_defaults(system_prompt='Be safe.')\n"
            "+ctx = ServiceContext.from_defaults()\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["index.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("critical", severities)

    def test_llamaindex_llm_changed(self):
        """Detects llm= change in LlamaIndex file → high finding."""
        diff = (
            "--- a/index.py\n"
            "+++ b/index.py\n"
            "@@ -1,5 +1,5 @@\n"
            " from llama_index import ServiceContext\n"
            "-ctx = ServiceContext.from_defaults(llm=OpenAI(model='gpt-4'))\n"
            "+ctx = ServiceContext.from_defaults(llm=OpenAI(model='gpt-3.5-turbo'))\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["index.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_llamaindex_response_mode_removed(self):
        """Detects removed response_mode= → medium finding."""
        diff = (
            "--- a/query.py\n"
            "+++ b/query.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from llama_index import QueryEngine\n"
            "-engine = index.as_query_engine(response_mode='tree_summarize')\n"
            "+engine = index.as_query_engine()\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["query.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("medium", severities)

    def test_llamaindex_node_postprocessors_removed(self):
        """Detects removed node_postprocessors= → high finding."""
        diff = (
            "--- a/pipeline.py\n"
            "+++ b/pipeline.py\n"
            "@@ -1,4 +1,3 @@\n"
            " from llama_index import QueryEngine\n"
            "-engine = index.as_query_engine(node_postprocessors=[filter])\n"
            "+engine = index.as_query_engine()\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["pipeline.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("high", severities)

    def test_llamaindex_similarity_top_k_reduced(self):
        """Detects similarity_top_k reduced → low finding."""
        diff = (
            "--- a/retriever.py\n"
            "+++ b/retriever.py\n"
            "@@ -1,4 +1,4 @@\n"
            " from llama_index import VectorStoreIndex\n"
            "-retriever = index.as_retriever(similarity_top_k=10)\n"
            "+retriever = index.as_retriever(similarity_top_k=2)\n"
        )
        findings = analyze_langchain_files(Path("/tmp"), ["retriever.py"], "origin/main", diff)
        severities = [f.severity for f in findings]
        self.assertIn("low", severities)

    def test_non_langchain_file_ignored(self):
        """Files without langchain/llama_index imports are ignored."""
        diff = (
            "--- a/utils.py\n"
            "+++ b/utils.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-x = 1\n"
            "+x = 2\n"
        )
        # utils.py on disk won't have langchain imports either
        findings = analyze_langchain_files(Path("/tmp"), ["utils.py"], "origin/main", diff)
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
