# Known issues

- Stack snapshot verified 2026-10-14; it becomes STALE after 2026-11-13 and must be re-verified.
- In this repository `validate_all.py` expects the identity in `governance/git_identity.json` (jimdev); contributors with another local identity use `--integrity-only`.
- Contracts v2 exist for all 59 agents and 90 skills, but their inputs, outputs and success criteria are category-derived (`curation: derived`) until curated (PAL-007-B).
- 20 agents and 9 skills are unreachable: no routing rule, profile, domain pack or coverage entry selects them (`pallaquino contracts`).
- Checkpoint SHA-256 detects accidental corruption, not deliberate tampering (hash chain planned for Phase 2).
- Only `no_secrets` of the 4 declared fitness rules has an implementation.
- `runtime/capabilities.json` in the framework tree still contains host paths from the 0.2.x build machine; it is no longer copied into new projects.
- Installations created with 0.2.1 keep inherited framework state until cleaned manually (MIGRATION_GUIDE.md).
- Internet, browser, MCP and subagent availability remains provider-session dependent.
- `v0.3.0` derives lock keys from `\` as a literal character on POSIX; fixed in 0.3.1, so prefer 0.3.1.
- Confidence: high
