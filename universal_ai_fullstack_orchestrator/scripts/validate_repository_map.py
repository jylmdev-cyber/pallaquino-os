#!/usr/bin/env python3
import json
from _bootstrap import ROOT
from pallaquino_cli.core import validate_repository_map
out = validate_repository_map(ROOT); print(json.dumps(out, indent=2)); raise SystemExit(0 if out["ok"] else 1)

