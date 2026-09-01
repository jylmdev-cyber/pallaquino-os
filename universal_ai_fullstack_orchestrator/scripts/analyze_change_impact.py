#!/usr/bin/env python3
import argparse, json
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import analyze_risk

p = argparse.ArgumentParser(); p.add_argument("request"); p.add_argument("--files", nargs="*", default=[]); a = p.parse_args()
payload = {"request": a.request, "files": a.files, "modules": sorted({Path(x).parts[0] for x in a.files if Path(x).parts}), "database": any("migration" in x.lower() or x.endswith(".sql") for x in a.files), "apis": any("api" in x.lower() for x in a.files), "tests": [x for x in a.files if "test" in x.lower()], "risk": analyze_risk(a.request + " " + " ".join(a.files)), "confidence": "medium"}
print(json.dumps(payload, indent=2))

