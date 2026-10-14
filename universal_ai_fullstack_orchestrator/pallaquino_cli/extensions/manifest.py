"""Plugin manifest v1 (`plugin.toml`): parsing and validation without importing any plugin code (ADR-0013).

The manifest is data. Parsing it uses `tomllib` only; nothing in this module imports, executes or evaluates the
plugin. Trust is never taken from the manifest: a plugin can only request permissions, and the effective trust state
comes from the project's trust policy (`governance/plugin_trust.json`) bound to the plugin's content hash.
"""
from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .. import __version__
from ..tools.contracts import CAPABILITIES, OPERATIONS
from ..tools.schema import check_schema
from .semver import Version, parse_range, satisfies

MANIFEST_VERSION = 1
MANIFEST_FILE = "plugin.toml"
PLUGIN_TYPES = ["CORE_PLUGIN", "AGENT_PLUGIN", "SKILL_PLUGIN", "TOOL_PLUGIN", "MCP_CONNECTOR", "PROVIDER_ADAPTER", "DATABASE_CONNECTOR",
                "DEVOPS_CONNECTOR", "OBSERVABILITY_PLUGIN", "QUALITY_GATE_PLUGIN", "PROJECT_TEMPLATE_PLUGIN"]
# Types whose runtime contributes tools in 0.5.0; the others are validated and registered, but contribute
# agents, skills, templates or gates through their declared data files only.
TOOL_CONTRIBUTING_TYPES = {"CORE_PLUGIN", "TOOL_PLUGIN", "MCP_CONNECTOR", "DATABASE_CONNECTOR", "DEVOPS_CONNECTOR", "QUALITY_GATE_PLUGIN"}
ISOLATION = {"process", "in_process"}
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,3}$")
ENTRYPOINT = re.compile(r"^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*:[A-Za-z_][\w]*$")
TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_MANIFEST_BYTES = 256 * 1024
HASH_SKIP = {"__pycache__", ".git", ".pytest_cache", ".venv", "venv", "build", "dist"}


class ManifestError(ValueError):
    """The manifest cannot be read or parsed."""


def load_manifest(path: Path) -> dict[str, Any]:
    path = Path(path)
    if path.is_dir(): path = path / MANIFEST_FILE
    try: raw = path.read_bytes()
    except OSError as exc: raise ManifestError(f"cannot read {path}: {exc}") from None
    return parse_manifest(raw, source=str(path))


def parse_manifest(raw: bytes | str, *, source: str = "<memory>") -> dict[str, Any]:
    data = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(data) > MAX_MANIFEST_BYTES: raise ManifestError(f"{source}: manifest exceeds {MAX_MANIFEST_BYTES} bytes")
    try: return tomllib.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc: raise ManifestError(f"{source}: invalid TOML: {exc}") from None


def _str(value: Any, field: str, errors: list[str], *, required: bool = True, max_len: int = 500) -> str | None:
    if value is None:
        if required: errors.append(f"missing {field}")
        return None
    if not isinstance(value, str) or not value.strip(): errors.append(f"{field} must be a non-empty string"); return None
    if len(value) > max_len: errors.append(f"{field} exceeds {max_len} characters")
    return value


