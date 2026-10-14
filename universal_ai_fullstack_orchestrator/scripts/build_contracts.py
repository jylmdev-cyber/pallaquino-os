#!/usr/bin/env python3
"""Rebuild agent/skill contracts v2 from registry facts (dry-run by default; curated fields are preserved)."""
import argparse, json
from _bootstrap import ROOT
from pallaquino_cli.contracts import AGENT_CONTRACTS, CONTRACT_VERSION, SKILL_CONTRACTS, derive_contracts, load_contract_files
from pallaquino_cli.core import atomic_json

p = argparse.ArgumentParser(description=__doc__); p.add_argument("--write", action="store_true", help="write the contract files; default only reports changes"); a = p.parse_args()
existing = load_contract_files(ROOT); built = derive_contracts(ROOT, existing)
summary = {}
for kind, rel in (("agents", AGENT_CONTRACTS), ("skills", SKILL_CONTRACTS)):
    changed = sorted(c["id"] for c in built[kind] if existing[kind].get(c["id"]) != c)
    summary[kind] = {"total": len(built[kind]), "changed": changed}
    if a.write: atomic_json(ROOT / rel, {"schema_version": 1, "contract_version": CONTRACT_VERSION, "contracts": built[kind]})
print(json.dumps({"written": a.write, **summary}, indent=2))
if not a.write: print("DRY RUN: review the changed contracts, then re-run with --write")
