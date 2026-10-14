"""PALLAQUINO Universal Plugin Manager: registry, lifecycle, trust policy, controlled install/update and isolation.

Lifecycle (PLUGIN_TRANSITIONS): DISCOVERED -> VALIDATED | INCOMPATIBLE -> INSTALLED -> ENABLED -> INITIALIZING ->
ACTIVE | FAILED, with DEGRADED, DISABLED and QUARANTINED. Rules:
- discovering or validating a plugin never runs its code;
- enabling needs a compatible, valid manifest, satisfied plugin dependencies and a trust-policy entry
  (`governance/plugin_trust.json`) whose content hash equals the plugin's current hash and whose allowed
  capabilities cover what the manifest requests; a plugin without such a policy never executes;
- a hash mismatch at activation (tampering) quarantines the plugin;
- external plugins always run in a separate process (`sdk.runner`) with a sanitized environment, and their tools
  are registered from the reviewed manifest after the live catalog is checked against it;
- install copies a local directory or a hash-verified archive into `plugins/<id>/<version>/` without running any
  install script; update keeps the previous version and restores it if the new one fails; uninstall removes only
  the directory this manager created.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import __version__
from ..core import atomic_json
from ..mcp.client import McpClient, McpError
from ..mcp.transports import StdioTransport, TransportError
from ..sdk import runner
from ..tools.contracts import new_tool
from ..tools.registry import ToolContext, tool_result
from .discovery import PROJECT_PLUGIN_DIR, discover
from .manifest import MANIFEST_FILE, ManifestError, content_hash, import_path_for, load_manifest, validate_manifest
from .semver import Version, satisfies

TRUST_POLICY_PATH = "governance/plugin_trust.json"
PLUGIN_TRANSITIONS: dict[str, set[str]] = {
    "DISCOVERED": {"VALIDATED", "INCOMPATIBLE", "QUARANTINED"},
    "VALIDATED": {"INSTALLED", "INCOMPATIBLE", "ENABLED", "QUARANTINED", "VALIDATED"},
    "INCOMPATIBLE": {"VALIDATED", "INCOMPATIBLE"},
    "INSTALLED": {"ENABLED", "DISABLED", "VALIDATED", "INCOMPATIBLE", "QUARANTINED"},
    "DISABLED": {"ENABLED", "VALIDATED", "INCOMPATIBLE", "QUARANTINED", "DISABLED"},
    "ENABLED": {"INITIALIZING", "DISABLED", "QUARANTINED", "VALIDATED"},
    "INITIALIZING": {"ACTIVE", "FAILED", "QUARANTINED"},
    "ACTIVE": {"DEGRADED", "FAILED", "DISABLED", "ENABLED", "QUARANTINED", "INITIALIZING"},  # INITIALIZING: restart in a new process
    "DEGRADED": {"ACTIVE", "FAILED", "DISABLED", "QUARANTINED", "INITIALIZING"},
    "FAILED": {"INITIALIZING", "DISABLED", "QUARANTINED", "ENABLED", "VALIDATED"},
    "QUARANTINED": {"VALIDATED", "DISABLED"},
}
EXECUTABLE_STATES = {"ENABLED", "ACTIVE", "DEGRADED"}
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 5000


class PluginError(RuntimeError):
    """A lifecycle operation was refused; the message explains the controlling rule."""


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_trust_policy(root: Path) -> dict[str, Any]:
    path = Path(root) / TRUST_POLICY_PATH
    if not path.is_file(): return {"schema_version": 1, "plugins": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"schema_version": data.get("schema_version", 1), "plugins": dict(data.get("plugins", {}))}


def trust_status(root: Path, descriptor: dict[str, Any]) -> dict[str, Any]:
    entry = load_trust_policy(root)["plugins"].get(descriptor.get("plugin_id") or "")
    if entry is None: return {"trusted": False, "reason": "no trust policy entry; a plugin without a trust policy never executes"}
    if entry.get("sha256") != descriptor.get("content_hash"):
        return {"trusted": False, "reason": "content hash differs from the approved hash (modified or different build)", "tampered": True}
    requested = set((descriptor.get("manifest") or {}).get("permissions", [])); allowed = set(entry.get("allowed_capabilities", []))
    if not requested <= allowed: return {"trusted": False, "reason": f"manifest requests {sorted(requested - allowed)} beyond the approved capabilities"}
    return {"trusted": True, "reason": f"approved by {entry.get('approved_by')} at {entry.get('approved_at')}", "level": entry.get("trust", "trusted")}


def _safe_extract(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ARCHIVE_ENTRIES: raise PluginError("archive has too many entries")
        if sum(i.file_size for i in infos) > MAX_ARCHIVE_BYTES: raise PluginError("archive expands beyond the size limit")
        for info in infos:
            name = Path(info.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in info.filename or info.filename.startswith("/"): raise PluginError(f"unsafe archive path {info.filename!r}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000: raise PluginError(f"archive contains a symbolic link {info.filename!r}")
        zf.extractall(destination)


class PluginManager:
    def __init__(self, store: Any, root: Path, *, workspace: Path | None = None, extra_paths: list[Path] | None = None, include_environment: bool = True):
        self.store = store; self.root = Path(root); self.workspace = Path(workspace or root); self.extra_paths = extra_paths or []
        self.include_environment = include_environment; self.hosts: dict[str, McpClient] = {}

    # -- registry -------------------------------------------------------------------------------------------
    def _doc(self, plugin_id: str) -> dict[str, Any]:
        doc = self.store.get_platform("plugin", plugin_id)
        if doc is None: raise LookupError(f"plugin {plugin_id!r} is not registered; run `pallaquino plugins discover`")
        return doc

    def _transition(self, doc: dict[str, Any], target: str, reason: str) -> dict[str, Any]:
        current = doc.get("state", "DISCOVERED")
        if target != current and target not in PLUGIN_TRANSITIONS.get(current, set()): raise PluginError(f"plugin transition {current} -> {target} is not allowed")
        doc["state"] = target; doc["updated_at"] = _iso()
        doc.setdefault("history", []).append({"from": current, "to": target, "at": doc["updated_at"], "reason": reason[:300]})
        doc["history"] = doc["history"][-50:]
        self.store.put_platform("plugin", doc["plugin_id"], doc, status=target)
        event = {"VALIDATED": "plugin_validated", "INCOMPATIBLE": "plugin_validated", "ENABLED": "plugin_enabled", "DISABLED": "plugin_disabled", "ACTIVE": "plugin_activated",
                 "FAILED": "plugin_failed", "QUARANTINED": "plugin_quarantined", "INSTALLED": "plugin_installed", "DEGRADED": "plugin_degraded"}.get(target)
        if event: self.store.add_event(event, severity="warning" if target in ("FAILED", "QUARANTINED", "INCOMPATIBLE", "DEGRADED") else "info",
                                       outcome=target.lower(), data={"plugin_id": doc["plugin_id"], "version": doc.get("version"), "reason": reason[:300]})
        return doc

    def discover(self) -> dict[str, Any]:
        found = discover(self.root, extra_paths=self.extra_paths, include_environment=self.include_environment)
        report = []
        for item in found["plugins"]:
            pid = item.get("plugin_id")
            self.store.add_event("plugin_discovered", data={"plugin_id": pid, "source": item["source_kind"], "location": item["location"], "valid": item["validation"]["ok"]})
            if not pid: report.append({"plugin_id": None, "location": item["location"], "state": "INVALID", "errors": item["validation"]["errors"]}); continue
            conflict = pid in found["conflicts"]
            doc = self.store.get_platform("plugin", pid) or {"plugin_id": pid, "state": "DISCOVERED", "created_at": _iso()}
            previous_location = doc.get("location")
            if conflict and previous_location and previous_location != item["location"]:
                report.append({"plugin_id": pid, "location": item["location"], "state": doc["state"], "errors": [f"duplicate plugin ID also at {previous_location}; ignored"]}); continue
            doc.update({k: item.get(k) for k in ("version", "type", "source_kind", "location", "import_path", "manifest", "content_hash", "distribution", "entry_point")})
            doc["validation"] = item["validation"]; doc["conflict"] = found["conflicts"].get(pid)
            target = "VALIDATED" if item["validation"]["ok"] and item["validation"]["compatible"] else "INCOMPATIBLE"
            if doc["state"] in ("DISCOVERED", "VALIDATED", "INCOMPATIBLE") or (target == "INCOMPATIBLE" and doc["state"] in ("INSTALLED", "DISABLED")):
                doc = self._transition(doc, target, "; ".join(item["validation"]["errors"][:3]) or "manifest valid and compatible")
            else: self.store.put_platform("plugin", pid, doc, status=doc["state"])
            report.append({"plugin_id": pid, "version": doc["version"], "source": doc["source_kind"], "state": doc["state"], "errors": item["validation"]["errors"],
                           "warnings": item["validation"]["warnings"], "trust": trust_status(self.root, doc)["reason"]})
        return {"plugins": report, "conflicts": found["conflicts"]}

    def list(self) -> list[dict[str, Any]]:
        return [{"plugin_id": d["plugin_id"], "version": d.get("version"), "type": d.get("type"), "state": d["state"], "source": d.get("source_kind"),
                 "trusted": trust_status(self.root, d)["trusted"], "tools": [t["name"] for t in (d.get("manifest") or {}).get("tools", [])]}
                for d in self.store.list_platform("plugin")]

    def inspect(self, plugin_id: str) -> dict[str, Any]:
        doc = self._doc(plugin_id)
        return {**{k: v for k, v in doc.items() if k != "history"}, "trust": trust_status(self.root, doc), "history": doc.get("history", [])[-10:]}

    def validate(self, plugin_id: str) -> dict[str, Any]:
        doc = self._doc(plugin_id)
        try: manifest = load_manifest(Path(doc["location"]))
        except ManifestError as exc: return {"ok": False, "errors": [str(exc)]}
        report = validate_manifest(manifest, base_dir=Path(doc["location"])); normalized = report.pop("normalized")
        current_hash = content_hash(Path(doc["location"])) if doc.get("source_kind") != "entry_point" else doc.get("content_hash")
        deps = self._dependency_problems(normalized)
        report["errors"] += deps; report["ok"] = report["ok"] and not deps
        report.update({"plugin_id": plugin_id, "content_hash": current_hash, "trust": trust_status(self.root, {**doc, "content_hash": current_hash, "manifest": normalized})})
        return report

    def _dependency_problems(self, manifest: dict[str, Any]) -> list[str]:
        problems = []
        for dep, spec in manifest["dependencies"]["plugins"].items():
            other = self.store.get_platform("plugin", dep)
            if other is None: problems.append(f"missing dependency {dep} {spec}"); continue
            if not satisfies(other.get("version") or "0.0.0", spec): problems.append(f"dependency {dep} {other.get('version')} does not satisfy {spec}")
            elif other["state"] not in EXECUTABLE_STATES: problems.append(f"dependency {dep} is {other['state']}, not enabled")
        return problems

    # -- trust policy (human action) ----------------------------------------------------------------------
    def trust(self, plugin_id: str, *, approved_by: str, capabilities: list[str] | None = None) -> dict[str, Any]:
        doc = self._doc(plugin_id)
        if doc["state"] == "QUARANTINED" and doc.get("content_hash") == (load_trust_policy(self.root)["plugins"].get(plugin_id) or {}).get("sha256"):
            raise PluginError("plugin is quarantined; re-discover it and review the new content before trusting it")
        current_hash = content_hash(Path(doc["location"])) if doc.get("source_kind") != "entry_point" else doc["content_hash"]
        requested = sorted((doc.get("manifest") or {}).get("permissions", []))
        allowed = sorted(capabilities) if capabilities is not None else requested
        policy = load_trust_policy(self.root)
        policy["plugins"][plugin_id] = {"sha256": current_hash, "trust": "trusted", "allowed_capabilities": allowed, "version": doc.get("version"),
                                        "approved_by": approved_by, "approved_at": _iso()}
        atomic_json(self.root / TRUST_POLICY_PATH, policy)
        doc["content_hash"] = current_hash
        if doc["state"] == "QUARANTINED": self._transition(doc, "VALIDATED", f"re-reviewed and trusted by {approved_by}")
        else: self.store.put_platform("plugin", plugin_id, doc, status=doc["state"])
        self.store.add_event("plugin_trusted", data={"plugin_id": plugin_id, "sha256": current_hash, "allowed_capabilities": allowed, "approved_by": approved_by})
        return policy["plugins"][plugin_id]

    def untrust(self, plugin_id: str) -> bool:
        policy = load_trust_policy(self.root); removed = policy["plugins"].pop(plugin_id, None) is not None
        if removed: atomic_json(self.root / TRUST_POLICY_PATH, policy)
        return removed

    # -- enable / disable / activate ----------------------------------------------------------------------
    def enable(self, plugin_id: str) -> dict[str, Any]:
        doc = self._doc(plugin_id)
        if doc["state"] in EXECUTABLE_STATES: return doc
        if doc["state"] in ("INCOMPATIBLE", "QUARANTINED", "DISCOVERED"): raise PluginError(f"plugin {plugin_id} is {doc['state']}; it cannot be enabled")
        report = self.validate(plugin_id)
        if not report["ok"] or not report["compatible"]: raise PluginError(f"plugin {plugin_id} does not validate: {report['errors'][:3]}")
        trust = report["trust"]
        if not trust["trusted"]:
            if trust.get("tampered"): self._transition(doc, "QUARANTINED", trust["reason"])
            raise PluginError(f"plugin {plugin_id} is not trusted: {trust['reason']}")
        return self._transition(doc, "ENABLED", "validated, compatible and trusted")

    def disable(self, plugin_id: str, *, registry: Any = None) -> dict[str, Any]:
        doc = self._doc(plugin_id); self.stop(plugin_id)
        if registry is not None: registry.unregister_source("plugin", plugin_id)
        return self._transition(doc, "DISABLED", "disabled by operator")

    def activate(self, plugin_id: str, registry: Any) -> dict[str, Any]:
        """Start the isolated process, verify the live catalog against the manifest, register the tools."""
        doc = self._doc(plugin_id)
        if doc["state"] not in EXECUTABLE_STATES and doc["state"] != "FAILED": raise PluginError(f"plugin {plugin_id} is {doc['state']}; enable it first")
        trust = trust_status(self.root, {**doc, "content_hash": content_hash(Path(doc["location"])) if doc.get("source_kind") != "entry_point" else doc["content_hash"]})
        if not trust["trusted"]:
            self._transition(doc, "QUARANTINED" if trust.get("tampered") else "FAILED", trust["reason"]); raise PluginError(f"plugin {plugin_id} refused at activation: {trust['reason']}")
        doc = self._transition(doc, "INITIALIZING", "starting isolated process")
        try:
            client = self._start(doc)
            live = {t["name"]: t for t in client.list_tools(use_cache=False)}
            declared = {t["name"]: t for t in doc["manifest"]["tools"]}
            if set(live) != set(declared): raise PluginError(f"live tools {sorted(live)} differ from the manifest {sorted(declared)}")
            for name, spec in declared.items():
                if live[name].get("inputSchema") != spec["input_schema"]: raise PluginError(f"tool {name} serves a schema different from its manifest")
            health = client.read_resource("plugin://health")
            if not json.loads(health[0].get("text") or "{}").get("ok"): raise PluginError(f"health check failed: {health[0].get('text')}")
        except (PluginError, McpError, TransportError, ValueError) as exc:
            self.stop(plugin_id); doc["last_error"] = str(exc)[:500]
            self._transition(doc, "FAILED", str(exc)); raise PluginError(f"plugin {plugin_id} failed to initialize: {exc}") from None
        registry.unregister_source("plugin", plugin_id)
        for spec in doc["manifest"]["tools"]:
            registry.register(self._contract(doc, spec), self._executor(plugin_id, spec["name"]), availability=self._availability(plugin_id))
        doc["last_error"] = None
        return self._transition(doc, "ACTIVE", f"{len(doc['manifest']['tools'])} tools registered")

    @staticmethod
    def _contract(doc: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
        return new_tool(f"plugin.{doc['plugin_id']}.{spec['name']}", description=spec["description"], source={"kind": "plugin", "id": doc["plugin_id"], "trust": "trusted"},
                        input_schema=spec["input_schema"], output_schema=spec["output_schema"], capabilities=spec["capabilities"], operation=spec["operation"],
                        timeout_seconds=float(spec.get("timeout_seconds") or doc["manifest"]["runtime"]["timeout_seconds"]), tool_version=doc["version"],
                        classification="reviewed_manifest", provides=spec.get("provides", []))

    def declared_tools(self) -> list[dict[str, Any]]:
        """Contracts of the tools enabled plugins declare, without starting them (used to scope grants)."""
        return [self._contract(doc, spec) for doc in self.store.list_platform("plugin") if doc["state"] in EXECUTABLE_STATES
                for spec in (doc.get("manifest") or {}).get("tools", [])]

    def _start(self, doc: dict[str, Any]) -> McpClient:
        framework_parent = Path(__file__).resolve().parents[2]
        sandbox = Path(tempfile.mkdtemp(prefix=f"pallaquino-plugin-{doc['plugin_id']}-"))
        workspace = self.workspace if set(doc["manifest"]["permissions"]) & {"FILE_READ", "FILE_WRITE", "GIT_READ", "DATABASE_READ"} else None
        argv = runner.command(framework_parent, Path(doc["location"]), [Path(doc["import_path"])], workspace=workspace)
        client = McpClient(StdioTransport(argv, cwd=str(sandbox)), mode="modern", timeout=float(doc["manifest"]["runtime"]["timeout_seconds"]))
        try: client.connect()
        except McpError as exc:
            stderr = list(client.transport.stderr)[-3:]; client.close()
            raise PluginError(f"isolated process did not start: {exc}; stderr: {stderr}") from None
        self.hosts[doc["plugin_id"]] = client; client.sandbox = sandbox
        return client

    def stop(self, plugin_id: str) -> None:
        client = self.hosts.pop(plugin_id, None)
        if client:
            client.close(); shutil.rmtree(getattr(client, "sandbox", ""), ignore_errors=True)

    def stop_all(self) -> None:
        for plugin_id in list(self.hosts): self.stop(plugin_id)

    def _availability(self, plugin_id: str):
        def probe() -> tuple[bool, str]:
            doc = self.store.get_platform("plugin", plugin_id)
            if doc is None or doc["state"] not in ("ACTIVE", "DEGRADED"): return False, f"plugin {plugin_id} is {doc['state'] if doc else 'unregistered'}"
            client = self.hosts.get(plugin_id)
            if client is None or not client.transport.alive(): return False, f"plugin {plugin_id} process is not running"
            return True, "isolated process running"
        return probe

    def _executor(self, plugin_id: str, name: str):
        def run(arguments: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
            client = self.hosts.get(plugin_id)
            if client is None: raise PluginError(f"plugin {plugin_id} is not running")
            import time as _time
            remaining = max(0.5, (ctx.deadline - _time.monotonic()) if ctx.deadline else 30.0)
            try: result = client.call_tool(name, arguments, timeout=remaining, cancel=ctx.cancel)
            except McpError as exc:
                if exc.kind == "unavailable":
                    doc = self._doc(plugin_id); doc["last_error"] = str(exc)[:300]; self._transition(doc, "DEGRADED", "plugin process exited during a call")
                error = RuntimeError(str(exc)); error.kind = exc.kind; raise error from None
            return tool_result(text=result["text"], structured=result["structured"], is_error=result["is_error"], content=result["content"])
        return run

    def health(self, plugin_id: str) -> dict[str, Any]:
        doc = self._doc(plugin_id); client = self.hosts.get(plugin_id)
        if doc["state"] not in ("ACTIVE", "DEGRADED") or client is None: return {"ok": False, "state": doc["state"], "detail": "not running"}
        try: data = json.loads(client.read_resource("plugin://health")[0].get("text") or "{}")
        except (McpError, ValueError) as exc:
            self._transition(doc, "DEGRADED", f"health check failed: {exc}"); return {"ok": False, "state": "DEGRADED", "detail": str(exc)}
        if doc["state"] == "DEGRADED" and data.get("ok"): self._transition(doc, "ACTIVE", "health restored")
        return {"ok": bool(data.get("ok")), "state": self._doc(plugin_id)["state"], "detail": data}

    # -- install / update / rollback / uninstall ------------------------------------------------------------
    def _stage(self, source: Path, sha256: str | None) -> tuple[Path, dict[str, Any], Path]:
        source = Path(source).resolve(); staging = Path(tempfile.mkdtemp(prefix="pallaquino-install-"))
        if source.is_file():
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            if not sha256: raise PluginError("installing an archive requires --sha256 of the archive")
            if digest != sha256.lower(): raise PluginError(f"archive SHA-256 {digest} does not match the expected {sha256}")
            if source.stat().st_size > MAX_ARCHIVE_BYTES: raise PluginError("archive exceeds the size limit")
            _safe_extract(source, staging / "x")
            roots = [p.parent for p in (staging / "x").rglob(MANIFEST_FILE)]
            if len(roots) != 1: raise PluginError(f"archive must contain exactly one {MANIFEST_FILE}, found {len(roots)}")
            plugin_dir = roots[0]
        elif source.is_dir():
            if not (source / MANIFEST_FILE).is_file(): raise PluginError(f"{source} has no {MANIFEST_FILE}")
            plugin_dir = staging / "x" / source.name  # keep the directory name: a manifest inside its package must stay importable
            shutil.copytree(source, plugin_dir, symlinks=False, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".venv", "venv", "build", "dist", "*.egg-info"))
            if sha256 and content_hash(plugin_dir) != sha256.lower(): raise PluginError("directory content hash does not match the expected --sha256")
        else: raise PluginError(f"{source} does not exist")
        if any(p.is_symlink() for p in plugin_dir.rglob("*")): raise PluginError("plugin sources must not contain symbolic links")
        report = validate_manifest(load_manifest(plugin_dir), base_dir=plugin_dir)
        if not report["ok"]: raise PluginError(f"manifest invalid: {report['errors'][:3]}")
        if not report["compatible"]: raise PluginError(f"plugin requires PALLAQUINO {report['normalized']['compatibility']['pallaquino']}; running {__version__}")
        return plugin_dir, report["normalized"], staging

    def install(self, source: Path, *, sha256: str | None = None) -> dict[str, Any]:
        """Copy (never execute) a plugin into plugins/<id>/<version>/; the result is INSTALLED and still untrusted."""
        plugin_dir, manifest, staging = self._stage(source, sha256)
        try:
            pid, version = manifest["id"], manifest["version"]
            existing = self.store.get_platform("plugin", pid)
            if existing and existing.get("source_kind") != "installed": raise PluginError(f"plugin ID {pid} is already provided by {existing.get('source_kind')}:{existing.get('location')}")
            if existing: raise PluginError(f"plugin {pid} is already installed ({existing.get('version')}); use `plugins update`")
            target_root = self.root / PROJECT_PLUGIN_DIR / pid; target = target_root / version
            if target_root.exists(): raise PluginError(f"{target_root} already exists and is not managed by this registry")
            location = target / plugin_dir.name
            target_root.mkdir(parents=True); shutil.copytree(plugin_dir, location); (target_root / "active").write_text(version, encoding="utf-8")
            doc = {"plugin_id": pid, "state": "VALIDATED", "created_at": _iso(), "source_kind": "installed", "location": str(location),
                   "import_path": str(import_path_for(location, manifest)), "version": version, "type": manifest["type"], "manifest": manifest,
                   "content_hash": content_hash(location), "validation": {"ok": True, "errors": [], "warnings": [], "compatible": True},
                   "owned_paths": [str(target_root)], "versions": [version], "source": str(Path(source).resolve()), "source_sha256": sha256}
            self.store.put_platform("plugin", pid, doc, status="VALIDATED")
            return self._transition(doc, "INSTALLED", f"installed {version} from {Path(source).name}")
        finally: shutil.rmtree(staging, ignore_errors=True)

    def update(self, source: Path, *, sha256: str | None = None, registry: Any = None) -> dict[str, Any]:
        plugin_dir, manifest, staging = self._stage(source, sha256)
        try:
            doc = self._doc(manifest["id"])
            if doc.get("source_kind") != "installed": raise PluginError("only plugins installed by `plugins install` can be updated here")
            if Version(manifest["version"]) <= Version(doc["version"]): raise PluginError(f"update must raise the version above {doc['version']}")
            target_root = Path(doc["owned_paths"][0]); target = target_root / manifest["version"] / plugin_dir.name
            shutil.copytree(plugin_dir, target)
            previous = {k: doc[k] for k in ("version", "location", "import_path", "manifest", "content_hash", "state")}
            was_running = doc["state"] in ("ACTIVE", "DEGRADED")
            if was_running: self.stop(doc["plugin_id"])
            doc.update({"version": manifest["version"], "location": str(target), "import_path": str(import_path_for(target, manifest)), "manifest": manifest,
                        "content_hash": content_hash(target), "previous": previous, "versions": sorted(set(doc.get("versions", [])) | {manifest["version"]}, key=Version)})
            (target_root / "active").write_text(manifest["version"], encoding="utf-8")
            self.store.put_platform("plugin", doc["plugin_id"], doc, status=doc["state"])
            self.store.add_event("plugin_updated", data={"plugin_id": doc["plugin_id"], "from": previous["version"], "to": manifest["version"]})
            if was_running and registry is not None:
                try:
                    if not trust_status(self.root, doc)["trusted"]: raise PluginError("the new version is not trusted yet; approve its hash with `plugins trust`")
                    self._transition(self._doc(doc["plugin_id"]), "ENABLED", "update applied"); self.activate(doc["plugin_id"], registry)
                except PluginError as exc:
                    restored = self.rollback(doc["plugin_id"], registry=registry, reason=f"update failed: {exc}")
                    return {**restored, "update_error": str(exc)}
            return self._doc(doc["plugin_id"])
        finally: shutil.rmtree(staging, ignore_errors=True)

    def rollback(self, plugin_id: str, *, registry: Any = None, reason: str = "rollback requested") -> dict[str, Any]:
        doc = self._doc(plugin_id); previous = doc.get("previous")
        if not previous: raise PluginError(f"plugin {plugin_id} has no previous version to restore")
        self.stop(plugin_id)
        failed_version = doc["version"]
        doc.update({k: previous[k] for k in ("version", "location", "import_path", "manifest", "content_hash")}); doc["previous"] = None
        doc["last_update_error"] = reason
        (Path(doc["owned_paths"][0]) / "active").write_text(doc["version"], encoding="utf-8")
        self.store.put_platform("plugin", plugin_id, doc, status=doc["state"])
        self.store.add_event("plugin_rolled_back", severity="warning", data={"plugin_id": plugin_id, "from": failed_version, "to": doc["version"], "reason": reason[:300]})
        if previous["state"] in ("ACTIVE", "DEGRADED") and registry is not None:
            if doc["state"] not in EXECUTABLE_STATES and doc["state"] != "FAILED": self._transition(doc, "ENABLED", "restoring previous version")
            try: return self.activate(plugin_id, registry)
            except PluginError: return self._doc(plugin_id)
        if doc["state"] in ("INITIALIZING", "FAILED"): self._transition(doc, "DISABLED", reason)
        return self._doc(plugin_id)

    def uninstall(self, plugin_id: str, *, confirm: bool = False, registry: Any = None) -> dict[str, Any]:
        doc = self._doc(plugin_id)
        if not confirm: raise PluginError("uninstalling requires explicit confirmation (--yes)")
        self.stop(plugin_id)
        if registry is not None: registry.unregister_source("plugin", plugin_id)
        removed = []
        if doc.get("source_kind") == "installed":
            managed = (self.root / PROJECT_PLUGIN_DIR).resolve()
            for owned in doc.get("owned_paths", []):
                path = Path(owned).resolve()
                if path.parent != managed or path.name != plugin_id: raise PluginError(f"refusing to delete {path}: not a directory this manager created")
                shutil.rmtree(path); removed.append(str(path))
        note = None if removed else f"{doc.get('source_kind')} plugin: files were not installed by PALLAQUINO and were left untouched (use pip uninstall {doc.get('distribution') or ''})".strip()
        self.store.delete_platform("plugin", plugin_id); self.untrust(plugin_id)
        self.store.add_event("plugin_uninstalled", data={"plugin_id": plugin_id, "removed": removed})
        return {"uninstalled": plugin_id, "removed_paths": removed, "note": note}

    def doctor(self) -> dict[str, Any]:
        rows = []
        for doc in self.store.list_platform("plugin"):
            problems = []
            location = Path(doc["location"]) if doc.get("location") else None
            if location is None or not location.exists(): problems.append("plugin files are missing")
            trust = trust_status(self.root, doc)
            if doc["state"] in EXECUTABLE_STATES and not trust["trusted"]: problems.append(trust["reason"])
            if doc.get("conflict"): problems.append(f"duplicate plugin ID at {doc['conflict']}")
            if doc.get("last_error"): problems.append(f"last error: {doc['last_error']}")
            rows.append({"plugin_id": doc["plugin_id"], "state": doc["state"], "ok": not problems and doc["state"] not in ("FAILED", "QUARANTINED"), "problems": problems})
        return {"ok": all(r["ok"] for r in rows), "plugins": rows, "trust_policy": str(self.root / TRUST_POLICY_PATH)}
