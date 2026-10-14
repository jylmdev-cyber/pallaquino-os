# Known issues

- Stack snapshot verified 2026-10-14; it becomes STALE after 2026-11-13 and must be re-verified.
- In this repository `validate_all.py` expects the identity in `governance/git_identity.json` (jimdev); contributors with another local identity use `--integrity-only`.
- 46 agent and 90 skill contracts keep category-derived inputs, outputs and success criteria (`curation: derived`); 13 role agents are curated.
- 19 agents and 52 skills still have no golden test case (`pallaquino contracts`).
- Checkpoint SHA-256 detects accidental corruption, not deliberate tampering (hash chain planned for Phase 2).
- Only `no_secrets` of the 4 declared fitness rules has an implementation.
- `runtime/capabilities.json` in the framework tree still contains host paths from the 0.2.x build machine; it is no longer copied into new projects.
- Installations created with 0.2.1 keep inherited framework state until cleaned manually (MIGRATION_GUIDE.md).
- Internet, browser, MCP and subagent availability remains provider-session dependent.
- `v0.3.0` derives lock keys from `\` as a literal character on POSIX; fixed in 0.3.1, so prefer 0.3.1.
- 0.4.0: tasks answered by the mock provider are simulated; the real-provider reference variant was not executed (no Ollama or credentials on this host).
- 0.4.0: memory/state checksums are unkeyed; scheduler throughput is bounded by per-transition SQLite commits (~84 tasks/s, 4 workers).
- 0.4.0: a task that exceeds its timeout keeps running in its thread; its late result is discarded but its effects are not undone.
- The published v0.4.0 release ZIP lacks `pallaquino_cli/memory/` (orchestration commands fail from the extracted archive). The repository and
  tag are complete; the archive defect is fixed in 0.5.0. A corrected 0.4.x archive, or a note on the v0.4.0 release, needs the owner's decision.
- 0.5.0:
  - interoperability with the official MCP SDK v2 is not verified: the test exists and is skipped on this host (`mcp` 1.26.0);
  - plugins run in a separate process but not in an OS sandbox; a trusted plugin has the user's file permissions;
  - the file credential vault is not encrypted (OS permissions only); prefer `env:` references or keyring;
  - builtin adapter timeouts are cooperative;
  - `subscriptions/listen` is not implemented;
  - symbolic-link escape tests are skipped on hosts that cannot create links (this Windows host); they run on Linux CI;
  - inherited Windows flake: SQLite WAL cleanup in `test_scheduler` sometimes fails with WinError 32 (seen once in the source tree and once in the
    extracted archive on 2026-10-14); watch CI;
  - with an editable install, the default root is the package checkout (ADR-0004); use `--root .pallaquino` or `PALLAQUINO_ROOT` in projects.
- Confidence: high
