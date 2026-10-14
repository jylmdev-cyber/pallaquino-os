"""Tool contract v1: capabilities, operation classes, derived risk and approval policy (ADR-0015).

A tool is described by PALLAQUINO, not by whoever provides it. External descriptions, MCP annotations and plugin
self-declarations are kept as untrusted hints; the operation class that drives authorization comes from PALLAQUINO
policy (builtin tools), the reviewed plugin manifest under a trust policy, or a human classification of an MCP
tool. Unclassified external tools default to EXTERNAL_SIDE_EFFECT, the most restrictive non-destructive class.
"""
from __future__ import annotations

import re
from typing import Any

from ..core import RISK_ORDER
from .schema import check_schema

CONTRACT_VERSION = 1
CAPABILITIES = ["FILE_READ", "FILE_WRITE", "CODE_EXECUTION", "GIT_READ", "GIT_WRITE", "DATABASE_READ", "DATABASE_WRITE", "NETWORK_READ",
                "NETWORK_WRITE", "CLOUD_MANAGEMENT", "DEPLOYMENT", "SECRETS_ACCESS"]
OPERATIONS = ["READ_ONLY", "WRITE_OPERATION", "SENSITIVE_OPERATION", "DESTRUCTIVE_OPERATION", "EXTERNAL_SIDE_EFFECT"]
SOURCES = {"builtin", "plugin", "mcp"}
TRUST_LEVELS = {"builtin", "trusted", "untrusted"}
APPROVAL_POLICIES = {"contract", "grant", "per_call"}
OPERATION_RISK = {"READ_ONLY": "LOW", "WRITE_OPERATION": "MEDIUM", "SENSITIVE_OPERATION": "HIGH", "EXTERNAL_SIDE_EFFECT": "HIGH",
                  "DESTRUCTIVE_OPERATION": "CRITICAL"}
CAPABILITY_RISK = {"SECRETS_ACCESS": "CRITICAL", "DEPLOYMENT": "CRITICAL", "CLOUD_MANAGEMENT": "CRITICAL", "DATABASE_WRITE": "HIGH",
                   "NETWORK_WRITE": "HIGH", "GIT_WRITE": "MEDIUM", "FILE_WRITE": "MEDIUM", "CODE_EXECUTION": "MEDIUM"}
# Bridge to agent contracts v2: the abstract tool an agent must be granted for a task before it may use a concrete
# tool with this capability. Governed abstract tools always need a human approval (ADR-0010).
CAPABILITY_GRANTS = {"FILE_READ": {"read_repository", "search_repository"}, "GIT_READ": {"read_repository"}, "FILE_WRITE": {"write_files"},
                     "GIT_WRITE": {"git_commit"}, "CODE_EXECUTION": {"run_tests", "run_linters", "run_build", "run_security_scan"},
                     "DATABASE_READ": {"read_repository"}, "DATABASE_WRITE": {"database_migration_apply"}, "NETWORK_READ": {"network_read"},
                     "NETWORK_WRITE": set(), "CLOUD_MANAGEMENT": {"infrastructure_apply"}, "DEPLOYMENT": {"deploy"}, "SECRETS_ACCESS": {"secrets_access"}}
TOOL_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9][a-z0-9_-]*)+$")
DEFAULT_LIMITS = {"max_input_bytes": 64 * 1024, "max_output_bytes": 256 * 1024}


def normalize_segment(text: str) -> str:
    """Make an external name safe for a tool-ID segment; collisions are detected by the registry, not hidden."""
    value = re.sub(r"[^a-z0-9_-]+", "_", text.strip().lower()).strip("_-") or "unnamed"
    return value if value[0].isalnum() else f"t{value}"


def derive_risk(operation: str, capabilities: list[str]) -> str:
    levels = [OPERATION_RISK[operation]] + [CAPABILITY_RISK[c] for c in capabilities if c in CAPABILITY_RISK]
    return max(levels, key=lambda level: RISK_ORDER[level])


def derive_approval(operation: str, trust: str, capabilities: list[str]) -> str:
    """READ_ONLY builtin tools follow the agent contract; other reads and writes need a scoped grant; anything
    sensitive, destructive, externally effective or touching secrets, deployment or cloud needs a per-call approval."""
    if operation in ("SENSITIVE_OPERATION", "DESTRUCTIVE_OPERATION", "EXTERNAL_SIDE_EFFECT"): return "per_call"
    if set(capabilities) & {"SECRETS_ACCESS", "DEPLOYMENT", "CLOUD_MANAGEMENT", "DATABASE_WRITE", "NETWORK_WRITE"}: return "per_call"
    if operation == "READ_ONLY" and trust == "builtin": return "contract"
    return "grant"


