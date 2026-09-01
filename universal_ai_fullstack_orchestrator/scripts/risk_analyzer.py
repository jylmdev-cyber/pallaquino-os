#!/usr/bin/env python3
import argparse, json
from _bootstrap import ROOT
from pallaquino_cli.core import analyze_risk, atomic_json

p = argparse.ArgumentParser(); p.add_argument("request"); p.add_argument("--persist", action="store_true"); a = p.parse_args(); out = analyze_risk(a.request)
if a.persist: atomic_json(ROOT / "risk/risk_state.json", {"schema_version": 1, **out})
print(json.dumps(out, indent=2))

