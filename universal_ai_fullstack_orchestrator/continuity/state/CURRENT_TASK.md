# Current task

- ID: PAL-008
- Objective: publish patch release 0.3.1 with the cross-platform lock-key fix found by Linux CI after v0.3.0
- Mode: MAINTENANCE
- Autonomy: STANDARD (owner approved on 2026-10-14: merge PR #3 with a merge commit and publish 0.3.1)
- Scope: version metadata, changelog, release manifest, deterministic archive, tag `v0.3.1`, GitHub Release
- Status: COMPLETE once tag `v0.3.1` and its GitHub Release are published and their assets verified
- Risk: LOW (one backward-compatible fix; no data migration)
- Acceptance: tests pass; archive reproducible and verified; release assets match the sidecar SHA-256
- Confidence: high
