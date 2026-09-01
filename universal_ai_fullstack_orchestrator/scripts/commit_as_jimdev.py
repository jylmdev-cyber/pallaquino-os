#!/usr/bin/env python3
import argparse, re, subprocess
from pathlib import Path

p = argparse.ArgumentParser(); p.add_argument("message"); p.add_argument("--all", action="store_true"); a = p.parse_args()
if not re.match(r"^(feat|fix|docs|test|refactor|perf|build|ci|chore)(\([a-z0-9_-]+\))?!?: .+", a.message): raise SystemExit("message is not Conventional Commits compliant")
if re.search(r"Co-authored-by:\s*(Claude|ChatGPT|Gemini|Grok|Mistral|Copilot)", a.message, re.I): raise SystemExit("AI co-author trailers are forbidden")
root = Path.cwd().resolve(); git = ["git", "-c", f"safe.directory={root.as_posix()}"]
if a.all: subprocess.run([*git, "add", "-A"], check=True)
subprocess.run([*git, "-c", "user.name=jimdev", "-c", "user.email=jylmdev@gmail.com", "commit", "-m", a.message], check=True)

