#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import create_archive

p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, default=ROOT.parent / "PALLAQUINO_autonomous_engineering_os.zip"); a = p.parse_args()
out = create_archive(ROOT, a.output.resolve()); print(json.dumps(out, indent=2)); raise SystemExit(0 if out["integrity"] else 1)

