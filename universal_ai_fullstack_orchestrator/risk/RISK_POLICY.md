# Risk policy

- LOW: test, lint and review.
- MEDIUM: unit/integration tests, lint, build and review.
- HIGH: unit, integration, E2E where applicable, build, security, review and rollback.
- CRITICAL: all tests, security audit, migration safety when applicable, rollback readiness and human approval.

Authentication, authorization, payments, financial/personal data, migrations,
public APIs, infrastructure, production, integrations, deletion and security raise
risk monotonically. `production` combined with deletion/destruction is CRITICAL.
