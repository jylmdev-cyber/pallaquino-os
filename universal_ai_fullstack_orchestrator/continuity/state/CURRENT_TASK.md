# Current task

- ID: PAL-010
- Objective: evolve PALLAQUINO to 0.4.0 (orchestration engine, persistent memory, provider abstraction) per the v0.4.0 master request
- Mode: BROWNFIELD
- Autonomy: STANDARD (local, non-destructive; push, tag and release require explicit approval)
- Scope: intent analyzer, agent router, task planner, multi-agent scheduler, executors, project memory, providers (mock, Ollama), observability, CLI, docs
- Status: COMPLETE as a local release candidate on branch `feat/v0.4.0-orchestration`
- Risk: HIGH (new execution engine with write access to workspaces), mitigated by deny-by-default grants, approvals and the adversarial suite
- Acceptance: 154 tests pass; reference scenario offline passes; real-provider variant reported as not executed
- Confidence: high for implemented behaviour; unverified on Linux and with a real model
