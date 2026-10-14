# Current task

- ID: PAL-007-B
- Objective: make every agent and skill selectable and curate the pipeline-role contracts
- Mode: BROWNFIELD
- Autonomy: STANDARD (branch `feat/pal-007-b-reachability`, stacked on PAL-007-A; publication awaits owner approval)
- Scope: specialist skill wiring, pipeline-stage roles, ten routing rules with goldens, 13 curated contracts, create-only generators
- Status: COMPLETE on branch
- Risk: MEDIUM (routing behaviour changes; covered by positive and negative goldens)
- Acceptance: 0 unreachable agents and skills; every new rule has a golden; all 67 tests pass; generators cannot revert curated registries without --overwrite
- Confidence: high
