# Quick start

1. Copy this directory into a software repository.
2. Run `python -m pallaquino_cli init --target <repository> --dry-run`, review, then rerun without `--dry-run`.
   The new `.pallaquino/` starts with clean project state.
3. Enter `<repository>/.pallaquino` and run `python -m pallaquino_cli doctor --root .`.
4. Record the request in `continuity/state/CURRENT_TASK.md`.
5. Run `analyze`, `risk`, `plan`, `graph`, then execute the declared pipeline.
6. Capture every executed gate with `scripts/evidence.py` (output is redacted) and run
   `python -m pallaquino_cli security audit --target <repository>`.
7. Use `checkpoint`, `handoff`, and `resume` for provider-neutral continuity.

`SAFE` is required for production, destructive or credential-sensitive work.
No command authorizes a production deploy or destructive action.

For copy-ready prompts and complete workflows, see `docs/TUTORIAL_DE_PROMPTS.md`.
