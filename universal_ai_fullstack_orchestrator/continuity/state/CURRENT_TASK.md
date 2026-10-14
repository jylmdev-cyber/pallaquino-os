# Current task

- ID: PAL-009
- Objective: release 0.3.2 so the distributed archive carries the stack snapshot re-verified in PAL-006
- Mode: MAINTENANCE
- Autonomy: STANDARD (owner approved on 2026-10-14: publish the PAL-006 pull request and release 0.3.2)
- Scope: version metadata, changelog, release manifest, deterministic archive, pull request, tag `v0.3.2`, GitHub Release
- Status: COMPLETE once the pull request is merged and tag `v0.3.2` with its GitHub Release is published and verified
- Risk: LOW (catalog data and one generator fix; no data migration)
- Acceptance: CI green; archive reproducible and verified; release assets match the sidecar SHA-256
- Confidence: high
