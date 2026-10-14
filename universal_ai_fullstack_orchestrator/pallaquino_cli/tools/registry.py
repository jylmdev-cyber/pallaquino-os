"""PALLAQUINO Universal Tool Registry: one catalog for builtin, plugin and MCP tools (ADR-0015).

A registered name is not an available tool. Each entry pairs a validated contract with the executor that
implements it and an availability probe (a disconnected MCP server or a disabled plugin makes its tools
unavailable). Tool IDs are namespaced by source (`core.*`, `plugin.<id>.*`, `mcp.<server>.*`) and a second
registration of an existing ID is a conflict, never a silent override.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .contracts import validate_tool

Executor = Callable[[dict[str, Any], "ToolContext"], dict[str, Any]]
Availability = Callable[[], tuple[bool, str]]


class ToolConflict(ValueError):
    """Two sources tried to register the same tool ID."""


class ToolNotFound(LookupError):
    """No tool with this ID is registered."""


@dataclass
class ToolContext:
    """What one execution may know and touch. Never carries credentials: adapters fetch their own by reference."""
    workspace: Path
    project: str
    principal: dict[str, str]
    call_id: str
    execution_id: str | None = None
    task_id: str | None = None
    cancel: threading.Event = field(default_factory=threading.Event)
    deadline: float | None = None
    limits: dict[str, int] = field(default_factory=dict)
    traceparent: str | None = None


def tool_result(*, text: str = "", structured: Any = None, is_error: bool = False, content: list[dict[str, Any]] | None = None, **extra: Any) -> dict[str, Any]:
    return {"is_error": is_error, "text": text, "structured": structured, "content": content if content is not None else ([{"type": "text", "text": text}] if text else []), **extra}


class ToolRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}; self._lock = threading.RLock(); self.rejected: list[dict[str, str]] = []

    def register(self, tool: dict[str, Any], executor: Executor, *, availability: Availability | None = None) -> None:
        errors = validate_tool(tool)
        if errors: raise ValueError("invalid tool contract: " + "; ".join(errors))
        with self._lock:
            existing = self._entries.get(tool["tool_id"])
            if existing and existing["tool"]["source"] != tool["source"]:
                raise ToolConflict(f"tool {tool['tool_id']} is already provided by {existing['tool']['source']['kind']}:{existing['tool']['source'].get('id')}")
            self._entries[tool["tool_id"]] = {"tool": tool, "executor": executor, "availability": availability or (lambda: (True, "available"))}

    def try_register(self, tool: dict[str, Any], executor: Executor, *, availability: Availability | None = None) -> bool:
        try: self.register(tool, executor, availability=availability); return True
        except (ValueError, ToolConflict) as exc:
            self.rejected.append({"tool_id": tool.get("tool_id", "?"), "reason": str(exc)}); return False

    def unregister_source(self, kind: str, source_id: str) -> int:
        with self._lock:
            doomed = [tid for tid, e in self._entries.items() if e["tool"]["source"]["kind"] == kind and e["tool"]["source"].get("id") == source_id]
            for tid in doomed: del self._entries[tid]
        return len(doomed)

    def entry(self, tool_id: str) -> dict[str, Any]:
        with self._lock:
            if tool_id not in self._entries: raise ToolNotFound(f"tool {tool_id!r} is not registered")
            return self._entries[tool_id]

    def get(self, tool_id: str) -> dict[str, Any]:
        return self.entry(tool_id)["tool"]

    def availability(self, tool_id: str) -> tuple[bool, str]:
        try: return self.entry(tool_id)["availability"]()
        except ToolNotFound as exc: return False, str(exc)
        except Exception as exc: return False, f"availability probe failed: {type(exc).__name__}"

    def list(self, *, capability: str | None = None, source: str | None = None, include_unavailable: bool = True) -> list[dict[str, Any]]:
        with self._lock: entries = sorted(self._entries.items())
        rows = []
        for tool_id, entry in entries:
            tool = entry["tool"]
            if capability and capability not in tool["capabilities"]: continue
            if source and tool["source"]["kind"] != source: continue
            available, reason = self.availability(tool_id)
            if not available and not include_unavailable: continue
            rows.append({**tool, "available": available, "availability": reason})
        return rows

    def __contains__(self, tool_id: str) -> bool:
        with self._lock: return tool_id in self._entries

    def __len__(self) -> int:
        with self._lock: return len(self._entries)
