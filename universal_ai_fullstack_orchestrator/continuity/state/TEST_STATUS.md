# Test status

- Result: PASSED locally for integrity scope; the environment-scope Git identity check needs the owner identity (configured in CI)
- Framework suite (0.5.0): 239 tests (154 from 0.4.0 + 85 new), green on Windows (`python -m unittest discover -s tests`):
  - Python 3.11.15: 3 skipped: symbolic links cannot be created on this host; 2 official-SDK interop tests (`mcp` 1.26.0 installed, needs ≥ 2);
  - Python 3.12.10: 4 skipped, the same 3 plus the offline pip build (no setuptools);
  - evidence: `evidence/test-2026-10-14T19-28-24+00-00.json` (3.11) and `evidence/test-2026-10-14T19-29-42+00-00.json` (3.12);
  - from the extracted release ZIP (no `.git`), the suite passes (the `git ls-files` test is skipped) and the demo reports `ok`.
- Statement coverage (coverage.py on 3.12, in-process): 93 % of the package; `tools/*` 96-98 %; MCP client 95 %, auth 94 %, connections 92 %;
  plugin manager 94 %. Code that runs in subprocesses (SDK runner, parts of the reference server) is exercised but not measured.
- End-to-end demo: `scripts/run_codebase_analysis_demo.py` 12/12 checks offline (`evidence/e2e_demo-2026-10-14T19-16-38+00-00.json`).
- Validators: integrity scope passes; validate_git_authorship fails locally without the repository-local owner identity, by design.
- Lint/typecheck proxy: `compileall` passed for pallaquino_cli, scripts, tests and examples.
- Security: secret scan 0 findings over 574 files (`evidence/security_check-2026-10-14T19-16-37+00-00.json`); fitness 0 violations.
- Not verified: Linux and Python 3.14 (CI runs after push); interoperability with the official MCP SDK v2; real identity providers.
- Updated: 2026-10-14
- Confidence: high
