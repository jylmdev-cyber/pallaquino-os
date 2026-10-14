#!/usr/bin/env python3
# Name kept for compatibility: commits as the project identity in governance/git_identity.json (default jimdev).
import argparse, re, subprocess
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import load_git_identity

p = argparse.ArgumentParser(); p.add_argument("message"); p.add_argument("--all", action="store_true"); a = p.parse_args()
if not re.match(r"^(feat|fix|docs|test|refactor|perf|build|ci|chore)(\([a-z0-9_-]+\))?!?: .+", a.message): raise SystemExit("message is not Conventional Commits compliant")
if re.search(r"Co-authored-by:\s*(Claude|ChatGPT|Gemini|Grok|Mistral|Copilot)", a.message, re.I): raise SystemExit("AI co-author trailers are forbidden")
identity = load_git_identity(ROOT)
if identity["errors"]: raise SystemExit("; ".join(identity["errors"]))
root = Path.cwd().resolve(); git = ["git", "-c", f"safe.directory={root.as_posix()}"]
if a.all: subprocess.run([*git, "add", "-A"], check=True)
subprocess.run([*git, "-c", f"user.name={identity['name']}", "-c", f"user.email={identity['email']}", "commit", "-m", a.message], check=True)
