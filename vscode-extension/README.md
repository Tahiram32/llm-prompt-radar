# LLM Prompt Radar — VS Code Extension

Detect risky changes to LLM prompts and AI configuration directly inside VS Code.

## Installation

### From VS Code Marketplace

Search for **"LLM Prompt Radar"** in the Extensions panel (`Ctrl+Shift+X`) or visit the Marketplace page.

### From VSIX (local build)

```bash
cd vscode-extension
npm install
npm run compile
npm run package          # produces llm-prompt-radar-*.vsix
code --install-extension llm-prompt-radar-*.vsix
```

### Prerequisite

The extension shells out to the `llm-prompt-radar` Python CLI. Install it first:

```bash
pip install llm-prompt-radar
```

---

## Commands

| Command | Keyboard / Menu | Description |
|---|---|---|
| `LLM Prompt Radar: Scan Repository` | `Ctrl+Shift+P` → type command | Runs a full diff scan and shows the markdown report in the Output panel |
| `LLM Prompt Radar: Scan Current File` | Right-click in editor → context menu | Runs a scan and surfaces findings as VS Code Diagnostics (Problems panel) |

---

## Configuration

Open **Settings** (`Ctrl+,`) and search for `llmPromptRadar`, or add to your `settings.json`:

```json
{
  "llmPromptRadar.baseRef": "origin/main",
  "llmPromptRadar.failOn": "high",
  "llmPromptRadar.executablePath": "llm-prompt-radar"
}
```

| Setting | Default | Description |
|---|---|---|
| `llmPromptRadar.baseRef` | `origin/main` | Git ref to diff against |
| `llmPromptRadar.failOn` | `high` | Minimum risk level shown as a VS Code Error (vs. Warning/Info) |
| `llmPromptRadar.executablePath` | `llm-prompt-radar` | Full path to the CLI if it's not on your `PATH` |

---

## How It Works

1. On command invocation the extension runs `llm-prompt-radar --format json` (for `runScan`) or `--format markdown` (for `runFullScan`) against your workspace root.
2. JSON findings are mapped to `vscode.Diagnostic` objects and shown in the **Problems** panel with file + line information.
3. The full markdown report is streamed to the **LLM Prompt Radar** Output Channel.
4. If the CLI binary is not found, an actionable error message appears with one-click copy of the install command.

---

## License

[MIT](../LICENSE) © 2026 Tahiram32
