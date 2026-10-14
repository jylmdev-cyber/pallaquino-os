"""Filesystem adapter: list, read, search, stat and (governed) write inside the workspace only.

Confinement: relative paths only, no `..` escape, symlinks are never followed out of the workspace and are never
written through, and walks do not follow directory links. Sensitive files (`.env*`, private keys, credential
stores, `.git/` internals) are refused by `read`/`search`/`write`; reaching them requires the governed
`secrets_access` path. Writes refuse secret-shaped content and support optimistic concurrency (`expected_sha256`).
"""
from __future__ import annotations

import fnmatch
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from ..core import _secret_kinds
from ..tools.contracts import new_tool
from ..tools.registry import ToolContext, tool_result

SOURCE = {"kind": "builtin", "id": "core.filesystem", "trust": "builtin"}
SENSITIVE = re.compile(r"(?i)(^|/)(\.env(\..*)?|.*\.(pem|key|p12|pfx|kdbx)|id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|\.netrc|\.npmrc|\.pypirc|credentials(\.json)?|\.git(/.*)?|.*secrets?\.(json|ya?ml|toml))$")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache", ".mypy_cache"}
MAX_READ = 512 * 1024


def confine(workspace: Path, relative: str, *, allow_root: bool = False) -> Path:
    if not isinstance(relative, str) or (not relative.strip() and not allow_root): raise PermissionError("empty path")
    text = relative.replace("\\", "/").strip() or "."
    candidate = Path(text)
    if candidate.is_absolute() or candidate.drive or text.startswith("/"): raise PermissionError(f"absolute path {relative!r} is outside the workspace")
    root = workspace.resolve(); target = (root / candidate).resolve()
    try: target.relative_to(root)
    except ValueError: raise PermissionError(f"path {relative!r} escapes the workspace (directly or through a symbolic link)") from None
    return target


def _rel(workspace: Path, path: Path) -> str:
    return path.relative_to(workspace.resolve()).as_posix() or "."


def _sensitive(rel: str) -> bool:
    return bool(SENSITIVE.search(rel))


def _walk(root: Path, base: Path, ctx: ToolContext):
    for current, dirs, files in os.walk(base, followlinks=False):
        if ctx.cancel.is_set(): return
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not os.path.islink(os.path.join(current, d)))
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink(): continue
            yield path


