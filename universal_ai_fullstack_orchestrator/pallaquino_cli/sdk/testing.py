"""Plugin test harness: runs a plugin through the same isolated runner and MCP channel PALLAQUINO uses.

    with PluginHarness(Path("src/my_plugin"), workspace=tmp) as harness:
        assert harness.call("my_tool", {"x": 1}) == {...}

The harness checks the manifest first and never trusts the plugin to describe itself: tool names and schemas
are compared with the manifest, as the plugin host does at activation.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .. import __version__
from ..extensions.manifest import import_path_for, load_manifest, validate_manifest
from ..mcp.client import McpClient
from ..mcp.transports import StdioTransport
from . import runner


class PluginHarness:
    def __init__(self, plugin_dir: Path, *, workspace: Path | None = None, config: dict[str, Any] | None = None, timeout: float = 20.0):
        self.plugin_dir = Path(plugin_dir).resolve(); self.workspace = workspace; self.config = config or {}; self.timeout = timeout
        report = validate_manifest(load_manifest(self.plugin_dir), base_dir=self.plugin_dir, framework_version=__version__)
        if not report["ok"]: raise ValueError(f"manifest invalid: {report['errors']}")
        self.manifest = report["normalized"]; self.client: McpClient | None = None; self._sandbox = None; self._live: dict[str, Any] = {}

    def __enter__(self) -> "PluginHarness":
        framework_parent = Path(__file__).resolve().parents[2]
        self._sandbox = tempfile.TemporaryDirectory(prefix="pallaquino-harness-")
        argv = runner.command(framework_parent, self.plugin_dir, [import_path_for(self.plugin_dir, self.manifest)], config=self.config, workspace=self.workspace)
        self.client = McpClient(StdioTransport(argv, cwd=self._sandbox.name), mode="modern", timeout=self.timeout)
        try: self.client.connect()
        except Exception:
            stderr = list(self.client.transport.stderr); self.client.close(); self._sandbox.cleanup()
            raise RuntimeError(f"plugin did not start; stderr: {stderr[-5:]}") from None
        self._live = {t["name"]: t for t in self.client.list_tools(use_cache=False)}
        declared = {t["name"] for t in self.manifest["tools"]}
        if set(self._live) != declared:
            self.__exit__(); raise AssertionError(f"live tools {sorted(self._live)} differ from manifest {sorted(declared)}")
        return self

    def __exit__(self, *exc) -> None:
        if self.client: self.client.close(); self.client = None
        if self._sandbox: self._sandbox.cleanup(); self._sandbox = None

    def tools(self) -> list[str]:
        return sorted(self._live)

    def call_raw(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.client.call_tool(name, arguments, tool=self._live[name])

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.call_raw(name, arguments)
        if result["is_error"]: raise AssertionError(f"{name} failed: {result['text']}")
        return result["structured"]

    def health(self) -> dict[str, Any]:
        return json.loads(self.client.read_resource("plugin://health")[0]["text"])
