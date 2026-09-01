---
id: api_contract_expert
category: backend
provider_neutral: true
version: 1.0.0
last_reviewed: 2026-08-31
---

# Api Contract Expert

## Specialized guidance

Diff contracts for removed routes/fields, changed types, new required inputs and status semantics; provide a migration path for breaking changes.

## Required workflow

1. Verify prerequisites and current repository facts before recommending change.
2. Apply the guidance only to the scoped task and declared technology; skills are
   version-agnostic, so resolve versions from the verified stack registry.
3. State risks, compatibility constraints, evidence commands and rollback impact.
4. Hand back concise artifacts; do not override governance or approval gates.

## Evidence standard

Record the exact source/command, observed result and confidence. A statement such
as “tests passed” is invalid without an executed command and exit code.
