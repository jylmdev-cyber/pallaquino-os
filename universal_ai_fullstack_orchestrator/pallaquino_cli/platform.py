"""PALLAQUINO extensible platform (0.5.0): one object that assembles the tool registry, permission gateway,
execution gateway, MCP connections, plugins and integration adapters for a project.

The core works without any of it: nothing here is imported by the 0.3/0.4 commands unless a task or command
needs tools. Builtin adapters (filesystem, Git, SQLite) are always registered; GitHub only when enabled in
`governance/integrations.json`; MCP tools only from pinned catalogs; plugin tools only from ACTIVE plugins.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .extensions.manager import PluginManager
from .integrations import database, filesystem, git, github
from .mcp.auth import CredentialStore
from .mcp.connections import ConnectionManager
from .memory.store import MemoryStore
from .tools.gateway import ToolGateway
from .tools.permissions import PermissionGateway
from .tools.registry import ToolRegistry
from .tools.routing import route

INTEGRATIONS_PATH = "governance/integrations.json"
DEFAULT_INTEGRATIONS = {"schema_version": 1, "github": {"enabled": False, "api_url": "https://api.github.com", "credential_ref": "env:GITHUB_TOKEN"}}


def load_integrations(root: Path) -> dict[str, Any]:
    path = Path(root) / INTEGRATIONS_PATH
    return {**DEFAULT_INTEGRATIONS, **json.loads(path.read_text(encoding="utf-8"))} if path.is_file() else dict(DEFAULT_INTEGRATIONS)


class Platform:
    def __init__(self, root: Path, *, workspace: Path | None = None, store: MemoryStore | None = None, plugin_paths: list[Path] | None = None,
                 include_environment_plugins: bool = True, credentials: CredentialStore | None = None):
        self.root = Path(root); self.workspace = Path(workspace or (self.root.parent if self.root.name == ".pallaquino" else Path.cwd())).resolve()
        self.owns_store = store is None; self.store = store or MemoryStore.for_root(self.root)
        self.credentials = credentials or CredentialStore(self.store.project)
        self.registry = ToolRegistry(); self.permissions = PermissionGateway(self.store)
        self.gateway = ToolGateway(self.registry, self.permissions, self.store, workspace=self.workspace)
        self.connections = ConnectionManager(self.store, self.root, credentials=self.credentials, workspace=self.workspace)
        self.plugins = PluginManager(self.store, self.root, workspace=self.workspace, extra_paths=plugin_paths, include_environment=include_environment_plugins)
        self.loaded: dict[str, Any] = {}

    def __enter__(self) -> "Platform":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.plugins.stop_all(); self.connections.close_all()
        if self.owns_store: self.store.close()

    def load(self, *, activate_plugins: bool = True, mcp: bool = True) -> dict[str, Any]:
        config = load_integrations(self.root)
        builtin = filesystem.tools() + git.tools() + database.tools()
        if config.get("github", {}).get("enabled"):
            builtin += github.tools(config["github"], lambda ref: self.credentials.resolve(ref, server="core.github"))
        for tool, executor in builtin: self.registry.register(tool, executor)
        report: dict[str, Any] = {"builtin": len(builtin), "mcp": None, "plugins": []}
        if mcp: report["mcp"] = self.connections.register_tools(self.registry)
        if activate_plugins:
            for doc in self.store.list_platform("plugin"):
                if doc["state"] in ("ENABLED", "ACTIVE", "DEGRADED"):  # FAILED plugins wait for an operator
                    try: self.plugins.activate(doc["plugin_id"], self.registry); report["plugins"].append({"plugin_id": doc["plugin_id"], "state": "ACTIVE"})
                    except Exception as exc: report["plugins"].append({"plugin_id": doc["plugin_id"], "state": "FAILED", "error": str(exc)[:300]})
        report["tools"] = len(self.registry); report["rejected"] = self.registry.rejected
        self.loaded = report
        return report

    def route(self, capabilities: list[str], **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("principal", {"kind": "human", "id": "cli"})
        return route(self.registry, self.permissions, capabilities=capabilities, store=self.store, **kwargs)

    def metrics(self) -> dict[str, Any]:
        """Platform metrics from persisted state and the audit trail (no sampling, no external exporter)."""
        events = self.store.list_events(); counts = Counter(e["event_type"] for e in events)
        calls = self.store.list_tool_calls(limit=10_000); by_tool: dict[str, list[float]] = {}
        for call in calls: by_tool.setdefault(call["tool_id"], []).append(call.get("duration_ms") or 0.0)
        plugins = self.store.list_platform("plugin"); connections = self.connections.list()
        tools = self.registry.list()
        return {"plugins_registered": len(plugins), "plugins_active": sum(p["state"] == "ACTIVE" for p in plugins),
                "connections_configured": len(connections), "connections_healthy": sum(c["state"] == "CONNECTED" for c in connections),
                "tools_registered": len(tools), "tools_available": sum(t["available"] for t in tools),
                "executions_succeeded": sum(c["status"] == "COMPLETED" for c in calls), "executions_failed": sum(c["status"] == "FAILED" for c in calls),
                "timeouts": sum(c.get("error_kind") == "timeout" for c in calls), "permission_denials": counts["permission_denied"],
                "authorization_errors": sum(c.get("error_kind") == "auth" for c in calls), "policy_violations": counts["policy_violation"],
                "latency_ms_by_tool": {tid: {"calls": len(v), "max": max(v), "mean": round(sum(v) / len(v), 2)} for tid, v in sorted(by_tool.items())},
                "events": {k: counts[k] for k in sorted(counts) if k.startswith(("plugin_", "mcp_", "tool_", "permission_", "policy_"))}}
