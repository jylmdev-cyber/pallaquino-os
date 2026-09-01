#!/usr/bin/env python3
"""Idempotently install PALLAQUINO technology expansion packs.

The catalog remains version-agnostic. Concrete versions are deliberately absent
until an adoption task performs the official-source stack audit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-08-31"


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.rstrip() + "\n", encoding="utf-8")


def load(path: str) -> Any:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def dump(path: str, value: Any) -> None:
    write(path, json.dumps(value, indent=2, ensure_ascii=False))


def merge_rows(existing: list[dict[str, Any]], additions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = {row["id"]: row for row in existing}
    rows.update({row["id"]: row for row in additions})
    return [rows[key] for key in sorted(rows)]


AGENTS = {
    "identity_access_engineer": ("security", ["identity", "security"], ["design", "code", "review"], ["openid_connect_expert", "application_security_expert"], "Design authentication, federation, session lifecycle and authorization boundaries with deny-by-default behavior and auditable privilege changes."),
    "integration_engineer": ("integration", ["api", "integration"], ["contract", "code", "test"], ["api_contract_expert", "event_driven_architecture_expert"], "Connect internal and external systems through explicit contracts, idempotency, retries, reconciliation and failure isolation."),
    "performance_engineer": ("quality", ["performance"], ["profile", "benchmark", "review"], ["database_performance_expert", "observability_expert"], "Establish representative workloads, locate measured bottlenecks and enforce latency, throughput and resource budgets without speculative optimization."),
    "api_governance_reviewer": ("governance", ["api"], ["contract", "compatibility", "review"], ["api_contract_expert"], "Review API consistency, lifecycle, pagination, errors, idempotency, compatibility and deprecation before public contract changes."),
    "web_platform_engineer": ("frontend", ["web", "platform"], ["code", "build", "performance"], ["react_expert", "playwright_expert"], "Maintain shared web foundations, rendering strategy, design-system integration, build performance and browser compatibility."),
    "cloud_architect": ("platform", ["cloud", "architecture"], ["design", "cost", "review"], ["terraform_expert", "cloud_cost_optimization_expert"], "Select cloud services and trust boundaries using portability, reliability, security, operational effort and total cost as explicit trade-offs."),
    "platform_engineer": ("platform", ["platform", "deployment"], ["code", "deploy", "operate"], ["kubernetes_expert", "terraform_expert"], "Build paved roads for delivery, runtime configuration, secrets, observability and self-service without weakening environment controls."),
    "kubernetes_engineer": ("platform", ["kubernetes"], ["deploy", "operate", "debug"], ["kubernetes_expert", "helm_expert"], "Engineer Kubernetes workloads with resource governance, probes, disruption safety, network boundaries and reversible releases."),
    "infrastructure_security_reviewer": ("security", ["cloud", "infrastructure"], ["threat_model", "iam", "review"], ["terraform_expert", "application_security_expert"], "Review infrastructure plans, IAM, network exposure, encryption, logging and secret paths before apply or deployment."),
    "finops_analyst": ("operations", ["cloud", "cost"], ["forecast", "measure", "optimize"], ["cloud_cost_optimization_expert"], "Attribute and forecast infrastructure cost, identify waste and set cost guardrails without trading away reliability or security invisibly."),
    "disaster_recovery_planner": ("operations", ["reliability", "data"], ["backup", "restore", "exercise"], ["backup_recovery_expert", "rollback_strategy_expert"], "Define RPO/RTO, dependency recovery order, immutable backups and recurring restore exercises for credible disaster recovery."),
    "distributed_systems_architect": ("architecture", ["distributed_systems"], ["design", "model", "review"], ["distributed_systems_expert", "event_driven_architecture_expert"], "Design distributed workflows around explicit consistency, partition, ordering, ownership and failure assumptions."),
    "event_contract_reviewer": ("integration", ["events", "api"], ["schema", "compatibility", "review"], ["event_driven_architecture_expert", "api_contract_expert"], "Protect event schema evolution, ownership, consumer compatibility, privacy and replay semantics."),
    "resilience_engineer": ("operations", ["reliability", "distributed_systems"], ["fault_model", "test", "review"], ["idempotency_expert", "distributed_systems_expert"], "Test timeouts, retries, duplicate delivery, dependency loss and partial failure while preventing retry storms and data corruption."),
    "database_reliability_engineer": ("data", ["database", "reliability"], ["profile", "backup", "operate"], ["database_performance_expert", "backup_recovery_expert"], "Own database capacity, query health, replication, backup verification, recovery and safe operational change."),
    "data_privacy_reviewer": ("security", ["privacy", "data"], ["classify", "minimize", "review"], ["data_privacy_expert"], "Trace personal and regulated data across collection, processing, retention, access, export and deletion with evidence."),
    "mobile_architect": ("mobile", ["mobile", "architecture"], ["design", "code", "review"], ["mobile_offline_sync_expert", "mobile_security_expert"], "Design mobile boundaries for offline behavior, synchronization, secure storage, permissions, upgrades and backend compatibility."),
    "mobile_qa_engineer": ("quality", ["mobile", "testing"], ["test", "accessibility", "compatibility"], ["testing_strategy_expert", "mobile_security_expert"], "Test devices, OS versions, lifecycle interruption, networks, permissions, accessibility and store-release regressions."),
    "ai_solution_architect": ("ai", ["ai", "architecture"], ["design", "evaluate", "cost"], ["rag_expert", "mcp_expert", "ai_guardrails_expert"], "Choose deterministic code, retrieval, tools and models deliberately while budgeting quality, latency, privacy and cost."),
    "rag_engineer": ("ai", ["ai", "retrieval"], ["ingest", "retrieve", "evaluate"], ["rag_expert", "vector_database_expert"], "Build traceable ingestion and retrieval with permission-aware indexing, grounded answers and measurable relevance."),
    "ai_evaluation_engineer": ("quality", ["ai", "testing"], ["dataset", "evaluate", "regress"], ["llm_evaluation_expert", "structured_output_expert"], "Create representative evaluation sets, deterministic checks and statistical review for model, prompt and retrieval changes."),
    "ai_red_team_reviewer": ("security", ["ai", "security"], ["attack", "evaluate", "review"], ["prompt_security_expert", "adversarial_review_expert"], "Probe prompt injection, tool abuse, data exfiltration, unsafe autonomy and cross-tenant retrieval with bounded test plans."),
    "payments_domain_reviewer": ("domain", ["payments", "fintech"], ["invariants", "risk", "review"], ["fintech_domain_expert", "accounting_domain_expert"], "Protect monetary precision, authorization, idempotency, reconciliation, refunds, audit and failure-state invariants."),
    "inventory_consistency_reviewer": ("domain", ["inventory", "erp"], ["invariants", "concurrency", "review"], ["restobar_domain_expert", "accounting_domain_expert"], "Review stock movements, reservations, costing, concurrency, reconciliation and immutable audit trails."),
}


SKILLS = {
    # Web expansion
    "react_expert": ("frontend", ["web"], ["react"], ["components", "state", "test"], "Model UI as accessible components with explicit state ownership, stable identities and effect boundaries; measure rendering before memoizing."),
    "nextjs_expert": ("frontend", ["web", "saas"], ["nextjs", "react", "nodejs", "typescript"], ["ssr", "routing", "cache"], "Choose server, client and edge execution intentionally; make caching, revalidation, authentication and streaming behavior observable and testable."),
    "angular_expert": ("frontend", ["web", "enterprise"], ["angular", "typescript"], ["components", "routing", "test"], "Use standalone boundaries, typed forms and dependency injection deliberately; keep domain state independent from components and framework lifecycle."),
    "spring_boot_expert": ("backend", ["backend", "enterprise"], ["java", "spring_boot"], ["api", "security", "persistence"], "Keep domain logic outside controllers and ORM entities; make transactions, authorization, validation and actuator exposure explicit."),
    "go_expert": ("language", ["backend", "platform"], ["go"], ["concurrency", "api", "test"], "Prefer simple packages and explicit errors; bound goroutines, propagate context cancellation, prevent leaks and test race-sensitive behavior."),
    "laravel_expert": ("backend", ["backend", "web"], ["php", "laravel"], ["api", "orm", "queue"], "Use policies for authorization, validate request boundaries, control Eloquent query shape and make jobs idempotent and retry-safe."),
    "mysql_expert": ("database", ["database"], ["mysql"], ["sql", "index", "migration"], "Design with engine, collation and isolation behavior in mind; inspect execution plans and use online-compatible schema changes with verified backups."),
    "redis_expert": ("data", ["cache", "distributed_systems"], ["redis"], ["cache", "lock", "queue"], "Define key lifecycle, eviction, consistency and failure behavior; never treat cache locks as safe without ownership tokens and expiry analysis."),
    "playwright_expert": ("testing", ["web", "testing"], ["playwright"], ["e2e", "browser", "accessibility"], "Test user-visible outcomes with resilient locators, isolated data and trace artifacts across browsers; avoid arbitrary sleeps."),
    "openid_connect_expert": ("security", ["identity", "api"], ["openid_connect"], ["oauth", "sso", "authorization"], "Validate issuer, audience, nonce, state, PKCE and redirect boundaries; separate authentication claims from application authorization."),
    # Cloud-native
    "kubernetes_expert": ("platform", ["deployment", "cloud"], ["kubernetes"], ["orchestration", "security", "operate"], "Set requests/limits, probes, disruption budgets and security contexts; design rollout, rollback and network policy before production use."),
    "terraform_expert": ("platform", ["infrastructure", "cloud"], ["terraform"], ["iac", "plan", "state"], "Use reviewed plans, remote protected state, constrained modules and immutable inputs; never apply destructive infrastructure changes implicitly."),
    "helm_expert": ("platform", ["deployment", "kubernetes"], ["helm", "kubernetes"], ["template", "release", "rollback"], "Keep values schemas explicit, render and validate manifests before release, and avoid templates that hide unsafe defaults."),
    "argocd_expert": ("platform", ["deployment", "kubernetes"], ["argocd", "kubernetes"], ["gitops", "sync", "rollback"], "Make desired state and promotion observable; constrain automated sync, drift correction and pruning according to environment risk."),
    "github_actions_expert": ("platform", ["ci", "release"], ["github_actions"], ["ci", "security", "artifact"], "Pin actions proportionally, minimize token permissions, isolate untrusted contributions and preserve artifact provenance and evidence."),
    "aws_expert": ("cloud", ["cloud", "infrastructure"], ["aws"], ["iam", "network", "operate"], "Design account, IAM, network, encryption, logging and service limits explicitly; prefer managed services only when ownership and exit cost are understood."),
    "azure_expert": ("cloud", ["cloud", "enterprise"], ["azure"], ["identity", "network", "operate"], "Integrate tenant identity, subscriptions, policy, private connectivity and diagnostics with clear responsibility and cost boundaries."),
    "gcp_expert": ("cloud", ["cloud", "data"], ["gcp"], ["iam", "network", "operate"], "Use projects, service accounts, organization policy and audit logging to create explicit trust and billing boundaries."),
    "nginx_expert": ("platform", ["web", "network"], ["nginx"], ["proxy", "tls", "performance"], "Configure forwarding trust, timeouts, body limits, TLS and health behavior explicitly; test real client IP and failure propagation."),
    "cloud_cost_optimization_expert": ("operations", ["cloud", "cost"], ["aws", "azure", "gcp"], ["forecast", "budget", "optimize"], "Attribute cost to owner and workload, forecast scenarios and enforce anomaly/budget guardrails while preserving SLO and security constraints."),
    # Distributed systems
    "kafka_expert": ("integration", ["events", "distributed_systems"], ["kafka"], ["stream", "schema", "operate"], "Define partition keys, ordering, retention, consumer ownership and replay behavior; monitor lag and protect schema compatibility."),
    "rabbitmq_expert": ("integration", ["events", "distributed_systems"], ["rabbitmq"], ["queue", "routing", "retry"], "Design exchanges, acknowledgements, prefetch, dead-letter and retry topology to avoid message loss and poison-message loops."),
    "event_driven_architecture_expert": ("architecture", ["events", "integration"], ["kafka", "rabbitmq"], ["event_model", "contract", "review"], "Publish facts with clear ownership and schemas; distinguish commands from events and define delivery, ordering, privacy and replay semantics."),
    "distributed_systems_expert": ("architecture", ["distributed_systems"], [], ["consistency", "resilience", "review"], "State consistency, availability and partition assumptions; design timeouts, retries, deduplication and reconciliation before introducing distribution."),
    "microservices_expert": ("architecture", ["distributed_systems", "backend"], ["kubernetes"], ["boundaries", "api", "operate"], "Require independent ownership and deployment benefits before splitting services; budget network failure, observability and data ownership costs."),
    "modular_monolith_expert": ("architecture", ["architecture", "backend"], [], ["modules", "boundaries", "test"], "Enforce module contracts and data ownership in one deployable, preserving a low-cost path to later extraction without premature distribution."),
    "outbox_pattern_expert": ("integration", ["events", "database"], ["postgresql", "mysql", "sql_server"], ["transaction", "publish", "reconcile"], "Atomically persist domain change and event intent, then publish idempotently with monitoring, cleanup and replay controls."),
    "idempotency_expert": ("reliability", ["api", "events", "payments"], [], ["deduplicate", "retry", "test"], "Define operation identity, result retention and concurrency semantics so duplicate requests or messages cannot duplicate effects."),
    # Data platforms
    "sql_server_expert": ("database", ["database", "enterprise"], ["sql_server"], ["sql", "index", "migration"], "Use constraints and execution plans, understand isolation and locking, and design online deployments, backups and recovery for the selected edition."),
    "mongodb_expert": ("database", ["database"], ["mongodb"], ["document", "index", "migration"], "Model documents from atomic access patterns, enforce schemas and indexes, and plan shard keys, transactions and migration compatibility deliberately."),
    "opensearch_expert": ("data", ["search", "observability"], ["opensearch"], ["index", "query", "operate"], "Design mappings and lifecycle before indexing; bound query cost, shard growth, refresh behavior and sensitive-data exposure."),
    "clickhouse_expert": ("data", ["analytics", "database"], ["clickhouse"], ["model", "query", "operate"], "Choose sort and partition keys from workload evidence, control cardinality and mutation cost, and validate retention and replication."),
    "data_modeling_expert": ("data", ["data", "database"], [], ["model", "invariants", "review"], "Translate business invariants into explicit entities, keys, constraints, histories and ownership; separate operational and analytical models."),
    "database_performance_expert": ("database", ["database", "performance"], ["postgresql", "mysql", "sql_server"], ["profile", "index", "capacity"], "Measure representative queries, plans, waits and cardinality; optimize the workload while accounting for write, storage and maintenance cost."),
    "backup_recovery_expert": ("operations", ["database", "reliability"], [], ["backup", "restore", "exercise"], "Set RPO/RTO, encrypt and isolate backups, verify completeness and regularly restore into a controlled environment with evidence."),
    "data_privacy_expert": ("security", ["privacy", "data"], [], ["classify", "minimize", "retain"], "Inventory data purpose and sensitivity, minimize collection, constrain access, define retention/deletion and test subject-right workflows."),
    # Mobile
    "flutter_expert": ("mobile", ["mobile"], ["flutter", "dart"], ["ui", "state", "test"], "Separate presentation, domain and platform services; test lifecycle, navigation, accessibility and platform differences without hiding them behind abstractions."),
    "react_native_expert": ("mobile", ["mobile"], ["react_native", "react", "nodejs", "typescript"], ["ui", "native_bridge", "test"], "Control JS/native boundaries, lifecycle and rendering; profile real devices and test permissions, upgrades and degraded networks."),
    "swiftui_expert": ("mobile", ["ios", "mobile"], ["swiftui"], ["ui", "state", "test"], "Model state ownership and navigation explicitly, respect platform conventions and test accessibility, concurrency and persistence behavior."),
    "kotlin_android_expert": ("mobile", ["android", "mobile"], ["kotlin"], ["ui", "lifecycle", "test"], "Use lifecycle-aware state and structured concurrency; test process death, configuration changes, permissions and background constraints."),
    "mobile_offline_sync_expert": ("mobile", ["mobile", "distributed_systems"], [], ["offline", "sync", "conflict"], "Define local source of truth, operation identity, ordering and conflict policy; test retries, clock drift, partial sync and schema upgrades."),
    "mobile_security_expert": ("security", ["mobile", "security"], ["flutter", "react_native", "swiftui", "kotlin"], ["storage", "permission", "review"], "Protect tokens and local data, minimize permissions, validate deep links and transport trust, and assume clients can be inspected or modified."),
    # AI systems
    "mcp_expert": ("ai", ["ai", "integration"], ["mcp"], ["tool", "permission", "protocol"], "Expose narrow, well-described tools with least privilege, validated arguments, bounded outputs and clear read/write side effects."),
    "rag_expert": ("ai", ["ai", "retrieval"], ["vector_database"], ["ingest", "retrieve", "ground"], "Preserve source identity and permissions through chunking, indexing and retrieval; measure relevance and require citations for grounded answers."),
    "vector_database_expert": ("data", ["ai", "database"], ["vector_database", "postgresql"], ["embedding", "index", "retrieve"], "Select metric, dimensions and index from measured recall/latency; enforce tenant filters, deletion and embedding-version migration."),
    "llm_evaluation_expert": ("quality", ["ai", "testing"], [], ["dataset", "score", "regress"], "Use representative frozen cases, deterministic assertions where possible, blinded review where necessary and confidence intervals for noisy metrics."),
    "prompt_security_expert": ("security", ["ai", "security"], [], ["injection", "exfiltration", "review"], "Separate trusted instructions from untrusted content, constrain tool/data access and test direct, indirect and encoded prompt-injection attacks."),
    "tool_calling_expert": ("ai", ["ai", "integration"], ["mcp"], ["schema", "permission", "execute"], "Define strict schemas and side-effect metadata, validate targets and make approval and idempotency requirements machine-readable."),
    "structured_output_expert": ("ai", ["ai", "api"], [], ["schema", "validate", "repair"], "Use explicit versioned schemas, reject invalid output safely and separate syntactic repair from semantic acceptance."),
    "model_routing_expert": ("ai", ["ai", "platform"], [], ["route", "fallback", "evaluate"], "Route by measured capability, latency, privacy and cost; test fallback semantics and avoid silently weakening safety or output contracts."),
    "ai_cost_optimization_expert": ("operations", ["ai", "cost"], [], ["budget", "measure", "optimize"], "Attribute token, model, retrieval and tool cost per workflow; optimize only with quality and latency regression evidence."),
    "ai_guardrails_expert": ("security", ["ai", "governance"], [], ["policy", "moderate", "evaluate"], "Layer input, policy, tool and output controls around explicit risks; measure false positives, bypasses and safe failure behavior."),
    # Domain packs
    "ecommerce_domain_expert": ("domain", ["ecommerce"], [], ["catalog", "order", "payment"], "Protect price snapshots, promotions, stock reservation, order states, fulfillment, returns and payment reconciliation."),
    "restobar_domain_expert": ("domain", ["restobar", "erp"], [], ["pos", "inventory", "cash"], "Model menus, modifiers, tables, kitchen flow, split payments, cash shifts, recipes, stock consumption and audit."),
    "healthcare_domain_expert": ("domain", ["healthcare"], [], ["privacy", "clinical", "audit"], "Separate clinical facts from workflow, enforce consent and least privilege, preserve provenance and make safety-critical changes reviewable."),
    "fintech_domain_expert": ("domain", ["fintech", "payments"], [], ["ledger", "payment", "risk"], "Use precise money types, immutable ledgers, idempotent operations, reconciliation and explicit pending/failure states."),
    "logistics_domain_expert": ("domain", ["logistics"], [], ["shipment", "tracking", "optimization"], "Model shipment custody, events, time windows, capacity, route changes, exceptions and proof of delivery."),
    "manufacturing_domain_expert": ("domain", ["manufacturing", "erp"], [], ["bom", "production", "quality"], "Protect BOM versions, work orders, material consumption, lot traceability, yields, quality holds and costing."),
    "crm_domain_expert": ("domain", ["crm", "saas"], [], ["account", "pipeline", "activity"], "Define account/contact identity, ownership, consent, activity history, pipeline transitions and forecast semantics."),
    "accounting_domain_expert": ("domain", ["accounting", "erp"], [], ["ledger", "period", "reconcile"], "Enforce balanced postings, immutable audit, currencies, business dates, period close, adjustments and reconciliation."),
}


TECHNOLOGIES = {
    "python": "language", "nodejs": "runtime", "typescript": "language", "dotnet": "runtime",
    "dotnet_sdk": "sdk", "dotnet_runtime": "runtime",
    "django": "framework", "nuxt": "framework", "postgresql": "database", "docker_engine": "platform",
    "docker_compose": "platform", "ubuntu": "operating_system", "react": "framework", "nextjs": "framework",
    "angular": "framework", "java": "language", "spring_boot": "framework", "go": "language", "php": "language",
    "laravel": "framework", "mysql": "database", "redis": "database", "playwright": "testing",
    "openid_connect": "protocol", "kubernetes": "platform", "terraform": "infrastructure_as_code",
    "helm": "platform", "argocd": "delivery", "github_actions": "ci", "aws": "cloud", "azure": "cloud",
    "gcp": "cloud", "nginx": "web_server", "kafka": "messaging", "rabbitmq": "messaging",
    "sql_server": "database", "mongodb": "database", "opensearch": "search", "clickhouse": "database",
    "flutter": "framework", "dart": "language", "react_native": "framework", "swiftui": "framework",
    "kotlin": "language", "mcp": "protocol", "vector_database": "database",
}


STACK_PROFILES = [
    {"id": "nextjs_saas", "technologies": ["nodejs", "typescript", "react", "nextjs", "postgresql", "redis", "docker_engine"], "agents": ["web_platform_engineer", "backend_engineer", "identity_access_engineer", "database_engineer", "qa_engineer"], "skills": ["nextjs_expert", "openid_connect_expert", "postgresql_expert", "redis_expert", "playwright_expert"], "required_gates": ["API_COMPATIBILITY", "ACCESSIBILITY", "SECURITY_CHECK", "BUILD"], "version_status": "VERIFY_BEFORE_USE"},
    {"id": "spring_enterprise", "technologies": ["java", "spring_boot", "postgresql", "redis", "kafka", "docker_engine"], "agents": ["software_architect", "backend_engineer", "identity_access_engineer", "integration_engineer", "qa_engineer"], "skills": ["spring_boot_expert", "openid_connect_expert", "postgresql_expert", "kafka_expert", "testing_strategy_expert"], "required_gates": ["API_COMPATIBILITY", "EVENT_COMPATIBILITY", "SECURITY_CHECK", "BUILD"], "version_status": "VERIFY_BEFORE_USE"},
    {"id": "dotnet_enterprise", "technologies": ["dotnet", "sql_server", "redis", "docker_engine"], "agents": ["software_architect", "backend_engineer", "identity_access_engineer", "database_engineer"], "skills": ["dotnet_expert", "sql_server_expert", "redis_expert", "openid_connect_expert"], "required_gates": ["API_COMPATIBILITY", "SECURITY_CHECK", "BUILD"], "version_status": "VERIFY_BEFORE_USE"},
    {"id": "cloud_native_microservices", "technologies": ["go", "kubernetes", "terraform", "helm", "argocd", "kafka", "postgresql", "redis"], "agents": ["cloud_architect", "platform_engineer", "distributed_systems_architect", "resilience_engineer", "sre_engineer"], "skills": ["go_expert", "kubernetes_expert", "terraform_expert", "event_driven_architecture_expert", "distributed_systems_expert"], "required_gates": ["INFRASTRUCTURE_PLAN_REVIEW", "IAM_LEAST_PRIVILEGE", "EVENT_COMPATIBILITY", "DISASTER_RECOVERY"], "version_status": "VERIFY_BEFORE_USE"},
    {"id": "flutter_mobile_backend", "technologies": ["flutter", "dart", "python", "django", "postgresql"], "agents": ["mobile_architect", "mobile_qa_engineer", "backend_engineer", "identity_access_engineer"], "skills": ["flutter_expert", "mobile_offline_sync_expert", "mobile_security_expert", "django_expert", "postgresql_expert"], "required_gates": ["MOBILE_SECURITY", "API_COMPATIBILITY", "SECURITY_CHECK"], "version_status": "VERIFY_BEFORE_USE"},
    {"id": "ai_rag_platform", "technologies": ["python", "mcp", "postgresql", "vector_database", "docker_engine"], "agents": ["ai_solution_architect", "rag_engineer", "ai_evaluation_engineer", "ai_red_team_reviewer", "data_privacy_reviewer"], "skills": ["rag_expert", "mcp_expert", "vector_database_expert", "llm_evaluation_expert", "prompt_security_expert"], "required_gates": ["AI_EVALUATION", "PROMPT_INJECTION_TEST", "TOOL_PERMISSION_REVIEW", "GROUNDING_VALIDATION", "DATA_PRIVACY"], "version_status": "VERIFY_BEFORE_USE"},
]


COMPATIBILITY = [
    {"id": "nextjs_requires_react_node", "when": "nextjs", "requires": ["react", "nodejs", "typescript"], "confidence": "high"},
    {"id": "spring_requires_java", "when": "spring_boot", "requires": ["java"], "confidence": "high"},
    {"id": "helm_requires_kubernetes", "when": "helm", "requires": ["kubernetes"], "confidence": "high"},
    {"id": "argocd_requires_kubernetes", "when": "argocd", "requires": ["kubernetes"], "confidence": "high"},
    {"id": "flutter_requires_dart", "when": "flutter", "requires": ["dart"], "confidence": "high"},
    {"id": "react_native_requires_react_node", "when": "react_native", "requires": ["react", "nodejs"], "confidence": "high"},
    {"id": "verified_version_required", "when": "profile_activation", "requires_policy": "TECH_STACK_VERSION_POLICY", "confidence": "high"},
]


DOMAIN_PACKS = [
    {"id": "ecommerce", "agents": ["product_manager", "software_architect", "payments_domain_reviewer", "inventory_consistency_reviewer"], "skills": ["ecommerce_domain_expert", "fintech_domain_expert", "accounting_domain_expert"], "risk_factors": ["payments", "personal_data", "external_integrations"]},
    {"id": "restobar", "agents": ["erp_domain_expert", "inventory_consistency_reviewer", "payments_domain_reviewer"], "skills": ["restobar_domain_expert", "accounting_domain_expert"], "risk_factors": ["payments", "financial_data", "database_migrations"]},
    {"id": "healthcare", "agents": ["data_privacy_reviewer", "security_architect", "adversarial_reviewer"], "skills": ["healthcare_domain_expert", "data_privacy_expert", "application_security_expert"], "risk_factors": ["personal_data", "authorization", "security"]},
    {"id": "fintech", "agents": ["payments_domain_reviewer", "security_architect", "database_reliability_engineer"], "skills": ["fintech_domain_expert", "accounting_domain_expert", "idempotency_expert"], "risk_factors": ["payments", "financial_data", "production"]},
    {"id": "logistics", "agents": ["integration_engineer", "resilience_engineer", "data_engineer"], "skills": ["logistics_domain_expert", "event_driven_architecture_expert"], "risk_factors": ["external_integrations", "public_api"]},
    {"id": "manufacturing", "agents": ["erp_domain_expert", "inventory_consistency_reviewer", "database_reliability_engineer"], "skills": ["manufacturing_domain_expert", "accounting_domain_expert"], "risk_factors": ["database_migrations", "financial_data"]},
    {"id": "crm", "agents": ["product_manager", "data_privacy_reviewer", "integration_engineer"], "skills": ["crm_domain_expert", "data_privacy_expert"], "risk_factors": ["personal_data", "external_integrations"]},
]


ROUTES = [
    {"id": "nextjs_react", "keywords": ["nextjs", "next.js", "react"], "agents": ["web_platform_engineer", "frontend_engineer", "identity_access_engineer", "qa_engineer"], "skills": ["nextjs_expert", "react_expert", "openid_connect_expert", "playwright_expert"]},
    {"id": "spring_java", "keywords": ["spring boot", "spring", "java"], "agents": ["backend_engineer", "software_architect", "identity_access_engineer"], "skills": ["spring_boot_expert", "openid_connect_expert", "testing_strategy_expert"]},
    {"id": "cloud_kubernetes", "keywords": ["kubernetes", "helm", "argocd", "cloud native"], "agents": ["cloud_architect", "platform_engineer", "kubernetes_engineer", "infrastructure_security_reviewer"], "skills": ["kubernetes_expert", "helm_expert", "terraform_expert", "argocd_expert"]},
    {"id": "cloud_provider", "keywords": ["aws", "azure", "gcp", "cloud"], "agents": ["cloud_architect", "finops_analyst", "infrastructure_security_reviewer"], "skills": ["cloud_cost_optimization_expert", "terraform_expert"]},
    {"id": "event_driven", "keywords": ["kafka", "rabbitmq", "event", "evento", "event driven", "eventos"], "agents": ["distributed_systems_architect", "event_contract_reviewer", "resilience_engineer"], "skills": ["event_driven_architecture_expert", "idempotency_expert", "outbox_pattern_expert"]},
    {"id": "inventory_consistency", "keywords": ["inventory", "inventario", "stock"], "agents": ["inventory_consistency_reviewer", "database_reliability_engineer", "qa_engineer"], "skills": ["data_modeling_expert", "accounting_domain_expert", "idempotency_expert"]},
    {"id": "mobile", "keywords": ["flutter", "react native", "swiftui", "android", "mobile"], "agents": ["mobile_architect", "mobile_qa_engineer", "identity_access_engineer"], "skills": ["mobile_offline_sync_expert", "mobile_security_expert"]},
    {"id": "ai_rag", "keywords": ["rag", "mcp", "vector", "agente de ia", "ai agent"], "agents": ["ai_solution_architect", "rag_engineer", "ai_evaluation_engineer", "ai_red_team_reviewer"], "skills": ["rag_expert", "mcp_expert", "llm_evaluation_expert", "prompt_security_expert", "tool_calling_expert"]},
    {"id": "privacy", "keywords": ["privacy", "privacidad", "pii", "healthcare", "salud", "patient", "paciente"], "agents": ["data_privacy_reviewer", "security_architect"], "skills": ["data_privacy_expert", "healthcare_domain_expert"]},
    {"id": "payments", "keywords": ["payment", "pago", "fintech", "ledger"], "agents": ["payments_domain_reviewer", "security_architect", "database_reliability_engineer"], "skills": ["fintech_domain_expert", "accounting_domain_expert", "idempotency_expert"]},
]


GATES = {
    "INFRASTRUCTURE_PLAN_REVIEW": "Review the exact infrastructure plan, replacements, deletions, IAM, network exposure, state and rollback before apply.",
    "CLOUD_COST_IMPACT": "Estimate recurring and peak cost, ownership tags, budget alerts and cost change under expected growth and failure scenarios.",
    "IAM_LEAST_PRIVILEGE": "Prove every human and workload identity has the minimum resource, action, condition and duration required.",
    "DISASTER_RECOVERY": "Verify RPO/RTO, backup isolation, dependency order, restore instructions and evidence from a recent recovery exercise.",
    "CONTAINER_SECURITY": "Inspect base provenance, packages, non-root execution, capabilities, secrets, filesystem permissions and image vulnerabilities.",
    "EVENT_COMPATIBILITY": "Diff event schemas and semantics, consumer compatibility, ordering, retention, privacy and replay before publication.",
    "IDEMPOTENCY": "Test duplicate, concurrent and retried requests/messages against operation identity and result-retention rules.",
    "MOBILE_SECURITY": "Review secure storage, permissions, deep links, transport, logging, local data and compromised-client assumptions.",
    "AI_EVALUATION": "Run representative frozen evaluation cases and compare quality, safety, latency and cost against approved thresholds.",
    "PROMPT_INJECTION_TEST": "Exercise direct, indirect, encoded and multi-step injection attempts across retrieval and tool boundaries.",
    "TOOL_PERMISSION_REVIEW": "Verify tool descriptions, schemas, side effects, target validation, least privilege, approval and audit behavior.",
    "MODEL_COST_BUDGET": "Measure and cap model, retrieval and tool cost per successful workflow with anomaly detection.",
    "GROUNDING_VALIDATION": "Measure retrieval relevance and answer support; ensure source identity, permissions and citations survive the pipeline.",
    "DATA_PRIVACY": "Trace classified data purpose, access, storage, retention, export, deletion and evidence without exposing values.",
}


REFERENCES = {
    "web_saas": "Use a browser/API boundary, server-side authorization, explicit cache ownership, transactional data, background jobs and end-to-end observability. Keep frontend independent from direct database access.",
    "cloud_native": "Separate application, platform and cloud-account ownership. Delivery flows through reviewed IaC and GitOps; workloads have resource, network, identity, telemetry and rollback contracts.",
    "event_driven": "Each event has an owning domain, versioned schema and delivery semantics. Use transactional outbox where database change and publication must agree; consumers are idempotent and replayable.",
    "mobile_backend": "The mobile client is an untrusted intermittently connected replica. Backend contracts are versioned; local operations have identity, conflict and retry rules; tokens and sensitive data use platform storage.",
    "ai_rag": "Ingestion preserves source identity, classification and permissions. Retrieval is tenant-aware; model context is untrusted data; tools are least-privileged; evaluation covers quality, injection, grounding and cost.",
    "regulated_domain": "Classify data and decisions, minimize collection, segregate duties, make access and change auditable, preserve retention/deletion rules and require human approval for irreversible or safety-critical actions.",
}


SCENARIOS = {
    "nextjs_saas_feature": ("Add a role-protected Next.js SaaS dashboard", ["web_platform_engineer", "identity_access_engineer"], ["nextjs_expert", "openid_connect_expert", "playwright_expert"]),
    "spring_event_service": ("Build a Spring Boot service that publishes Kafka events", ["backend_engineer", "event_contract_reviewer"], ["spring_boot_expert", "event_driven_architecture_expert", "outbox_pattern_expert"]),
    "kubernetes_deployment": ("Deploy a production workload with Kubernetes and Terraform", ["platform_engineer", "infrastructure_security_reviewer"], ["kubernetes_expert", "terraform_expert"]),
    "event_consistency": ("Prevent duplicate payment effects during event retries", ["payments_domain_reviewer", "resilience_engineer"], ["idempotency_expert", "fintech_domain_expert"]),
    "mobile_offline": ("Build an offline-capable mobile inventory workflow", ["mobile_architect", "inventory_consistency_reviewer"], ["mobile_offline_sync_expert", "mobile_security_expert"]),
    "rag_security": ("Build a permission-aware RAG assistant with tools", ["rag_engineer", "ai_red_team_reviewer"], ["rag_expert", "prompt_security_expert", "tool_calling_expert"]),
    "healthcare_privacy": ("Add patient-data export and deletion workflows", ["data_privacy_reviewer", "security_architect"], ["healthcare_domain_expert", "data_privacy_expert"]),
}


def agent_rows() -> list[dict[str, Any]]:
    rows = []
    critical = {"infrastructure_security_reviewer", "disaster_recovery_planner", "data_privacy_reviewer", "ai_red_team_reviewer", "payments_domain_reviewer"}
    for aid, (category, domains, capabilities, required, mission) in AGENTS.items():
        path = f"agents/prompt_agent_{aid}.md"
        write(path, f"""---
