#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import build_repository_map

p = argparse.ArgumentParser(); p.add_argument("target", nargs="?", type=Path, default=Path.cwd()); a = p.parse_args()
print(json.dumps(build_repository_map(a.target.resolve(), ROOT), indent=2))

