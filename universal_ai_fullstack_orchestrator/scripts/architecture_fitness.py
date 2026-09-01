#!/usr/bin/env python3
import json, re
from _bootstrap import ROOT
from pallaquino_cli.core import read_json

rules = read_json(ROOT / "architecture/fitness_rules.json")["rules"]; violations = []
secret = re.compile(r"(?i)(api[_-]?key|password|private[_-]?key)\s*[:=]\s*['\"][^'\"]+")
for path in ROOT.rglob("*"):
    if path.is_file() and ".git" not in path.parts and path.suffix.lower() in {".py", ".json", ".md", ".toml", ".yml", ".yaml"}:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if secret.search(text) and ".env.example" not in path.name: violations.append({"rule": "no_secrets", "path": str(path.relative_to(ROOT))})
print(json.dumps({"ok": not violations, "rules": len(rules), "violations": violations}, indent=2)); raise SystemExit(1 if violations else 0)

