---
id: saas_tenancy_expert
category: architecture
provider_neutral: true
version: 1.0.0
last_reviewed: 2026-08-31
---

# Saas Tenancy Expert

## Specialized guidance

Make tenant scope unavoidable in storage and authorization; test cross-tenant denial, lifecycle deletion and entitlement changes.

## Required workflow

1. Verify prerequisites and current repository facts before recommending change.
2. Apply the guidance only to the scoped task and declared technology; skills are
   version-agnostic, so resolve versions from the verified stack registry.
3. State risks, compatibility constraints, evidence commands and rollback impact.
4. Hand back concise artifacts; do not override governance or approval gates.

## Evidence standard

Record the exact source/command, observed result and confidence. A statement such
as “tests passed” is invalid without an executed command and exit code.
