# CLI launchers

Install the package with `pip install .` (or `-e .`) to obtain `pallaquino`, or run the
portable module directly with `python -m pallaquino_cli`. The framework root is
resolved from `--root`, then `$PALLAQUINO_ROOT`, then the package checkout, then
`./.pallaquino` or a parent directory; an unresolvable root exits with code 2. Windows users may use
the root `pallaquino.cmd`; POSIX users may invoke `cli/pallaquino`.

Orchestration commands (0.4.0): `plan "<request>"`, `run --plan <id> [--dry-run] [--approve <task>]`,
`status|resume|pause|cancel --execution <id>`, `approve --execution <id> --task <task>`, `agents match "<text>"`,
`memory status|search|inspect|verify|delete|purge`, `providers list|doctor`, `executions list|report|trace|metrics|export`.
Without the new arguments, `plan`, `status`, `resume`, `agents` and `skills` keep their 0.3 output.
Exit codes for executions: 0 completed, 1 failed or error, 2 root not found, 3 waiting for approval or paused, 4 cancelled.

Platform commands (0.5.0):
`plugins list|discover|inspect|validate|enable|disable|doctor|install|update|rollback|uninstall|trust|untrust|health`,
`plugin create|validate|test <dir>`, `mcp servers|add|inspect|test|tools|pin|remove|doctor|enable|disable|auth|logout`,
`tools list|inspect|check|run|route|calls|metrics` and `permissions list|inspect|grant|revoke|history`.
`mcp add --stdio <command...>` takes the rest of the line, so put it last. `tools run` exits 3 when the call needs a per-call approval
(re-run with `--approve` to approve exactly those arguments) and 5 when the gateway denies it; any `PermissionError` also exits 5.

