#!/usr/bin/env python3
import argparse, json, subprocess
from _bootstrap import ROOT
from pallaquino_cli.core import atomic_json, utc_now

p = argparse.ArgumentParser(); p.add_argument("gate"); p.add_argument("--agent", required=True); p.add_argument("--artifact"); p.add_argument("command", nargs=argparse.REMAINDER); a = p.parse_args()
if not a.command: raise SystemExit("an executed command is required")
proc = subprocess.run(a.command, cwd=ROOT, text=True, capture_output=True, check=False)
record = {"gate": a.gate.upper(), "command": a.command, "timestamp": utc_now(), "agent": a.agent, "exit_code": proc.returncode, "result": "passed" if proc.returncode == 0 else "failed", "summary": (proc.stdout + proc.stderr)[-4000:], "artifact": a.artifact}
path = ROOT / "evidence" / f"{a.gate.lower()}-{utc_now().replace(':', '-')}.json"; atomic_json(path, record); print(json.dumps({**record, "record": str(path)}, indent=2)); raise SystemExit(proc.returncode)

