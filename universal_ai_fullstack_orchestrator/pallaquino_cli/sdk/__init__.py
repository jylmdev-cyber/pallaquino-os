"""PALLAQUINO Extension Development Kit: the public API a plugin implements (ADR-0013).

A plugin is a `Plugin` subclass instance exposed by the manifest's `runtime.entrypoint`. Its tools are declared
in `plugin.toml` (names, schemas, capabilities, operation class) and implemented with `@plugin.tool("name")`;
the host refuses a plugin whose implementations and declarations differ. Lifecycle: `configure(config)` ->
`initialize(context)` -> tool calls -> `health()` -> `shutdown()`. Plugins run in their own process and talk to
PALLAQUINO over MCP stdio, so they never receive PALLAQUINO's credentials, memory or other plugins' state.

    from pallaquino_cli.sdk import Plugin, ToolCall

    plugin = Plugin()

    @plugin.tool("count_words")
    def count_words(args: dict, call: ToolCall) -> dict:
        return {"words": len(args["text"].split())}
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SDK_VERSION = "1.0.0"
ToolFunction = Callable[[dict[str, Any], "ToolCall"], Any]


@dataclass
class ToolCall:
    """Per-call context handed to a tool implementation."""
    tool: str
    workspace: Path | None
    config: dict[str, Any]
    cancelled: Any
    progress: Callable[[float, float | None, str | None], None] = field(default=lambda *a: None)

    def resolve(self, relative: str) -> Path:
        """Resolve a path inside the workspace the host granted; anything outside raises PermissionError."""
        if self.workspace is None: raise PermissionError("this plugin was not granted a workspace")
        candidate = Path(relative.replace("\\", "/"))
        if candidate.is_absolute() or candidate.drive: raise PermissionError(f"absolute path {relative!r} is outside the workspace")
        target = (self.workspace / candidate).resolve()
        try: target.relative_to(self.workspace.resolve())
        except ValueError: raise PermissionError(f"path {relative!r} escapes the workspace") from None
        return target


class Plugin:
    """Base class. Override the lifecycle hooks you need; register tools with the `tool` decorator."""

    def __init__(self) -> None:
        self.tools: dict[str, ToolFunction] = {}; self.config: dict[str, Any] = {}; self.context: dict[str, Any] = {}; self.initialized = False

    def tool(self, name: str) -> Callable[[ToolFunction], ToolFunction]:
        def register(function: ToolFunction) -> ToolFunction:
            if name in self.tools: raise ValueError(f"tool {name!r} is implemented twice")
            self.tools[name] = function; return function
        return register

    # lifecycle hooks -----------------------------------------------------------------------------------
    def configure(self, config: dict[str, Any]) -> None:
        self.config = dict(config)

    def initialize(self, context: dict[str, Any]) -> None:
        self.context = dict(context); self.initialized = True

    def capabilities(self) -> dict[str, Any]:
        return {"tools": sorted(self.tools), "sdk_version": SDK_VERSION}

    def health(self) -> dict[str, Any]:
        return {"ok": self.initialized, "detail": "initialized" if self.initialized else "not initialized"}

    def shutdown(self) -> None:
        self.initialized = False
