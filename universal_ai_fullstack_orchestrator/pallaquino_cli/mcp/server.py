"""Reference MCP server (revision 2026-07-28) with stdio and Streamable HTTP bindings, stdlib only.

Used by the plugin SDK (an isolated plugin is served to PALLAQUINO as an MCP stdio server), by the offline demo and
by the conformance tests. It implements the stateless core: `server/discover`, tools, resources, prompts,
multi round-trip requests, progress, cancellation, the Tasks extension and the HTTP header validation rules.
`era="legacy"` turns it into a 2025-11-25-style server (initialize handshake, session header) so the client's
backward-compatibility path can be exercised; it is a test double, not a full legacy implementation.
"""
from __future__ import annotations

import base64
import json
import secrets
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, TextIO

from ..tools.schema import SchemaError, check_schema, validate
from . import protocol as p

MAX_MESSAGE_BYTES = 4 * 1024 * 1024
PAGE_SIZE = 50


@dataclass
class InputRequired:
    """Returned by a handler that needs more input; the client retries with `inputResponses` (MRTR)."""
    input_requests: dict[str, Any] | None = None
    request_state: str | None = None


@dataclass
class ToolResult:
    content: list[dict[str, Any]] = field(default_factory=list)
    structured: Any = None
    is_error: bool = False


@dataclass
class CallContext:
    request_id: Any
    meta: dict[str, Any]
    input_responses: dict[str, Any]
    request_state: str | None
    cancelled: threading.Event
    notify: Callable[[dict[str, Any]], None]

    @property
    def client_capabilities(self) -> dict[str, Any]:
        return self.meta.get(p.META_CLIENT_CAPS) or {}

    def progress(self, progress: float, total: float | None = None, message: str | None = None) -> None:
        token = self.meta.get("progressToken")
        if token is None: return
        params: dict[str, Any] = {"progressToken": token, "progress": progress}
        if total is not None: params["total"] = total
        if message: params["message"] = message
        self.notify(p.notification("notifications/progress", params))


