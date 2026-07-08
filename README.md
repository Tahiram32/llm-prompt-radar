# llm-prompt-radar

[![CI](https://github.com/Tahiram32/llm-prompt-radar/actions/workflows/ci.yml/badge.svg)](https://github.com/Tahiram32/llm-prompt-radar/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/llm-prompt-radar?color=blue)](https://pypi.org/project/llm-prompt-radar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/Tahiram32?label=Sponsor&logo=githubsponsors)](https://github.com/sponsors/Tahiram32)

> **The missing CI check for AI-powered applications.**

---

## Why?

Prompts are code — but they have no CI.

When a developer ships a new feature, every line of Python, TypeScript, and SQL is reviewed, linted, tested, and guarded by merge checks. Prompts get none of that. A single word swap in a system message — replacing *"refuse requests that violate policy"* with *"always try to help the user"* — can silently remove a critical safety guardrail, downgrade response quality, or introduce a jailbreak vector. It ships on Friday at 5 pm and nobody notices until users start complaining.

**llm-prompt-radar** closes that gap. It runs in your CI pipeline as a GitHub Action (or locally as a CLI) and analyses every diff that touches an LLM prompt, AI config file, or SDK call. It scores the change by risk level and can block the merge — just like a failing test.

---

## ✨ Features

- 🛡️ **Safety guardrail removal detection** — flags diffs that delete or weaken instructions like *refuse*, *do not*, *never*, *you must not*
- 🤖 **Model downgrade detection** — catches regressions like `gpt-4o` → `gpt-3.5-turbo`, `claude-3-opus` → `claude-instant`, and similar capability drops
- 📝 **Prompt file change analysis** — deep-diffs `.prompt`, `.jinja`, and `.j2` template files
- 🔍 **In-code system message detection** — parses diffs for OpenAI, Anthropic, and Gemini SDK call sites and extracts changed `system`/`human`/`user` messages
- ⚙️ **LLM parameter change tracking** — surfaces modifications to `temperature`, `max_tokens`, `top_p`, `frequency_penalty`, and other inference knobs
- 🎯 **Risk scoring** — every finding is classified as `none` / `low` / `medium` / `high` / `critical`
- 📊 **Multiple output formats** — `text`, `json`, `markdown`, `github` (annotations), `sarif` (GitHub Code Scanning)
- 🪶 **Zero dependencies** — pure Python standard library; installs in < 1 second

---

## 🚀 Quick Start

### GitHub Action

Add the following step to any workflow that runs on pull requests:

```yaml
name: AI Safety Check

on: [pull_request]

jobs:
  prompt-radar:
    runs-on: ubuntu-latest
    permissions:
      contents: read

    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0          # full history required for diffing

      - uses: Tahiram32/llm-prompt-radar@v0.1.0
        with:
          base-ref: origin/main   # ref to diff against
          format: github          # emit GitHub PR annotations
          fail-on: high           # block merge on high/critical findings
```

### CLI

```bash
# Install
pip install llm-prompt-radar

# Analyse uncommitted changes vs. main
llm-prompt-radar --base origin/main

# Analyse a specific repo with JSON output
llm-prompt-radar --repo /path/to/repo --base origin/main --format json --fail-on medium

# Get full help
llm-prompt-radar --help
```

---

## ⚙️ Configuration

| Flag | Default | Description |
|---|---|---|
| `--repo` | `.` | Path to the repository root |
| `--base-ref` | `origin/main` | Git ref to diff against |
| `--format` | `markdown` | Output format: `text` \| `json` \| `markdown` \| `github` \| `sarif` |
| `--fail-on` | `high` | Exit non-zero when the highest risk is ≥ this level: `none` \| `low` \| `medium` \| `high` \| `critical` |
| `--badge` | _(off)_ | Print a `shields.io` badge URL to stdout |

When used as a **GitHub Action**, these map 1-to-1 to `inputs:` in your workflow YAML.

---

## 🔬 How It Works

llm-prompt-radar analyses your diff through four independent layers:

1. **Prompt file layer** — detects additions, deletions, and modifications in files ending with `.prompt`, `.jinja`, or `.j2`. Sentence-level diffing highlights removed safety instructions and added jailbreak-adjacent language.

2. **SDK call layer** — parses unified diffs for patterns from the OpenAI Python SDK (`openai.ChatCompletion.create`, `client.chat.completions.create`), Anthropic SDK (`anthropic.messages.create`), and Google Gemini SDK (`model.generate_content`). It extracts the `system`, `user`, and `human` message strings that changed.

3. **Model & parameter layer** — uses regex to find model name strings (e.g. `"model": "gpt-4o"`) and numeric parameters (`temperature=0.7`) in the diff. Raises findings when a model is replaced with a known lower-capability variant or when a parameter moves outside a safe range.

4. **Risk scoring layer** — each finding from the three layers above is assigned a severity (`low` / `medium` / `high` / `critical`) based on a weighted rule set. The highest severity across all findings becomes the overall risk level returned as the Action output and CLI exit code signal.

---

## 🗺️ Roadmap

- [x] Unified diff parsing engine
- [x] Safety guardrail removal detection
- [x] Model downgrade detection
- [x] LLM parameter change tracking
- [x] GitHub Action composite workflow
- [x] SARIF output for GitHub Code Scanning
- [ ] YAML/TOML config file support (`.promptradar.yml`)
- [ ] LangChain and LlamaIndex SDK support
- [ ] PR comment posting with risk summary table
- [ ] Custom rule definitions (bring-your-own regex)
- [ ] VS Code extension
- [ ] Pre-commit hook integration

---

## ❤️ Sponsor

If llm-prompt-radar saves you from a bad deploy, consider sponsoring its development:

**[→ github.com/sponsors/Tahiram32](https://github.com/sponsors/Tahiram32)**

Your support helps keep the project dependency-free, well-tested, and actively maintained.

---

## License

[MIT](LICENSE) © 2026 Tahiram32
