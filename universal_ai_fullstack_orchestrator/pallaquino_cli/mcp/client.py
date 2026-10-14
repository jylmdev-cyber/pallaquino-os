"""PALLAQUINO MCP client for revision 2026-07-28 with an explicit legacy fallback (ADR-0014).

Connection: `server/discover` first (the probe the specification recommends on stdio and that also works on HTTP).
A DiscoverResult or a recognized modern error means a modern server; any other error or a timeout means a legacy
server, which is reached through the `initialize` handshake only when the connection allows it (`mode="auto"`).
Everything a server returns (descriptions, annotations, instructions, results) is untrusted data; this client only
validates shapes, schemas and sizes, and leaves authorization to the permission gateway.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import threading
import time
from typing import Any, Callable

from .. import __version__
from ..tools.schema import SchemaError, check_schema, validate
from . import protocol as p
from .transports import TransportError

CLIENT_INFO = {"name": "pallaquino", "version": __version__}
MAX_LIST_PAGES = 50
MAX_TOOLS = 2000
MAX_MRTR_ROUNDS = 3
InputHandler = Callable[[dict[str, Any]], dict[str, Any]]


class McpError(RuntimeError):
    """Normalized client error; `kind` is one of protocol, timeout, unavailable, cancelled, incompatible, invalid_response, input_denied, auth."""

    def __init__(self, kind: str, message: str, *, code: int | None = None, data: Any = None, status: int | None = None, headers: dict[str, str] | None = None):
        super().__init__(message); self.kind = kind; self.code = code; self.data = data; self.status = status; self.headers = headers or {}


def deny_all_input(requests: dict[str, Any]) -> dict[str, Any]:
    """Default MRTR handler: a server cannot obtain user input or approvals without the central control path."""
    raise McpError("input_denied", f"server requested input {sorted(requests)}; no input handler is authorized for this call")


def definition_digest(tool: dict[str, Any]) -> str:
    """Stable digest of what the client relies on, used to pin a reviewed catalog (rug-pull detection)."""
    pinned = {k: tool.get(k) for k in ("name", "description", "inputSchema", "outputSchema", "annotations")}
    return hashlib.sha256(json.dumps(pinned, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class McpClient:
    def __init__(self, transport: Any, *, mode: str = "auto", capabilities: dict[str, Any] | None = None, timeout: float = 30.0,
                 client_info: dict[str, str] | None = None, extensions: list[str] | None = None):
        if mode not in ("auto", "modern", "legacy"): raise ValueError("mode must be auto, modern or legacy")
        self.transport = transport; self.mode = mode; self.timeout = timeout; self.client_info = client_info or CLIENT_INFO
        self.capabilities = dict(capabilities or {})
        if extensions: self.capabilities["extensions"] = {name: {} for name in extensions}
        self.era: str | None = None; self.protocol_version: str | None = None; self.discover: dict[str, Any] | None = None
        self.server_info: dict[str, Any] | None = None; self.server_capabilities: dict[str, Any] = {}
        self._ids = itertools.count(1); self._cache: dict[str, tuple[float, Any]] = {}; self.warnings: list[str] = []
        self.header_mode = getattr(transport, "kind", "stdio") == "http"

    # -- low level ----------------------------------------------------------------------------------------
    def _send(self, method: str, params: dict[str, Any] | None, *, timeout: float | None = None, cancel: threading.Event | None = None,
              on_notification: Callable[[dict[str, Any]], None] | None = None, extra_headers: dict[str, str] | None = None,
              version: str | None = None, legacy: bool = False) -> dict[str, Any]:
        request_id = next(self._ids)
        if not legacy:
            params = p.with_meta(params, p.request_meta(version or self.protocol_version or p.PROTOCOL_VERSION, self.client_info, self.capabilities))
        message = p.request(request_id, method, params)
        headers: dict[str, str] = {}
        if self.header_mode:
            headers["MCP-Protocol-Version"] = version or self.protocol_version or p.PROTOCOL_VERSION
            if not legacy:
                headers["Mcp-Method"] = method
                field_name = p.METHODS_WITH_NAME.get(method)
                if field_name and params and params.get(field_name) is not None: headers["Mcp-Name"] = p.encode_header_value(params[field_name])
            headers.update(extra_headers or {})
        try:
            reply = self.transport.request(message, timeout=timeout or self.timeout, cancel=cancel, on_notification=on_notification, headers=headers)
        except TransportError as exc:
            if exc.kind == "http_status" and isinstance(exc.payload, dict) and "error" in exc.payload: reply = exc.payload
            elif exc.kind == "http_status" and exc.status in (401, 403):
                raise McpError("auth", f"MCP server answered HTTP {exc.status}", status=exc.status, headers=exc.headers) from None
            else: raise McpError(exc.kind if exc.kind in ("timeout", "cancelled", "unavailable") else "invalid_response", str(exc), status=exc.status, data=exc.payload) from None
        if not isinstance(reply, dict) or reply.get("jsonrpc") != p.JSONRPC: raise McpError("invalid_response", "response is not JSON-RPC 2.0")
        if "error" in reply:
            error = reply["error"] if isinstance(reply["error"], dict) else {}
            raise McpError("protocol", str(error.get("message", "error"))[:500], code=error.get("code"), data=error.get("data"))
        if reply.get("id") != request_id or not isinstance(reply.get("result"), dict): raise McpError("invalid_response", "response id or result is malformed")
        return reply["result"]

    def request(self, method: str, params: dict[str, Any] | None = None, **kwargs) -> dict[str, Any]:
        if self.era is None: self.connect()
        if self.era == "legacy": return self._send(method, params, legacy=True, **kwargs)
        try: return self._send(method, params, **kwargs)
        except McpError as exc:
            if exc.code == p.UNSUPPORTED_PROTOCOL_VERSION and isinstance(exc.data, dict):
                common = [v for v in exc.data.get("supported", []) if v in p.MODERN_VERSIONS]
                if common and common[0] != self.protocol_version: self.protocol_version = common[0]; return self._send(method, params, **kwargs)
                raise McpError("incompatible", f"server supports {exc.data.get('supported')}; client supports {p.MODERN_VERSIONS}") from None
            raise

    # -- connection -------------------------------------------------------------------------------------
    def connect(self) -> dict[str, Any]:
        if self.mode == "legacy": return self._legacy_connect()
        try:
            result = self._send("server/discover", {}, version=p.PROTOCOL_VERSION)
        except McpError as exc:
            if exc.code == p.UNSUPPORTED_PROTOCOL_VERSION and isinstance(exc.data, dict):
                common = [v for v in exc.data.get("supported", []) if v in p.MODERN_VERSIONS]
                if not common: raise McpError("incompatible", f"server supports {exc.data.get('supported')}; client supports {p.MODERN_VERSIONS}") from None
                result = self._send("server/discover", {}, version=common[0])
            elif exc.code in p.MODERN_ERROR_CODES: raise
            elif self.mode == "auto" and exc.kind in ("protocol", "timeout", "invalid_response"): return self._legacy_connect()
            else: raise
        p.result_type(result, {p.RESULT_COMPLETE})
        versions = [v for v in result.get("supportedVersions", []) if v in p.MODERN_VERSIONS]
        if not versions: raise McpError("incompatible", f"server supports {result.get('supportedVersions')}; client supports {p.MODERN_VERSIONS}")
        self.era = "modern"; self.protocol_version = versions[0]; self.discover = result
        self.server_capabilities = result.get("capabilities") if isinstance(result.get("capabilities"), dict) else {}
        self.server_info = (result.get("_meta") or {}).get(p.META_SERVER_INFO)
        return self.describe()

    def _legacy_connect(self) -> dict[str, Any]:
        """Compatibility path for 2025-era servers: initialize handshake, then notifications/initialized."""
        params = {"protocolVersion": p.LEGACY_VERSIONS[0], "capabilities": {k: v for k, v in self.capabilities.items() if k != "extensions"}, "clientInfo": self.client_info}
        result = self._send("initialize", params, legacy=True, version=p.LEGACY_VERSIONS[0])
        version = result.get("protocolVersion")
        if version not in p.LEGACY_VERSIONS: raise McpError("incompatible", f"legacy server negotiated unsupported version {version!r}")
        self.era = "legacy"; self.protocol_version = version
        self.server_capabilities = result.get("capabilities") or {}; self.server_info = result.get("serverInfo")
        message = p.notification("notifications/initialized")
        try:
            if getattr(self.transport, "kind", "") == "stdio": self.transport.send(message)
            else: self.transport.request(message, timeout=self.timeout, headers={"MCP-Protocol-Version": version})
        except TransportError as exc: raise McpError("unavailable", str(exc)) from None
        return self.describe()

    def describe(self) -> dict[str, Any]:
        return {"era": self.era, "protocol_version": self.protocol_version, "server_info": self.server_info, "capabilities": self.server_capabilities,
                "instructions": (self.discover or {}).get("instructions"), "extensions": sorted((self.server_capabilities.get("extensions") or {}))}

    def close(self) -> None:
        self.transport.close()

    # -- catalogs -----------------------------------------------------------------------------------------
    def _list(self, method: str, key: str, *, use_cache: bool = True) -> list[dict[str, Any]]:
        cached = self._cache.get(method)
        if use_cache and cached and cached[0] > time.monotonic(): return cached[1]
        items: list[dict[str, Any]] = []; cursor = None; ttl = None
        for _ in range(MAX_LIST_PAGES):
            result = self.request(method, {"cursor": cursor} if cursor else {})
            p.result_type(result, {p.RESULT_COMPLETE})
            page = result.get(key)
            if not isinstance(page, list): raise McpError("invalid_response", f"{method} result has no {key} list")
            items += [i for i in page if isinstance(i, dict)]
            ttl = result.get("ttlMs") if isinstance(result.get("ttlMs"), (int, float)) else ttl
            cursor = result.get("nextCursor")
            if not cursor or len(items) > MAX_TOOLS: break
        if cursor: self.warnings.append(f"{method}: listing truncated after {len(items)} items")
        if ttl: self._cache[method] = (time.monotonic() + min(ttl, 3_600_000) / 1000, items)
        return items

    def list_tools(self, *, use_cache: bool = True) -> list[dict[str, Any]]:
        """Tools with valid names and schemas; invalid definitions are excluded (and reported), never repaired."""
        valid = []; seen: set[str] = set()
        for tool in self._list("tools/list", "tools", use_cache=use_cache):
            name = tool.get("name")
            if not isinstance(name, str) or not 0 < len(name) <= 128: self.warnings.append("excluded a tool with an invalid name"); continue
            if name in seen: self.warnings.append(f"excluded duplicate tool {name!r}"); continue
            schema = tool.get("inputSchema")
            problems = check_schema(schema) if isinstance(schema, dict) else ["inputSchema must be an object"]
            if not problems and tool.get("outputSchema") is not None: problems = check_schema(tool["outputSchema"])
            if not problems and self.header_mode:
                try: p.header_parameters(schema)
                except ValueError as exc: problems = [str(exc)]
            if problems: self.warnings.append(f"excluded tool {name!r}: {problems[0]}"); continue
            seen.add(name); valid.append({**tool, "definition_sha256": definition_digest(tool)})
        return valid

    def list_resources(self) -> list[dict[str, Any]]:
        return self._list("resources/list", "resources")

    def list_prompts(self) -> list[dict[str, Any]]:
        return self._list("prompts/list", "prompts")

    # -- calls --------------------------------------------------------------------------------------------
    def _mrtr(self, method: str, params: dict[str, Any], *, input_handler: InputHandler, allowed: set[str], **kwargs) -> dict[str, Any]:
        """Run a request through multi round-trip input exchanges; each retry is a new request with a new ID."""
        attempt = dict(params)
        for _ in range(MAX_MRTR_ROUNDS + 1):
            result = self.request(method, attempt, **kwargs)
            kind = p.result_type(result, allowed)
            if kind != p.RESULT_INPUT_REQUIRED: return result
            requests = result.get("inputRequests") or {}
            if not isinstance(requests, dict): raise McpError("invalid_response", "inputRequests must be an object")
            if not requests and "requestState" not in result: raise McpError("invalid_response", "InputRequiredResult carries neither inputRequests nor requestState")
            attempt = {k: v for k, v in params.items() if k not in ("inputResponses", "requestState")}
            if requests: attempt["inputResponses"] = input_handler(requests)
            if "requestState" in result: attempt["requestState"] = result["requestState"]
        raise McpError("protocol", f"server kept requesting input after {MAX_MRTR_ROUNDS} rounds")

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None, *, tool: dict[str, Any] | None = None, timeout: float | None = None,
                  cancel: threading.Event | None = None, input_handler: InputHandler = deny_all_input,
                  on_progress: Callable[[dict[str, Any]], None] | None = None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        """`meta` carries optional request metadata such as W3C `traceparent` (OpenTelemetry context propagation)."""
        arguments = arguments or {}; extra_headers: dict[str, str] = {}
        if tool is not None:
            try: problems = validate(arguments, tool.get("inputSchema") or {"type": "object"})
            except SchemaError as exc: problems = [str(exc)]
            if problems: raise McpError("invalid_arguments", "arguments do not match the tool inputSchema: " + "; ".join(problems))
            if self.header_mode: extra_headers = p.header_values(p.header_parameters(tool.get("inputSchema") or {}), arguments)
        params: dict[str, Any] = {"name": name, "arguments": arguments}
        token = f"progress-{name}-{time.monotonic_ns()}"
        if on_progress or meta: params["_meta"] = {**({"progressToken": token} if on_progress else {}), **{k: v for k, v in (meta or {}).items() if k in ("traceparent", "tracestate")}}
        def notified(message: dict[str, Any]) -> None:
            if on_progress and message.get("method") == "notifications/progress" and (message.get("params") or {}).get("progressToken") == token: on_progress(message["params"])
        allowed = set(p.CORE_RESULT_TYPES) | ({p.RESULT_TASK} if p.TASKS_EXTENSION in (self.capabilities.get("extensions") or {}) else set())
        started = time.monotonic(); budget = timeout or self.timeout
        result = self._mrtr("tools/call", params, input_handler=input_handler, allowed=allowed, timeout=budget, cancel=cancel,
                            on_notification=notified, extra_headers=extra_headers)
        if p.result_type(result, allowed) == p.RESULT_TASK:
            result = self._await_task(result, deadline=started + budget, cancel=cancel)
        return self._normalize_tool_result(result, tool)

    def _await_task(self, created: dict[str, Any], *, deadline: float, cancel: threading.Event | None) -> dict[str, Any]:
        """Tasks extension: poll tasks/get honoring pollIntervalMs until a terminal status, a cancel or the deadline."""
        task_id = created.get("taskId")
        if not isinstance(task_id, str): raise McpError("invalid_response", "CreateTaskResult without taskId")
        interval = max(0.02, min(float(created.get("pollIntervalMs") or 500) / 1000, 5.0))
        while True:
            if cancel is not None and cancel.is_set():
                self.request("tasks/cancel", {"taskId": task_id}); raise McpError("cancelled", f"task {task_id} cancelled")
            if time.monotonic() > deadline:
                self.request("tasks/cancel", {"taskId": task_id}); raise McpError("timeout", f"task {task_id} did not finish in time; cancellation requested")
            state = self.request("tasks/get", {"taskId": task_id})
            status = state.get("status")
            if status not in p.TASK_STATUSES: raise McpError("invalid_response", f"unknown task status {status!r}")
            if status == "completed":
                result = state.get("result")
                if not isinstance(result, dict): raise McpError("invalid_response", "completed task without result")
                return {**result, "_task": {"taskId": task_id, "status": status}}
            if status == "failed": raise McpError("protocol", f"task {task_id} failed: {(state.get('error') or {}).get('message')}", data=state.get("error"))
            if status == "cancelled": raise McpError("cancelled", f"task {task_id} was cancelled by the server")
            if status == "input_required": raise McpError("input_denied", f"task {task_id} needs input {sorted(state.get('inputRequests') or {})}; no handler authorized")
            time.sleep(interval)

    def _normalize_tool_result(self, result: dict[str, Any], tool: dict[str, Any] | None) -> dict[str, Any]:
        content = result.get("content", [])
        if not isinstance(content, list): raise McpError("invalid_response", "tool result content must be a list")
        text = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
        normalized = {"is_error": bool(result.get("isError")), "content": content, "text": text, "structured": result.get("structuredContent"),
                      "task": result.get("_task")}
        schema = (tool or {}).get("outputSchema")
        if schema is not None and not normalized["is_error"]:
            if normalized["structured"] is None: raise McpError("invalid_response", "tool declares an outputSchema but returned no structuredContent")
            problems = validate(normalized["structured"], schema)
            if problems: raise McpError("invalid_response", "structuredContent violates the tool outputSchema: " + "; ".join(problems[:3]))
        return normalized

    def read_resource(self, uri: str, *, input_handler: InputHandler = deny_all_input) -> list[dict[str, Any]]:
        result = self._mrtr("resources/read", {"uri": uri}, input_handler=input_handler, allowed=set(p.CORE_RESULT_TYPES))
        contents = result.get("contents")
        if not isinstance(contents, list): raise McpError("invalid_response", "resources/read result has no contents list")
        return contents

    def get_prompt(self, name: str, arguments: dict[str, str] | None = None, *, input_handler: InputHandler = deny_all_input) -> dict[str, Any]:
        result = self._mrtr("prompts/get", {"name": name, "arguments": arguments or {}}, input_handler=input_handler, allowed=set(p.CORE_RESULT_TYPES))
        if not isinstance(result.get("messages"), list): raise McpError("invalid_response", "prompts/get result has no messages list")
        return {"description": result.get("description"), "messages": result["messages"]}
