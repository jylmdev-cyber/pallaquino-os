# Architecture state

- Status: documented (`docs/ARCHITECTURE.md`, ADR-0001 to ADR-0016)
- Updated: 2026-10-14
- Implemented:
  - registries, pipeline data, continuity, CLI, validators, secret scanning, isolated init, deterministic release;
  - orchestration engine, project memory and providers (0.4.0);
  - plugin system with hash-bound trust and process isolation, MCP 2026-07-28 client and connections, OAuth and credential manager,
    network policy, unified tool registry, permission and execution gateways, tool router, filesystem/Git/SQLite/GitHub adapters,
    plugin SDK (0.5.0).
- Planned: `subscriptions/listen`, OS-level plugin sandboxing, Docker and cloud adapters, PostgreSQL and MySQL connectors,
  loaders for agent, skill and template plugins, project factory (0.6.0), control center UI.
- Confidence: high
