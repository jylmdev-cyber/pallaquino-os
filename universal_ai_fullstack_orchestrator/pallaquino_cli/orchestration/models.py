"""Versioned orchestration contracts and the formal task/execution state machines (ADR-0010).

Contracts are plain JSON-compatible dicts so they persist and travel between processes and providers without
custom serialization; every contract carries `contract` and `version` and has a validator returning errors.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

CONTRACT_VERSION = 1
INTENTS = [
    "PROJECT_DISCOVERY", "ARCHITECTURE_DESIGN", "FEATURE_IMPLEMENTATION", "BUG_FIX", "CODE_REFACTOR", "SECURITY_AUDIT",
    "TEST_GENERATION", "DATABASE_MIGRATION", "API_DEVELOPMENT", "FRONTEND_DEVELOPMENT", "DOCUMENTATION",
    "PERFORMANCE_OPTIMIZATION", "DEVOPS_AUTOMATION", "RELEASE_PREPARATION",
]
EXECUTOR_KINDS = {"internal", "command", "agent"}

# Task state machine. Terminal states have no outgoing edges; FAILED -> READY exists only for an explicit
# `resume --retry-failed`; RUNNING -> RETRYING also covers reconciliation of a task orphaned by a crash.
TASK_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"PLANNED", "CANCELLED"},
    "PLANNED": {"WAITING_APPROVAL", "READY", "BLOCKED", "CANCELLED"},
    "WAITING_APPROVAL": {"READY", "CANCELLED"},
    "READY": {"RUNNING", "PAUSED", "BLOCKED", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "RETRYING", "CANCELLED"},
    "RETRYING": {"RUNNING", "FAILED", "CANCELLED"},
    "PAUSED": {"READY", "CANCELLED"},
    "BLOCKED": {"READY", "CANCELLED"},
    "FAILED": {"READY"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
TASK_STATES = list(TASK_TRANSITIONS)
TERMINAL_TASK_STATES = {"COMPLETED", "CANCELLED", "FAILED"}
EXECUTION_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"RUNNING", "WAITING_APPROVAL", "CANCELLED"},
    "RUNNING": {"COMPLETED", "FAILED", "PAUSED", "WAITING_APPROVAL", "CANCELLED", "RUNNING"},
    "WAITING_APPROVAL": {"RUNNING", "CANCELLED"},
    "PAUSED": {"RUNNING", "CANCELLED"},
    "FAILED": {"RUNNING"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class InvalidTransition(ValueError):
    """Raised when a task or execution would move along an edge the state machine does not declare."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def check_task_transition(current: str, target: str) -> None:
    if target not in TASK_TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"task transition {current} -> {target} is not allowed")


def check_execution_transition(current: str, target: str) -> None:
    if target not in EXECUTION_TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"execution transition {current} -> {target} is not allowed")


def new_task(task_id: str, title: str, *, objective: str, intent: str, capabilities: list[str], domains: list[str],
             executor: dict[str, Any], tools: list[str], acceptance_criteria: list[str], dependencies: Iterable[str] = (),
             resources: Iterable[str] = (), risk: str = "LOW", stage: str | None = None, estimated_minutes: int = 10) -> dict[str, Any]:
    return {"contract": "task", "version": CONTRACT_VERSION, "task_id": task_id, "title": title, "description": title, "objective": objective,
            "intent": intent, "stage": stage, "capabilities": capabilities, "domains": domains, "dependencies": list(dependencies),
            "agent": None, "routing": None, "skills": [], "executor": executor, "tools": tools, "resources": list(resources),
            "permissions": {"allowed": [], "approval_required": []}, "requires_approval": False, "risk": risk,
            "acceptance_criteria": acceptance_criteria, "estimated_minutes": estimated_minutes, "status": "CREATED",
            "attempts": 0, "result": None, "evidence": [], "history": []}


def validate_intent_result(value: dict[str, Any]) -> list[str]:
    errors = []
    for field in ("contract", "version", "request_id", "request", "intents", "primary_intent", "confidence", "scope", "technologies",
                  "required_capabilities", "risk", "permissions_required", "suggested_agents", "suggested_skills", "acceptance_criteria", "mode"):
        if field not in value: errors.append(f"intent result missing {field}")
    if errors: return errors
    if value["contract"] != "intent_result": errors.append("contract must be intent_result")
    for item in value["intents"]:
        if item.get("intent") not in INTENTS: errors.append(f"unknown intent {item.get('intent')}")
        if not 0 <= float(item.get("confidence", -1)) <= 1: errors.append(f"confidence out of range for {item.get('intent')}")
    if value["primary_intent"] not in INTENTS: errors.append("primary_intent is not a known intent")
    if value["risk"].get("source") != "deterministic": errors.append("risk must come from the deterministic engine")
    if not value["acceptance_criteria"]: errors.append("acceptance criteria are required")
    return errors


def validate_handoff(value: dict[str, Any]) -> list[str]:
    errors = [f"handoff missing {f}" for f in ("contract", "version", "source_agent", "target_agent", "execution_id", "task_id", "context_summary",
                                               "artifacts", "findings", "known_limitations", "pending_actions", "risk_level", "validation_evidence", "provenance")
              if f not in value]
    if errors: return errors
    if value["contract"] != "handoff": errors.append("contract must be handoff")
    for finding in value["findings"]:
        if finding.get("kind") not in ("fact", "hypothesis"): errors.append("each finding must be labelled fact or hypothesis")
        if finding.get("kind") == "fact" and not finding.get("evidence"): errors.append("facts need evidence; label unsupported claims as hypothesis")
    if len(value["context_summary"]) > 4000: errors.append("context summary exceeds 4000 characters")
    return errors
