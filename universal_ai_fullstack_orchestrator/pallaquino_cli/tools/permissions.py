"""PALLAQUINO Zero-Trust Tool Governance: deny by default, scoped grants, per-call approvals (ADR-0015).

Decision order for every call:
1. an agent may only use a tool whose capabilities its task grant covers (contracts v2 bridge), and a capability
   that maps to a governed abstract tool always needs a per-call approval;
2. the tool's approval policy then decides: `contract` (builtin read-only) needs nothing more, `grant` needs an
   active grant scoped to project, principal, tool and operation, and `per_call` needs a human approval bound to
   the exact argument digest, consumed on use.
Grants can never authorize `per_call` tools, so critical actions are never approved implicitly. Grants expire,
can be limited in uses and revoked; every decision is recorded as an event.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ..contracts import TOOL_TIERS
from .contracts import CAPABILITY_GRANTS, OPERATIONS, contract_covers

MAX_GRANT_DAYS = 90
DEFAULT_APPROVAL_MINUTES = 60


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def args_digest(tool_id: str, arguments: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps([tool_id, arguments], sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


class PermissionGateway:
    def __init__(self, store: Any):
        self.store = store

    # -- administration (human-initiated) -----------------------------------------------------------------
    def grant(self, tool_pattern: str, *, principal: str = "*", operations: list[str] | None = None, days: float = 7, max_uses: int | None = None,
              granted_by: str = "cli", reason: str = "", registry: Any = None) -> dict[str, Any]:
        operations = operations or ["READ_ONLY"]
        if any(o not in OPERATIONS for o in operations): raise ValueError(f"operations must be from {OPERATIONS}")
        if not 0 < days <= MAX_GRANT_DAYS: raise ValueError(f"grants last between 0 and {MAX_GRANT_DAYS} days")
        if not tool_pattern or tool_pattern in ("*", "**") or tool_pattern.count("*") > 1 or ("*" in tool_pattern and not tool_pattern.endswith(".*")):
            raise ValueError("tool pattern must be a tool ID or a namespace wildcard such as 'mcp.quality.*'")
        if set(operations) & {"SENSITIVE_OPERATION", "DESTRUCTIVE_OPERATION", "EXTERNAL_SIDE_EFFECT"}:
            raise ValueError("sensitive, destructive and external-side-effect operations are approved per call, never by a standing grant")
        if registry is not None:
            matched = [t for t in registry.list() if fnmatch.fnmatchcase(t["tool_id"], tool_pattern)]
            if not matched: raise ValueError(f"no registered tool matches {tool_pattern!r}")
            critical = [t["tool_id"] for t in matched if t["approval"] == "per_call"]
            if critical and "*" not in tool_pattern: raise ValueError(f"{critical} require a per-call approval; a grant cannot cover them")
        now = _now()
        grant = {"grant_id": f"grant-{uuid.uuid4().hex[:12]}", "tool_pattern": tool_pattern, "principal": principal, "operations": sorted(operations),
                 "project": self.store.project, "created_at": _iso(now), "expires_at": _iso(now + timedelta(days=days)), "max_uses": max_uses, "uses": 0,
                 "granted_by": granted_by, "reason": reason, "revoked_at": None}
        self.store.put_platform("grant", grant["grant_id"], grant, status="active")
        self.store.add_event("permission_grant_created", outcome="granted", data={k: grant[k] for k in ("grant_id", "tool_pattern", "principal", "operations", "expires_at")})
        return grant

    def revoke(self, grant_id: str, *, revoked_by: str = "cli") -> dict[str, Any]:
        grant = self.store.get_platform("grant", grant_id)
        if grant is None: raise LookupError(f"grant {grant_id} not found")
        grant["revoked_at"] = _iso(_now()); grant["revoked_by"] = revoked_by
        self.store.put_platform("grant", grant_id, grant, status="revoked")
        self.store.add_event("permission_revoked", outcome="revoked", data={"grant_id": grant_id})
        return grant

    def approve_call(self, tool_id: str, arguments: dict[str, Any], *, principal: str = "*", approved_by: str = "cli", minutes: float = DEFAULT_APPROVAL_MINUTES) -> dict[str, Any]:
        now = _now()
        approval = {"approval_id": f"appr-{uuid.uuid4().hex[:12]}", "tool_id": tool_id, "args_digest": args_digest(tool_id, arguments), "principal": principal,
                    "approved_by": approved_by, "created_at": _iso(now), "expires_at": _iso(now + timedelta(minutes=minutes)), "used_at": None}
        self.store.put_platform("approval", approval["approval_id"], approval, status="active")
        self.store.add_event("permission_approval_created", outcome="approved", data={k: approval[k] for k in ("approval_id", "tool_id", "args_digest", "expires_at")})
        return approval

    def list(self, *, include_inactive: bool = False) -> dict[str, Any]:
        grants = self.store.list_platform("grant"); approvals = self.store.list_platform("approval"); now = _iso(_now())
        def state(doc):
            if doc.get("revoked_at"): return "revoked"
            if doc.get("used_at"): return "used"
            if doc["expires_at"] < now: return "expired"
            if doc.get("max_uses") is not None and doc.get("uses", 0) >= doc["max_uses"]: return "exhausted"
            return "active"
        grants = [{**g, "state": state(g)} for g in grants]; approvals = [{**a, "state": state(a)} for a in approvals]
        if not include_inactive: grants = [g for g in grants if g["state"] == "active"]; approvals = [a for a in approvals if a["state"] == "active"]
        return {"grants": grants, "approvals": approvals}

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        kinds = {"permission_granted", "permission_denied", "permission_grant_created", "permission_revoked", "permission_approval_created", "policy_violation"}
        return [e for e in self.store.list_events() if e["event_type"] in kinds][-limit:]

    # -- evaluation ---------------------------------------------------------------------------------------
    def evaluate(self, tool: dict[str, Any], arguments: dict[str, Any], *, principal: dict[str, str], agent_grants: set[str] | None,
                 consume: bool = True) -> dict[str, Any]:
        """Return {allowed, outcome, reason, checks, grant_id?, approval_id?}; outcome is allowed, denied or approval_required."""
        checks: list[str] = []; tool_id = tool["tool_id"]; who = principal.get("id", "?")
        if principal.get("kind") == "agent":
            if agent_grants is None: return self._deny(tool, principal, record=consume, reason="agent call without a task grant", checks=checks)
            covered, missing = contract_covers(tool, agent_grants)
            if not covered: return self._deny(tool, principal, record=consume, reason=f"task grant does not cover capabilities {missing}", checks=checks)
            checks.append(f"agent contract covers {tool['capabilities']}")
            governed = {g for c in tool["capabilities"] for g in CAPABILITY_GRANTS.get(c, set()) & agent_grants if TOOL_TIERS.get(g) == "governed"}
            if governed: checks.append(f"capability maps to governed tools {sorted(governed)}")
        else:
            governed = set()
        policy = "per_call" if governed else tool["approval"]
        if policy == "contract":
            checks.append("builtin read-only tool: contract coverage suffices" if principal.get("kind") == "agent" else "builtin read-only tool invoked by a human")
            return self._allow(tool, principal, record=consume, checks=checks)
        if policy == "grant":
            grant = self._matching_grant(tool, who)
            if grant is None: return self._deny(tool, principal, record=consume, reason=f"no active grant covers {tool_id} ({tool['operation']}) for {who}", checks=checks)
            if consume:
                grant["uses"] = grant.get("uses", 0) + 1
                self.store.put_platform("grant", grant["grant_id"], grant, status="active")
            checks.append(f"grant {grant['grant_id']} ({grant['tool_pattern']}, expires {grant['expires_at']})")
            return self._allow(tool, principal, record=consume, checks=checks, grant_id=grant["grant_id"])
        approval = self._matching_approval(tool_id, arguments, who)
        if approval is None:
            decision = {"allowed": False, "outcome": "approval_required", "reason": f"{tool_id} needs a per-call approval for these exact arguments",
                        "checks": checks + ["per-call approval missing"], "args_digest": args_digest(tool_id, arguments)}
            if consume:
                self.store.add_event("permission_denied", agent_id=who if principal.get("kind") == "agent" else None, severity="warning", outcome="approval_required",
                                     data={"tool_id": tool_id, "reason": decision["reason"], "args_digest": decision["args_digest"]})
            return decision
        if consume:
            approval["used_at"] = _iso(_now()); self.store.put_platform("approval", approval["approval_id"], approval, status="used")
        checks.append(f"per-call approval {approval['approval_id']} by {approval['approved_by']}")
        return self._allow(tool, principal, record=consume, checks=checks, approval_id=approval["approval_id"])

    def _matching_grant(self, tool: dict[str, Any], who: str) -> dict[str, Any] | None:
        now = _iso(_now())
        for grant in self.store.list_platform("grant", status="active"):
            if grant.get("revoked_at") or grant["expires_at"] < now: continue
            if grant.get("max_uses") is not None and grant.get("uses", 0) >= grant["max_uses"]: continue
            if grant["project"] != self.store.project or grant["principal"] not in ("*", who): continue
            if not fnmatch.fnmatchcase(tool["tool_id"], grant["tool_pattern"]): continue
            if tool["operation"] not in grant["operations"]: continue
            return grant
        return None

    def _matching_approval(self, tool_id: str, arguments: dict[str, Any], who: str) -> dict[str, Any] | None:
        digest = args_digest(tool_id, arguments); now = _iso(_now())
        for approval in self.store.list_platform("approval", status="active"):
            if approval["tool_id"] == tool_id and approval["args_digest"] == digest and approval["principal"] in ("*", who) and not approval.get("used_at") and approval["expires_at"] >= now:
                return approval
        return None

    def _allow(self, tool, principal, *, record: bool, checks, **ids) -> dict[str, Any]:
        if record: self.store.add_event("permission_granted", agent_id=principal.get("id") if principal.get("kind") == "agent" else None, outcome="allowed",
                             data={"tool_id": tool["tool_id"], "checks": checks, **ids})
        return {"allowed": True, "outcome": "allowed", "reason": "authorized", "checks": checks, **ids}

    def _deny(self, tool, principal, checks=None, *, record: bool, reason: str) -> dict[str, Any]:
        checks = checks or []
        if record: self.store.add_event("permission_denied", agent_id=principal.get("id") if principal.get("kind") == "agent" else None, severity="warning", outcome="denied",
                             data={"tool_id": tool["tool_id"], "reason": reason})
        return {"allowed": False, "outcome": "denied", "reason": reason, "checks": checks + [f"denied: {reason}"]}
