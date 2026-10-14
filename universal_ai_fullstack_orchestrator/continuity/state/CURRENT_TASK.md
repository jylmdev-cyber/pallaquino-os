# Current task

- ID: PAL-007-A
- Objective: Phase 2, first increment: agent and skill contracts v2 (schema, derivation, validation, controlled loading)
- Mode: BROWNFIELD
- Autonomy: STANDARD (branch `feat/pal-007-contracts-v2`; publication awaits owner approval)
- Scope: `pallaquino_cli/contracts.py`, `scripts/build_contracts.py`, contract registries, `contracts` CLI command, tests, ADR-0008
- Status: COMPLETE on branch
- Risk: MEDIUM (new integrity validator; no change to routing or existing contracts)
- Acceptance: all 149 contracts valid; tampered sources and unauthorized tools are rejected; curated fields survive regeneration; 60 tests pass
- Confidence: high