id: {aid}
category: {category}
provider_neutral: true
version: 1.0.0
last_reviewed: {TODAY}
---

# PALLAQUINO agent: {aid.replace('_', ' ').title()}

## Mission

{mission}

## Operating contract

1. Read governing policy, current state, acceptance criteria, risk and capability evidence.
2. Declare assumptions, intended files, external side effects and required approvals.
3. Prefer reversible increments and reserve shared files before implementation.
4. Produce inspectable artifacts and evidence; never convert an unrun check into passed.
5. Return changed contracts, residual risk, rollback, confidence and next pipeline stage.

## Specialist review

- Which domain invariant or failure model is most important here?
- Which compatibility, security, operational and cost assumptions require evidence?
- What would make this change unsafe to deploy or difficult to reverse?
""")
        rows.append({"id": aid, "path": path, "category": category, "domains": domains, "capabilities": capabilities, "technologies": [], "required_skills": required, "can_write_code": aid not in {"api_governance_reviewer", "infrastructure_security_reviewer", "event_contract_reviewer", "data_privacy_reviewer", "ai_red_team_reviewer", "payments_domain_reviewer", "inventory_consistency_reviewer"}, "can_review": True, "can_deploy": aid in {"platform_engineer", "kubernetes_engineer"}, "risk_limit": "CRITICAL" if aid in critical else "HIGH", "context_weight": 3, "priority": 55, "provider_neutral": True, "version": "1.0.0", "last_reviewed": TODAY, "deprecated": False, "superseded_by": None})
    return rows


def skill_rows() -> list[dict[str, Any]]:
    rows = []
    high_categories = {"security", "database", "operations", "cloud", "reliability"}
    for sid, (category, domains, technologies, capabilities, guidance) in SKILLS.items():
        path = f"skills/{sid}/SKILL.md"
        write(path, f"""---
