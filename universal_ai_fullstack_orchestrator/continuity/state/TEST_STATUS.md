# Test status

- Result: PASSED locally for integrity scope; the environment-scope Git identity check needs the owner identity (configured in CI)
- Framework suite (0.5.0): 242 tests (154 from 0.4.0 + 88 new), green on Windows (`python -m unittest discover -s tests`):
  - Python 3.11.15 with `mcp` 2.3.0 in an isolated venv: 1 skipped (symbolic links cannot be created on this host) (`evidence/test-2026-10-14T20-37-33+00-00.json`);
  - Python 3.11.15 without the SDK: 6 skipped (symlinks + 5 interop tests); Python 3.12.10: the same plus the offline pip build (no setuptools);
  - official MCP SDK interop: 5/5 with `mcp` 2.3.0, both directions, stdio and Streamable HTTP, modern and legacy (`evidence/mcp_interop-2026-10-14T20-35-44+00-00.json`);
  - evidence: `evidence/test-2026-10-14T19-28-24+00-00.json` (3.11) and `evidence/test-2026-10-14T19-29-42+00-00.json` (3.12);
  - from the extracted release ZIP (no `.git`), the suite passes (the `git ls-files` test is skipped) and the demo reports `ok`.
- Statement coverage (coverage.py on 3.12, in-process): 93 % of the package; `tools/*` 96-98 %; MCP client 95 %, auth 94 %, connections 92 %;
  plugin manager 94 %. Code that runs in subprocesses (SDK runner, parts of the reference server) is exercised but not measured.
- End-to-end demo: `scripts/run_codebase_analysis_demo.py` 12/12 checks offline (`evidence/e2e_demo-2026-10-14T19-16-38+00-00.json`).
- Validators: integrity scope passes; validate_git_authorship fails locally without the repository-local owner identity, by design.
- Lint/typecheck proxy: `compileall` passed for pallaquino_cli, scripts, tests and examples.
- Security: secret scan 0 findings over 574 files (`evidence/security_check-2026-10-14T19-16-37+00-00.json`); fitness 0 violations.
- Not verified: Linux and Python 3.14 (CI runs on the publication pull request); real identity providers and public MCP servers.
- Academy (PAL-012), 2026-10-14, Windows 11, Node 24 / Python 3.11.15:
  - `npm run ci` green (`evidence/docs_validation-2026-10-14T23-14-58+00-00.json`):
    - generated data matches the code;
    - `astro check` and `vue-tsc` with 0 errors;
    - 29 vitest tests (logic and components with axe-core);
    - content validation: 64 pages, 46 lessons, 133 CLI commands;
    - build of 127 pages;
    - 11448 internal links;
    - axe-core on 65 built pages.
  - In-browser axe-core sweep of 63 pages: dark and light at 1280 px, light at 375 px, with no horizontal overflow. The only remaining rule is
    Starlight's search button (`label-content-name-mismatch`, audit H-11)
    (`evidence/accessibility_browser-2026-10-14T23-20-00+00-00.json`).
  - Not run: the academy CI workflow on GitHub (needs a push), tests with real users (protocol only), and deployment.
- Framework suite re-run after the PAL-012 changes: 242 OK, 6 skipped (`evidence/test-2026-10-14T23-16-55+00-00.json`).
- PAL-013 (H-6 fix), Windows 11 / Python 3.11.15:
  - 243 tests OK, 6 skipped (`evidence/test-2026-10-14T23-33-18+00-00.json`);
  - the new regression test fails without the fix;
  - the previous run (`evidence/test-2026-10-14T23-31-18+00-00.json`) hit the known WinError 32 WAL-cleanup flake in a tearDown.
- Session close on `main` `fc42622` (2026-10-14, Windows 11, Python 3.11.15, Node 24.15.0):
  - framework: 243 tests OK, 6 skipped (`evidence/test-2026-10-14T23-57-44+00-00.json`);
  - compileall (`evidence/lint_typecheck-2026-10-14T23-55-46+00-00.json`);
  - integrity validation (`evidence/integrity-2026-10-14T23-55-46+00-00.json`);
  - secret scan, 0 findings (`evidence/security_check-2026-10-14T23-55-51+00-00.json`);
  - architecture fitness (`evidence/architecture_fitness-2026-10-14T23-55-51+00-00.json`);
  - committed 0.5.0 ZIP integrity (`evidence/build-2026-10-14T23-55-52+00-00.json`; this verifies the existing archive, it is not a new
    release build);
  - academy `npm run ci` (`evidence/docs_validation-2026-10-14T23-58-40+00-00.json`).
- GitHub CI on PRs #8, #9 and #10: CI (Python 3.11, 3.14) and Academy (build and validate) green; Academy deploy runs 38655034166 and
  38655943918 green.
- Live site checks (built-in browser, 2026-10-14): pages 200, unknown path 404, Pagefind search, terminal replay and module-folder rule, and
  local progress persisting across navigation (test data cleared afterwards).
- Not verified:
  - the full `validate` with Git identity in this checkout (local identity unset; CI applies it);
  - real-user testing;
  - other browsers than the desktop app's built-in Chromium;
  - screen readers (only axe-core automated checks).
- PAL-014 release gates for 0.5.1 (2026-10-15 UTC):
  - 243 tests OK, 6 skipped (`evidence/test-2026-10-15T00-08-18+00-00.json`);
  - compileall (`evidence/lint_typecheck-2026-10-15T00-06-44+00-00.json`);
  - integrity validation (`evidence/integrity-2026-10-15T00-06-45+00-00.json`);
  - secret scan, 0 findings (`evidence/security_check-2026-10-15T00-06-48+00-00.json`);
  - architecture fitness (`evidence/architecture_fitness-2026-10-15T00-06-49+00-00.json`);
  - academy `npm run ci` (`evidence/docs_validation-2026-10-15T00-08-59+00-00.json`).
- 0.5.1 publication checks (2026-10-15 UTC):
  - CI on PR #12 green: Python 3.11 and 3.14, including the committed-archive verification and the non-editable install smoke test;
  - Academy build and validate green;
  - GitHub Release assets downloaded and checked with `sha256sum -c` (OK);
  - live academy pages show 0.5.1.
- Updated: 2026-10-15
- Confidence: high
