#!/usr/bin/env python3
import json
from _bootstrap import ROOT
from pallaquino_cli.core import read_json, scan_secrets

# Only rules with an implemented check are enforced; the rest are reported, never silently counted as passing.
rules = read_json(ROOT / "architecture/fitness_rules.json")["rules"]; implemented = {"no_secrets"}
scan = scan_secrets(ROOT)
violations = [{"rule": "no_secrets", "path": f["path"], "line": f["line"], "kind": f["kind"]} for f in scan["findings"]]
not_enforced = [{"rule": r["id"], "reason": "no static analyzer implemented; product repositories must supply one"} for r in rules if r["id"] not in implemented]
print(json.dumps({"ok": not violations, "rules": len(rules), "enforced": sorted(implemented), "not_enforced": not_enforced, "files_scanned": scan["files_scanned"], "violations": violations}, indent=2)); raise SystemExit(1 if violations else 0)