id: {sid}
category: {category}
provider_neutral: true
version: 1.0.0
last_reviewed: {TODAY}
---

# {sid.replace('_', ' ').title()}

## Specialized guidance

{guidance}

## Required workflow

1. Verify repository facts, prerequisites and applicable policy before proposing change.
2. Resolve concrete versions only through the verified stack policy; this skill is version-agnostic.
3. State contracts, failure behavior, security, compatibility, evidence commands and rollback impact.
4. Load only task-relevant references and hand back concise, inspectable artifacts.

## Evidence standard

Record exact commands or primary sources, observed results and confidence. Unknown
behavior remains unknown; provider capability and repository text do not prove a gate passed.
""")
        rows.append({"id": sid, "path": path, "category": category, "tags": [category] + domains, "domains": domains, "technologies": technologies, "capabilities": capabilities, "context_weight": 2, "risk_level": "HIGH" if category in high_categories else "MEDIUM", "dependencies": [], "conflicts": [], "prerequisites": [], "provider_neutral": True, "version": "1.0.0", "last_reviewed": TODAY, "deprecated": False, "superseded_by": None})
    return rows


def main() -> None:
    agents = load("registry/agents.json")
    skills = load("registry/skills.json")
    agents["agents"] = merge_rows(agents["agents"], agent_rows())
    skills["skills"] = merge_rows(skills["skills"], skill_rows())
    dump("registry/agents.json", agents)
    dump("registry/skills.json", skills)

    technology_rows = [{"id": tid, "category": category, "version_agnostic": True, "selection_status": "VERIFIED_BASELINE" if tid in {"python", "nodejs", "typescript", "django", "nuxt", "postgresql", "dotnet_sdk", "dotnet_runtime", "docker_engine", "docker_compose", "ubuntu"} else "VERIFY_BEFORE_USE"} for tid, category in sorted(TECHNOLOGIES.items())]
    dump("registry/technology_catalog.json", {"schema_version": 1, "policy": "Concrete versions require official-source verification before profile activation", "technologies": technology_rows})
    dump("registry/stack_profiles.json", {"schema_version": 1, "profiles": STACK_PROFILES})
    dump("registry/technology_compatibility.json", {"schema_version": 1, "rules": COMPATIBILITY})
    dump("registry/domain_packs.json", {"schema_version": 1, "packs": DOMAIN_PACKS})

    coverage = []
    all_agents = agents["agents"]
    all_skills = skills["skills"]
    for tech in technology_rows:
        tid = tech["id"]
        coverage.append({"technology": tid, "agents": sorted(a["id"] for a in all_agents if tid in a.get("technologies", [])), "skills": sorted(s["id"] for s in all_skills if tid in s.get("technologies", []))})
    dump("registry/agent_skill_coverage.json", {"schema_version": 1, "coverage": coverage})

    routing = load("registry/routing_rules.json")
    routing["rules"] = merge_rows(routing["rules"], ROUTES)
    dump("registry/routing_rules.json", routing)

    for gate, description in GATES.items():
        write(f"pipeline/gates/{gate}.md", f"""# {gate}

