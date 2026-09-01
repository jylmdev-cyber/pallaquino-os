# PALLAQUINO Autonomous Engineering OS

Portable, provider-neutral engineering governance and execution framework for AI
agents. Version `0.2.1` turns a human request into a risk-aware task graph,
implementation pipeline, evidence trail, checkpoint and handoff.

The framework is executable, not merely a prompt collection. Its standard-library
Python CLI analyzes repositories, ranks routes, classifies risk, manages locks and
continuity, validates its own registries, and builds verified release archives.

## Start

```console
python -m pallaquino_cli doctor
python -m pallaquino_cli analyze
python -m pallaquino_cli risk "add role-based login"
python -m pallaquino_cli validate
```

See `QUICK_START.md` and `docs/TUTORIAL_DE_PROMPTS.md`, then give the active provider `AI_ENTRYPOINT.md`. The brand
root is always **PALLAQUINO** and provider capabilities adapt execution without
changing architecture or bypassing gates.

Repository-local Git identity can be configured safely with:

```console
python scripts/configure_git_identity.py --name "Your Name" --email "you@example.com"
python scripts/configure_git_identity.py --show
```

The expanded catalog contains 59 agents, 90 version-agnostic skills, 46
technologies and six adoptable stack profiles. See
`docs/TECHNOLOGY_EXPANSION.md`; every new profile remains
`VERIFY_BEFORE_USE` until official versions are audited for the target project.
