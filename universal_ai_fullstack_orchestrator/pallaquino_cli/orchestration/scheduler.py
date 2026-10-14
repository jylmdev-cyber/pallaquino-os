"""PALLAQUINO Multi-Agent Scheduler: runs a validated plan as a persistent execution.

Delivery semantics are at-least-once. Each attempt has a token; a task orphaned by a crash is reconciled on
resume: if its write-ahead intent shows every planned file already holds the planned content it is completed
without re-running, otherwise it is retried with the same idempotency key. Tasks with external effects (governed
tools) never run without a recorded approval. Every state change is validated against the state machine and
persisted before the scheduler acts on it, so an interrupted process leaves a consistent, resumable record.
"""
from __future__ import annotations

import copy
import os
import threading
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from ..memory.store import MemoryStore
from ..providers.base import Budget
from ..providers.router import load_config
from .executors import ExecutionContext, build_handoff, confine, execute_task, sha256_text
from .models import (CONTRACT_VERSION, InvalidTransition, check_execution_transition, check_task_transition, new_id, new_task, utc_now)

DEFAULTS = {"max_workers": 4, "task_timeout": 300.0, "max_attempts": 3, "backoff_base": 0.5, "max_review_rounds": 2,
            "max_delegation_depth": 2, "lease_seconds": 120.0, "command_timeout": 300.0}
ACTIVE = {"PLANNED", "WAITING_APPROVAL", "READY", "RUNNING", "RETRYING", "PAUSED", "BLOCKED"}


class ExecutionLocked(RuntimeError):
    """Another live process holds this execution's lease."""


def _iso_in(seconds: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="milliseconds")