@dataclass
class _Tool:
    name: str; description: str; input_schema: dict[str, Any]; output_schema: dict[str, Any] | None
    handler: Callable[[dict[str, Any], CallContext], Any]; annotations: dict[str, Any] | None; title: str | None; task: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class McpServer:
    def __init__(self, name: str, version: str = "1.0.0", *, instructions: str | None = None, supported_versions: list[str] | None = None,
                 era: str = "modern", ttl_ms: int = 60_000, task_poll_ms: int = 50):
        if era not in ("modern", "legacy"): raise ValueError("era must be modern or legacy")
        self.info = {"name": name, "version": version}; self.instructions = instructions; self.era = era
        self.supported = supported_versions or list(p.MODERN_VERSIONS); self.ttl_ms = ttl_ms; self.task_poll_ms = task_poll_ms
        self.tools: dict[str, _Tool] = {}; self.resources: dict[str, dict[str, Any]] = {}; self.prompts: dict[str, dict[str, Any]] = {}
        self.tasks: dict[str, dict[str, Any]] = {}; self._tasks_lock = threading.Lock(); self.calls: list[dict[str, Any]] = []
        self.legacy_sessions: set[str] = set(); self._legacy_initialized = False

    # -- registration -----------------------------------------------------------------------------------
    def tool(self, name: str, description: str, input_schema: dict[str, Any] | None = None, *, output_schema: dict[str, Any] | None = None,
             annotations: dict[str, Any] | None = None, title: str | None = None, task: bool = False):
        schema = input_schema or {"type": "object", "additionalProperties": False}
        problems = check_schema(schema) + (check_schema(output_schema) if output_schema is not None else [])
        if problems: raise ValueError(f"tool {name}: {problems}")
        def register(handler):
            self.tools[name] = _Tool(name, description, schema, output_schema, handler, annotations, title, task); return handler
        return register

    def resource(self, uri: str, name: str, *, mime_type: str = "text/plain", description: str | None = None):
        def register(reader):
            self.resources[uri] = {"uri": uri, "name": name, "mimeType": mime_type, "description": description, "reader": reader}; return reader
        return register

    def prompt(self, name: str, description: str, arguments: list[dict[str, Any]] | None = None):
        def register(render):
            self.prompts[name] = {"name": name, "description": description, "arguments": arguments or [], "render": render}; return render
        return register

    def capabilities(self) -> dict[str, Any]:
        caps: dict[str, Any] = {}
        if self.tools: caps["tools"] = {"listChanged": False}
        if self.resources: caps["resources"] = {}
        if self.prompts: caps["prompts"] = {"listChanged": False}
        if any(t.task for t in self.tools.values()): caps["extensions"] = {p.TASKS_EXTENSION: {}}
        return caps

    # -- dispatch ---------------------------------------------------------------------------------------
    def handle(self, message: Any, *, notify: Callable[[dict[str, Any]], None] = lambda m: None, cancelled: threading.Event | None = None,
               session: str | None = None) -> dict[str, Any] | None:
        """Process one JSON-RPC message; return the response (None for notifications)."""
        if not isinstance(message, dict) or message.get("jsonrpc") != p.JSONRPC or not isinstance(message.get("method"), str):
            return p.error_response(message.get("id") if isinstance(message, dict) else None, p.INVALID_REQUEST, "invalid JSON-RPC request")
        request_id = message.get("id"); method = message["method"]; params = message.get("params") or {}
        if "id" not in message: return None  # notifications (notifications/cancelled is handled by the transport)
        if request_id is None or isinstance(request_id, bool) or not isinstance(request_id, (int, str)):
            return p.error_response(None, p.INVALID_REQUEST, "request id must be a string or an integer")
        if not isinstance(params, dict): return p.error_response(request_id, p.INVALID_PARAMS, "params must be an object")
        try:
            if self.era == "legacy": return p.response(request_id, self._legacy(method, params, session))
            meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
            version = meta.get(p.META_PROTOCOL)
            if method == "initialize":
                raise p.ProtocolError(p.METHOD_NOT_FOUND, f"initialize is not supported; this server speaks {self.supported}")
            if version is None or p.META_CLIENT_CAPS not in meta:
                raise p.ProtocolError(p.INVALID_PARAMS, "request _meta must carry protocolVersion and clientCapabilities")
            if version not in self.supported:
                raise p.ProtocolError(p.UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", {"supported": self.supported, "requested": version})
            self.calls.append({"method": method, "name": params.get("name") or params.get("uri")})
            result = self._dispatch(method, params, meta, request_id, notify, cancelled or threading.Event())
            result.setdefault("resultType", p.RESULT_COMPLETE)
            result.setdefault("_meta", {})[p.META_SERVER_INFO] = self.info
            return p.response(request_id, result)
        except p.ProtocolError as exc:
            return p.error_response(request_id, exc.code, exc.message, exc.data)
        except Exception as exc:  # a handler bug becomes an internal error, never a crash of the server loop
            return p.error_response(request_id, p.INTERNAL_ERROR, f"internal error: {type(exc).__name__}")

    def _page(self, items: list[dict[str, Any]], params: dict[str, Any], key: str) -> dict[str, Any]:
        start = 0
        if params.get("cursor"):
            try: start = int(base64.urlsafe_b64decode(params["cursor"].encode()).decode())
            except (ValueError, TypeError): raise p.ProtocolError(p.INVALID_PARAMS, "invalid cursor") from None
        page = items[start:start + PAGE_SIZE]
        result: dict[str, Any] = {key: page, "ttlMs": self.ttl_ms, "cacheScope": "private"}
        if start + PAGE_SIZE < len(items): result["nextCursor"] = base64.urlsafe_b64encode(str(start + PAGE_SIZE).encode()).decode()
        return result

    def _tool_listing(self, tool: _Tool) -> dict[str, Any]:
        item: dict[str, Any] = {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
        if tool.title: item["title"] = tool.title
        if tool.output_schema is not None: item["outputSchema"] = tool.output_schema
        if tool.annotations: item["annotations"] = tool.annotations
        return item

    def _dispatch(self, method: str, params: dict[str, Any], meta: dict[str, Any], request_id: Any, notify, cancelled) -> dict[str, Any]:
        if method == "server/discover":
            result: dict[str, Any] = {"supportedVersions": self.supported, "capabilities": self.capabilities(), "ttlMs": self.ttl_ms, "cacheScope": "private"}
            if self.instructions: result["instructions"] = self.instructions
            return result
        if method == "tools/list": return self._page([self._tool_listing(self.tools[n]) for n in sorted(self.tools)], params, "tools")
        if method == "resources/list":
            return self._page([{k: v for k, v in r.items() if k != "reader" and v is not None} for _, r in sorted(self.resources.items())], params, "resources")
        if method == "resources/templates/list": return self._page([], params, "resourceTemplates")
        if method == "prompts/list":
            return self._page([{k: v for k, v in pr.items() if k != "render"} for _, pr in sorted(self.prompts.items())], params, "prompts")
        ctx = CallContext(request_id, meta, params.get("inputResponses") or {}, params.get("requestState"), cancelled, notify)
        if method == "tools/call": return self._call_tool(params, ctx)
        if method == "resources/read":
            uri = params.get("uri"); resource = self.resources.get(uri) if isinstance(uri, str) else None
            if resource is None: raise p.ProtocolError(p.INVALID_PARAMS, "Resource not found", {"uri": uri})
            value = resource["reader"](ctx)
            if isinstance(value, InputRequired): return self._input_required(value, ctx)
            return {"contents": [{"uri": uri, "mimeType": resource["mimeType"], "text": str(value)}], "ttlMs": self.ttl_ms, "cacheScope": "private"}
        if method == "prompts/get":
            prompt = self.prompts.get(params.get("name"))
            if prompt is None: raise p.ProtocolError(p.INVALID_PARAMS, f"unknown prompt {params.get('name')!r}")
            arguments = params.get("arguments") or {}
            missing = [a["name"] for a in prompt["arguments"] if a.get("required") and a["name"] not in arguments]
            if missing: raise p.ProtocolError(p.INVALID_PARAMS, f"missing required prompt arguments {missing}")
            value = prompt["render"](arguments, ctx)
            if isinstance(value, InputRequired): return self._input_required(value, ctx)
            return {"description": prompt["description"], "messages": value}
        if method in ("tasks/get", "tasks/cancel", "tasks/update"): return self._task_op(method, params)
        raise p.ProtocolError(p.METHOD_NOT_FOUND, f"method {method!r} not found")

    def _input_required(self, value: InputRequired, ctx: CallContext) -> dict[str, Any]:
        if not value.input_requests and value.request_state is None: raise ValueError("InputRequired needs input_requests or request_state")
        needed = sorted({r.get("method", "").split("/")[0] for r in (value.input_requests or {}).values()} - {""})
        caps = {"elicitation": "elicitation", "sampling": "sampling", "roots": "roots"}
        missing = [caps[n] for n in needed if n in caps and caps[n] not in ctx.client_capabilities]
        if missing: raise p.ProtocolError(p.MISSING_CLIENT_CAPABILITY, "missing required client capability", {"requiredCapabilities": missing})
        result: dict[str, Any] = {"resultType": p.RESULT_INPUT_REQUIRED}
        if value.input_requests: result["inputRequests"] = value.input_requests
        if value.request_state is not None: result["requestState"] = value.request_state
        return result

    def _run_tool(self, tool: _Tool, arguments: dict[str, Any], ctx: CallContext) -> dict[str, Any]:
        try: value = tool.handler(arguments, ctx)
        except Exception as exc:  # tool execution error: actionable text, never a traceback
            return {"content": [{"type": "text", "text": f"tool failed: {type(exc).__name__}: {exc}"[:2000]}], "isError": True}
        if isinstance(value, InputRequired): return self._input_required(value, ctx)
        if not isinstance(value, ToolResult):
            value = ToolResult(content=[{"type": "text", "text": json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value}],
                               structured=value if not isinstance(value, str) else None)
        result: dict[str, Any] = {"content": value.content, "isError": value.is_error}
        if value.structured is not None:
            if tool.output_schema is not None and not value.is_error and validate(value.structured, tool.output_schema):
                raise p.ProtocolError(p.INTERNAL_ERROR, "tool produced output that violates its outputSchema")
            result["structuredContent"] = value.structured
        return result

    def _call_tool(self, params: dict[str, Any], ctx: CallContext) -> dict[str, Any]:
        tool = self.tools.get(params.get("name"))
        if tool is None: raise p.ProtocolError(p.INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict): raise p.ProtocolError(p.INVALID_PARAMS, "arguments must be an object")
        try: problems = validate(arguments, tool.input_schema)
        except SchemaError as exc: problems = [str(exc)]
        if problems: return {"content": [{"type": "text", "text": "invalid arguments: " + "; ".join(problems)}], "isError": True}
        if tool.task and p.TASKS_EXTENSION in (ctx.client_capabilities.get("extensions") or {}): return self._start_task(tool, arguments, ctx)
        return self._run_tool(tool, arguments, ctx)

    # -- Tasks extension ----------------------------------------------------------------------------------
    def _start_task(self, tool: _Tool, arguments: dict[str, Any], ctx: CallContext) -> dict[str, Any]:
        task_id = f"task-{uuid.uuid4().hex}"; stamp = _now(); cancel = threading.Event()
        record = {"taskId": task_id, "status": "working", "createdAt": stamp, "lastUpdatedAt": stamp, "ttlMs": 600_000, "pollIntervalMs": self.task_poll_ms}
        task_ctx = CallContext(ctx.request_id, ctx.meta, {}, None, cancel, lambda m: None)
        with self._tasks_lock: self.tasks[task_id] = {"task": record, "cancel": cancel}
        def work():
            outcome = self._run_tool(tool, arguments, task_ctx)
            with self._tasks_lock:
                current = self.tasks[task_id]["task"]
                if current["status"] == "cancelled": return
                current.update({"status": "completed", "result": {**outcome, "resultType": p.RESULT_COMPLETE}, "lastUpdatedAt": _now()})
        threading.Thread(target=work, daemon=True, name=f"mcp-task-{task_id}").start()
        return {"resultType": p.RESULT_TASK, **record}

    def _task_op(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._tasks_lock:
            entry = self.tasks.get(params.get("taskId"))
            if entry is None: raise p.ProtocolError(p.INVALID_PARAMS, f"unknown task {params.get('taskId')!r}")
            if method == "tasks/get": return dict(entry["task"])
            if method == "tasks/cancel":
                if entry["task"]["status"] not in p.TERMINAL_TASK_STATUSES:
                    entry["cancel"].set(); entry["task"].update({"status": "cancelled", "lastUpdatedAt": _now()})
                return {}
            return {}  # tasks/update: no tool of the reference server asks for mid-flight input

    # -- legacy era (test double) ---------------------------------------------------------------------------
    def _legacy(self, method: str, params: dict[str, Any], session: str | None) -> dict[str, Any]:
        if method == "initialize":
            self._legacy_initialized = True
            return {"protocolVersion": p.LEGACY_VERSIONS[0], "capabilities": self.capabilities(), "serverInfo": self.info}
        if method == "server/discover" or not self._legacy_initialized: raise p.ProtocolError(p.METHOD_NOT_FOUND, f"Method not found: {method}")
        if method == "tools/list": return {"tools": [self._tool_listing(self.tools[n]) for n in sorted(self.tools)]}
        if method == "tools/call":
            tool = self.tools.get(params.get("name"))
            if tool is None: raise p.ProtocolError(p.INVALID_PARAMS, f"Unknown tool: {params.get('name')}")
            ctx = CallContext(None, {}, {}, None, threading.Event(), lambda m: None)
            return self._run_tool(tool, params.get("arguments") or {}, ctx)
        raise p.ProtocolError(p.METHOD_NOT_FOUND, f"Method not found: {method}")


# -- stdio binding -------------------------------------------------------------------------------------------
def serve_stdio(server: McpServer, stdin: TextIO | None = None, stdout: TextIO | None = None, *, workers: int = 4) -> None:
    """Newline-delimited JSON-RPC on stdin/stdout until stdin closes; requests run concurrently so a
    `notifications/cancelled` can reach an in-flight request. Nothing but MCP messages is written to stdout."""
    stdin = stdin or sys.stdin; stdout = stdout or sys.stdout; write_lock = threading.Lock(); inflight: dict[Any, threading.Event] = {}
    def write(message: dict[str, Any]) -> None:
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        with write_lock: stdout.write(line + "\n"); stdout.flush()
    def run(message: dict[str, Any], cancel: threading.Event) -> None:
        reply = server.handle(message, notify=write, cancelled=cancel)
        inflight.pop(message.get("id"), None)
        if reply is not None and not cancel.is_set(): write(reply)  # MUST NOT answer a cancelled request
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="mcp-stdio") as pool:
        for line in stdin:
            if not line.strip(): continue
            if len(line) > MAX_MESSAGE_BYTES: write(p.error_response(None, p.INVALID_REQUEST, "message too large")); continue
            try: message = json.loads(line)
            except ValueError: write(p.error_response(None, p.PARSE_ERROR, "parse error")); continue
            if isinstance(message, dict) and message.get("method") == "notifications/cancelled":
                event = inflight.get((message.get("params") or {}).get("requestId"))
                if event: event.set()
                continue
            cancel = threading.Event()
            if isinstance(message, dict) and "id" in message: inflight[message["id"]] = cancel
            pool.submit(run, message, cancel)


# -- Streamable HTTP binding ---------------------------------------------------------------------------------
class McpHttpServer:
    """Single MCP endpoint (POST) bound to 127.0.0.1 by default, with Origin validation, the 2026-07-28 header
    rules and optional bearer authentication (401/403 with `WWW-Authenticate` and protected resource metadata)."""

    def __init__(self, server: McpServer, *, host: str = "127.0.0.1", port: int = 0, path: str = "/mcp", allowed_origins: set[str] | None = None,
                 auth: Callable[[str | None], tuple[bool, str | None]] | None = None, resource_metadata: dict[str, Any] | None = None,
                 response_delay: float = 0.0, max_body: int = MAX_MESSAGE_BYTES):
        self.server = server; self.path = path; self.allowed_origins = allowed_origins or set(); self.auth = auth
        self.resource_metadata = resource_metadata; self.response_delay = response_delay; self.max_body = max_body
        self.requests: list[dict[str, Any]] = []; outer = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *args): pass
            def do_GET(self):
                if self.path.startswith("/.well-known/oauth-protected-resource") and outer.resource_metadata is not None:
                    return outer._send_json(self, 200, outer.resource_metadata)
                outer._send_json(self, 405, None)
            def do_DELETE(self): outer._send_json(self, 405, None)
            def do_POST(self): outer._post(self)
        self.httpd = ThreadingHTTPServer((host, port), Handler); self.httpd.daemon_threads = True
        default_error = self.httpd.handle_error
        def handle_error(request, client_address):  # a client closing its stream is a cancellation, not a server error
            if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)): default_error(request, client_address)
        self.httpd.handle_error = handle_error
        self.thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}{self.path}"

    def start(self) -> "McpHttpServer":
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True, name="mcp-http"); self.thread.start(); return self

    def stop(self) -> None:
        self.httpd.shutdown(); self.httpd.server_close()

    def __enter__(self): return self.start()
    def __exit__(self, *exc): self.stop()

    def _send_json(self, handler, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        handler.send_response(status)
        for key, value in (headers or {}).items(): handler.send_header(key, value)
        if payload is not None: handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body))); handler.end_headers()
        if body: handler.wfile.write(body)

    def _post(self, handler) -> None:
        if handler.path.split("?")[0] != self.path: return self._send_json(handler, 404, None)
        origin = handler.headers.get("Origin")
        if origin is not None and origin not in self.allowed_origins:
            return self._send_json(handler, 403, p.error_response(None, p.INVALID_REQUEST, "invalid Origin"))
        if self.auth is not None:
            ok, challenge = self.auth(handler.headers.get("Authorization"))
            if not ok:
                status = 403 if challenge and "insufficient_scope" in challenge else 401
                return self._send_json(handler, status, None, {"WWW-Authenticate": challenge or "Bearer"})
        length = int(handler.headers.get("Content-Length") or 0)
        if length > self.max_body: return self._send_json(handler, 413, None)
        try: message = json.loads(handler.rfile.read(length) or b"null")
        except ValueError: return self._send_json(handler, 400, p.error_response(None, p.PARSE_ERROR, "parse error"))
        headers = {k.lower(): v for k, v in handler.headers.items()}
        self.requests.append({"headers": headers, "body": message})
        session = None
        if self.server.era == "legacy":
            session = headers.get("mcp-session-id")
            if isinstance(message, dict) and message.get("method") == "initialize": session = secrets.token_hex(8); self.server.legacy_sessions.add(session)
            elif session not in self.server.legacy_sessions: return self._send_json(handler, 400, {"error": "missing or unknown session"})
        else:
            problem = self._validate_headers(headers, message)
            if problem: return self._send_json(handler, 400, p.error_response(message.get("id") if isinstance(message, dict) else None, p.HEADER_MISMATCH, problem))
        if isinstance(message, dict) and "id" not in message: return self._send_json(handler, 202, None)
        accept = headers.get("accept", "")
        wants_stream = "text/event-stream" in accept and isinstance(message, dict) and ((message.get("params") or {}).get("_meta") or {}).get("progressToken") is not None
        if self.response_delay: threading.Event().wait(self.response_delay)
        if wants_stream: return self._stream(handler, message)
        reply = self.server.handle(message, session=session)
        self._send_json(handler, self._status_for(reply), reply, {"Mcp-Session-Id": session} if session and self.server.era == "legacy" else None)

    def _status_for(self, reply: dict[str, Any] | None) -> int:
        """404 for an unknown method, 400 for version, capability, header and missing-_meta failures, else 200."""
        if self.server.era != "modern" or not reply or "error" not in reply: return 200
        code = reply["error"]["code"]
        if code == p.METHOD_NOT_FOUND: return 404
        if code in p.MODERN_ERROR_CODES: return 400
        if code == p.INVALID_PARAMS and "_meta" in reply["error"]["message"]: return 400
        return 200

    def _validate_headers(self, headers: dict[str, str], message: Any) -> str | None:
        if not isinstance(message, dict): return None
        if "id" not in message: return None  # header requirements for notification POSTs are not defined by 2026-07-28
        version = headers.get("mcp-protocol-version"); method = headers.get("mcp-method")
        if version is None or method is None: return "missing required MCP-Protocol-Version or Mcp-Method header"
        params = message.get("params") or {}; meta = params.get("_meta") or {}
        if meta.get(p.META_PROTOCOL) is not None and version != meta[p.META_PROTOCOL]: return f"MCP-Protocol-Version header {version!r} does not match the body"
        # a body without the required _meta is malformed (-32602, answered by handle()), not a header mismatch
        if method != message.get("method"): return f"Mcp-Method header {method!r} does not match body method"
        field_name = p.METHODS_WITH_NAME.get(message.get("method"))
        if field_name:
            raw = headers.get("mcp-name")
            if raw is None: return "missing required Mcp-Name header"
            try: name = p.decode_header_value(raw)
            except p.ProtocolError as exc: return exc.message
            if name != params.get(field_name): return f"Mcp-Name header value {name!r} does not match body value {params.get(field_name)!r}"
        if message.get("method") == "tools/call":
            tool = self.server.tools.get(params.get("name"))
            if tool is not None:
                try: pairs = p.header_parameters(tool.input_schema)
                except ValueError: pairs = []
                expected = p.header_values(pairs, params.get("arguments") or {})
                for key, value in expected.items():
                    sent = headers.get(key.lower())
                    if sent is None: return f"missing required {key} header"
                    if p.decode_header_value(sent) != p.decode_header_value(value): return f"{key} header does not match the body"
        return None

    def _stream(self, handler, message: dict[str, Any]) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream"); handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Accel-Buffering", "no"); handler.send_header("Connection", "close"); handler.end_headers()
        cancelled = threading.Event(); lock = threading.Lock()
        def emit(payload: dict[str, Any]) -> None:
            with lock:
                try: handler.wfile.write(b"data: " + json.dumps(payload).encode("utf-8") + b"\n\n"); handler.wfile.flush()
                except OSError: cancelled.set()  # closing the response stream is the HTTP cancellation signal
        reply = self.server.handle(message, notify=emit, cancelled=cancelled)
        if reply is not None and not cancelled.is_set(): emit(reply)
        handler.close_connection = True
