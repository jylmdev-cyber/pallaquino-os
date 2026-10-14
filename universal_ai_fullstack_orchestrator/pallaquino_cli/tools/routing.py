"""PALLAQUINO Tool Router: explainable selection of registered, available, permitted tools for a capability need.

Hard filters: the tool must exist, cover every required capability, be available and pass a dry-run permission
check for the requesting principal (tools needing a missing grant or approval are reported, not offered). Remote
tools are excluded for sensitive data unless the caller authorizes them. Ranking: locality (builtin, then local
plugin process, then local stdio MCP server, then remote), lower risk, verified reliability and latency from the
audit trail (only after MIN_HISTORY calls), then tool ID. Descriptions never influence the score: they are
untrusted text. The router never invents a tool: an uncovered need is returned as `missing`.
"""
from __future__ import annotations

from statistics import median
from typing import Any, Iterable

from ..core import RISK_ORDER

LOCALITY = {"builtin": 0, "plugin": 1, "mcp_stdio": 2, "mcp_http": 3}
MIN_HISTORY = 5


def _locality(tool: dict[str, Any]) -> str:
    kind = tool["source"]["kind"]
    if kind == "mcp": return "mcp_http" if tool["source"].get("transport") == "http" else "mcp_stdio"
    return kind


def _history(store: Any, tool_id: str) -> dict[str, Any]:
    calls = [c for c in store.list_tool_calls(tool_id=tool_id, limit=200) if c.get("status") in ("COMPLETED", "FAILED")] if store is not None else []
    if len(calls) < MIN_HISTORY: return {"calls": len(calls), "success_rate": None, "median_ms": None}
    return {"calls": len(calls), "success_rate": sum(c["status"] == "COMPLETED" for c in calls) / len(calls),
            "median_ms": median(c.get("duration_ms") or 0 for c in calls)}


def route(registry: Any, permissions: Any, *, capabilities: Iterable[str], principal: dict[str, str], agent_grants: set[str] | None = None,
          sensitive: bool = False, allow_remote: bool = False, store: Any = None, limit: int = 5) -> dict[str, Any]:
    wanted = sorted(set(capabilities)); candidates = []; excluded = []
    for tool in registry.list():
        if not set(wanted) <= set(tool["capabilities"]): continue
        tid = tool["tool_id"]; place = _locality(tool)
        if not tool["available"]: excluded.append({"tool_id": tid, "reason": f"unavailable: {tool['availability']}"}); continue
        if place == "mcp_http" and sensitive and not allow_remote: excluded.append({"tool_id": tid, "reason": "remote tool excluded for sensitive data without authorization"}); continue
        decision = permissions.evaluate(tool, {}, principal=principal, agent_grants=agent_grants, consume=False)
        if decision["outcome"] == "denied": excluded.append({"tool_id": tid, "reason": decision["reason"]}); continue
        stats = _history(store, tid)
        reasons = [f"covers {wanted}", f"locality {place}", f"risk {tool['risk']}"]
        if decision["outcome"] == "approval_required": reasons.append("each call needs a human approval")
        if stats["success_rate"] is not None: reasons.append(f"{stats['calls']} audited calls, success {stats['success_rate']:.0%}, median {stats['median_ms']:.0f} ms")
        candidates.append({"tool_id": tid, "source": tool["source"]["kind"], "locality": place, "risk": tool["risk"], "operation": tool["operation"],
                           "needs_approval": decision["outcome"] == "approval_required", "history": stats, "reasons": reasons,
                           "_key": (LOCALITY[place], RISK_ORDER[tool["risk"]], decision["outcome"] == "approval_required",
                                    -(stats["success_rate"] if stats["success_rate"] is not None else 0.5), stats["median_ms"] or 0, tid)})
    candidates.sort(key=lambda c: c["_key"])
    for c in candidates: c.pop("_key")
    return {"capabilities": wanted, "selected": candidates[:limit], "excluded": excluded, "missing": [] if candidates else wanted}
