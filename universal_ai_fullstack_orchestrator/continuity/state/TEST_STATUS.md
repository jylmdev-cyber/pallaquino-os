# Test status

- Result: PASSED for integrity scope; the environment-scope Git identity check needs the owner identity (configured in CI)
- Framework suite: 60/60 passed (`python -m unittest discover -s tests`)
- Statement coverage (stdlib trace, in-process): core.py 92.1 %, __main__.py 86.4 %
- Validators: 9/9 integrity checks pass; validate_git_authorship fails locally without the owner identity, by design
- Lint/typecheck proxy: Python compileall passed
- Security: repository-wide secret scan 0 findings; fitness enforces 1 of 4 declared rules and reports 3 as not_enforced
- Risk goldens 14/14; routing goldens 3/3 and 7/7
- Archive: deterministic (identical SHA-256 for identical content); integrity verified after extraction
- Non-editable install: verified locally (framework dir, nested project dir, outside any project exits 2)
- Evidence: `evidence/*-2026-10-13T*.json` for PAL-005
- GitHub Actions: green on Ubuntu with Python 3.11 and 3.14 for the 0.3.1 fix (PR #3, commit 066fa50)
- Updated: 2026-10-14
- Confidence: high