def validate_manifest(manifest: dict[str, Any], *, framework_version: str = __version__, base_dir: Path | None = None) -> dict[str, Any]:
    """Return {ok, errors, warnings, compatible, normalized}. `compatible` is False when only the version range fails."""
    errors: list[str] = []; warnings: list[str] = []
    if manifest.get("manifest_version") != MANIFEST_VERSION: errors.append(f"manifest_version must be {MANIFEST_VERSION}")
    plugin = manifest.get("plugin") if isinstance(manifest.get("plugin"), dict) else {}
    if not plugin: errors.append("missing [plugin] table")
    plugin_id = _str(plugin.get("id"), "plugin.id", errors, max_len=64)
    if plugin_id and not PLUGIN_ID.match(plugin_id): errors.append("plugin.id must be 2-4 lowercase dotted segments such as 'acme.text_stats'")
    if plugin_id and plugin_id.split(".")[0] in ("core", "mcp", "plugin", "pallaquino"): errors.append(f"plugin.id prefix {plugin_id.split('.')[0]!r} is reserved")
    for field in ("name", "description", "author"): _str(plugin.get(field), f"plugin.{field}", errors, max_len=2000 if field == "description" else 200)
    version = _str(plugin.get("version"), "plugin.version", errors, max_len=64)
    if version:
        try: Version(version)
        except ValueError as exc: errors.append(str(exc))
    plugin_type = plugin.get("type")
    if plugin_type not in PLUGIN_TYPES: errors.append(f"plugin.type must be one of {PLUGIN_TYPES}")
    compatibility = manifest.get("compatibility") if isinstance(manifest.get("compatibility"), dict) else {}
    compatible = True
    framework_range = _str(compatibility.get("pallaquino"), "compatibility.pallaquino", errors, max_len=100)
    if framework_range:
        try: compatible = satisfies(framework_version, framework_range)
        except ValueError as exc: errors.append(f"compatibility.pallaquino: {exc}"); compatible = False
    runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    entrypoint = runtime.get("entrypoint")
    contributes_tools = plugin_type in TOOL_CONTRIBUTING_TYPES
    if contributes_tools and not (isinstance(entrypoint, str) and ENTRYPOINT.match(entrypoint)):
        errors.append("runtime.entrypoint must be 'package.module:attribute' for a plugin that provides tools")
    isolation = runtime.get("isolation", "process")
    if isolation not in ISOLATION: errors.append(f"runtime.isolation must be one of {sorted(ISOLATION)}")
    if isolation == "in_process" and plugin_type != "CORE_PLUGIN": errors.append("only CORE_PLUGIN may declare in_process isolation; external plugins always run in a separate process")
    timeout = runtime.get("timeout_seconds", 30)
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 600: errors.append("runtime.timeout_seconds must be in (0, 600]")
    source_root = runtime.get("source_root", "src")
    if not isinstance(source_root, str) or Path(source_root).is_absolute() or ".." in Path(source_root).parts: errors.append("runtime.source_root must be a relative path inside the plugin")
    permissions = manifest.get("permissions") if isinstance(manifest.get("permissions"), dict) else {}
    requested = permissions.get("requested", [])
    if not isinstance(requested, list) or any(c not in CAPABILITIES for c in requested): errors.append(f"permissions.requested must list capabilities from {CAPABILITIES}")
    requested = set(requested) if isinstance(requested, list) else set()
    tools = manifest.get("tools", [])
    if not isinstance(tools, list): errors.append("tools must be an array of tables"); tools = []
    if tools and not contributes_tools: errors.append(f"plugin type {plugin_type} cannot expose tools")
    names: set[str] = set(); normalized_tools = []
    for index, tool in enumerate(tools):
        where = f"tools[{index}]"
        if not isinstance(tool, dict): errors.append(f"{where} must be a table"); continue
        name = tool.get("name")
        if not isinstance(name, str) or not TOOL_NAME.match(name): errors.append(f"{where}.name must match {TOOL_NAME.pattern}"); continue
        if name in names: errors.append(f"duplicate tool name {name!r}")
        names.add(name)
        _str(tool.get("description"), f"{where}.description", errors, max_len=2000)
        caps = tool.get("capabilities", [])
        if not isinstance(caps, list) or not caps or any(c not in CAPABILITIES for c in caps): errors.append(f"{where}.capabilities must be a non-empty list from {CAPABILITIES}"); caps = []
        undeclared = sorted(set(caps) - requested)
        if undeclared: errors.append(f"{where} uses capabilities {undeclared} that permissions.requested does not declare")
        operation = tool.get("operation")
        if operation not in OPERATIONS: errors.append(f"{where}.operation must be one of {OPERATIONS}")
        schemas = {}
        for key in ("input_schema", "output_schema"):
            schema = tool.get(key)
            if isinstance(schema, str):  # a JSON file inside the plugin
                schema_path = (base_dir / schema) if base_dir else None
                if schema_path is None or Path(schema).is_absolute() or ".." in Path(schema).parts: errors.append(f"{where}.{key} file must be a relative path inside the plugin"); continue
                try: schema = json.loads(schema_path.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc: errors.append(f"{where}.{key}: cannot load {schema}: {exc}"); continue
            if schema is None:
                if key == "input_schema": errors.append(f"{where}.input_schema is required")
                continue
            problems = check_schema(schema)
            if problems: errors += [f"{where}.{key}: {p}" for p in problems[:5]]
            elif key == "input_schema" and schema.get("type") != "object": errors.append(f"{where}.input_schema must describe an object")
            schemas[key] = schema
        provides = tool.get("provides", [])
        if not isinstance(provides, list) or any(not isinstance(t, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", t) for t in provides):
            errors.append(f"{where}.provides must list lowercase tags"); provides = []
        normalized_tools.append({"name": name, "description": tool.get("description"), "capabilities": sorted(set(caps)), "operation": operation, "provides": sorted(set(provides)),
                                 "input_schema": schemas.get("input_schema"), "output_schema": schemas.get("output_schema"),
                                 "timeout_seconds": tool.get("timeout_seconds", timeout)})
    dependencies = manifest.get("dependencies") if isinstance(manifest.get("dependencies"), dict) else {}
    plugin_deps = dependencies.get("plugins", {})
    if not isinstance(plugin_deps, dict): errors.append("dependencies.plugins must map plugin IDs to version ranges"); plugin_deps = {}
    for dep, spec in plugin_deps.items():
        if not PLUGIN_ID.match(str(dep)): errors.append(f"dependency {dep!r} is not a valid plugin ID")
        try: parse_range(spec)
        except ValueError as exc: errors.append(f"dependency {dep}: {exc}")
    packages = dependencies.get("python_packages", [])
    if not isinstance(packages, list): errors.append("dependencies.python_packages must be a list")
    elif packages: warnings.append(f"declares Python packages {packages}; PALLAQUINO never installs them automatically")
    configuration = manifest.get("configuration") if isinstance(manifest.get("configuration"), dict) else {}
    if "schema" in configuration and check_schema(configuration["schema"]): errors.append("configuration.schema is not a valid JSON Schema")
    if not compatible and framework_range: warnings.append(f"requires PALLAQUINO {framework_range}; running {framework_version}")
    normalized = {"manifest_version": MANIFEST_VERSION, "id": plugin_id, "name": plugin.get("name"), "description": plugin.get("description"),
                  "author": plugin.get("author"), "version": version, "type": plugin_type, "license": plugin.get("license"),
                  "compatibility": {"pallaquino": framework_range, "python": compatibility.get("python")},
                  "runtime": {"entrypoint": entrypoint, "isolation": isolation, "timeout_seconds": timeout, "source_root": source_root},
                  "capabilities": manifest.get("capabilities", {}).get("provides", []) if isinstance(manifest.get("capabilities"), dict) else [],
                  "permissions": sorted(requested), "tools": normalized_tools,
                  "dependencies": {"plugins": dict(plugin_deps), "python_packages": packages if isinstance(packages, list) else []},
                  "configuration": {"schema": configuration.get("schema"), "methods": configuration.get("methods", ["file"])},
                  "trust_requested": (manifest.get("trust") or {}).get("level", "untrusted") if isinstance(manifest.get("trust"), dict) else "untrusted"}
    return {"ok": not errors, "errors": errors, "warnings": warnings, "compatible": compatible, "normalized": normalized}


def content_hash(directory: Path, files: list[Path] | None = None) -> str:
    """SHA-256 over the sorted (relative path, file digest) pairs of a plugin's files; reading is not executing."""
    directory = Path(directory); entries = []
    candidates = files if files is not None else [p for p in directory.rglob("*") if p.is_file()]
    for path in candidates:
        rel = path.relative_to(directory)
        if any(part in HASH_SKIP for part in rel.parts) or path.suffix in (".pyc", ".pyo") or path.is_symlink(): continue
        entries.append(f"{rel.as_posix()}\0{hashlib.sha256(path.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(sorted(entries)).encode("utf-8")).hexdigest()


def import_path_for(plugin_dir: Path, manifest: dict[str, Any]) -> Path:
    """Where the entrypoint's top-level package is importable from: the parent of a manifest that sits inside the
    package itself (the layout that ships in wheels), otherwise `plugin_dir / runtime.source_root`."""
    plugin_dir = Path(plugin_dir); entrypoint = manifest["runtime"].get("entrypoint") or ""
    top = entrypoint.split(":", 1)[0].split(".")[0]
    if top and plugin_dir.name == top: return plugin_dir.parent
    return plugin_dir / manifest["runtime"].get("source_root", "src")
