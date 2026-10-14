# CLI launchers

Install the package with `pip install .` (or `-e .`) to obtain `pallaquino`, or run the
portable module directly with `python -m pallaquino_cli`. The framework root is
resolved from `--root`, then `$PALLAQUINO_ROOT`, then the package checkout, then
`./.pallaquino` or a parent directory; an unresolvable root exits with code 2. Windows users may use
the root `pallaquino.cmd`; POSIX users may invoke `cli/pallaquino`.

