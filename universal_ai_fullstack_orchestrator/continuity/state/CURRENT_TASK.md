# Current task

- ID: PAL-010
- Objective: evolve PALLAQUINO to 0.4.0 (orchestration engine, persistent memory, provider abstraction) per the v0.4.0 master request
- Mode: BROWNFIELD
- Autonomy: STANDARD (publication approved by the owner on 2026-10-14: PR, merge after green CI, tag `v0.4.0`, GitHub Release)
- Scope: intent analyzer, agent router, task planner, multi-agent scheduler, executors, project memory, providers (mock, Ollama), observability, CLI, docs
- Status: COMPLETE once the pull request passes CI and is merged, and tag `v0.4.0` with its GitHub Release is published and verified
- Risk: HIGH (new execution engine with write access to workspaces), mitigated by deny-by-default grants, approvals and the adversarial suite
- Acceptance: 154 tests pass; reference scenario offline passes; real-provider variant reported as not executed
- Confidence: high for implemented behaviour; unverified on Linux and with a real model
