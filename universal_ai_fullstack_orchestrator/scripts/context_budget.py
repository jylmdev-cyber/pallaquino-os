#!/usr/bin/env python3
import argparse, json

p = argparse.ArgumentParser(); p.add_argument("items", help="JSON array of {id, weight, relevance, required}"); p.add_argument("--budget", type=int, required=True); a = p.parse_args()
items = json.loads(a.items); required = [x for x in items if x.get("required")]; optional = [x for x in items if not x.get("required")]
used = sum(int(x["weight"]) for x in required)
if used > a.budget: raise SystemExit("mandatory context exceeds budget")
selected = list(required)
for item in sorted(optional, key=lambda x: (-float(x.get("relevance", 0)) / max(int(x.get("weight", 1)), 1), str(x["id"]))):
    if used + int(item["weight"]) <= a.budget: selected.append(item); used += int(item["weight"])
print(json.dumps({"budget": a.budget, "used": used, "selected": selected}, indent=2))

