#!/usr/bin/env python3
import argparse, json
from _bootstrap import ROOT
from pallaquino_cli.core import acquire_lock, release_lock

p = argparse.ArgumentParser(); sub = p.add_subparsers(dest="command", required=True)
a = sub.add_parser("acquire"); a.add_argument("path"); a.add_argument("--owner", required=True); a.add_argument("--task", required=True); a.add_argument("--ttl", type=int, default=60)
r = sub.add_parser("release"); r.add_argument("path"); r.add_argument("--owner", required=True)
args = p.parse_args()
out = acquire_lock(ROOT, args.path, args.owner, args.task, args.ttl) if args.command == "acquire" else {"released": release_lock(ROOT, args.path, args.owner)}
print(json.dumps(out, indent=2))