def list_files(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    base = confine(ctx.workspace, args.get("path", "."), allow_root=True)
    if not base.is_dir(): raise ValueError(f"{args.get('path')} is not a directory")
    pattern = args.get("pattern", "*"); limit = args.get("max_entries", 500); entries = []; truncated = False
    walker = _walk(ctx.workspace, base, ctx) if args.get("recursive", True) else (p for p in sorted(base.iterdir()) if p.is_file() and not p.is_symlink())
    for path in walker:
        rel = _rel(ctx.workspace, path)
        if not fnmatch.fnmatch(path.name, pattern): continue
        if len(entries) >= limit: truncated = True; break
        entries.append({"path": rel, "bytes": path.stat().st_size, "sensitive": _sensitive(rel)})
    return tool_result(text=f"{len(entries)} files" + (" (truncated)" if truncated else ""), structured={"files": entries, "truncated": truncated})


def read_file(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    target = confine(ctx.workspace, args["path"]); rel = _rel(ctx.workspace, target)
    if _sensitive(rel): raise PermissionError(f"{rel} is a sensitive file; reading it requires the governed secrets_access path")
    if not target.is_file(): raise FileNotFoundError(f"{rel} does not exist")
    limit = min(int(args.get("max_bytes", 200_000)), MAX_READ)
    with target.open("rb") as handle: data = handle.read(limit + 1)
    if b"\0" in data[:8192]: raise ValueError(f"{rel} is binary")
    truncated = len(data) > limit; text = data[:limit].decode("utf-8", errors="replace")
    return tool_result(text=text, structured={"path": rel, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "truncated": truncated, "bytes": target.stat().st_size})


def search(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    base = confine(ctx.workspace, args.get("path", "."), allow_root=True); query = args["query"]
    matcher = re.compile(query) if args.get("regex") else None; glob = args.get("glob", "*"); limit = args.get("max_matches", 200); matches = []
    for path in _walk(ctx.workspace, base, ctx):
        rel = _rel(ctx.workspace, path)
        if _sensitive(rel) or not fnmatch.fnmatch(path.name, glob) or path.stat().st_size > MAX_READ: continue
        try: text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue
        for number, line in enumerate(text.splitlines(), 1):
            if (matcher.search(line) if matcher else query in line):
                matches.append({"path": rel, "line": number, "text": line.strip()[:200]})
                if len(matches) >= limit: return tool_result(text=f"{limit} matches (truncated)", structured={"matches": matches, "truncated": True})
    return tool_result(text=f"{len(matches)} matches", structured={"matches": matches, "truncated": False})


def stat(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    target = confine(ctx.workspace, args["path"], allow_root=True); rel = _rel(ctx.workspace, target)
    if not target.exists(): return tool_result(text=f"{rel} does not exist", structured={"path": rel, "exists": False})
    info = target.stat()
    return tool_result(text=f"{rel}: {info.st_size} bytes", structured={"path": rel, "exists": True, "is_dir": target.is_dir(), "bytes": info.st_size,
                                                                     "modified": int(info.st_mtime), "sensitive": _sensitive(rel)})


def write_file(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    raw = args["path"]; target = confine(ctx.workspace, raw); rel = _rel(ctx.workspace, target)
    lexical = ctx.workspace.resolve() / Path(raw.replace("\\", "/"))
    if any(part.is_symlink() for part in [lexical, *lexical.parents] if part != ctx.workspace.resolve() and ctx.workspace.resolve() in part.parents):
        raise PermissionError(f"refusing to write {rel} through a symbolic link")
    if _sensitive(rel): raise PermissionError(f"{rel} is a sensitive file; writes are refused")
    content = args["content"]
    if any(_secret_kinds(line) for line in content.splitlines()): raise PermissionError(f"refusing to write a secret-shaped value to {rel}")
    current = target.read_text(encoding="utf-8") if target.is_file() else None
    if args.get("create_only") and current is not None: raise FileExistsError(f"{rel} already exists")
    expected = args.get("expected_sha256")
    if expected and (current is None or hashlib.sha256(current.encode("utf-8")).hexdigest() != expected): raise PermissionError(f"write conflict on {rel}: file changed since it was read")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle: handle.write(content)
    os.replace(tmp, target)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return tool_result(text=f"wrote {rel} ({len(content)} chars)", structured={"path": rel, "sha256": digest, "created": current is None})


PATH = {"type": "string", "minLength": 1, "maxLength": 1024}


def tools() -> list[tuple[dict[str, Any], Any]]:
    obj = lambda props, required=(): {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}
    return [
        (new_tool("core.files.list", description="List files under a workspace directory (no symlink traversal).", source=SOURCE, capabilities=["FILE_READ"], operation="READ_ONLY",
                  input_schema=obj({"path": PATH, "pattern": {"type": "string", "maxLength": 200}, "recursive": {"type": "boolean"}, "max_entries": {"type": "integer", "minimum": 1, "maximum": 5000}})), list_files),
        (new_tool("core.files.read", description="Read a text file inside the workspace; sensitive files are refused.", source=SOURCE, capabilities=["FILE_READ"], operation="READ_ONLY",
                  input_schema=obj({"path": PATH, "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_READ}}, ["path"])), read_file),
        (new_tool("core.files.search", description="Search text files for a literal or regular expression.", source=SOURCE, capabilities=["FILE_READ"], operation="READ_ONLY",
                  input_schema=obj({"query": {"type": "string", "minLength": 1, "maxLength": 500}, "path": PATH, "glob": {"type": "string", "maxLength": 200},
                                    "regex": {"type": "boolean"}, "max_matches": {"type": "integer", "minimum": 1, "maximum": 2000}}, ["query"])), search),
        (new_tool("core.files.stat", description="Metadata of a workspace path.", source=SOURCE, capabilities=["FILE_READ"], operation="READ_ONLY",
                  input_schema=obj({"path": PATH}, ["path"])), stat),
        (new_tool("core.files.write", description="Create or replace a text file inside the workspace (governed write).", source=SOURCE, capabilities=["FILE_WRITE"],
                  operation="WRITE_OPERATION", input_schema=obj({"path": PATH, "content": {"type": "string", "maxLength": 1_000_000}, "expected_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                                                                 "create_only": {"type": "boolean"}}, ["path", "content"]), limits={"max_input_bytes": 1_100_000}), write_file),
    ]
