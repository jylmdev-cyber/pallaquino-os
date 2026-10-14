"""Git adapter: read-only inspection plus a governed local `stage`. Never pushes, fetches, rewrites or deletes.

Every command is a fixed argv run without a shell; user values are validated (revisions cannot start with `-`)
and paths are confined to the workspace and passed after `--`, which blocks option injection. Interactive prompts
and credential helpers are disabled.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Any

from ..core import redact
from ..tools.contracts import new_tool
from ..tools.registry import ToolContext, tool_result
from .filesystem import PATH, confine

SOURCE = {"kind": "builtin", "id": "core.git", "trust": "builtin"}
REVISION = re.compile(r"^(?!-)[A-Za-z0-9._/~^@{}:-]{1,200}$")
MAX_OUTPUT = 200_000


class GitError(RuntimeError):
    kind = "executor_error"


def _git(ctx: ToolContext, *args: str, timeout: float = 30.0) -> str:
    binary = shutil.which("git")
    if binary is None:
        error = GitError("git is not installed"); error.kind = "not_configured"; raise error
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": "", "LC_ALL": "C"}
    proc = subprocess.run([binary, "-C", str(ctx.workspace), "-c", "core.quotepath=false", "-c", "core.longpaths=true", "-c", "credential.helper=", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, env=env, check=False)
    if proc.returncode != 0: raise GitError(redact(proc.stderr.strip())[:500] or f"git exited {proc.returncode}")
    return proc.stdout[:MAX_OUTPUT]


def status(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    out = _git(ctx, "status", "--porcelain=v1", "--branch", "--untracked-files=normal")
    lines = out.splitlines(); branch = lines[0][3:] if lines and lines[0].startswith("## ") else None; changes = []
    for line in lines[1:] if branch is not None else lines:
        changes.append({"index": line[0], "worktree": line[1], "path": line[3:]})
    clean = not changes
    text = f"branch {branch}: " + ("clean" if clean else f"{len(changes)} changed paths")
    return tool_result(text=text, structured={"branch": branch, "clean": clean, "changes": changes[:500], "total_changes": len(changes)})


def diff(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    argv = ["diff", "--no-color", "--no-ext-diff"]
    if args.get("staged"): argv.append("--cached")
    if args.get("stat_only"): argv.append("--stat")
    if args.get("path"): argv += ["--", confine(ctx.workspace, args["path"], allow_root=True).relative_to(ctx.workspace.resolve()).as_posix() or "."]
    out = _git(ctx, *argv); limit = args.get("max_bytes", 100_000)
    return tool_result(text=redact(out[:limit]), structured={"truncated": len(out) > limit, "bytes": len(out)})


def log(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    argv = ["log", f"--max-count={args.get('max_count', 20)}", "--format=%H%x1f%an%x1f%aI%x1f%s"]
    if args.get("path"): argv += ["--", confine(ctx.workspace, args["path"], allow_root=True).relative_to(ctx.workspace.resolve()).as_posix() or "."]
    commits = [dict(zip(("sha", "author", "date", "subject"), line.split("\x1f"))) for line in _git(ctx, *argv).splitlines() if line]
    return tool_result(text=f"{len(commits)} commits", structured={"commits": commits})


def branches(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    rows = [line.split("\x1f") for line in _git(ctx, "branch", "--list", "--format=%(refname:short)%1f%(HEAD)%1f%(objectname:short)").splitlines() if line]
    items = [{"name": r[0], "current": r[1] == "*", "head": r[2]} for r in rows if len(r) == 3]
    return tool_result(text=f"{len(items)} local branches", structured={"branches": items})


def show(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    rev = args["revision"]
    if not REVISION.match(rev): raise PermissionError(f"invalid revision {rev!r}")
    out = _git(ctx, "show", "--no-color", "--stat", "--format=%H%n%an%n%aI%n%s%n%n%b", rev, "--")
    return tool_result(text=redact(out[:50_000]), structured={"revision": rev, "truncated": len(out) > 50_000})


def stage(args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
    paths = [confine(ctx.workspace, p).relative_to(ctx.workspace.resolve()).as_posix() for p in args["paths"]]
    _git(ctx, "add", "--", *paths)
    return tool_result(text=f"staged {len(paths)} paths", structured={"staged": paths})


def tools() -> list[tuple[dict[str, Any], Any]]:
    obj = lambda props, required=(): {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}
    read = dict(source=SOURCE, capabilities=["GIT_READ"], operation="READ_ONLY")
    return [
        (new_tool("core.git.status", description="Branch and working-tree status (porcelain).", input_schema=obj({}), provides=["git_status"], **read), status),
        (new_tool("core.git.diff", description="Unstaged or staged diff, optionally for one path.", input_schema=obj({"staged": {"type": "boolean"}, "stat_only": {"type": "boolean"},
                  "path": PATH, "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_OUTPUT}}), provides=["git_diff"], **read), diff),
        (new_tool("core.git.log", description="Recent commits.", input_schema=obj({"max_count": {"type": "integer", "minimum": 1, "maximum": 200}, "path": PATH}), provides=["git_history"], **read), log),
        (new_tool("core.git.branches", description="Local branches.", input_schema=obj({}), **read), branches),
        (new_tool("core.git.show", description="One commit with its file statistics.", input_schema=obj({"revision": {"type": "string", "maxLength": 200}}, ["revision"]), **read), show),
        (new_tool("core.git.stage", description="Stage workspace paths (local, reversible with git restore --staged).", source=SOURCE, capabilities=["GIT_WRITE"],
                  operation="WRITE_OPERATION", input_schema=obj({"paths": {"type": "array", "items": PATH, "minItems": 1, "maxItems": 200}}, ["paths"])), stage),
    ]
