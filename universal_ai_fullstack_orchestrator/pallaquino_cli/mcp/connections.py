"""PALLAQUINO MCP Connection Manager: persistent connection registry, health, catalog review and tool bridging.

Persistent configuration (`connection` documents) is separate from transient transport state (live clients held
in memory) and from the reviewed catalog (`catalog` documents). A server's tools reach the unified registry only
after a human pins the catalog (`pallaquino mcp pin`). Each call re-checks the live definition against the pinned
digest: a changed description or schema (rug pull, tool poisoning) makes the tool unavailable and the connection
DEGRADED until it is reviewed again. Tool descriptions with instruction-like content are never registered.
External tools are classified by PALLAQUINO: by default EXTERNAL_SIDE_EFFECT (per-call approval), unless a human
classified them in `tool_policies`. Annotations such as `readOnlyHint` are displayed, never trusted.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..memory.store import INJECTION_PATTERNS
from ..tools.contracts import CAPABILITIES, OPERATIONS, new_tool, normalize_segment
from ..tools.registry import ToolContext, tool_result
from .auth import AuthError, CredentialStore, bearer_provider
from .client import McpClient, McpError, definition_digest, deny_all_input
from .netpolicy import NetworkPolicy, NetworkPolicyError, check_url
from .transports import HttpTransport, StdioTransport, TransportError

STATES = ["CONFIGURED", "DISCONNECTED", "CONNECTING", "CONNECTED", "DEGRADED", "AUTH_REQUIRED", "FAILED", "DISABLED"]
CONNECTION_ID = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
RETRY_BACKOFF = (0.2, 0.6)


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_connection(config: dict[str, Any], *, root: Path) -> list[str]:
    errors = []
    if not CONNECTION_ID.match(str(config.get("connection_id", ""))): errors.append("connection_id must be 2-32 lowercase letters, digits or underscores")
    transport = config.get("transport")
    if transport == "stdio":
        command = config.get("command")
        if not (isinstance(command, list) and command and all(isinstance(c, str) and c for c in command)): errors.append("stdio connections need a command list")
        for name, ref in (config.get("env") or {}).items():
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name) or not isinstance(ref, str) or not ref.startswith("env:"):
                errors.append(f"env {name}: values must be credential references like env:VAR, never literal secrets")
    elif transport == "http":
        try: check_url(str(config.get("url")), NetworkPolicy.from_config(config.get("network")), resolve=False)
        except NetworkPolicyError as exc: errors.append(f"url: {exc}")
    else: errors.append("transport must be stdio or http")
    if config.get("mode", "auto") not in ("auto", "modern", "legacy"): errors.append("mode must be auto, modern or legacy")
    for name, policy in (config.get("tool_policies") or {}).items():
        if policy.get("operation") not in OPERATIONS: errors.append(f"tool_policies.{name}.operation must be one of {OPERATIONS}")
        if not policy.get("capabilities") or any(c not in CAPABILITIES for c in policy.get("capabilities", [])): errors.append(f"tool_policies.{name}.capabilities must be from {CAPABILITIES}")
    if config.get("trust", "untrusted") not in ("untrusted", "trusted"): errors.append("trust must be untrusted or trusted")
    return errors


class ConnectionManager:
    def __init__(self, store: Any, root: Path, *, credentials: CredentialStore | None = None, workspace: Path | None = None):
        self.store = store; self.root = Path(root); self.workspace = Path(workspace or root)
        self.credentials = credentials or CredentialStore(store.project); self.clients: dict[str, McpClient] = {}
        self.state: dict[str, dict[str, Any]] = {}; self._lock = threading.RLock()

    # -- configuration ------------------------------------------------------------------------------------
    def add(self, config: dict[str, Any], *, added_by: str = "cli") -> dict[str, Any]:
        config = {"mode": "auto", "timeout_seconds": 30, "trust": "untrusted", "enabled": True, "tool_policies": {}, **config}
        errors = validate_connection(config, root=self.root)
        if errors: raise ValueError("; ".join(errors))
        if self.store.get_platform("connection", config["connection_id"]): raise ValueError(f"connection {config['connection_id']} already exists")
        config.update({"project": self.store.project, "created_at": _iso(), "added_by": added_by})
        self.store.put_platform("connection", config["connection_id"], config, status="CONFIGURED")
        self.store.add_event("mcp_server_configured", data={"connection_id": config["connection_id"], "transport": config["transport"]})
        return config

    def remove(self, connection_id: str) -> dict[str, Any]:
        self.disconnect(connection_id); config = self.config(connection_id)
        self.store.delete_platform("connection", connection_id); self.store.delete_platform("catalog", connection_id)
        deleted = self.credentials.delete(connection_id)
        self.store.add_event("mcp_server_removed", data={"connection_id": connection_id, "credentials_deleted": deleted})
        return {"removed": connection_id, "transport": config["transport"], "credentials_deleted": deleted}

    def config(self, connection_id: str) -> dict[str, Any]:
        config = self.store.get_platform("connection", connection_id)
        if config is None: raise LookupError(f"MCP connection {connection_id!r} is not configured")
        return config

    def set_enabled(self, connection_id: str, enabled: bool) -> dict[str, Any]:
        config = self.config(connection_id); config["enabled"] = enabled
        self.store.put_platform("connection", connection_id, config, status="CONFIGURED" if enabled else "DISABLED")
        if not enabled: self.disconnect(connection_id)
        return config

    def list(self) -> list[dict[str, Any]]:
        rows = []
        for config in self.store.list_platform("connection"):
            catalog = self.store.get_platform("catalog", config["connection_id"]) or {}
            live = self.state.get(config["connection_id"], {})
            rows.append({"connection_id": config["connection_id"], "transport": config["transport"], "target": config.get("url") or " ".join(config.get("command", [])),
                         "enabled": config.get("enabled", True), "trust": config.get("trust"), "state": self._state(config),
                         "negotiated_version": live.get("protocol_version") or catalog.get("protocol_version"), "pinned_tools": len(catalog.get("tools", {})),
                         "last_checked": live.get("checked_at") or catalog.get("checked_at"), "last_error": live.get("error"),
                         "credential_ref": config.get("credential_ref")})
        return rows

    def _state(self, config: dict[str, Any]) -> str:
        if not config.get("enabled", True): return "DISABLED"
        return self.state.get(config["connection_id"], {}).get("state") or ("DISCONNECTED" if self.store.get_platform("catalog", config["connection_id"]) else "CONFIGURED")

    def _set_state(self, connection_id: str, state: str, **info: Any) -> None:
        with self._lock: self.state[connection_id] = {**self.state.get(connection_id, {}), "state": state, "checked_at": _iso(), **info}
        event = {"CONNECTED": "mcp_server_connected", "FAILED": "mcp_connection_failed", "AUTH_REQUIRED": "mcp_connection_failed", "DEGRADED": "mcp_connection_degraded"}.get(state)
        if event: self.store.add_event(event, severity="info" if state == "CONNECTED" else "warning", outcome=state.lower(),
                                       data={"connection_id": connection_id, **{k: v for k, v in info.items() if k in ("protocol_version", "era", "error")}})

    # -- transport ------------------------------------------------------------------------------------------
    def _transport(self, config: dict[str, Any]):
        if config["transport"] == "stdio":
            env = {name: (self.credentials.resolve(ref, server=config["connection_id"]) or "") for name, ref in (config.get("env") or {}).items()}
            command = [str(self.root / c) if i > 0 and c.endswith(".py") and not Path(c).is_absolute() and (self.root / c).is_file() else c for i, c in enumerate(config["command"])]
            return StdioTransport(command, cwd=str(self.root), env=env)
        policy = NetworkPolicy.from_config(config.get("network")); issuer = config.get("issuer")
        auth = None
        if config.get("credential_ref", "").startswith("vault:") and issuer: auth = bearer_provider(self.credentials, config["connection_id"], issuer, policy=policy)
        elif config.get("credential_ref"):
            ref = config["credential_ref"]; auth = lambda: (lambda t: f"Bearer {t}" if t else None)(self.credentials.resolve(ref, server=config["connection_id"]))
        return HttpTransport(config["url"], policy=policy, auth_header=auth)

    def connect(self, connection_id: str, *, retries: int = 1) -> McpClient:
        with self._lock:
            client = self.clients.get(connection_id)
            if client is not None and client.transport.alive(): return client
        config = self.config(connection_id)
        if not config.get("enabled", True): raise McpError("unavailable", f"connection {connection_id} is disabled")
        last: Exception | None = None
        for attempt in range(retries + 1):
            self._set_state(connection_id, "CONNECTING")
            try:
                client = McpClient(self._transport(config), mode=config.get("mode", "auto"), timeout=float(config.get("timeout_seconds", 30)), extensions=config.get("extensions"))
                info = client.connect()
                with self._lock: self.clients[connection_id] = client
                self._set_state(connection_id, "CONNECTED", protocol_version=info["protocol_version"], era=info["era"], error=None)
                return client
            except (McpError, TransportError, AuthError, NetworkPolicyError, OSError) as exc:
                last = exc; kind = getattr(exc, "kind", "unavailable")
                if kind == "auth" or isinstance(exc, AuthError):
                    self._set_state(connection_id, "AUTH_REQUIRED", error=str(exc)[:300]); break
                if kind == "incompatible" or isinstance(exc, NetworkPolicyError): self._set_state(connection_id, "FAILED", error=str(exc)[:300]); break
                self._set_state(connection_id, "FAILED", error=str(exc)[:300])
                if attempt < retries: time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
        raise last if isinstance(last, McpError) else McpError(getattr(last, "kind", "unavailable"), str(last))

    def disconnect(self, connection_id: str) -> None:
        with self._lock: client = self.clients.pop(connection_id, None)
        if client: client.close()
        if connection_id in self.state: self._set_state(connection_id, "DISCONNECTED")

    def close_all(self) -> None:
        for connection_id in list(self.clients): self.disconnect(connection_id)

    # -- diagnostics and catalog review ---------------------------------------------------------------------
    def test(self, connection_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            client = self.connect(connection_id, retries=0); tools = client.list_tools(use_cache=False)
            report = {"ok": True, **client.describe(), "tools": len(tools), "warnings": client.warnings, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
            if report.get("instructions"): report["instructions"] = {"text": str(report["instructions"])[:500], "trust": "untrusted"}
            return report
        except McpError as exc:
            return {"ok": False, "error_kind": exc.kind, "error": str(exc)[:500], "state": self.state.get(connection_id, {}).get("state"),
                    "latency_ms": round((time.perf_counter() - started) * 1000, 1), "stderr": list(getattr(getattr(self.clients.get(connection_id), "transport", None), "stderr", []))[-5:]}

    def review(self, connection_id: str) -> dict[str, Any]:
        """Live tools compared with the pinned catalog: pinned, changed, new, removed and poisoned (never registrable)."""
        client = self.connect(connection_id); live = client.list_tools(use_cache=False)
        pinned = (self.store.get_platform("catalog", connection_id) or {}).get("tools", {}); rows = []
        for tool in live:
            text = f"{tool.get('description', '')} {tool.get('title', '')}"
            poisoned = bool(INJECTION_PATTERNS.search(text))
            status = "poisoned" if poisoned else "pinned" if pinned.get(tool["name"], {}).get("digest") == tool["definition_sha256"] else "changed" if tool["name"] in pinned else "new"
            rows.append({"name": tool["name"], "status": status, "digest": tool["definition_sha256"], "description": {"text": str(tool.get("description", ""))[:300], "trust": "untrusted"},
                         "annotations": {"hints": tool.get("annotations") or {}, "trust": "untrusted"}})
        removed = sorted(set(pinned) - {t["name"] for t in live})
        return {"connection_id": connection_id, "tools": rows, "removed": removed, "warnings": client.warnings}

    def pin(self, connection_id: str, *, approved_by: str = "cli", tools: list[str] | None = None) -> dict[str, Any]:
        client = self.connect(connection_id); live = client.list_tools(use_cache=False); review = {r["name"]: r for r in self.review(connection_id)["tools"]}
        chosen = {}; refused = []
        for tool in live:
            if tools is not None and tool["name"] not in tools: continue
            if review[tool["name"]]["status"] == "poisoned": refused.append(tool["name"]); continue
            chosen[tool["name"]] = {"digest": tool["definition_sha256"], "definition": {k: tool.get(k) for k in ("name", "title", "description", "inputSchema", "outputSchema", "annotations")}}
        catalog = {"connection_id": connection_id, "tools": chosen, "refused": refused, "approved_by": approved_by, "checked_at": _iso(),
                   "protocol_version": client.protocol_version, "era": client.era}
        self.store.put_platform("catalog", connection_id, catalog, status="pinned")
        self.store.add_event("mcp_catalog_pinned", data={"connection_id": connection_id, "tools": sorted(chosen), "refused": refused})
        if self.state.get(connection_id, {}).get("state") == "DEGRADED": self._set_state(connection_id, "CONNECTED")
        return catalog

    def doctor(self) -> dict[str, Any]:
        results = {c["connection_id"]: (self.test(c["connection_id"]) if c.get("enabled", True) else {"ok": True, "state": "DISABLED"}) for c in self.store.list_platform("connection")}
        return {"ok": all(r["ok"] for r in results.values()), "connections": results, "credentials": self.credentials.describe()}

    # -- bridge to the unified tool registry -------------------------------------------------------------------
    def tool_contract(self, config: dict[str, Any], definition: dict[str, Any], digest: str) -> dict[str, Any]:
        policy = (config.get("tool_policies") or {}).get(definition["name"])
        default_caps = ["CODE_EXECUTION"] if config["transport"] == "stdio" else ["NETWORK_WRITE"]
        trust = "trusted" if config.get("trust") == "trusted" else "untrusted"
        return new_tool(f"mcp.{config['connection_id']}.{normalize_segment(definition['name'])}", title=definition.get("title"),
                        description=str(definition.get("description") or "")[:2000],
                        source={"kind": "mcp", "id": config["connection_id"], "trust": trust, "transport": config["transport"], "remote_name": definition["name"]},
                        input_schema=definition.get("inputSchema") or {"type": "object"}, output_schema=definition.get("outputSchema"),
                        capabilities=policy["capabilities"] if policy else default_caps, operation=policy["operation"] if policy else "EXTERNAL_SIDE_EFFECT",
                        timeout_seconds=float(config.get("timeout_seconds", 30)), requires_connection=config["connection_id"],
                        annotations=definition.get("annotations") or {}, classification="human" if policy else "pallaquino_default", definition_sha256=digest,
                        provides=(policy or {}).get("provides", []))

    def register_tools(self, registry: Any) -> dict[str, Any]:
        registered = []; skipped = []
        for config in self.store.list_platform("connection"):
            if not config.get("enabled", True): continue
            catalog = self.store.get_platform("catalog", config["connection_id"])
            if not catalog: skipped.append({"connection_id": config["connection_id"], "reason": "catalog not pinned; run `pallaquino mcp pin`"}); continue
            for name, entry in sorted(catalog["tools"].items()):
                if (config.get("tool_policies") or {}).get(name, {}).get("enabled") is False: continue
                tool = self.tool_contract(config, entry["definition"], entry["digest"])
                if registry.try_register(tool, self._executor(config["connection_id"], name, entry), availability=self._availability(config["connection_id"])):
                    registered.append(tool["tool_id"])
        return {"registered": registered, "skipped": skipped, "rejected": list(registry.rejected)}

    def _availability(self, connection_id: str):
        def probe() -> tuple[bool, str]:
            state = self.state.get(connection_id, {}).get("state")
            if state in ("FAILED", "AUTH_REQUIRED", "DISABLED"): return False, f"connection {state}: {self.state[connection_id].get('error')}"
            if state == "DEGRADED": return False, "catalog changed since it was pinned; review with `pallaquino mcp tools`"
            return True, "pinned; connects on demand" if state != "CONNECTED" else "connected"
        return probe

    def _executor(self, connection_id: str, name: str, entry: dict[str, Any]):
        def run(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
            client = self.connect(connection_id)
            live = {t["name"]: t for t in client.list_tools()}
            current = live.get(name)
            if current is None or current["definition_sha256"] != entry["digest"]:
                self._set_state(connection_id, "DEGRADED", error=f"tool {name} changed or disappeared since it was pinned")
                raise PermissionError(f"tool {name} no longer matches its pinned definition (possible rug pull); call refused")
            remaining = max(0.5, (ctx.deadline - time.monotonic()) if ctx.deadline else 30.0)
            try:
                result = client.call_tool(name, arguments, tool=current, timeout=remaining, cancel=ctx.cancel, input_handler=deny_all_input,
                                          meta={"traceparent": ctx.traceparent} if ctx.traceparent else None)
            except McpError as exc:
                if exc.kind == "unavailable": self.disconnect(connection_id)
                error = RuntimeError(str(exc)); error.kind = exc.kind; raise error from None
            return tool_result(text=result["text"], structured=result["structured"], is_error=result["is_error"], content=result["content"], task=result.get("task"),
                               protocol_version=client.protocol_version)
        return run
