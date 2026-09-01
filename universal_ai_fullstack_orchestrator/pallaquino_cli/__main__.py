from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import (
    analyze_risk, build_repository_map, create_handoff, detect_capabilities,
    framework_root, init_target, make_checkpoint, read_json, resume,
    route_request, stack_status, validate_all,
)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=framework_root(), help="PALLAQUINO/framework root")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="pallaquino", description="PALLAQUINO Autonomous Engineering OS")
    top.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subs = top.add_subparsers(dest="command", required=True)
    for name, help_text in [
        ("status", "show current framework state"), ("doctor", "diagnose framework and environment"),
        ("analyze", "build a repository map"), ("plan", "show the execution plan"),
        ("agents", "list registered agents"), ("skills", "list registered skills"),
        ("pipeline", "show strict pipeline state"), ("checkpoint", "create a continuity checkpoint"),
        ("handoff", "create a provider-neutral handoff"), ("resume", "recover the newest valid checkpoint"),
        ("validate", "run all framework validators"), ("stack", "show verified stack freshness"),
        ("risk", "classify request risk"), ("graph", "show and validate the task graph"),
    ]:
        item = subs.add_parser(name, help=help_text); add_common(item)
        if name == "analyze": item.add_argument("--target", type=Path, default=Path.cwd())
        if name == "risk": item.add_argument("request", nargs="*", help="request text")
        if name == "checkpoint": item.add_argument("--task", default="UNSPECIFIED")
    init = subs.add_parser("init", help="copy PALLAQUINO into a repository"); add_common(init); init.add_argument("--target", type=Path, default=Path.cwd())
    return top


def emit(payload: object, machine: bool) -> None:
    if machine:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, dict):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv); root = args.root.resolve(); command = args.command
    try:
        if command == "init": payload = init_target(root, args.target.resolve())
        elif command == "status":
            payload = {"version": __version__, "root": str(root), "pipeline_state": (root / "continuity/state/PIPELINE_STATE.md").read_text(encoding="utf-8"), "locks": read_json(root / "execution/file_locks.json")["locks"]}
        elif command == "doctor":
            validation = validate_all(root); capabilities = detect_capabilities(root, persist=False); stack = stack_status(root)
            payload = {"ok": validation["ok"] and stack["ok"], "validation": validation, "capabilities": capabilities, "stack": stack}
        elif command == "analyze": payload = build_repository_map(args.target.resolve(), root)
        elif command == "plan": payload = read_json(root / "planning/execution_plan.json")
        elif command == "agents": payload = read_json(root / "registry/agents.json")["agents"]
        elif command == "skills": payload = read_json(root / "registry/skills.json")["skills"]
        elif command == "pipeline": payload = read_json(root / "pipeline/pipeline_definition.json")
        elif command == "checkpoint": payload = make_checkpoint(root, args.task)
        elif command == "handoff": payload = create_handoff(root)
        elif command == "resume": payload = resume(root)
        elif command == "validate": payload = validate_all(root)
        elif command == "stack": payload = stack_status(root)
        elif command == "risk":
            text = " ".join(args.request) if args.request else sys.stdin.read(); payload = analyze_risk(text); payload["routing"] = route_request(root, text)
        elif command == "graph":
            from .core import validate_task_graph
            payload = {"validation": validate_task_graph(root), "graph": read_json(root / "planning/task_graph.json")}
        else: raise ValueError(f"unsupported command: {command}")
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        error = {"ok": False, "error": str(exc)}
        if getattr(args, "json", False): print(json.dumps(error, ensure_ascii=False))
        else: print(f"pallaquino: {exc}", file=sys.stderr)
        return 1
    emit(payload, args.json)
    if isinstance(payload, dict) and payload.get("ok") is False: return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