def new_tool(tool_id: str, *, description: str, source: dict[str, Any], input_schema: dict[str, Any], capabilities: list[str], operation: str,
             output_schema: dict[str, Any] | None = None, tool_version: str = "1.0.0", timeout_seconds: float = 30.0,
             retry: dict[str, Any] | None = None, requires_connection: str | None = None, annotations: dict[str, Any] | None = None,
             classification: str = "builtin", limits: dict[str, int] | None = None, definition_sha256: str | None = None,
             title: str | None = None, provides: list[str] | None = None) -> dict[str, Any]:
    namespace, _, name = tool_id.rpartition(".")
    trust = source.get("trust", "untrusted")
    idempotent = operation == "READ_ONLY"
    return {"contract": "tool", "version": CONTRACT_VERSION, "tool_id": tool_id, "namespace": namespace, "name": name, "title": title or name,
            "description": description, "source": source, "tool_version": tool_version, "input_schema": input_schema, "output_schema": output_schema,
            "capabilities": sorted(set(capabilities)), "provides": sorted(set(provides or [])), "operation": operation, "risk": derive_risk(operation, capabilities),
            "supported_operations": ["call", "check"], "timeout_seconds": timeout_seconds,
            "retry": retry or {"max_attempts": 2 if idempotent else 1, "retry_on": ["timeout", "unavailable"] if idempotent else []},
            "approval": derive_approval(operation, trust, capabilities), "requires_connection": requires_connection,
            "limits": {**DEFAULT_LIMITS, **(limits or {})}, "classification": classification, "annotations": annotations or {},
            "definition_sha256": definition_sha256}


def validate_tool(tool: dict[str, Any]) -> list[str]:
    errors = [f"tool missing {f}" for f in ("contract", "version", "tool_id", "namespace", "name", "description", "source", "input_schema",
                                             "capabilities", "operation", "risk", "approval", "timeout_seconds", "retry", "limits") if f not in tool]
    if errors: return errors
    if not TOOL_ID.match(tool["tool_id"]): errors.append(f"tool ID {tool['tool_id']!r} must be a lowercase dotted namespace.name")
    if tool["source"].get("kind") not in SOURCES: errors.append(f"{tool['tool_id']}: unknown source kind {tool['source'].get('kind')!r}")
    if tool["source"].get("trust") not in TRUST_LEVELS: errors.append(f"{tool['tool_id']}: unknown trust {tool['source'].get('trust')!r}")
    if tool["source"].get("kind") != "builtin" and tool["source"].get("trust") == "builtin": errors.append(f"{tool['tool_id']}: only builtin tools can have builtin trust")
    unknown = [c for c in tool["capabilities"] if c not in CAPABILITIES]
    if unknown: errors.append(f"{tool['tool_id']}: unknown capabilities {unknown}")
    if not tool["capabilities"]: errors.append(f"{tool['tool_id']}: at least one capability is required")
    if not isinstance(tool.get("provides", []), list) or any(not isinstance(t, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", t) for t in tool.get("provides", [])):
        errors.append(f"{tool['tool_id']}: provides must list lowercase functional tags")
    if tool["operation"] not in OPERATIONS: errors.append(f"{tool['tool_id']}: unknown operation class {tool['operation']!r}")
    elif tool["approval"] != derive_approval(tool["operation"], tool["source"]["trust"], tool["capabilities"]):
        errors.append(f"{tool['tool_id']}: approval policy {tool['approval']!r} is weaker or different than the derived policy")
    if tool["risk"] not in RISK_ORDER: errors.append(f"{tool['tool_id']}: unknown risk {tool['risk']!r}")
    elif tool["operation"] in OPERATIONS and RISK_ORDER[tool["risk"]] < RISK_ORDER[derive_risk(tool["operation"], tool["capabilities"])]:
        errors.append(f"{tool['tool_id']}: risk {tool['risk']} is below the derived risk")
    for key in ("input_schema", "output_schema"):
        if tool.get(key) is not None:
            errors += [f"{tool['tool_id']} {key}: {p}" for p in check_schema(tool[key])[:5]]
    if tool["input_schema"] is not None and tool["input_schema"].get("type") not in ("object", None): errors.append(f"{tool['tool_id']}: input schema must describe an object")
    if not 0 < float(tool["timeout_seconds"]) <= 3600: errors.append(f"{tool['tool_id']}: timeout must be in (0, 3600] seconds")
    if tool["operation"] != "READ_ONLY" and tool["retry"].get("max_attempts", 1) > 1: errors.append(f"{tool['tool_id']}: only READ_ONLY tools may be retried automatically")
    return errors


def required_grants(tool: dict[str, Any]) -> list[set[str]]:
    """For each capability, the abstract agent tools any one of which authorizes it (empty set = never by contract)."""
    return [CAPABILITY_GRANTS.get(c, set()) for c in tool["capabilities"]]


def contract_covers(tool: dict[str, Any], granted: set[str]) -> tuple[bool, list[str]]:
    missing = [c for c, options in zip(tool["capabilities"], required_grants(tool)) if not options & granted]
    return not missing, missing
