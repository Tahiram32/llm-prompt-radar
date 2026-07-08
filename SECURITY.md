# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes     |

Only the latest patch release of the current minor version receives security fixes.

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Report security issues privately using **[GitHub Security Advisories](https://github.com/Tahiram32/llm-prompt-radar/security/advisories/new)**.

You will receive an acknowledgement within **72 hours**. If the issue is confirmed, a patch will be developed and a new release cut — typically within **14 days** for high/critical severity findings.

Please include:

- A description of the vulnerability and its potential impact
- Steps to reproduce (diff input, CLI invocation, or Action config)
- Your assessment of severity (Low / Medium / High / Critical)
- Any suggested mitigations or patches (optional but very welcome)

---

## Security Considerations

llm-prompt-radar is designed to be safe to run in CI pipelines. Here is what it does and does **not** do:

| Property | Detail |
|---|---|
| **No code execution** | The tool never evaluates, imports, or executes any code from the analysed repository. It reads only the text output of `git diff`. |
| **Zero external dependencies** | The package uses only the Python standard library. There is no supply-chain risk from third-party packages. |
| **No network access** | llm-prompt-radar makes no outbound network requests at runtime. It does not send diffs, findings, or telemetry anywhere. |
| **Read-only filesystem access** | The tool reads git diff output and prompt files. It writes only to stdout/stderr and `$GITHUB_STEP_SUMMARY` when running as a GitHub Action. |
| **No secrets in scope** | The tool does not read, parse, or log environment variables, `.env` files, or secrets. |

### Threat model notes

- **Input validation:** Diff text is parsed with standard string operations. Maliciously crafted diff content cannot cause code execution or path traversal.
- **GitHub Action isolation:** The composite Action runs inside the caller's existing job runner. It has no additional permissions beyond those granted to the workflow.
- **SARIF output:** When `--format sarif` is used, the SARIF file is written to stdout or a local path only. It is the caller's responsibility to upload it to GitHub Code Scanning.

---

## Acknowledgements

We are grateful to researchers who responsibly disclose vulnerabilities. Confirmed security reporters will be credited in the release notes (with their permission).
