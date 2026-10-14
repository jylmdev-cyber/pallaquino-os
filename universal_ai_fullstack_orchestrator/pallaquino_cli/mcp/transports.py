"""Client transports for MCP 2026-07-28: stdio subprocess and Streamable HTTP (ADR-0014).

Both expose `request(message, *, timeout, cancel, on_notification) -> response` and `close()`. Cancellation follows
the bindings: on stdio the client sends `notifications/cancelled`; on HTTP it closes the request's response stream.
Responses larger than the configured limit are refused, a server that writes non-JSON to stdout is reported, and
stderr is drained into a bounded buffer so a chatty server cannot block or exhaust memory.
"""
from __future__ import annotations

import collections
import http.client
import json
import os
import socket
import ssl
import subprocess
import sys
import threading
import time
from typing import Any, Callable
from urllib.parse import urlsplit

from . import protocol as p
from .netpolicy import NetworkPolicy, check_url

Notify = Callable[[dict[str, Any]], None]
SAFE_ENV_KEYS = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "LANG", "LC_ALL")


class TransportError(RuntimeError):
    """Connection-level failure; `kind` is one of timeout, unavailable, cancelled, too_large, invalid_response, http_status."""

    def __init__(self, kind: str, message: str, *, status: int | None = None, payload: Any = None, headers: dict[str, str] | None = None):
        super().__init__(message); self.kind = kind; self.status = status; self.payload = payload; self.headers = headers or {}


def sanitized_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Only OS essentials plus explicitly configured values reach a server process: no inherited tokens or keys."""
    env = {k: os.environ[k] for k in SAFE_ENV_KEYS if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"; env["PYTHONUTF8"] = "1"
    env.update(extra or {})
    return env


class StdioTransport:
    kind = "stdio"

    def __init__(self, command: list[str], *, cwd: str | None = None, env: dict[str, str] | None = None, max_message_bytes: int = 4 * 1024 * 1024,
                 stderr_lines: int = 200):
        if not command: raise ValueError("stdio transport needs a command")
        argv = [sys.executable if command[0] in ("python", "python3") else command[0], *command[1:]]
        self.command = argv; self.max_message_bytes = max_message_bytes; self.stderr = collections.deque(maxlen=stderr_lines)
        self.pending: dict[Any, dict[str, Any]] = {}; self.lock = threading.Lock(); self.protocol_violations: list[str] = []
        try:
            self.proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
                                         env=sanitized_env(env), text=True, encoding="utf-8", errors="replace", bufsize=1)
        except OSError as exc: raise TransportError("unavailable", f"cannot start MCP server {argv[0]}: {exc}") from None
        self.closed = False
        threading.Thread(target=self._read_stdout, daemon=True, name="mcp-stdio-out").start()
        threading.Thread(target=self._read_stderr, daemon=True, name="mcp-stdio-err").start()

    def _read_stderr(self) -> None:
        for line in self.proc.stderr: self.stderr.append(line.rstrip()[:500])

    def _read_stdout(self) -> None:
        for line in self.proc.stdout:
            if len(line) > self.max_message_bytes: self.protocol_violations.append("message exceeds size limit"); continue
            try: message = json.loads(line)
            except ValueError: self.protocol_violations.append(f"non-JSON output on stdout: {line[:80]!r}"); continue
            if not isinstance(message, dict): continue
            if "id" in message and ("result" in message or "error" in message):
                with self.lock: waiter = self.pending.get(message["id"])
                if waiter: waiter["response"] = message; waiter["event"].set()
            elif "method" in message:
                with self.lock: waiters = list(self.pending.values())
                for waiter in waiters:
                    if waiter["on_notification"]: waiter["on_notification"](message)
        with self.lock:
            for waiter in self.pending.values(): waiter["event"].set()  # server exited: wake every waiter

    def alive(self) -> bool:
        return self.proc.poll() is None

    def send(self, message: dict[str, Any]) -> None:
        if not self.alive(): raise TransportError("unavailable", f"MCP server exited with code {self.proc.returncode}")
        line = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        try:
            with self.lock: self.proc.stdin.write(line + "\n"); self.proc.stdin.flush()
        except (OSError, ValueError) as exc: raise TransportError("unavailable", f"cannot write to MCP server: {exc}") from None

    def request(self, message: dict[str, Any], *, timeout: float = 30.0, cancel: threading.Event | None = None, on_notification: Notify | None = None,
                headers: dict[str, str] | None = None) -> dict[str, Any]:
        waiter = {"event": threading.Event(), "response": None, "on_notification": on_notification}
        with self.lock: self.pending[message["id"]] = waiter
        try:
            self.send(message); deadline = time.monotonic() + timeout
            while not waiter["event"].wait(0.05):
                if cancel is not None and cancel.is_set():
                    self._cancel(message["id"], "cancelled by PALLAQUINO"); raise TransportError("cancelled", "request cancelled")
                if time.monotonic() > deadline:
                    self._cancel(message["id"], "timeout"); raise TransportError("timeout", f"no response within {timeout}s")
            if waiter["response"] is None: raise TransportError("unavailable", f"MCP server exited (code {self.proc.poll()}); stderr: {list(self.stderr)[-3:]}")
            return waiter["response"]
        finally:
            with self.lock: self.pending.pop(message["id"], None)

    def _cancel(self, request_id: Any, reason: str) -> None:
        try: self.send(p.notification("notifications/cancelled", {"requestId": request_id, "reason": reason}))
        except TransportError: pass

    def close(self, grace: float = 2.0) -> None:
        """Close stdin, wait, then terminate and finally kill (the 2026-07-28 shutdown sequence)."""
        if self.closed: return
        self.closed = True
        try: self.proc.stdin.close()
        except OSError: pass
        try: self.proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try: self.proc.wait(timeout=grace)
            except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait(timeout=grace)
        for stream in (self.proc.stdout, self.proc.stderr):
            try: stream.close()
            except OSError: pass


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connect to the address the network policy checked, keeping the hostname for SNI and certificate checks."""

    def __init__(self, host: str, port: int, pinned_ip: str, **kwargs):
        super().__init__(host, port, **kwargs); self.pinned_ip = pinned_ip

    def connect(self):
        sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, port: int, pinned_ip: str, **kwargs):
        super().__init__(host, port, **kwargs); self.pinned_ip = pinned_ip

    def connect(self):
        self.sock = socket.create_connection((self.pinned_ip, self.port), self.timeout)


