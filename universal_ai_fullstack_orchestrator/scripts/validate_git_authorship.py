#!/usr/bin/env python3
import json
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import validate_git_authorship

target = ROOT.parent if (ROOT.parent / ".git").exists() else ROOT
out = validate_git_authorship(target); print(json.dumps(out, indent=2)); raise SystemExit(0 if out["ok"] else 1)

