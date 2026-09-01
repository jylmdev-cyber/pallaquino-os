# PALLAQUINO technology expansion

Version 0.2.0 expands the operational catalog without selecting unverified
technology versions. Every new skill is version-agnostic and each stack profile
uses `VERIFY_BEFORE_USE`; adoption must run the official-source stack audit.

## Catalog

- 59 specialized agents.
- 90 skills.
- 46 technologies.
- 6 stack profiles.
- 7 domain packs.
- 17 routing rules.
- 14 conditional quality gates.
- 15 evaluation scenarios in total, including 7 expansion scenarios.

Machine-readable sources:

- `registry/technology_catalog.json`
- `registry/stack_profiles.json`
- `registry/technology_compatibility.json`
- `registry/agent_skill_coverage.json`
- `registry/domain_packs.json`

## Expansion packs

### Web and enterprise

React, Next.js, Angular, Spring Boot, Go, Laravel, MySQL, Redis, Playwright and
OpenID Connect. Agents cover identity, integrations, performance, API governance
and shared web-platform concerns.

### Cloud native

Kubernetes, Terraform, Helm, Argo CD, GitHub Actions, AWS, Azure, GCP and Nginx.
Cloud architecture, platform engineering, infrastructure security, FinOps and
disaster recovery are separate responsibilities.

### Distributed systems

Kafka, RabbitMQ, event-driven architecture, distributed-system design,
microservices, modular monoliths, transactional outbox and idempotency. Conditional
gates protect event compatibility and duplicate-effect behavior.

### Data platforms

SQL Server, MongoDB, OpenSearch, ClickHouse, data modeling, database performance,
backup/recovery and privacy. The catalog distinguishes database implementation,
reliability and privacy review.

### Mobile

Flutter, React Native, SwiftUI, Kotlin/Android, offline synchronization and mobile
security, with dedicated architecture and QA agents.

### AI systems

MCP, RAG, vector databases, LLM evaluation, prompt security, tool calling,
structured output, model routing, cost optimization and guardrails. AI gates cover
evaluation, injection, permissions, grounding, privacy and cost.

### Domain packs

Ecommerce, restobar, healthcare, fintech, logistics, manufacturing and CRM reuse
specialized skills and agents while adding domain-specific risk factors.

## Stack profiles

- `nextjs_saas`
- `spring_enterprise`
- `dotnet_enterprise`
- `cloud_native_microservices`
- `flutter_mobile_backend`
- `ai_rag_platform`

A profile is a coherent starting point, not an automatic dependency selection.
Before activation, verify official support, Active LTS or stable release, latest
security patch and compatibility; then record concrete versions in
`stack_versions_verified.json`.

## Maintenance

The expansion is reproducible and idempotent:

```console
python scripts/expand_catalog.py
python scripts/validate_registry.py
python -m unittest discover -s tests -v
```

New entries must add specialized guidance, routing or profile value and evaluation
coverage. Avoid aliases that merely duplicate an existing skill or agent.

