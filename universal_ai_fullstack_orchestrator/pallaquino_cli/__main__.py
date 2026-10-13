from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import (
    ROOT_ENV, FrameworkRootNotFound, analyze_risk, build_repository_map, create_handoff,
    detect_capabilities, init_target, make_checkpoint, read_json, resolve_root, resume,
    route_request, scan_secrets, stack_status, validate_all,
)

ROOT_HELP = f"PALLAQUINO/framework root (default: ${ROOT_ENV}, the package checkout, then ./.pallaquino or a parent)"


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--root", type=Path, default=None, help=ROOT_HELP)
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
        ("security", "read-only security audit (secret scan) of a target"),
    ]:
        item = subs.add_parser(name, help=help_text); add_common(item)
        if name == "analyze": item.add_argument("--target", type=Path, default=Path.cwd())
        if name == "risk": item.add_argument("request", nargs="*", help="request text")
        if name == "checkpoint": item.add_argument("--task", default="UNSPECIFIED")
        if name == "validate": item.add_argument("--integrity-only", action="store_true", help="skip host-dependent checks such as local Git identity")
        if name == "security":
            item.add_argument("action", nargs="?", choices=["audit"], default="audit")
            item.add_argument("--target", type=Path, default=Path.cwd())
        if name == "handoff":
            item.add_argument("--next-action", help="exact next action for the receiving agent")
            item.add_argument("--missing", action="append", default=[], help="requested but not implemented (repeatable)")
            item.add_argument("--unverified", action="append", default=[], help="implemented but not verified (repeatable)")
    init = subs.add_parser("init", help="copy PALLAQUINO into a repository"); add_common(init); init.add_argument("--target", type=Path, default=Path.cwd())
    init.add_argument("--dry-run", action="store_true", help="report what would be written without writing")
    return top


def emit(payload: object, machine: bool) -> None:
    if machine:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    if isinstance(payload, list) and all(isinstance(row, dict) and "id" in row for row in payload):
        for row in payload:
            print(f"{row['id']}\t{row.get('category', '')}")
    elif isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv); command = args.command
    try:
        root = resolve_root(args.root)
        if command == "init": payload = init_target(root, args.target.resolve(), dry_run=args.dry_run)
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
        elif command == "handoff": payload = create_handoff(root, args.next_action, args.missing, args.unverified)
        elif command == "resume": payload = resume(root)
        elif command == "validate": payload = validate_all(root, include_environment=not args.integrity_only)
        elif command == "stack": payload = stack_status(root)
        elif command == "security": payload = scan_secrets(args.target.resolve())
        elif command == "risk":
            text = " ".join(args.request) if args.request else sys.stdin.read(); payload = analyze_risk(text); payload["routing"] = route_request(root, text)
        elif command == "graph":
            from .core import validate_task_graph
            payload = {"validation": validate_task_graph(root), "graph": read_json(root / "planning/task_graph.json")}
        else: raise ValueError(f"unsupported command: {command}")
    except FrameworkRootNotFound as exc:
        return fail(args, str(exc), 2)
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        return fail(args, str(exc), 1)
    emit(payload, args.json)
    if isinstance(payload, dict) and payload.get("ok") is False: return 1
    return 0


def fail(args: argparse.Namespace, message: str, code: int) -> int:
    if getattr(args, "json", False): print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
    else: print(f"pallaquino: {message}", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
