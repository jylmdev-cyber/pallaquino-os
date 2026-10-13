# Known issues

- Stack snapshot (verified 2026-08-31) is STALE since 2026-09-30; `doctor` and `stack` exit 1 until PAL-006 re-verifies it.
- `validate_all.py` fails for anyone whose local Git identity is not the owner identity; contributors use `--integrity-only` (OPEN_QUESTIONS Q-1).
- Agent and skill files are templates whose only specific content is one sentence; inputs, outputs, tools, activation and success criteria are missing (Phase 2 contracts v2).
- Checkpoint SHA-256 detects accidental corruption, not deliberate tampering (hash chain planned for Phase 2).
- Only `no_secrets` of the 4 declared fitness rules has an implementation.
- `runtime/capabilities.json` in the framework tree still contains host paths from the 0.2.x build machine; it is no longer copied into new projects.
- Installations created with 0.2.1 keep inherited framework state until cleaned manually (MIGRATION_GUIDE.md).
- Internet, browser, MCP and subagent availability remains provider-session dependent.
- Confidence: high
