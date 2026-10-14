"""CLI surface of the orchestration engine (0.4.0). Legacy forms of plan/status/resume/agents/skills keep their 0.3 output.

Exit codes for executions: 0 completed, 1 failed or error, 2 framework root not found, 3 waiting for approval or
paused, 4 cancelled.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

EXECUTION_EXIT = {"COMPLETED": 0, "FAILED": 1, "WAITING_APPROVAL": 3, "PAUSED": 3, "CANCELLED": 4, "RUNNING": 3, "CREATED": 3}
NEW_COMMANDS = ["run", "cancel", "pause", "approve", "memory", "providers", "executions"]


def add_arguments(name: str, item: argparse.ArgumentParser) -> None:
    if name == "plan":
        item.add_argument("request", nargs="*", help="request to plan; without it, show the legacy execution plan")
        item.add_argument("--workspace", type=Path, help="project directory the plan targets (default: the project of --root, else cwd)")
        item.add_argument("--ai", action="store_true", help="AI-assisted intent analysis with the configured provider (risk stays deterministic)")
    if name in ("status", "resume", "cancel", "pause", "approve"):
        item.add_argument("--execution", required=name in ("cancel", "pause", "approve"), help="execution ID")
    if name in ("run", "resume", "approve"):
        item.add_argument("--approve" if name != "approve" else "--task", action="append", default=[], dest="approve",
                          help="task ID whose governed tools you explicitly approve (repeatable)")
    if name in ("run", "resume"):
        item.add_argument("--max-workers", type=int, help="concurrency limit (default 4)")
        item.add_argument("--force", action="store_true", help="take over an execution whose runner lease is still valid")
    if name == "run":
        item.add_argument("--plan", required=True, help="plan ID from `pallaquino plan`")
        item.add_argument("--dry-run", action="store_true", help="show what would run without running it")
    if name == "resume": item.add_argument("--retry-failed", action="store_true", help="move FAILED tasks back to READY")
    if name == "agents":
        item.add_argument("action", nargs="?", choices=["list", "match"], default="list")
        item.add_argument("text", nargs="*", help="request text for `agents match`")
    if name == "skills": item.add_argument("action", nargs="?", choices=["list"], default="list")
    if name == "memory":
        item.add_argument("action", choices=["status", "search", "inspect", "verify", "delete", "purge"])
        item.add_argument("query", nargs="*", help="search terms")
        item.add_argument("--id", type=int, help="record ID for inspect/delete"); item.add_argument("--category")
        item.add_argument("--limit", type=int, default=10); item.add_argument("--include-stale", action="store_true")
        item.add_argument("--expired", action="store_true", help="purge expired records"); item.add_argument("--older-than", type=float, help="purge records older than N days")
        item.add_argument("--yes", action="store_true", help="confirm a destructive memory operation")
    if name == "providers": item.add_argument("action", choices=["list", "doctor"])
    if name == "executions":
        item.add_argument("action", choices=["list", "report", "trace", "metrics", "export"])
        item.add_argument("execution_id", nargs="?"); item.add_argument("--output", type=Path, help="JSONL path for export")


def _store(root: Path):
    from .memory import MemoryStore
    return MemoryStore.for_root(root)


def _default_workspace(root: Path) -> Path:
    return root.parent if root.name == ".pallaquino" else Path.cwd()


def _providers(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    from .providers.router import build_provider, load_config
    config = load_config(root)
    return config, {name: build_provider(name, s, root) for name, s in config["providers"].items() if s.get("enabled")}


def _platform(root: Path, store: Any, workspace: Path, *, plugins: bool = False):
    """The 0.5.0 tool platform for plans with tool tasks; plugin processes start only when a task uses a plugin tool."""
    from .platform import Platform
    platform = Platform(root, workspace=workspace, store=store)
    _OPEN.append(platform); platform.load(activate_plugins=plugins)
    return platform


_OPEN: list[Any] = []


def _needs_platform(tasks: list[dict[str, Any]]) -> tuple[bool, bool]:
    tool_tasks = [t for t in tasks if t["executor"]["kind"] == "tool"]
    uses_plugins = any(str(r.get("tool_id") or "").startswith("plugin.") for t in tool_tasks for r in t["executor"].get("resolved") or [])
    return bool(tool_tasks), uses_plugins


def _scheduler(root: Path, store: Any, workspace: Path, args: argparse.Namespace, tasks: list[dict[str, Any]] | None = None):
    from .orchestration.scheduler import Scheduler
    config, providers = _providers(root)
    settings = {"max_workers": args.max_workers} if getattr(args, "max_workers", None) else {}
    needed, plugins = _needs_platform(tasks or [])
    platform = _platform(root, store, workspace, plugins=plugins) if needed else None
    return Scheduler(root, store, workspace=workspace, providers=providers, provider_config=config, settings=settings, platform=platform)


def handles(command: str, args: argparse.Namespace) -> bool:
    if command in NEW_COMMANDS: return True
    if command == "plan": return bool(args.request)
    if command in ("status", "resume"): return bool(args.execution)
    if command == "agents": return args.action == "match"
    return False


def handle(command: str, args: argparse.Namespace, root: Path) -> tuple[Any, int | None]:
    """Return (payload, exit_code_override)."""
    if command == "agents":
        from .orchestration.routing import match_request
        text = " ".join(args.text)
        if not text: raise ValueError("agents match needs request text")
        return match_request(root, text), None
    if command == "providers":
        from .providers.router import describe, doctor
        if args.action == "list": return describe(root), None
        report = doctor(root); return report, 0 if report["ok"] else 1
    store = _store(root)
    try:
        if command == "plan":
            from .orchestration.planning import build_plan
            workspace = (args.workspace or _default_workspace(root)).resolve(); intent = None
            if args.ai:
                from .orchestration.intent import analyze_intent
                from .providers.router import complete_with_fallback
                config, providers = _providers(root)
                class _Routed:  # route the intent call through the same authorized-fallback policy as agents
                    name = config["default"]
                    def complete(self, request):
                        return complete_with_fallback(config, providers, request)[0]
                intent = analyze_intent(root, " ".join(args.request), workspace=workspace, provider=_Routed(), mode="ai_assisted")
            platform = _platform(root, store, workspace)
            try: plan = build_plan(root, " ".join(args.request), workspace=workspace, intent=intent, history=store, platform=platform)
            finally: platform.plugins.stop_all(); platform.connections.close_all()
            store.save_plan(plan); store.add_event("plan_created", data={"plan_id": plan["plan_id"], "status": plan["status"], "tasks": len(plan["tasks"])})
            return plan, 0 if plan["status"] == "PLANNED" else 1
        if command == "run":
            plan = store.load_plan(args.plan); workspace = Path(plan["workspace"] or _default_workspace(root))
            scheduler = _scheduler(root, store, workspace, args, plan["tasks"])
            if args.dry_run: return scheduler.preview(plan), 0 if plan["status"] == "PLANNED" else 1
            execution = scheduler.create_execution(plan, approvals=args.approve)
            report = scheduler.run(execution["execution_id"], force=args.force)
            return report, EXECUTION_EXIT.get(report["status"], 1)
        if command in ("status", "resume", "cancel", "pause", "approve"):
            execution = store.load_execution(args.execution); workspace = Path(execution["workspace"])
            scheduler = _scheduler(root, store, workspace, args, store.load_tasks(args.execution) if command in ("resume",) else None)
            if command == "status":
                from .orchestration.observability import metrics
                return {"execution": {k: execution[k] for k in ("execution_id", "plan_id", "status", "approvals", "flags", "usage", "updated_at")},
                        "tasks": [{k: t.get(k) for k in ("task_id", "step", "agent", "status", "attempts", "requires_approval", "last_error")} for t in store.load_tasks(args.execution)],
                        "metrics": metrics(store, args.execution)}, EXECUTION_EXIT.get(execution["status"], 1)
            if command == "approve":
                for task_id in args.approve: scheduler.approve(args.execution, task_id)
                return store.load_execution(args.execution)["approvals"], 0
            if command in ("cancel", "pause"):
                result = scheduler.request(args.execution, "cancel_requested" if command == "cancel" else "pause_requested")
                return {"execution_id": args.execution, "status": result["status"], "flags": result["flags"]}, 0
            for task_id in args.approve: scheduler.approve(args.execution, task_id)
            report = scheduler.run(args.execution, force=args.force, retry_failed=args.retry_failed)
            return report, EXECUTION_EXIT.get(report["status"], 1)
        if command == "memory":
            if args.action == "status": return store.status(), None
            if args.action == "verify": report = store.verify_integrity(); return report, 0 if report["ok"] else 1
            if args.action == "search": return store.search(" ".join(args.query), category=args.category, limit=args.limit, include_stale=args.include_stale), None
            if args.action == "inspect":
                if args.id is not None: return store.get_record(args.id), None
                return {"status": store.status(), "recent": store.search("", limit=args.limit, include_stale=True)["items"]}, None
            if args.action == "delete":
                if args.id is None: raise ValueError("memory delete needs --id")
                return {"deleted": store.delete_record(args.id, confirm=args.yes)}, None
            return {"purged": store.purge(expired=args.expired, older_than_days=args.older_than, confirm=args.yes)}, None
        if command == "executions":
            from .orchestration.observability import export_jsonl, metrics, trace
            if args.action == "list": return store.list_executions(), None
            if not args.execution_id: raise ValueError(f"executions {args.action} needs an execution ID")
            if args.action == "metrics": return metrics(store, args.execution_id), None
            if args.action in ("report", "trace"): return {"trace": trace(store, args.execution_id), "metrics": metrics(store, args.execution_id)}, None
            output = args.output or root / "logs" / f"{args.execution_id}.jsonl"
            return {"exported": export_jsonl(store, args.execution_id, output), "path": str(output)}, None
    finally:
        while _OPEN: _OPEN.pop().close()  # stops plugin processes and MCP connections; the store is closed below
        store.close()
    raise ValueError(f"unsupported command: {command}")
