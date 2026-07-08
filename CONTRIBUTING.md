# Contributing to llm-prompt-radar

Thank you for taking the time to contribute! This document explains how to set up a development environment, run tests, and get your pull request merged.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development setup](#development-setup)
3. [Running tests](#running-tests)
4. [Code style](#code-style)
5. [Pull request guidelines](#pull-request-guidelines)
6. [Commit message convention](#commit-message-convention)
7. [Reporting issues](#reporting-issues)

---

## Code of Conduct

This project follows the [Contributor Covenant v2.1](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms.

---

## Development setup

> **Requirements:** Python 3.10 or newer, Git.

```bash
# 1. Fork & clone
git clone https://github.com/YOUR_USERNAME/llm-prompt-radar.git
cd llm-prompt-radar

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# 3. Install the package in editable mode
pip install -e .

# 4. Verify the CLI is available
llm-prompt-radar --help
```

No additional packages are required — llm-prompt-radar has **zero runtime dependencies**.

---

## Running tests

Tests use the Python **standard-library `unittest` framework** (do **not** install or use pytest).

```bash
# Run the full test suite with verbose output
python -m unittest discover -s tests -v

# Run a specific test module
python -m unittest tests.test_scanner -v

# Run a single test case
python -m unittest tests.test_scanner.ScannerTest.test_model_downgrade -v
```

All tests must pass before a PR will be merged. New behaviour must be accompanied by a new test.

---

## Code style

- **Language:** Python 3.10+ only — use modern syntax (`match`, `|` union types, etc.) where it improves clarity.
- **Type hints:** All public functions and methods must have complete type annotations (`def foo(x: str) -> list[Finding]:`).
- **Zero dependencies:** Do **not** add any third-party imports. The standard library is sufficient. If you feel a dependency is truly necessary, open an issue for discussion first.
- **Formatting:** Use 4-space indentation. Keep lines ≤ 100 characters. No trailing whitespace.
- **Docstrings:** Public classes and functions should have a one-line docstring.
- **No linter required:** There is intentionally no linter config in the repo. Just follow the rules above and match the style of the surrounding code.

---

## Pull request guidelines

1. **Branch off `main`** — create a feature branch: `git checkout -b feat/your-feature-name`.
2. **One logical change per PR** — keep diffs small and focused.
3. **Write tests first** if adding a new detection rule or output format.
4. **Update `README.md`** if you add, remove, or change a CLI flag or detection capability.
5. **Mark the roadmap item** as checked in `README.md` if your PR completes one.
6. **Do not bump the version** in `pyproject.toml` — that is handled by the maintainer at release time.
7. Open the PR against `main`. Fill out the PR template completely.

---

## Commit message convention

We use a lightweight [Conventional Commits](https://www.conventionalcommits.org/) style:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

| Type | When to use |
|---|---|
| `feat` | New detection rule, output format, or user-visible feature |
| `fix` | Bug fix |
| `test` | Adding or updating tests only |
| `docs` | README, CONTRIBUTING, docstrings |
| `chore` | Dependency bumps, CI tweaks, repo maintenance |
| `refactor` | Internal restructuring with no behaviour change |

Example: `feat(scanner): detect claude-instant model downgrades`

---

## Reporting issues

- **Bugs** → use the [Bug report](.github/ISSUE_TEMPLATE/bug_report.md) template.
- **Feature requests** → use the [Feature request](.github/ISSUE_TEMPLATE/feature_request.md) template.
- **Security vulnerabilities** → see [SECURITY.md](SECURITY.md). Do **not** open a public issue.

---

Thank you again for contributing! 🎉
