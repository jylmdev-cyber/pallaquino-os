#!/usr/bin/env python3
"""End-to-end demo (v0.5.0): "Analiza el repositorio actual, identifica problemas de calidad, revisa el estado de Git
y genera un informe técnico", offline, through the real CLI.

Flow: a throw-away project is initialized with `pallaquino init` (so no state is written to the analysed repository);
a local MCP test server is configured, reviewed, classified and pinned; a scoped grant is created; `plan` routes the
request to agents and tools; `run` executes git, filesystem and MCP tools through the permission and execution
gateways; the report, audit trail, metrics and memory are checked; and the analysed repository's `git status` is
compared before and after. No API keys, no network, no commercial service.

    python scripts/run_codebase_analysis_demo.py [--workspace PATH] [--evidence PATH] [--keep]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from _bootstrap import ROOT
from pallaquino_cli.__main__ import main as cli
from pallaquino_cli.core import init_target

REQUEST = "Analiza el repositorio actual, identifica problemas de calidad, revisa el estado de Git y genera un informe técnico"
SERVER = ROOT / "examples" / "mcp_servers" / "quality_server.py"


def run_cli(*argv: str) -> tuple[int, object]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer): code = cli([*argv])
    text = buffer.getvalue()
    try: return code, json.loads(text)
    except ValueError: return code, text


def git_status(path: Path) -> str:
    proc = subprocess.run(["git", "-C", str(path), "-c", "core.longpaths=true", "status", "--porcelain=v1", "--untracked-files=all"], capture_output=True, text=True, encoding="utf-8")
    return proc.stdout if proc.returncode == 0 else f"not a git repository: {proc.stderr.strip()}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    default_workspace = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or str(ROOT)
    parser.add_argument("--workspace", type=Path, default=Path(default_workspace), help="repository to analyse (default: this repository)")
    parser.add_argument("--evidence", type=Path, help="write the evidence JSON here"); parser.add_argument("--keep", action="store_true", help="keep the temporary project")
    args = parser.parse_args(); workspace = args.workspace.resolve()
    temp = Path(tempfile.mkdtemp(prefix="pallaquino-demo-")); project = temp / "project"; project.mkdir()
    checks: dict[str, bool] = {}; steps: dict[str, object] = {}
    try:
        before = git_status(workspace)
        init_target(ROOT, project); root = project / ".pallaquino"; common = ["--root", str(root), "--json"]
        code, added = run_cli("mcp", "add", "quality", *common, "--classify", "quality_scan=READ_ONLY:FILE_READ:quality_scan", "--stdio", "python", str(SERVER))
        checks["mcp server configured"] = code == 0
        code, tested = run_cli("mcp", "test", "quality", *common); steps["mcp_test"] = tested
        checks["MCP 2026-07-28 connection over stdio"] = code == 0 and tested.get("protocol_version") == "2026-07-28" and tested.get("era") == "modern"
        code, review = run_cli("mcp", "tools", "quality", *common); steps["mcp_review"] = [{k: t[k] for k in ("name", "status")} for t in review["tools"]]
        code, pinned = run_cli("mcp", "pin", "quality", *common, "--tool", "quality_scan"); checks["catalog reviewed and pinned"] = code == 0 and "quality_scan" in pinned["tools"]
        code, grant = run_cli("permissions", "grant", "mcp.quality.quality_scan", *common, "--principal", "project_analyzer", "--operation", "READ_ONLY", "--days", "1",
                              "--reason", "codebase analysis demo")
        checks["scoped grant created"] = code == 0
        code, plan = run_cli("plan", REQUEST, *common, "--workspace", str(workspace)); steps["plan"] = {"plan_id": plan["plan_id"], "status": plan["status"],
            "tasks": [{"task_id": t["task_id"], "step": t["step"], "agent": t["agent"], "executor": t["executor"]["kind"],
                       "tools": [r.get("tool_id") for r in t["executor"].get("resolved", [])]} for t in plan["tasks"]], "warnings": plan["validation"]["warnings"]}
        resolved = {r.get("tool_id") for t in plan["tasks"] for r in t["executor"].get("resolved", [])}
        checks["intent analysed and agents routed"] = plan["status"] == "PLANNED" and plan["intent"]["primary_intent"] == "PROJECT_DISCOVERY"
        checks["tool router selected git and MCP tools"] = {"core.git.status", "core.git.log", "mcp.quality.quality_scan"} <= resolved
        code, report = run_cli("run", *common, "--plan", plan["plan_id"]); steps["run"] = {"status": report["status"], "tasks": report["tasks"]}
        checks["execution completed without simulation"] = report["status"] == "COMPLETED" and not any(t["simulated"] for t in report["tasks"])
        code, trace = run_cli("executions", "report", report["execution_id"], *common)
        code, calls = run_cli("tools", "calls", *common, "--no-plugins")
        mcp_calls = [c for c in calls if c["tool_id"] == "mcp.quality.quality_scan"]
        checks["MCP tool executed through the gateway"] = bool(mcp_calls) and mcp_calls[0]["status"] == "COMPLETED" and any("grant" in c for c in mcp_calls[0]["checks"])
        report_files = sorted((root / "logs" / "reports").glob(f"{report['execution_id']}.md"))
        report_text = report_files[0].read_text(encoding="utf-8") if report_files else ""
        checks["report written with a passed quality gate"] = "Result: PASSED" in report_text and "mcp.quality.quality_scan" in report_text
        code, metrics = run_cli("tools", "metrics", *common, "--no-plugins"); steps["metrics"] = {k: metrics[k] for k in ("tools_registered", "executions_succeeded", "executions_failed", "permission_denials")}
        code, memory = run_cli("memory", "search", "report", *common)
        checks["project memory recorded the report"] = any(i["kind"] == "technical_report" for i in memory["items"])
        code, denied = run_cli("tools", "run", "core.files.write", *common, "--no-plugins", "--workspace", str(workspace), "--args", json.dumps({"path": "SHOULD_NOT_EXIST.txt", "content": "x"}))
        checks["unauthorized write blocked"] = code == 5 and denied["status"] == "DENIED"
        checks["analysed repository not modified"] = git_status(workspace) == before
        steps["report_path"] = str(report_files[0]) if report_files else None
        print(report_text)
    finally:
        if not args.keep: shutil.rmtree(temp, ignore_errors=True)
    evidence = {"demo": "codebase_analysis", "request": REQUEST, "workspace": str(workspace), "checks": checks, "ok": all(checks.values()), "steps": steps,
                "offline": True, "simulated": False, "kept_project": str(project) if args.keep else None}
    if args.evidence: args.evidence.parent.mkdir(parents=True, exist_ok=True); args.evidence.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"ok": evidence["ok"], "checks": checks}, indent=2, ensure_ascii=False))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