{description}

## Evidence

Record scope, exact command or reviewer, timestamp, result, artifact, confidence,
residual risk and remediation target. Failure returns to `IMPLEMENTATION` or
`PLAN` when architecture, cost or contract assumptions must change.
""")

    for rid, body in REFERENCES.items():
        write(f"architecture/reference_architectures/{rid}.md", f"""# Reference architecture: {rid.replace('_', ' ').title()}

{body}

This is a decision aid, not a mandatory blueprint. Select it only after repository,
domain, risk and capability analysis; record material deviations as ADRs.
""")

    for sid, (request, required_agents, required_skills) in SCENARIOS.items():
        dump(f"evaluation/{sid}/scenario.json", {"id": sid, "request": request, "required_agents": required_agents, "required_skills": required_skills, "expected": "Select the specialized route, proportional gates and no unrelated expert without rationale."})
    dump("evaluation/stack_routing/golden.json", {"schema_version": 1, "cases": [{"request": request, "required_agents": agents, "required_skills": skills} for request, agents, skills in SCENARIOS.values()]})

    print(json.dumps({"agents": len(agents["agents"]), "skills": len(skills["skills"]), "technologies": len(technology_rows), "profiles": len(STACK_PROFILES), "domain_packs": len(DOMAIN_PACKS), "routes": len(routing["rules"]), "gates_added": len(GATES), "scenarios_added": len(SCENARIOS)}, indent=2))


if __name__ == "__main__":
    main()
