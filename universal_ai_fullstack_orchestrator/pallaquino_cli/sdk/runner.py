"""Isolated plugin runner: imports one plugin in its own process and serves it as an MCP 2026-07-28 stdio server.

Started by the plugin host as `python -I -c <bootstrap> --plugin-dir ... --import-path ...`: `-I` ignores
PYTHONPATH, user site-packages and the current directory, so only the framework, the plugin's own import path and
the interpreter's site-packages are importable. Tool schemas come from the reviewed manifest, not from the code;
a plugin that implements tools its manifest does not declare (or misses declared ones) refuses to start.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from pathlib import Path


def _fail(message: str) -> int:
    print(f"pallaquino plugin runner: {message}", file=sys.stderr, flush=True)
    return 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pallaquino-plugin-runner")
    parser.add_argument("--plugin-dir", required=True, type=Path); parser.add_argument("--import-path", action="append", default=[], type=Path)
    parser.add_argument("--config", default="{}"); parser.add_argument("--workspace", type=Path)
    args = parser.parse_args(argv)
    from ..extensions.manifest import load_manifest, validate_manifest
    from ..mcp.server import McpServer, ToolResult, serve_stdio
    from . import Plugin, ToolCall
    report = validate_manifest(load_manifest(args.plugin_dir), base_dir=args.plugin_dir)
    if not report["ok"]: return _fail(f"invalid manifest: {report['errors'][:3]}")
    manifest = report["normalized"]
    for path in reversed(args.import_path): sys.path.insert(0, str(path.resolve()))
    module_name, _, attribute = manifest["runtime"]["entrypoint"].partition(":")
    try: plugin = getattr(importlib.import_module(module_name), attribute)
    except Exception as exc: return _fail(f"cannot import {manifest['runtime']['entrypoint']}: {type(exc).__name__}: {exc}")
    if not isinstance(plugin, Plugin): return _fail(f"{manifest['runtime']['entrypoint']} is not a pallaquino_cli.sdk.Plugin instance")
    declared = {t["name"] for t in manifest["tools"]}; implemented = set(plugin.tools)
    if declared != implemented: return _fail(f"declared tools {sorted(declared)} differ from implemented tools {sorted(implemented)}")
    config = json.loads(args.config); workspace = args.workspace.resolve() if args.workspace else None
    try:
        plugin.configure(config); plugin.initialize({"workspace": str(workspace) if workspace else None, "plugin_id": manifest["id"], "version": manifest["version"]})
    except Exception as exc: return _fail(f"initialization failed: {type(exc).__name__}: {exc}")
    server = McpServer(f"plugin:{manifest['id']}", manifest["version"], instructions=None)
    for spec in manifest["tools"]:
        function = plugin.tools[spec["name"]]
        def handler(arguments, ctx, function=function, name=spec["name"]):
            call = ToolCall(name, workspace, config, ctx.cancelled, lambda done, total=None, message=None: ctx.progress(done, total, message))
            value = function(arguments, call)
            return value if isinstance(value, ToolResult) else ToolResult(content=[{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], structured=value)
        server.tool(spec["name"], spec["description"], spec["input_schema"], output_schema=spec["output_schema"])(handler)
    server.resource("plugin://health", "health", mime_type="application/json")(lambda ctx: json.dumps(plugin.health()))
    try: serve_stdio(server)
    finally: plugin.shutdown()
    return 0


BOOTSTRAP = "import sys; sys.path.insert(0, sys.argv.pop(1)); from pallaquino_cli.sdk.runner import main; raise SystemExit(main(sys.argv[1:]))"


def command(framework_parent: Path, plugin_dir: Path, import_paths: list[Path], *, config: dict | None = None, workspace: Path | None = None) -> list[str]:
    argv = [sys.executable, "-I", "-c", BOOTSTRAP, str(framework_parent), "--plugin-dir", str(plugin_dir), "--config", json.dumps(config or {})]
    for path in import_paths: argv += ["--import-path", str(path)]
    if workspace is not None: argv += ["--workspace", str(workspace)]
    return argv


if __name__ == "__main__":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    raise SystemExit(main())
