"""Execution observability: metrics, full traces and JSONL export from the structured event log.

Events are already redacted when stored. Field names in exports follow OpenTelemetry log conventions
(`timestamp`, `severity_text`, `trace_id`, `span_id`, `attributes`) so an optional exporter can forward them
without reshaping; no OpenTelemetry dependency is required.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..memory.store import MemoryStore


def metrics(store: MemoryStore, execution_id: str) -> dict[str, Any]:
    execution = store.load_execution(execution_id); tasks = store.load_tasks(execution_id); events = store.list_events(execution_id)
    states = Counter(t["status"] for t in tasks); retries = sum(max(t["attempts"] - 1, 0) for t in tasks)
    durations = [t["duration_ms"] for t in tasks if t.get("duration_ms") is not None]
    errors = Counter(e["data"].get("reason", "").split(":", 1)[0] for e in events if e["event_type"] == "task_state" and e["data"].get("to") in ("FAILED", "RETRYING"))
    calls = [e["data"] for e in events if e["event_type"] == "provider_call"]
    verified = [c for c in calls if c.get("verified")]
    gates = [t for t in tasks if t["executor"]["kind"] == "command"]
    waits = []
    for t in tasks:
        ready = next((h["at"] for h in t["history"] if h["to"] == "READY"), None); started = next((h["at"] for h in t["history"] if h["to"] == "RUNNING"), None)
        if ready and started: waits.append((_ms(started) - _ms(ready)))
    return {"execution_id": execution_id, "status": execution["status"], "tasks_created": len(tasks), "tasks_by_state": dict(states),
            "tasks_completed": states.get("COMPLETED", 0), "tasks_failed": states.get("FAILED", 0), "retries": retries,
            "duration_ms": {"total_task_time": round(sum(durations), 1), "max_task": max(durations, default=0)},
            "wait_ms": {"max": round(max(waits, default=0), 1), "mean": round(sum(waits) / len(waits), 1) if waits else 0},
            "agents_selected": sorted({t["agent"] for t in tasks if t["agent"]}), "errors_by_type": {k: v for k, v in errors.items() if k},
            "provider_calls": len(calls), "tokens_reported": sum((c.get("input_tokens") or 0) + (c.get("output_tokens") or 0) for c in verified),
            "calls_with_unverified_usage": len(calls) - len(verified), "cost_estimated": round(sum(c.get("cost_estimated") or 0 for c in calls), 6),
            "cost_verified": False, "simulated_tasks": sum(bool(t.get("simulated")) for t in tasks),
            "quality_gates": {"passed": sum(t["status"] == "COMPLETED" for t in gates), "failed": sum(t["status"] == "FAILED" for t in gates)},
            "security_events": sum(e["event_type"] == "security_violation" for e in events), "memory": store.status()["records"]}


def _ms(stamp: str) -> float:
    from datetime import datetime
    return datetime.fromisoformat(stamp).timestamp() * 1000


def trace(store: MemoryStore, execution_id: str) -> dict[str, Any]:
    """Request -> plan -> agent -> execution -> validation -> result, rebuilt from persisted state only."""
    execution = store.load_execution(execution_id); plan = store.load_plan(execution["plan_id"]); tasks = store.load_tasks(execution_id)
    return {"request": {"id": plan["request_id"], "text": plan["request"], "primary_intent": plan["intent"]["primary_intent"], "risk": plan["intent"]["risk"]["level"]},
            "plan": {"id": plan["plan_id"], "status": plan["status"], "warnings": plan["validation"]["warnings"], "revisions": plan["revisions"] + execution["revisions"]},
            "approvals": execution["approvals"],
            "tasks": [{"task_id": t["task_id"], "step": t["step"], "agent": t["agent"], "routing": t["routing"], "tools": t["permissions"],
                       "attempts": t["attempts"], "status": t["status"], "simulated": t.get("simulated", False),
                       "validation": [{k: e.get(k) for k in ("type", "command", "exit_code", "op", "provider") if k in e} for e in t.get("evidence") or []],
                       "result": (t.get("result") or {}).get("summary"), "history": t["history"]} for t in tasks],
            "result": {"status": execution["status"], "usage": execution["usage"]}}


def export_jsonl(store: MemoryStore, execution_id: str, path: Path) -> int:
    rows = store.list_events(execution_id); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for e in rows:
            handle.write(json.dumps({"timestamp": e["ts"], "severity_text": e["severity"].upper(), "trace_id": execution_id, "span_id": e["task_id"],
                                     "body": e["event_type"], "attributes": {"agent.id": e["agent_id"], "outcome": e["outcome"], "duration_ms": e["duration_ms"], **e["data"]}},
                                    ensure_ascii=False, default=str) + "\n")
    return len(rows)