class Scheduler:
    def __init__(self, root: Path, store: MemoryStore, *, workspace: Path, providers: dict[str, Any] | None = None,
                 provider_config: dict[str, Any] | None = None, settings: dict[str, Any] | None = None, sleep: Callable[[float], None] = time.sleep,
                 platform: Any = None):
        self.root = Path(root); self.store = store; self.workspace = Path(workspace).resolve(); self.sleep = sleep
        self.provider_config = provider_config or load_config(self.root)
        self.providers = providers if providers is not None else {}
        self.settings = {**DEFAULTS, **(settings or {})}; self._lock = threading.RLock(); self.runner_id = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
        self.platform = platform  # tool tasks (0.5.0) run through this platform's gateway

    # -- creation -------------------------------------------------------------------------------------------
    def preview(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Dry run: what would execute, in which order and with which grants. Persists nothing."""
        from .planning import analyze_dag
        dag = plan.get("dag") or analyze_dag(plan["tasks"]); by_id = {t["task_id"]: t for t in plan["tasks"]}
        return {"dry_run": True, "plan_id": plan["plan_id"], "status": plan["status"], "levels": dag["levels"], "approvals_required": plan.get("approvals_required", []),
                "would_run": [{"task_id": tid, "agent": by_id[tid]["agent"], "executor": by_id[tid]["executor"]["kind"], "tools": by_id[tid]["permissions"]["allowed"],
                               "requires_approval": by_id[tid]["requires_approval"]} for tid in dag["order"]]}

    def create_execution(self, plan: dict[str, Any], *, approvals: list[str] = ()) -> dict[str, Any]:
        if plan.get("status") != "PLANNED" or not plan["validation"]["ok"]:
            raise ValueError("only a valid plan can be executed: " + "; ".join(plan["validation"]["errors"]))
        budgets = self.provider_config.get("budgets", {})
        execution = {"contract": "execution", "version": CONTRACT_VERSION, "execution_id": new_id("exec"), "plan_id": plan["plan_id"], "request": plan["request"],
                     "request_id": plan["request_id"], "workspace": str(self.workspace), "status": "CREATED", "created_at": utc_now(), "updated_at": utc_now(),
                     "approvals": [], "flags": {"cancel_requested": False, "pause_requested": False}, "settings": dict(self.settings),
                     "budget_limits": budgets, "usage": {"calls": 0, "tokens": 0, "unverified_calls": 0}, "review_rounds": {}, "revisions": [],
                     "runner": None, "summary": None}
        self.store.save_execution(execution)
        for task in copy.deepcopy(plan["tasks"]):
            task["updated_at"] = utc_now(); task["delegation_chain"] = [task["agent"]]; self.store.save_task(execution["execution_id"], task)
        self.store.add_event("execution_created", execution_id=execution["execution_id"], data={"plan_id": plan["plan_id"], "tasks": len(plan["tasks"])})
        for task_id in approvals: self.approve(execution["execution_id"], task_id)
        return self.store.load_execution(execution["execution_id"])

    def approve(self, execution_id: str, task_id: str, approver: str = "cli") -> None:
        execution = self.store.load_execution(execution_id); tasks = {t["task_id"]: t for t in self.store.load_tasks(execution_id)}
        if task_id not in tasks: raise LookupError(f"task {task_id} not in execution {execution_id}")
        if not tasks[task_id]["requires_approval"]: raise ValueError(f"task {task_id} does not require approval")
        if any(a["task_id"] == task_id for a in execution["approvals"]): return
        execution["approvals"].append({"task_id": task_id, "approved_by": approver, "at": utc_now(), "scope": tasks[task_id]["permissions"]["approval_required"]})
        self._save_execution(execution)
        self.store.add_event("approval_recorded", execution_id=execution_id, task_id=task_id, data=execution["approvals"][-1])

    # -- cross-process control ------------------------------------------------------------------------------
    def request(self, execution_id: str, flag: str) -> dict[str, Any]:
        if flag not in ("cancel_requested", "pause_requested"): raise ValueError(flag)
        execution = self.store.load_execution(execution_id)
        if execution["status"] in ("COMPLETED", "CANCELLED"): raise ValueError(f"execution is already {execution['status']}")
        execution["flags"][flag] = True; self._save_execution(execution)
        self.store.add_event(flag.replace("_requested", "_requested_by_user"), execution_id=execution_id)
        if execution["status"] in ("CREATED", "WAITING_APPROVAL", "PAUSED", "FAILED") and flag == "cancel_requested":
            return self._finish_cancel(execution_id)
        return self.store.load_execution(execution_id)

    # -- helpers ----------------------------------------------------------------------------------------------
    def _save_execution(self, execution: dict[str, Any]) -> None:
        execution["updated_at"] = utc_now(); self.store.save_execution(execution)

    def _set_execution_status(self, execution: dict[str, Any], status: str, reason: str) -> None:
        if execution["status"] != status:
            check_execution_transition(execution["status"], status)
            self.store.add_event("execution_state", execution_id=execution["execution_id"], data={"from": execution["status"], "to": status, "reason": reason})
            execution["status"] = status
        self._save_execution(execution)

    def _transition(self, execution_id: str, task: dict[str, Any], target: str, reason: str, **fields: Any) -> None:
        check_task_transition(task["status"], target)
        task["history"].append({"from": task["status"], "to": target, "at": utc_now(), "reason": reason})
        previous = task["status"]; task["status"] = target; task.update(fields); task["updated_at"] = utc_now()
        self.store.save_task(execution_id, task)
        self.store.add_event("task_state", execution_id=execution_id, task_id=task["task_id"], agent_id=task["agent"], data={"from": previous, "to": target, "reason": reason},
                             severity="error" if target == "FAILED" else "info", outcome=target)

    def _claim(self, execution: dict[str, Any], force: bool = False) -> None:
        runner = execution.get("runner")
        if runner and runner["id"] != self.runner_id and runner["lease_expires"] > utc_now() and not force:
            raise ExecutionLocked(f"execution {execution['execution_id']} is held by runner {runner['id']} until {runner['lease_expires']}")
        execution["runner"] = {"id": self.runner_id, "pid": os.getpid(), "lease_expires": _iso_in(self.settings["lease_seconds"])}
        self._save_execution(execution)

    def _heartbeat(self, execution_id: str) -> dict[str, Any]:
        """Re-read control flags every loop; renew the lease only once a third of it has elapsed."""
        execution = self.store.load_execution(execution_id)
        if time.monotonic() - getattr(self, "_last_beat", 0.0) > float(self.settings["lease_seconds"]) / 3:
            execution["runner"] = {"id": self.runner_id, "pid": os.getpid(), "lease_expires": _iso_in(self.settings["lease_seconds"])}
            self._save_execution(execution); self._last_beat = time.monotonic()
        return execution

    def _dependents(self, tasks: dict[str, dict[str, Any]], task_id: str) -> list[dict[str, Any]]:
        out, frontier = [], [task_id]
        while frontier:
            current = frontier.pop()
            for t in tasks.values():
                if current in t["dependencies"] and t not in out: out.append(t); frontier.append(t["task_id"])
        return out

    # -- reconciliation after a crash --------------------------------------------------------------------------
    def _reconcile(self, execution_id: str, tasks: dict[str, dict[str, Any]]) -> list[str]:
        notes = []
        for task in tasks.values():
            if task["status"] != "RUNNING": continue
            intent = task.get("write_intent")
            if intent and all(self._file_matches(entry) for entry in intent):
                self._transition(execution_id, task, "COMPLETED", "reconciled: every planned write is already applied", reconciled=True)
                notes.append(f"{task['task_id']} reconciled as completed")
            else:
                self._transition(execution_id, task, "RETRYING", "orphaned by an interrupted runner; re-running with the same idempotency key", retry_at=utc_now())
                notes.append(f"{task['task_id']} will be retried")
            self.store.add_event("reconciliation", execution_id=execution_id, task_id=task["task_id"], data={"note": notes[-1]})
        return notes

    def _file_matches(self, entry: dict[str, Any]) -> bool:
        try: path = confine(self.workspace, entry["path"])
        except PermissionError: return False
        return path.is_file() and sha256_text(path.read_text(encoding="utf-8")) == entry["sha256"]

    # -- main loop ------------------------------------------------------------------------------------------
    def run(self, execution_id: str, *, force: bool = False, retry_failed: bool = False) -> dict[str, Any]:
        execution = self.store.load_execution(execution_id)
        if execution["status"] in ("COMPLETED", "CANCELLED"):  # terminal: resuming is a read-only report
            return self._report(execution_id, {t["task_id"]: t for t in self.store.load_tasks(execution_id)}, [])
        self._claim(execution, force=force)
        tasks = {t["task_id"]: t for t in self.store.load_tasks(execution_id)}
        reconciliation = self._reconcile(execution_id, tasks)
        if retry_failed:
            for t in tasks.values():
                if t["status"] == "FAILED": self._transition(execution_id, t, "READY", "retry requested by resume --retry-failed", attempts=0)
        if execution["status"] in ("CREATED", "WAITING_APPROVAL", "PAUSED", "FAILED"): self._set_execution_status(execution, "RUNNING", "runner started")
        execution_budget = Budget(scope="execution", **(execution["budget_limits"].get("execution") or {}))
        running: dict[Future, tuple[str, str, float]] = {}; pool = ThreadPoolExecutor(max_workers=int(self.settings["max_workers"]))
        handoffs: dict[str, dict[str, Any]] = {t["task_id"]: t["handoff"] for t in tasks.values() if t.get("handoff")}
        self._task_budgets: dict[str, Budget] = {}
        try:
            while True:
                execution = self._heartbeat(execution_id); flags = execution["flags"]
                if flags["cancel_requested"]:
                    for t in tasks.values():
                        if t["status"] in ACTIVE - {"RUNNING"}: self._transition(execution_id, t, "CANCELLED", "execution cancelled")
                    if not running: return self._finalize(execution_id, tasks, "CANCELLED", reconciliation, execution_budget)
                self._promote(execution, tasks)
                if flags["pause_requested"]:
                    for t in tasks.values():
                        if t["status"] == "READY": self._transition(execution_id, t, "PAUSED", "execution paused")
                    if not running:
                        execution = self.store.load_execution(execution_id); execution["flags"]["pause_requested"] = False; execution["runner"] = None  # release the lease
                        self._set_execution_status(execution, "PAUSED", "paused by user"); return self._report(execution_id, tasks, reconciliation)
                elif not flags["cancel_requested"]:
                    for t in sorted(tasks.values(), key=lambda x: x["task_id"]):
                        if len(running) >= int(self.settings["max_workers"]): break
                        due = t["status"] == "READY" or (t["status"] == "RETRYING" and t.get("retry_at", "") <= utc_now())
                        if not due: continue
                        token = uuid.uuid4().hex
                        self._transition(execution_id, t, "RUNNING", f"attempt {t['attempts'] + 1}", attempts=t["attempts"] + 1, attempt_token=token)
                        ctx = self._context(execution, t, tasks, handoffs, execution_budget, token)
                        running[pool.submit(self._run_task, t, ctx)] = (t["task_id"], token, time.monotonic() + float(self.settings["task_timeout"]))
                if not running:
                    if any(t["status"] == "RETRYING" for t in tasks.values()): self.sleep(0.01); continue
                    return self._finalize(execution_id, tasks, None, reconciliation, execution_budget)
                done, _ = wait(list(running), timeout=0.05, return_when=FIRST_COMPLETED)
                now = time.monotonic()
                for future in list(running):
                    task_id, token, deadline = running[future]; task = tasks[task_id]
                    if future in done:
                        del running[future]
                        if task.get("attempt_token") != token or task["status"] != "RUNNING": continue  # stale attempt (timed out or cancelled)
                        self._apply_outcome(execution_id, tasks, task, future.result(), handoffs)
                    elif now > deadline:
                        del running[future]
                        self._failure(execution_id, tasks, task, {"error": f"task exceeded {self.settings['task_timeout']}s", "error_kind": "timeout", "retryable": True})
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def _context(self, execution: dict[str, Any], task: dict[str, Any], tasks: dict[str, dict[str, Any]], handoffs: dict[str, dict[str, Any]], budget: Budget, token: str) -> ExecutionContext:
        def record_intent(t: dict[str, Any], planned: list[dict[str, Any]]) -> None:
            with self._lock: t["write_intent"] = planned; t["updated_at"] = utc_now(); self.store.save_task(execution["execution_id"], t)
        return ExecutionContext(root=self.root, workspace=self.workspace, store=self.store, execution=execution, providers=self.providers,
                                provider_config=self.provider_config, execution_budget=budget, task_budget_limits=execution["budget_limits"].get("task") or {},
                                dependency_handoffs=[handoffs[d] for d in task["dependencies"] if d in handoffs], record_intent=record_intent,
                                command_timeout=float(self.settings["command_timeout"]), lock_owner=f"{execution['execution_id']}:{task['task_id']}:{token}",
                                task_budget=self._task_budgets.setdefault(task["task_id"], Budget(scope=f"task {task['task_id']}", **(execution["budget_limits"].get("task") or {}))),
                                platform=self.platform)

    def _run_task(self, task: dict[str, Any], ctx: ExecutionContext) -> dict[str, Any]:
        owner = ctx.lock_owner; started = time.perf_counter()  # per-attempt owner: a timed-out attempt cannot free its retry's locks
        try:
            for resource in task["resources"]:
                if not self.store.try_lock(f"resource:{resource}", owner, self.settings["lease_seconds"]):
                    return {"status": "FAILED", "retryable": True, "error": f"resource {resource} is held by {self.store.lock_owner(f'resource:{resource}')}", "error_kind": "resource_busy"}
            result = execute_task(task, ctx); result["duration_ms"] = round((time.perf_counter() - started) * 1000, 1); return result
        finally:
            self.store.release_locks(owner)

    def _promote(self, execution: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> None:
        approved = {a["task_id"] for a in execution["approvals"]}; eid = execution["execution_id"]
        for t in sorted(tasks.values(), key=lambda x: x["task_id"]):
            deps = [tasks[d] for d in t["dependencies"] if d in tasks]
            if t["status"] in ("PLANNED", "READY") and any(d["status"] in ("FAILED", "CANCELLED", "BLOCKED") for d in deps):
                self._transition(eid, t, "BLOCKED", f"dependency {next(d['task_id'] for d in deps if d['status'] in ('FAILED', 'CANCELLED', 'BLOCKED'))} did not complete"); continue
            ready = all(d["status"] == "COMPLETED" for d in deps)
            if t["status"] in ("PLANNED", "BLOCKED") and ready and not t["requires_approval"]: self._transition(eid, t, "READY", "dependencies completed")
            elif t["status"] == "WAITING_APPROVAL" and t["task_id"] in approved and ready: self._transition(eid, t, "READY", "approved and dependencies completed")
            elif t["status"] == "PAUSED": self._transition(eid, t, "READY", "execution resumed")

    def _apply_outcome(self, execution_id: str, tasks: dict[str, dict[str, Any]], task: dict[str, Any], result: dict[str, Any], handoffs: dict[str, dict[str, Any]]) -> None:
        self.store.record_agent_run(task["agent"], execution_id, task["task_id"], result["status"], verified=result["status"] == "COMPLETED" and not result.get("simulated"),
                                    simulated=bool(result.get("simulated")), duration_ms=result.get("duration_ms"))
        if result.get("usage"): self.store.add_event("provider_call", execution_id=execution_id, task_id=task["task_id"], agent_id=task["agent"], data=result["usage"], duration_ms=result.get("duration_ms"))
        if result["status"] != "COMPLETED": return self._failure(execution_id, tasks, task, result)
        verdict = (result.get("result") or {}).get("verdict")
        if task.get("review") and verdict == "request_changes" and self._review_exhausted(execution_id, task):
            rounds = self.settings["max_review_rounds"]
            self.store.add_event("review_limit", execution_id=execution_id, task_id=task["task_id"], severity="warning", data={"rounds": rounds})
            return self._failure(execution_id, tasks, task, {**result, "retryable": False, "error_kind": "review_rejected",
                                                              "error": f"changes still requested after {rounds} review round(s)"})
        targets = [t["agent"] for t in tasks.values() if task["task_id"] in t["dependencies"]]
        handoff = build_handoff(task, result, execution_id, targets); handoffs[task["task_id"]] = handoff
        self._transition(execution_id, task, "COMPLETED", "acceptance evidence recorded", result=result.get("result"), evidence=result.get("evidence", []),
                         handoff=handoff, simulated=bool(result.get("simulated")), duration_ms=result.get("duration_ms"))
        if task.get("review") and verdict == "request_changes": self._review_round(execution_id, tasks, task, result)
        delegate = (result.get("result") or {}).get("delegate")
        if delegate: self._delegate(execution_id, tasks, task, delegate)

    def _failure(self, execution_id: str, tasks: dict[str, dict[str, Any]], task: dict[str, Any], result: dict[str, Any]) -> None:
        if result.get("error_kind") == "resource_busy":  # waiting for a lock is not an attempt: requeue without spending one
            self._transition(execution_id, task, "RETRYING", f"waiting: {result.get('error')}", retry_at=_iso_in(0.05), attempts=task["attempts"] - 1); return
        if result.get("retryable") and task["attempts"] < int(self.settings["max_attempts"]):
            delay = float(self.settings["backoff_base"]) * (2 ** (task["attempts"] - 1))
            self._transition(execution_id, task, "RETRYING", f"{result.get('error_kind')}: {result.get('error')}; retry in {delay:.2f}s",
                             retry_at=_iso_in(delay), last_error=result.get("error")); return
        self._transition(execution_id, task, "FAILED", f"{result.get('error_kind')}: {result.get('error')}", last_error=result.get("error"), result=result.get("result"),
                         evidence=result.get("evidence", []))
        for dependent in self._dependents(tasks, task["task_id"]):
            if dependent["status"] in ("PLANNED", "READY", "PAUSED"): self._transition(execution_id, dependent, "BLOCKED", f"dependency {task['task_id']} failed")

    def _revise(self, execution_id: str, reason: str, added: list[dict[str, Any]], rewired: dict[str, list[str]]) -> None:
        execution = self.store.load_execution(execution_id)
        execution["revisions"].append({"revision": len(execution["revisions"]) + 2, "at": utc_now(), "reason": reason, "added": [t["task_id"] for t in added], "rewired": rewired})
        self._save_execution(execution); self.store.add_event("plan_revision", execution_id=execution_id, data=execution["revisions"][-1])

    def _review_exhausted(self, execution_id: str, review: dict[str, Any]) -> bool:
        execution = self.store.load_execution(execution_id); key = review.get("review_of") or review["task_id"]
        return execution["review_rounds"].get(key, 0) >= int(self.settings["max_review_rounds"])

    def _review_round(self, execution_id: str, tasks: dict[str, dict[str, Any]], review: dict[str, Any], result: dict[str, Any]) -> None:
        execution = self.store.load_execution(execution_id); key = review.get("review_of") or review["task_id"]
        rounds = execution["review_rounds"].get(key, 0) + 1
        execution["review_rounds"][key] = rounds; self._save_execution(execution)
        implementers = [tasks[d] for d in self._ancestors(tasks, review["task_id"]) if "write_files" in tasks[d]["permissions"]["allowed"]]
        if not implementers: return
        source = max(implementers, key=lambda t: t["task_id"]); base = len(tasks) + 1
        rework = self._clone(source, f"T{base:02d}", f"Address review findings (round {rounds})", [review["task_id"]])
        rereview = self._clone(review, f"T{base + 1:02d}", f"Re-review after round {rounds}", [rework["task_id"]]); rereview["review_of"] = key
        rewired = {}
        for dependent in [t for t in tasks.values() if review["task_id"] in t["dependencies"]]:
            dependent["dependencies"].append(rereview["task_id"]); rewired[dependent["task_id"]] = dependent["dependencies"]; self.store.save_task(execution_id, dependent)
        for t in (rework, rereview): tasks[t["task_id"]] = t; self.store.save_task(execution_id, t)
        self._revise(execution_id, f"review {key} requested changes (round {rounds}/{self.settings['max_review_rounds']})", [rework, rereview], rewired)

    def _delegate(self, execution_id: str, tasks: dict[str, dict[str, Any]], task: dict[str, Any], delegate: dict[str, Any]) -> None:
        from ..contracts import load_contract
        chain = task.get("delegation_chain") or [task["agent"]]; target = delegate.get("target_agent") if isinstance(delegate, dict) else None
        reason = None
        if not target: reason = "delegation without target_agent"
        elif target in chain: reason = f"delegation cycle {' -> '.join(chain + [target])}"
        elif len(chain) > int(self.settings["max_delegation_depth"]): reason = f"delegation depth {len(chain)} exceeds {self.settings['max_delegation_depth']}"
        contract = None
        if reason is None:
            try: contract = load_contract(self.root, target)["contract"]
            except (LookupError, ValueError) as exc: reason = f"unknown or unloadable target agent {target}: {exc}"
        if reason:
            self.store.add_event("delegation_rejected", execution_id=execution_id, task_id=task["task_id"], agent_id=task["agent"], severity="warning", data={"reason": reason}); return
        granted = set(task["permissions"]["allowed"]) & set(contract["tools"]["allowed"])  # never broader than the delegating task
        child = self._clone(task, f"T{len(tasks) + 1:02d}", f"Delegated by {task['agent']}: {str(delegate.get('objective', ''))[:120]}", [task["task_id"]])
        child.update(agent=target, delegation_chain=chain + [target], permissions={"allowed": sorted(granted), "approval_required": []}, tools=sorted(granted))
        tasks[child["task_id"]] = child; self.store.save_task(execution_id, child)
        self._revise(execution_id, f"{task['agent']} delegated to {target}", [child], {})

    def _clone(self, source: dict[str, Any], task_id: str, title: str, deps: list[str]) -> dict[str, Any]:
        task = new_task(task_id, title, objective=title, intent=source["intent"], capabilities=source["capabilities"], domains=source["domains"],
                        executor=dict(source["executor"]), tools=list(source["tools"]), acceptance_criteria=list(source["acceptance_criteria"]),
                        dependencies=deps, resources=list(source["resources"]), risk=source["risk"], stage=source.get("stage"), estimated_minutes=source["estimated_minutes"])
        task.update(agent=source["agent"], routing=source.get("routing"), skills=source.get("skills", []), permissions=copy.deepcopy(source["permissions"]),
                    requires_approval=source["requires_approval"], step=source["step"], review=source.get("review", False),
                    idempotency_key=f"{source.get('idempotency_key', '')}:{task_id}", delegation_chain=list(source.get("delegation_chain") or [source["agent"]]))
        task["history"].append({"from": "CREATED", "to": "PLANNED", "at": utc_now(), "reason": f"added by plan revision from {source['task_id']}"}); task["status"] = "PLANNED"
        return task

    def _ancestors(self, tasks: dict[str, dict[str, Any]], task_id: str) -> set[str]:
        seen, frontier = set(), list(tasks[task_id]["dependencies"])
        while frontier:
            current = frontier.pop()
            if current in seen or current not in tasks: continue
            seen.add(current); frontier += tasks[current]["dependencies"]
        return seen

    # -- completion -------------------------------------------------------------------------------------------
    def _finish_cancel(self, execution_id: str) -> dict[str, Any]:
        execution = self.store.load_execution(execution_id); tasks = {t["task_id"]: t for t in self.store.load_tasks(execution_id)}
        for t in tasks.values():
            if t["status"] in ACTIVE - {"RUNNING"}: self._transition(execution_id, t, "CANCELLED", "execution cancelled")
        self._set_execution_status(execution, "CANCELLED", "cancelled by user"); return self.store.load_execution(execution_id)

    def _finalize(self, execution_id: str, tasks: dict[str, dict[str, Any]], forced: str | None, reconciliation: list[str], budget: Budget) -> dict[str, Any]:
        execution = self.store.load_execution(execution_id); states = [t["status"] for t in tasks.values()]
        if forced: status = forced
        elif all(s == "COMPLETED" for s in states): status = "COMPLETED"
        elif "WAITING_APPROVAL" in states and not any(s in ("FAILED", "BLOCKED") for s in states if s != "WAITING_APPROVAL"): status = "WAITING_APPROVAL"
        else: status = "FAILED"
        execution["usage"] = budget.to_dict(); execution["runner"] = None
        try: self._set_execution_status(execution, status, "no runnable task left")
        except InvalidTransition: self._save_execution(execution)
        self._remember(execution_id, tasks, status)
        return self._report(execution_id, tasks, reconciliation)

    def _remember(self, execution_id: str, tasks: dict[str, dict[str, Any]], status: str) -> None:
        execution = self.store.load_execution(execution_id); simulated = any(t.get("simulated") for t in tasks.values())
        self.store.put_record("execution", "summary", execution_id, {"request": execution["request"], "status": status, "tasks": {t["task_id"]: t["status"] for t in tasks.values()},
                              "simulated": simulated}, f"Execution {execution_id} {status}: {execution['request'][:120]}", tags=["execution", status.lower()], source=f"execution:{execution_id}")
        for t in tasks.values():
            for ev in t.get("evidence") or []:
                if ev.get("type") == "command":
                    self.store.put_record("quality", "test_run", f"{execution_id}:{t['task_id']}", {"command": ev["command"], "exit_code": ev["exit_code"]},
                                          f"{' '.join(ev['command'])} exited {ev['exit_code']}", tags=["tests"], source=f"execution:{execution_id}")
            if t.get("step") == "decision" and t["status"] == "COMPLETED":
                self.store.put_record("decision", "adr", f"{execution_id}:{t['task_id']}", t.get("result") or {}, (t.get("result") or {}).get("summary", "decision")[:200],
                                      tags=["decision"], source=f"execution:{execution_id}")

    def _report(self, execution_id: str, tasks: dict[str, dict[str, Any]], reconciliation: list[str]) -> dict[str, Any]:
        execution = self.store.load_execution(execution_id)
        return {"execution_id": execution_id, "status": execution["status"], "plan_id": execution["plan_id"], "reconciliation": reconciliation,
                "usage": execution["usage"], "revisions": execution["revisions"], "approvals": execution["approvals"],
                "tasks": [{"task_id": t["task_id"], "step": t["step"], "agent": t["agent"], "status": t["status"], "attempts": t["attempts"],
                           "simulated": t.get("simulated", False), "last_error": t.get("last_error")} for t in sorted(tasks.values(), key=lambda x: x["task_id"])]}
