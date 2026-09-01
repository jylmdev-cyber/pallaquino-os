#!/usr/bin/env python3
import subprocess
from pathlib import Path

root = Path.cwd().resolve(); base = ["git", "-c", f"safe.directory={root.as_posix()}", "config", "--local"]
subprocess.run([*base, "user.name", "jimdev"], check=True); subprocess.run([*base, "user.email", "jylmdev@gmail.com"], check=True)
print("Configured repository-local identity: jimdev <jylmdev@gmail.com>")

