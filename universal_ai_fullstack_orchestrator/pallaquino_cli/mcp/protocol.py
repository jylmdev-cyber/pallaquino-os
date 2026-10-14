"""MCP wire protocol for revision 2026-07-28, shared by the client and the reference server (ADR-0014).

2026-07-28 is stateless: there is no `initialize` handshake and no session. Every request carries its protocol
version and client capabilities in `_meta`, servers implement `server/discover`, every result carries `resultType`,
and server-to-client interactions travel inside results (multi round-trip requests). Legacy revisions
(2025-11-25 and earlier) are reachable only through the explicit compatibility path in the client.

Sources: https://modelcontextprotocol.io/specification/2026-07-28 (basic, versioning, transports, server/*,
patterns/mrtr, patterns/cancellation) and the Tasks extension schema (modelcontextprotocol/ext-tasks).
"""
from __future__ import annotations

import base64
import re
from typing import Any

PROTOCOL_VERSION = "2026-07-28"
MODERN_VERSIONS = ["2026-07-28"]
LEGACY_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26"]
JSONRPC = "2.0"
META_PROTOCOL = "io.modelcontextprotocol/protocolVersion"
META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
META_CLIENT_CAPS = "io.modelcontextprotocol/clientCapabilities"
META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
META_LOG_LEVEL = "io.modelcontextprotocol/logLevel"
TASKS_EXTENSION = "io.modelcontextprotocol/tasks"
RESULT_COMPLETE, RESULT_INPUT_REQUIRED, RESULT_TASK = "complete", "input_required", "task"
CORE_RESULT_TYPES = {RESULT_COMPLETE, RESULT_INPUT_REQUIRED}

# JSON-RPC and MCP error codes (basic/index#error-codes).
PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR = -32700, -32600, -32601, -32602, -32603
HEADER_MISMATCH, MISSING_CLIENT_CAPABILITY, UNSUPPORTED_PROTOCOL_VERSION = -32020, -32021, -32022
LEGACY_RESOURCE_NOT_FOUND = -32002
MODERN_ERROR_CODES = {HEADER_MISMATCH, MISSING_CLIENT_CAPABILITY, UNSUPPORTED_PROTOCOL_VERSION}

METHODS_WITH_NAME = {"tools/call": "name", "prompts/get": "name", "resources/read": "uri"}
MRTR_METHODS = {"tools/call", "prompts/get", "resources/read"}
CACHEABLE_METHODS = {"tools/list", "prompts/list", "resources/list", "resources/read", "resources/templates/list", "server/discover"}
TASK_STATUSES = {"working", "input_required", "completed", "failed", "cancelled"}
TERMINAL_TASK_STATUSES = {"completed", "failed", "cancelled"}
_HEADER_SAFE = re.compile(r"^[\x21-\x7e](?:[\x20-\x7e]*[\x21-\x7e])?$")
_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
SENTINEL_PREFIX, SENTINEL_SUFFIX = "=?base64?", "?="


