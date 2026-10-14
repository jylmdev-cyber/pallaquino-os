#!/usr/bin/env python3
"""Reference scenario: add a small feature to a test project through plan -> agents -> execution -> tests -> memory -> handoff.

Variant `offline` is deterministic: the mock provider is scripted by evaluation/reference_scenario/responses.json;
repository discovery and the project's test run are executed for real. Variant `real_provider` runs only when the
configured provider passes `providers doctor`; otherwise it is reported as not executed (never simulated).
Everything runs in a temporary copy, through the public CLI in subprocesses. Exit code 0 means every check passed.
"""
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path
from _bootstrap import ROOT
from pallaquino_cli.core import atomic_json, init_target, read_json

SCENARIO = ROOT / "evaluation" / "reference_scenario"


def cli(root: Path, *args: str) -> tuple[int, object]:
    proc = subprocess.run([sys.executable, "-m", "pallaquino_cli", *args, "--root", str(root), "--json"], cwd=root, text=True, capture_output=True, check=False,
                          env={**__import__("os").environ, "PYTHONPATH": str(root)})
    try: payload = json.loads(proc.stdout)
    except ValueError: payload = {"stdout": proc.stdout[-2000:], "stderr": proc.stderr[-2000:]}
    return proc.returncode, payload


def run_variant(variant: str, workdir: Path) -> dict:
    project = workdir / variant; shutil.copytree(SCENARIO / "fixture", project)
    init_target(ROOT, project); framework = project / ".pallaquino"
    config = read_json(framework / "governance" / "providers.json")
    if variant == "offline":
        config["providers"]["mock"].update(enabled=True, responses_file="evaluation/reference_scenario/responses.json"); config["default"] = "mock"
    else:
        config["providers"]["mock"]["enabled"] = False; config["providers"]["ollama"]["enabled"] = True; config["default"] = "ollama"
    atomic_json(framework / "governance" / "providers.json", config)
    report = {"variant": variant, "stages": {}, "checks": {}}
    if variant == "real_provider":
        code, doctor = cli(framework, "providers", "doctor")
        if code != 0:
            report.update(executed=False, reason="no authorized provider is reachable or configured; nothing was simulated in its place", doctor=doctor); return report
    request = read_json(SCENARIO / "scenario.json")["request"]
    code, plan = cli(framework, "plan", request, "--workspace", str(project)); report["stages"]["plan"] = {"exit": code, "status": plan.get("status"), "tasks": len(plan.get("tasks", []))}
    if code != 0: report.update(executed=True, ok=False); return report
    code, run = cli(framework, "run", "--plan", plan["plan_id"]); report["stages"]["run"] = {"exit": code, "status": run.get("status")}
    execution_id = run.get("execution_id")
    _, status = cli(framework, "status", "--execution", execution_id)
    _, trace = cli(framework, "executions", "report", execution_id)
    _, memory = cli(framework, "memory", "search", "execution", "multiply")
    _, checkpoint = cli(framework, "checkpoint", "--task", "REFERENCE-SCENARIO")
    tasks = trace["trace"]["tasks"]
    report["stages"].update({
        "agents": [{"task": t["task_id"], "step": t["step"], "agent": t["agent"], "status": t["status"], "simulated": t["simulated"], "routing": t["routing"]["method"]} for t in tasks],
        "memory": {"matches": memory.get("count"), "notice": memory.get("notice")}, "checkpoint": checkpoint.get("path") is not None,
        "handoffs": sum(1 for t in tasks if t["status"] == "COMPLETED"), "metrics": trace["metrics"]})
    verify = next((t for t in tasks if t["step"] == "verify"), None)
    report["checks"] = {
        "execution_completed": run.get("status") == "COMPLETED",
        "feature_present": "def multiply" in (project / "calc.py").read_text(encoding="utf-8"),
        "tests_ran_for_real": bool(verify and verify["validation"] and verify["validation"][0].get("exit_code") == 0),
        "memory_persisted": (memory.get("count") or 0) > 0,
        "trace_complete": all(t["history"] for t in tasks) and trace["trace"]["request"]["text"] == request,
    }
    report["executed_for_real"] = sorted({t["step"] for t in tasks if not t["simulated"]})
    report["simulated"] = sorted({t["step"] for t in tasks if t["simulated"]})
    report.update(executed=True, ok=all(report["checks"].values()), status_exit=status.get("execution", {}).get("status"))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0]); parser.add_argument("--variant", choices=["offline", "real_provider", "both"], default="both")
    parser.add_argument("--keep", type=Path, help="keep the working copy in this directory"); args = parser.parse_args()
    variants = ["offline", "real_provider"] if args.variant == "both" else [args.variant]
    with tempfile.TemporaryDirectory() as temp:
        workdir = args.keep or Path(temp); workdir.mkdir(parents=True, exist_ok=True)
        reports = [run_variant(v, workdir) for v in variants]
    print(json.dumps({"scenario": "reference_scenario", "reports": reports}, indent=2))
    return 0 if all(r.get("ok", True) for r in reports if r.get("executed")) and any(r.get("executed") for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
