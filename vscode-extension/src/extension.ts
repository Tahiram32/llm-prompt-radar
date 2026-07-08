import * as vscode from 'vscode';
import { execSync } from 'child_process';
import * as path from 'path';

let diagnosticCollection: vscode.DiagnosticCollection;
let outputChannel: vscode.OutputChannel;

export function activate(context: vscode.ExtensionContext): void {
  diagnosticCollection = vscode.languages.createDiagnosticCollection('llm-prompt-radar');
  outputChannel = vscode.window.createOutputChannel('LLM Prompt Radar');

  context.subscriptions.push(diagnosticCollection);
  context.subscriptions.push(outputChannel);

  context.subscriptions.push(
    vscode.commands.registerCommand('llmPromptRadar.runScan', runScan),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand('llmPromptRadar.runFullScan', runFullScan),
  );
}

export function deactivate(): void {
  diagnosticCollection.clear();
  diagnosticCollection.dispose();
  outputChannel.dispose();
}

function getConfig(): { baseRef: string; failOn: string; executablePath: string } {
  const cfg = vscode.workspace.getConfiguration('llmPromptRadar');
  return {
    baseRef: cfg.get<string>('baseRef', 'origin/main'),
    failOn: cfg.get<string>('failOn', 'high'),
    executablePath: cfg.get<string>('executablePath', 'llm-prompt-radar'),
  };
}

function getWorkspaceRoot(): string | undefined {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) {
    return undefined;
  }
  return folders[0].uri.fsPath;
}

interface Finding {
  file?: string;
  line?: number;
  severity?: string;
  message?: string;
  rule?: string;
}

interface RadarOutput {
  findings?: Finding[];
  risk_level?: string;
}

function severityToDiagnostic(severity: string | undefined): vscode.DiagnosticSeverity {
  switch ((severity ?? '').toLowerCase()) {
    case 'critical':
    case 'high':
      return vscode.DiagnosticSeverity.Error;
    case 'medium':
      return vscode.DiagnosticSeverity.Warning;
    case 'low':
    default:
      return vscode.DiagnosticSeverity.Information;
  }
}

async function runScan(): Promise<void> {
  const repoRoot = getWorkspaceRoot();
  if (!repoRoot) {
    vscode.window.showWarningMessage('LLM Prompt Radar: No workspace folder open.');
    return;
  }

  const { baseRef, executablePath } = getConfig();

  diagnosticCollection.clear();

  try {
    const raw = execSync(
      `"${executablePath}" --repo "${repoRoot}" --base "${baseRef}" --format json --fail-on none`,
      { cwd: repoRoot, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
    );

    let parsed: RadarOutput = {};
    try {
      parsed = JSON.parse(raw);
    } catch {
      vscode.window.showInformationMessage('LLM Prompt Radar: No findings or unexpected output format.');
      return;
    }

    const findings: Finding[] = parsed.findings ?? [];
    if (findings.length === 0) {
      vscode.window.showInformationMessage('LLM Prompt Radar: ✅ No risky prompt changes detected.');
      return;
    }

    const diagMap = new Map<string, vscode.Diagnostic[]>();

    for (const finding of findings) {
      const filePath = finding.file
        ? path.isAbsolute(finding.file)
          ? finding.file
          : path.join(repoRoot, finding.file)
        : undefined;

      const lineNum = Math.max(0, (finding.line ?? 1) - 1);
      const range = new vscode.Range(lineNum, 0, lineNum, 999);
      const diagSeverity = severityToDiagnostic(finding.severity);
      const message = `[${finding.severity?.toUpperCase() ?? 'INFO'}] ${finding.message ?? finding.rule ?? 'Prompt risk detected'}`;
      const diag = new vscode.Diagnostic(range, message, diagSeverity);
      diag.source = 'llm-prompt-radar';

      const key = filePath ?? repoRoot;
      if (!diagMap.has(key)) {
        diagMap.set(key, []);
      }
      diagMap.get(key)!.push(diag);
    }

    for (const [filePath, diags] of diagMap) {
      const uri = vscode.Uri.file(filePath);
      diagnosticCollection.set(uri, diags);
    }

    const riskLevel = parsed.risk_level ?? 'unknown';
    vscode.window.showWarningMessage(
      `LLM Prompt Radar: ${findings.length} finding(s) detected. Highest risk: ${riskLevel.toUpperCase()}. See Problems panel.`,
    );
  } catch (err: unknown) {
    handleCliError(err, executablePath);
  }
}

async function runFullScan(): Promise<void> {
  const repoRoot = getWorkspaceRoot();
  if (!repoRoot) {
    vscode.window.showWarningMessage('LLM Prompt Radar: No workspace folder open.');
    return;
  }

  const { baseRef, failOn, executablePath } = getConfig();

  outputChannel.clear();
  outputChannel.show(true);
  outputChannel.appendLine('Running LLM Prompt Radar full repository scan…');
  outputChannel.appendLine(`  Repo:    ${repoRoot}`);
  outputChannel.appendLine(`  Base:    ${baseRef}`);
  outputChannel.appendLine(`  Fail-on: ${failOn}`);
  outputChannel.appendLine('');

  try {
    const raw = execSync(
      `"${executablePath}" --repo "${repoRoot}" --base "${baseRef}" --format markdown --fail-on none`,
      { cwd: repoRoot, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
    );
    outputChannel.appendLine(raw || '✅ No risky prompt changes detected.');
  } catch (err: unknown) {
    if (err instanceof Error && 'stdout' in err) {
      // CLI exited non-zero but still produced output
      outputChannel.appendLine((err as NodeJS.ErrnoException & { stdout: string }).stdout || '');
      outputChannel.appendLine(`\n⚠️  llm-prompt-radar exited with a non-zero code (findings above fail-on threshold).`);
    } else {
      handleCliError(err, executablePath);
    }
  }
}

function handleCliError(err: unknown, executablePath: string): void {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes('ENOENT') || msg.includes('not found') || msg.includes('No such file')) {
    vscode.window
      .showErrorMessage(
        `LLM Prompt Radar: CLI not found ("${executablePath}"). Install it with: pip install llm-prompt-radar`,
        'Copy install command',
      )
      .then((selection) => {
        if (selection === 'Copy install command') {
          vscode.env.clipboard.writeText('pip install llm-prompt-radar');
        }
      });
  } else {
    vscode.window.showErrorMessage(`LLM Prompt Radar error: ${msg}`);
  }
}