class ProtocolError(Exception):
    """A JSON-RPC error received from (or to be sent to) the peer."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"{message} (code {code})"); self.code = code; self.message = message; self.data = data

    def to_error(self) -> dict[str, Any]:
        error = {"code": self.code, "message": self.message}
        if self.data is not None: error["data"] = self.data
        return error


def request(request_id: int | str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": JSONRPC, "id": request_id, "method": method}
    if params is not None: message["params"] = params
    return message


def notification(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": JSONRPC, "method": method}
    if params is not None: message["params"] = params
    return message


def response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC, "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None: error["data"] = data
    payload: dict[str, Any] = {"jsonrpc": JSONRPC, "error": error}
    if request_id is not None: payload["id"] = request_id
    return payload


def request_meta(version: str, client_info: dict[str, str], capabilities: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    return {META_PROTOCOL: version, META_CLIENT_INFO: client_info, META_CLIENT_CAPS: capabilities, **(extra or {})}


def with_meta(params: dict[str, Any] | None, meta: dict[str, Any]) -> dict[str, Any]:
    merged = dict(params or {}); merged["_meta"] = {**merged.get("_meta", {}), **meta}
    return merged


def result_type(result: dict[str, Any], allowed: set[str]) -> str:
    """Absent resultType means 'complete' (earlier revisions); an unrecognized value is invalid."""
    value = result.get("resultType", RESULT_COMPLETE)
    if value not in allowed: raise ProtocolError(INVALID_REQUEST, f"unrecognized resultType {value!r}")
    return value


def is_modern_error(payload: Any) -> bool:
    """A recognized modern error identifies a 2026-era server (versioning: backward compatibility)."""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict) or error.get("code") not in MODERN_ERROR_CODES: return False
    if error["code"] == UNSUPPORTED_PROTOCOL_VERSION:
        return isinstance(error.get("data"), dict) and isinstance(error["data"].get("supported"), list)
    return True


def encode_header_value(value: str | int | bool) -> str:
    """Streamable HTTP value encoding: plain visible ASCII, else the `=?base64?...?=` sentinel over UTF-8."""
    text = ("true" if value else "false") if isinstance(value, bool) else str(value)
    plain = bool(_HEADER_SAFE.match(text)) and not (text.startswith(SENTINEL_PREFIX) and text.endswith(SENTINEL_SUFFIX))
    return text if plain else SENTINEL_PREFIX + base64.b64encode(text.encode("utf-8")).decode("ascii") + SENTINEL_SUFFIX


def decode_header_value(value: str) -> str:
    if value.startswith(SENTINEL_PREFIX) and value.endswith(SENTINEL_SUFFIX):
        try: return base64.b64decode(value[len(SENTINEL_PREFIX):-len(SENTINEL_SUFFIX)], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError): raise ProtocolError(HEADER_MISMATCH, "malformed base64 header value") from None
    return value


def _reachable_properties(schema: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], dict[str, Any]]]:
    found = []
    for name, sub in (schema.get("properties") or {}).items():
        if isinstance(sub, dict):
            found.append((prefix + (name,), sub)); found += _reachable_properties(sub, prefix + (name,))
    return found


def _all_annotations(node: Any, path: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    found = []
    if isinstance(node, dict):
        if "x-mcp-header" in node: found.append(path)
        for key, value in node.items(): found += _all_annotations(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node): found += _all_annotations(value, path + (str(index),))
    return found


def header_parameters(input_schema: dict[str, Any]) -> list[tuple[tuple[str, ...], str]]:
    """Validate `x-mcp-header` annotations; return (property path, header name) pairs or raise ValueError."""
    reachable = {path: sub for path, sub in _reachable_properties(input_schema)}
    pairs = []; seen: set[str] = set()
    for location in _all_annotations(input_schema):
        prop_path = tuple(location[i + 1] for i in range(0, len(location), 2)) if all(location[i] == "properties" for i in range(0, len(location), 2)) else None
        if prop_path is None or prop_path not in reachable: raise ValueError(f"x-mcp-header at {'/'.join(location)} is not statically reachable through properties")
        sub = reachable[prop_path]; name = sub["x-mcp-header"]
        if not isinstance(name, str) or not name or not _TOKEN.match(name): raise ValueError(f"invalid x-mcp-header name {name!r}")
        if name.lower() in seen: raise ValueError(f"duplicate x-mcp-header {name!r}")
        if sub.get("type") not in ("string", "integer", "boolean"): raise ValueError(f"x-mcp-header {name!r} must annotate a string, integer or boolean property")
        seen.add(name.lower()); pairs.append((prop_path, name))
    return pairs


def header_values(pairs: list[tuple[tuple[str, ...], str]], arguments: dict[str, Any]) -> dict[str, str]:
    headers = {}
    for path, name in pairs:
        value: Any = arguments
        for key in path: value = value.get(key) if isinstance(value, dict) else None
        if value is None: continue
        if isinstance(value, int) and not isinstance(value, bool) and not -(2**53) + 1 <= value <= 2**53 - 1: raise ValueError(f"{name}: integer outside the safe range")
        headers[f"Mcp-Param-{name}"] = encode_header_value(value)
    return headers
