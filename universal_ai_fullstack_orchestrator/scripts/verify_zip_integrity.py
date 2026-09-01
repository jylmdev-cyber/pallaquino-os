#!/usr/bin/env python3
import argparse, hashlib, json, tempfile, zipfile
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import validate_registry, validate_pipeline, validate_continuity, validate_governance, validate_task_graph, validate_context, validate_risk, validate_cli

p = argparse.ArgumentParser(); p.add_argument("archive", nargs="?", type=Path, default=ROOT.parent / "PALLAQUINO_autonomous_engineering_os.zip"); a = p.parse_args(); archive = a.archive.resolve()
with zipfile.ZipFile(archive) as zf:
    bad = zf.testzip(); names = zf.namelist(); unsafe = [n for n in names if Path(n).is_absolute() or ".." in Path(n).parts or "\\" in n]
    with tempfile.TemporaryDirectory() as tmp:
        zf.extractall(tmp); extracted = Path(tmp) / ROOT.name
        checks = [f(extracted) for f in [validate_registry, validate_pipeline, validate_continuity, validate_governance, validate_task_graph, validate_context, validate_risk, validate_cli]]
digest = hashlib.sha256(archive.read_bytes()).hexdigest(); sidecar = archive.with_suffix(".sha256"); sidecar_ok = sidecar.exists() and sidecar.read_text(encoding="ascii").split()[0] == digest
out = {"ok": bad is None and not unsafe and all(x["ok"] for x in checks) and sidecar_ok, "bad_entry": bad, "unsafe_paths": unsafe, "entries": len(names), "checks": checks, "sha256": digest, "sidecar_ok": sidecar_ok}
print(json.dumps(out, indent=2)); raise SystemExit(0 if out["ok"] else 1)