def http_exchange(url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, policy: NetworkPolicy,
                  timeout: float | None = None, ssl_context: ssl.SSLContext | None = None) -> tuple[int, dict[str, str], bytes]:
    """One HTTP exchange under the network policy: no redirects followed, bounded response size."""
    scheme, host, port, pinned = check_url(url, policy)
    parts = urlsplit(url); target = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    timeout = timeout or policy.timeout_seconds
    conn = (_PinnedHTTPSConnection(host, port, pinned, timeout=timeout, context=ssl_context or ssl.create_default_context()) if scheme == "https"
            else _PinnedHTTPConnection(host, port, pinned, timeout=timeout))
    try:
        conn.request(method, target, body=body, headers=headers or {})
        resp = conn.getresponse(); data = resp.read(policy.max_response_bytes + 1)
        if len(data) > policy.max_response_bytes: raise TransportError("too_large", f"response exceeds {policy.max_response_bytes} bytes")
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, data
    except (OSError, http.client.HTTPException) as exc:
        raise TransportError("timeout" if isinstance(exc, (socket.timeout, TimeoutError)) else "unavailable", f"{method} {url}: {exc}") from None
    finally: conn.close()


class HttpTransport:
    """Streamable HTTP: each JSON-RPC message is its own POST; responses are JSON or a request-scoped SSE stream."""

    kind = "http"

    def __init__(self, url: str, *, policy: NetworkPolicy, auth_header: Callable[[], str | None] | None = None, ssl_context: ssl.SSLContext | None = None):
        check_url(url, policy)  # fail fast on configuration
        self.url = url; self.policy = policy; self.auth_header = auth_header; self.ssl_context = ssl_context; self.session_id: str | None = None

    def alive(self) -> bool:
        return True

    def _connection(self, timeout: float):
        scheme, host, port, pinned = check_url(self.url, self.policy)
        if scheme == "https": return _PinnedHTTPSConnection(host, port, pinned, timeout=timeout, context=self.ssl_context or ssl.create_default_context())
        return _PinnedHTTPConnection(host, port, pinned, timeout=timeout)

    def request(self, message: dict[str, Any], *, timeout: float = 30.0, cancel: threading.Event | None = None, on_notification: Notify | None = None,
                headers: dict[str, str] | None = None) -> dict[str, Any]:
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        all_headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **(headers or {})}
        token = self.auth_header() if self.auth_header else None
        if token: all_headers["Authorization"] = token
        if self.session_id: all_headers["Mcp-Session-Id"] = self.session_id
        conn = self._connection(timeout); done = threading.Event()
        def watch():  # closing the response stream is the HTTP cancellation signal
            while not done.wait(0.05):
                if cancel is not None and cancel.is_set():
                    try: conn.sock and conn.sock.shutdown(socket.SHUT_RDWR)
                    except OSError: pass
                    return
        if cancel is not None: threading.Thread(target=watch, daemon=True).start()
        try:
            path = urlsplit(self.url).path or "/"
            conn.request("POST", path, body=body, headers=all_headers)
            resp = conn.getresponse(); response_headers = {k.lower(): v for k, v in resp.getheaders()}
            if response_headers.get("mcp-session-id"): self.session_id = response_headers["mcp-session-id"]
            if resp.status == 202: return {}
            content_type = response_headers.get("content-type", "")
            if "text/event-stream" in content_type and resp.status == 200: return self._read_stream(resp, message.get("id"), on_notification, cancel)
            data = resp.read(self.policy.max_response_bytes + 1)
            if len(data) > self.policy.max_response_bytes: raise TransportError("too_large", f"response exceeds {self.policy.max_response_bytes} bytes")
            payload = None
            if data:
                try: payload = json.loads(data)
                except ValueError: payload = None
            if resp.status != 200 or not isinstance(payload, dict):
                raise TransportError("http_status", f"HTTP {resp.status} from MCP server", status=resp.status, payload=payload, headers=response_headers)
            return payload
        except TransportError: raise
        except (OSError, http.client.HTTPException) as exc:
            if cancel is not None and cancel.is_set(): raise TransportError("cancelled", "request cancelled") from None
            kind = "timeout" if isinstance(exc, (socket.timeout, TimeoutError)) else "unavailable"
            raise TransportError(kind, f"MCP HTTP request failed: {exc}") from None
        finally:
            done.set(); conn.close()

    def _read_stream(self, resp, request_id: Any, on_notification: Notify | None, cancel: threading.Event | None) -> dict[str, Any]:
        received = 0; data_lines: list[str] = []
        while True:
            if cancel is not None and cancel.is_set(): raise TransportError("cancelled", "request cancelled")
            raw = resp.readline(self.policy.max_response_bytes)
            if not raw: raise TransportError("unavailable", "SSE stream closed before the response; re-issue the request with a new ID")
            received += len(raw)
            if received > self.policy.max_response_bytes: raise TransportError("too_large", "SSE stream exceeds the size limit")
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith(":"): continue  # keep-alive comment
            if line.startswith("data:"): data_lines.append(line[5:].lstrip()); continue
            if line == "" and data_lines:
                try: message = json.loads("\n".join(data_lines))
                except ValueError: raise TransportError("invalid_response", "malformed SSE event data") from None
                data_lines = []
                if isinstance(message, dict) and message.get("id") == request_id and ("result" in message or "error" in message): return message
                if isinstance(message, dict) and "method" in message and on_notification: on_notification(message)

    def close(self) -> None:
        self.session_id = None
