"""Plugin discovery from metadata only: Python entry points (`pallaquino.plugins`) and project plugin directories.

Discovering reads distribution metadata and `plugin.toml` files; it never imports or runs plugin code. Entry
point objects are inspected for their declared value, not loaded. The content hash is computed by reading files.
"""
from __future__ import annotations

import importlib.metadata as md
from pathlib import Path
from typing import Any

from .manifest import MANIFEST_FILE, ManifestError, content_hash, import_path_for, parse_manifest, validate_manifest

ENTRY_POINT_GROUP = "pallaquino.plugins"
PROJECT_PLUGIN_DIR = "plugins"


def _descriptor(manifest_raw: bytes, *, source_kind: str, location: Path, import_path: Path, files: list[Path] | None, extra: dict[str, Any]) -> dict[str, Any]:
    try: manifest = parse_manifest(manifest_raw, source=str(location))
    except ManifestError as exc:
        return {"plugin_id": None, "source_kind": source_kind, "location": str(location), "validation": {"ok": False, "errors": [str(exc)], "warnings": [], "compatible": False}, **extra}
    base = location if location.is_dir() else location.parent
    validation = validate_manifest(manifest, base_dir=base)
    normalized = validation.pop("normalized")
    return {"plugin_id": normalized["id"], "version": normalized["version"], "type": normalized["type"], "source_kind": source_kind, "location": str(base),
            "import_path": str(import_path), "manifest": normalized, "validation": validation, "content_hash": content_hash(base, files), **extra}


def discover_entry_points(paths: list[Path] | None = None) -> list[dict[str, Any]]:
    found = []
    distributions = md.distributions(path=[str(p) for p in paths]) if paths else md.distributions()
    seen: set[tuple[str, str]] = set()
    for dist in distributions:
        points = [ep for ep in dist.entry_points if ep.group == ENTRY_POINT_GROUP]
        if not points: continue
        name = dist.metadata["Name"]; key = (name, dist.version)
        if key in seen: continue
        seen.add(key)
        for ep in points:
            package = ep.value.split(":", 1)[0].split(".")[0]
            manifest_file = next((f for f in dist.files or [] if f.parts[:1] == (package,) and f.name == MANIFEST_FILE), None)
            extra = {"distribution": name, "distribution_version": dist.version, "entry_point": {"name": ep.name, "value": ep.value}}
            if manifest_file is None:
                found.append({"plugin_id": None, "source_kind": "entry_point", "location": name, **extra,
                              "validation": {"ok": False, "errors": [f"distribution {name} declares a pallaquino.plugins entry point but ships no {package}/{MANIFEST_FILE}"], "warnings": [], "compatible": False}})
                continue
            manifest_path = Path(str(dist.locate_file(manifest_file))); package_dir = manifest_path.parent
            files = [Path(str(dist.locate_file(f))) for f in dist.files or [] if f.parts[:1] == (package,)]
            descriptor = _descriptor(manifest_path.read_bytes(), source_kind="entry_point", location=package_dir, import_path=package_dir.parent, files=files, extra=extra)
            if descriptor.get("manifest") and descriptor["manifest"]["runtime"]["entrypoint"] not in (None, ep.value):
                descriptor["validation"]["ok"] = False
                descriptor["validation"]["errors"].append(f"entry point value {ep.value!r} differs from manifest runtime.entrypoint {descriptor['manifest']['runtime']['entrypoint']!r}")
            found.append(descriptor)
    return found


def discover_directories(root: Path) -> list[dict[str, Any]]:
    base = Path(root) / PROJECT_PLUGIN_DIR; found = []
    if not base.is_dir(): return found
    for entry in sorted(p for p in base.iterdir() if p.is_dir() and not p.is_symlink()):
        # A project plugin is either a plugin directory itself or an installed plugin `<id>/<version>/` whose
        # `active` file names the version in use (earlier versions are kept for rollback, not discovered).
        if (entry / MANIFEST_FILE).is_file(): plugin_dir = entry
        elif (entry / "active").is_file():
            version_dir = entry / (entry / "active").read_text(encoding="utf-8").strip()
            if version_dir.parent != entry or not version_dir.is_dir(): continue
            nested = sorted(version_dir.glob(f"*/{MANIFEST_FILE}"))
            plugin_dir = version_dir if (version_dir / MANIFEST_FILE).is_file() else nested[0].parent if len(nested) == 1 else None
            if plugin_dir is None: continue
        else: continue
        manifest_path = plugin_dir / MANIFEST_FILE
        descriptor = _descriptor(manifest_path.read_bytes(), source_kind="directory", location=plugin_dir, import_path=plugin_dir, files=None, extra={})
        if descriptor.get("manifest"):
            descriptor["import_path"] = str(import_path_for(plugin_dir, descriptor["manifest"]))
        found.append(descriptor)
    return found


def discover(root: Path, *, extra_paths: list[Path] | None = None, include_environment: bool = True) -> dict[str, Any]:
    """All plugins visible to this project, with duplicates reported instead of resolved silently."""
    items = discover_directories(root)
    if include_environment: items += discover_entry_points()
    if extra_paths: items += discover_entry_points(extra_paths)
    by_id: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        if item.get("plugin_id"): by_id.setdefault(item["plugin_id"], []).append(item)
    conflicts = {pid: [f"{i['source_kind']}:{i['location']}" for i in group] for pid, group in by_id.items() if len({(i['location'], i.get('version')) for i in group}) > 1}
    return {"plugins": items, "conflicts": conflicts}
