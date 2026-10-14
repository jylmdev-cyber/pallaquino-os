"""CLI surface of the extensible platform (0.5.0): plugins, plugin (SDK), mcp, tools, permissions.

Exit codes: 0 ok, 1 failure, 2 framework root not found, 3 approval required, 5 permission denied.
Nothing sensitive runs because a command was typed: per-call approvals need `--approve`, grants need
`permissions grant`, enabling a plugin needs a trust-policy entry, and MCP tools need a pinned catalog.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

COMMANDS = {"plugins", "plugin", "mcp", "tools", "permissions"}
EXIT_APPROVAL, EXIT_DENIED = 3, 5
STATUS_EXIT = {"COMPLETED": 0, "FAILED": 1, "APPROVAL_REQUIRED": EXIT_APPROVAL, "DENIED": EXIT_DENIED}


def add_arguments(name: str, item: argparse.ArgumentParser) -> None:
    workspace = lambda: item.add_argument("--workspace", type=Path, help="project directory tools act on (default: the project of --root, else cwd)")
    if name == "plugins":
        item.add_argument("action", choices=["list", "discover", "inspect", "validate", "enable", "disable", "doctor", "install", "update", "rollback",
                                             "uninstall", "trust", "untrust", "health"])
        item.add_argument("target", nargs="?", help="plugin ID, or a plugin directory/archive for install and update")
        item.add_argument("--sha256", help="expected SHA-256 of the archive (required) or of the directory content")
        item.add_argument("--path", action="append", type=Path, default=[], help="extra site directory to discover installed distributions from")
        item.add_argument("--approved-by", help="who approves the trust entry (plugins trust)")
        item.add_argument("--capability", action="append", help="capability to allow (plugins trust; default: what the manifest requests)")
        item.add_argument("--yes", action="store_true", help="confirm uninstall"); workspace()
    if name == "plugin":
        item.add_argument("action", choices=["create", "validate", "test"])
        item.add_argument("target", type=Path, help="plugin directory (create: project directory to scaffold)")
        item.add_argument("--id", dest="plugin_id", help="plugin ID for create, e.g. acme.text_tools"); item.add_argument("--name")
        item.add_argument("--author", default="unknown"); item.add_argument("--type", dest="plugin_type", default="TOOL_PLUGIN")
        item.add_argument("--write", action="store_true", help="write the scaffold (default: dry run)")
    if name == "mcp":
        item.add_argument("action", choices=["servers", "add", "inspect", "test", "tools", "pin", "remove", "doctor", "enable", "disable", "auth", "logout"])
        item.add_argument("server_id", nargs="?")
        item.add_argument("--stdio", nargs=argparse.REMAINDER, help="(add) command that starts a local stdio server; must be last")
        item.add_argument("--url", help="(add) Streamable HTTP endpoint"); item.add_argument("--mode", choices=["auto", "modern", "legacy"], default="auto")
        item.add_argument("--credential-ref", help="(add) env:VAR or vault:<server_id>"); item.add_argument("--issuer", help="(add) authorization server issuer for vault tokens")
        item.add_argument("--allow-http-loopback", action="store_true", help="(add) allow plain http to a loopback server")
        item.add_argument("--classify", action="append", default=[], metavar="TOOL=OPERATION:CAP[,CAP]", help="(add) human classification of a server tool")
        item.add_argument("--trusted", action="store_true", help="(add) mark the server as trusted (annotations are still never trusted)")
        item.add_argument("--timeout", type=float, default=30); item.add_argument("--tool", action="append", help="(pin) pin only these tools")
        item.add_argument("--client-id", help="(auth) pre-registered client ID or Client ID Metadata Document URL"); workspace()
    if name == "tools":
        item.add_argument("action", choices=["list", "inspect", "check", "run", "route", "calls", "metrics"])
        item.add_argument("tool_id", nargs="?"); item.add_argument("--args", default="{}", help="JSON arguments")
        item.add_argument("--approve", action="store_true", help="approve this exact call (per-call approval recorded with its argument digest)")
        item.add_argument("--capability", action="append", default=[], help="(route, list) capability filter")
        item.add_argument("--source", choices=["builtin", "plugin", "mcp"]); item.add_argument("--sensitive", action="store_true")
        item.add_argument("--no-plugins", action="store_true", help="do not start enabled plugins"); workspace()
    if name == "permissions":
        item.add_argument("action", choices=["list", "inspect", "grant", "revoke", "history"])
        item.add_argument("target", nargs="?", help="tool ID or namespace wildcard (grant), grant ID (revoke, inspect)")
        item.add_argument("--principal", default="*", help="agent ID or * (grant)"); item.add_argument("--operation", action="append", help="operation class (grant)")
        item.add_argument("--days", type=float, default=7); item.add_argument("--max-uses", type=int); item.add_argument("--reason", default="")
        item.add_argument("--all", action="store_true", help="include expired, revoked and used entries"); workspace()


def handles(command: str) -> bool:
    return command in COMMANDS


def _workspace(root: Path, args: argparse.Namespace) -> Path:
    explicit = getattr(args, "workspace", None)
    return (explicit or (root.parent if root.name == ".pallaquino" else Path.cwd())).resolve()


def _platform(root: Path, args: argparse.Namespace, **kwargs: Any):
    from .platform import Platform
    return Platform(root, workspace=_workspace(root, args), plugin_paths=getattr(args, "path", None) or None, **kwargs)


def _classification(values: list[str]) -> dict[str, Any]:
    policies = {}
    for value in values:
        tool, _, rest = value.partition("="); operation, _, caps = rest.partition(":")
        if not tool or not operation or not caps: raise ValueError(f"--classify expects TOOL=OPERATION:CAP[,CAP], got {value!r}")
        policies[tool] = {"operation": operation, "capabilities": caps.split(",")}
    return policies


def handle(command: str, args: argparse.Namespace, root: Path) -> tuple[Any, int | None]:
    if command == "plugin": return _plugin_sdk(args)
    platform = _platform(root, args)
    try:
        if command == "plugins": return _plugins(platform, args)
        if command == "mcp": return _mcp(platform, args)
        if command == "tools": return _tools(platform, args)
        return _permissions(platform, args)
    finally: platform.close()


def _need(value: Any, what: str) -> Any:
    if not value: raise ValueError(f"this action needs {what}")
    return value


def _plugin_sdk(args: argparse.Namespace) -> tuple[Any, int | None]:
    if args.action == "create":
        from .sdk.scaffold import create_plugin
        return create_plugin(args.target, _need(args.plugin_id, "--id"), name=args.name, author=args.author, plugin_type=args.plugin_type, write=args.write), None
    from .extensions.manifest import content_hash, load_manifest, validate_manifest
    report = validate_manifest(load_manifest(args.target), base_dir=args.target)
    report["content_hash"] = content_hash(args.target)
    if args.action == "validate": return report, 0 if report["ok"] else 1
    if not report["ok"]: return report, 1
    from .sdk.testing import PluginHarness
    with PluginHarness(args.target) as harness:
        return {"ok": True, "plugin_id": report["normalized"]["id"], "tools": harness.tools(), "health": harness.health(), "isolated": True}, 0


def _plugins(platform, args: argparse.Namespace) -> tuple[Any, int | None]:
    plugins = platform.plugins; action = args.action
    if action == "list": return plugins.list(), None
    if action == "discover": return plugins.discover(), None
    if action == "doctor": report = plugins.doctor(); return report, 0 if report["ok"] else 1
    if action == "install": return plugins.install(Path(_need(args.target, "a plugin directory or archive")), sha256=args.sha256), None
    if action == "update":
        platform.load(); return plugins.update(Path(_need(args.target, "a plugin directory or archive")), sha256=args.sha256, registry=platform.registry), None
    pid = _need(args.target, "a plugin ID")
    if action == "inspect": return plugins.inspect(pid), None
    if action == "validate": report = plugins.validate(pid); return report, 0 if report["ok"] else 1
    if action == "enable": return plugins.enable(pid), None
    if action == "disable": return plugins.disable(pid), None
    if action == "trust": return plugins.trust(pid, approved_by=_need(args.approved_by, "--approved-by"), capabilities=args.capability), None
    if action == "untrust": return {"removed": plugins.untrust(pid)}, None
    if action == "rollback": platform.load(); return plugins.rollback(pid, registry=platform.registry), None
    if action == "uninstall": return plugins.uninstall(pid, confirm=args.yes), None
    platform.load(); report = plugins.health(pid); return report, 0 if report["ok"] else 1


def _mcp(platform, args: argparse.Namespace) -> tuple[Any, int | None]:
    manager = platform.connections; action = args.action
    if action == "servers": return manager.list(), None
    if action == "doctor": report = manager.doctor(); return report, 0 if report["ok"] else 1
    sid = _need(args.server_id, "a server ID")
    if action == "add":
        config: dict[str, Any] = {"connection_id": sid, "mode": args.mode, "timeout_seconds": args.timeout, "trust": "trusted" if args.trusted else "untrusted",
                                  "tool_policies": _classification(args.classify)}
        if args.stdio: config.update({"transport": "stdio", "command": args.stdio})
        elif args.url:
            config.update({"transport": "http", "url": args.url, "network": {"allow_http_loopback": args.allow_http_loopback}})
            if args.credential_ref: config["credential_ref"] = args.credential_ref
            if args.issuer: config["issuer"] = args.issuer
        else: raise ValueError("mcp add needs --url or --stdio <command...>")
        return manager.add(config), None
    if action == "inspect": return {"config": manager.config(sid), "state": next((c for c in manager.list() if c["connection_id"] == sid), None)}, None
    if action == "test": report = manager.test(sid); return report, 0 if report["ok"] else 1
    if action == "tools": return manager.review(sid), None
    if action == "pin": return manager.pin(sid, tools=args.tool), None
    if action == "remove": return manager.remove(sid), None
    if action in ("enable", "disable"): return manager.set_enabled(sid, action == "enable"), None
    from .mcp import auth
    from .mcp.netpolicy import NetworkPolicy
    config = manager.config(sid)
    if config["transport"] != "http": raise ValueError("stdio servers take credentials from the environment (env: references), not OAuth")
    policy = NetworkPolicy.from_config(config.get("network"))
    if action == "logout": return auth.revoke(platform.credentials, sid, config.get("issuer", ""), policy=policy), None
    challenge = None
    try: manager.connect(sid, retries=0)
    except Exception as exc: challenge = (getattr(exc, "headers", None) or {}).get("www-authenticate")
    discovery = auth.discover(config["url"], policy=policy, challenge=challenge)
    result = auth.loopback_authorize(sid, discovery, platform.credentials, client_id=_need(args.client_id, "--client-id"), policy=policy)
    config.update({"credential_ref": result["credential_ref"], "issuer": result["issuer"]}); platform.store.put_platform("connection", sid, config, status="CONFIGURED")
    return result, None


def _tools(platform, args: argparse.Namespace) -> tuple[Any, int | None]:
    platform.load(activate_plugins=not args.no_plugins)
    if args.action == "list":
        rows = [t for t in platform.registry.list(source=args.source) if not args.capability or set(args.capability) <= set(t["capabilities"])]
        return [{"id": t["tool_id"], "category": t["source"]["kind"], "operation": t["operation"], "risk": t["risk"], "approval": t["approval"], "available": t["available"]} for t in rows], None
    if args.action == "route": return platform.route(_need(args.capability, "--capability"), sensitive=args.sensitive), None
    if args.action == "calls": return platform.store.list_tool_calls(tool_id=args.tool_id, limit=50), None
    if args.action == "metrics": return platform.metrics(), None
    tool_id = _need(args.tool_id, "a tool ID")
    if args.action == "inspect": return {**platform.registry.get(tool_id), "available": platform.registry.availability(tool_id)}, None
    arguments = json.loads(args.args)
    if args.action == "check": report = platform.gateway.check(tool_id, arguments); return report, 0 if report["ok"] else 1
    if args.approve: platform.permissions.approve_call(tool_id, arguments, approved_by="cli")
    outcome = platform.gateway.call(tool_id, arguments)
    return outcome, STATUS_EXIT.get(outcome["status"], 1)


def _permissions(platform, args: argparse.Namespace) -> tuple[Any, int | None]:
    gateway = platform.permissions
    if args.action == "list": return gateway.list(include_inactive=args.all), None
    if args.action == "history": return gateway.history(), None
    target = _need(args.target, "a tool pattern or grant ID")
    if args.action == "grant":
        platform.load(activate_plugins=False)
        return gateway.grant(target, principal=args.principal, operations=args.operation, days=args.days, max_uses=args.max_uses, reason=args.reason, registry=platform.registry), None
    if args.action == "revoke": return gateway.revoke(target), None
    for kind in ("grant", "approval"):
        doc = platform.store.get_platform(kind, target)
        if doc: return {"kind": kind, **doc}, None
    raise LookupError(f"no grant or approval {target!r}")
