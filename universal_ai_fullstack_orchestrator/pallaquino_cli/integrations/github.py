"""GitHub adapter (read-only): repositories, issues, pull requests, workflow runs.

Disabled until `governance/integrations.json` enables it. Requests go through the network policy (HTTPS, SSRF
guard, address pinning, size limits); the token comes from `credential_ref` (default `env:GITHUB_TOKEN`) and is
sent only to the configured API host. Responses are reduced to a small set of fields. Write operations (comments,
labels, merges) are not offered: they would need GitHub scopes and per-call approvals and are out of scope for 0.5.0.
"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from ..mcp.netpolicy import NetworkPolicy
from ..mcp.transports import http_exchange
from ..tools.contracts import new_tool
from ..tools.registry import ToolContext, tool_result

SOURCE = {"kind": "builtin", "id": "core.github", "trust": "builtin"}
NAME = {"type": "string", "pattern": r"^[A-Za-z0-9_.-]{1,100}$"}
_NAME = re.compile(NAME["pattern"])


class GithubError(RuntimeError):
    kind = "unavailable"


class GithubClient:
    def __init__(self, config: dict[str, Any], resolve_credential):
        self.api = config.get("api_url", "https://api.github.com").rstrip("/")
        self.policy = NetworkPolicy.from_config(config.get("network"))
        self.credential_ref = config.get("credential_ref", "env:GITHUB_TOKEN"); self.resolve = resolve_credential

    def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        url = f"{self.api}{path}" + (f"?{urlencode(query)}" if query else "")
        if urlsplit(url).netloc != urlsplit(self.api).netloc: raise PermissionError("GitHub requests must stay on the configured API host")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "pallaquino", "X-GitHub-Api-Version": "2022-11-28"}
        token = self.resolve(self.credential_ref)
        if token: headers["Authorization"] = f"Bearer {token}"
        status, _, body = http_exchange(url, headers=headers, policy=self.policy)
        if status in (401, 403):
            error = GithubError(f"GitHub answered HTTP {status} (credentials or scopes)"); error.kind = "auth"; raise error
        if status == 404:
            error = GithubError("not found or not visible with the configured credentials"); error.kind = "not_found"; raise error
        if status != 200: raise GithubError(f"GitHub answered HTTP {status}")
        return json.loads(body)


def _repo(args: dict[str, Any]) -> str:
    owner, repo = args["owner"], args["repo"]
    if not (_NAME.match(owner) and _NAME.match(repo)): raise PermissionError("invalid owner or repository name")
    return f"/repos/{owner}/{repo}"


def _issue(i: dict[str, Any]) -> dict[str, Any]:
    return {"number": i.get("number"), "title": i.get("title"), "state": i.get("state"), "user": (i.get("user") or {}).get("login"),
            "labels": [l.get("name") for l in i.get("labels", []) if isinstance(l, dict)], "updated_at": i.get("updated_at"), "is_pull_request": "pull_request" in i}


def tools(config: dict[str, Any], resolve_credential) -> list[tuple[dict[str, Any], Any]]:
    client = GithubClient(config, resolve_credential)
    obj = lambda props, required=(): {"type": "object", "additionalProperties": False, "properties": props, "required": list(required)}
    repo_args = {"owner": NAME, "repo": NAME}
    read = dict(source=SOURCE, capabilities=["NETWORK_READ"], operation="READ_ONLY", timeout_seconds=30)

    def repository(args, ctx: ToolContext):
        data = client.get(_repo(args))
        summary = {k: data.get(k) for k in ("full_name", "description", "default_branch", "visibility", "open_issues_count", "pushed_at")}
        return tool_result(text=f"{summary['full_name']}: {summary['open_issues_count']} open issues", structured=summary)

    def issues(args, ctx: ToolContext):
        items = [_issue(i) for i in client.get(_repo(args) + "/issues", {"state": args.get("state", "open"), "per_page": args.get("limit", 20)})]
        return tool_result(text=f"{len(items)} issues", structured={"issues": items})

    def pulls(args, ctx: ToolContext):
        items = [{"number": p.get("number"), "title": p.get("title"), "state": p.get("state"), "head": (p.get("head") or {}).get("ref"),
                  "base": (p.get("base") or {}).get("ref"), "draft": p.get("draft")} for p in client.get(_repo(args) + "/pulls", {"state": args.get("state", "open"), "per_page": args.get("limit", 20)})]
        return tool_result(text=f"{len(items)} pull requests", structured={"pulls": items})

    def runs(args, ctx: ToolContext):
        data = client.get(_repo(args) + "/actions/runs", {"per_page": args.get("limit", 10)})
        items = [{"id": r.get("id"), "name": r.get("name"), "status": r.get("status"), "conclusion": r.get("conclusion"), "head_sha": r.get("head_sha"),
                  "branch": r.get("head_branch")} for r in data.get("workflow_runs", [])]
        return tool_result(text=f"{len(items)} workflow runs", structured={"runs": items})

    state = {"type": "string", "enum": ["open", "closed", "all"]}; limit = {"type": "integer", "minimum": 1, "maximum": 100}
    return [
        (new_tool("core.github.repository", description="Repository summary.", input_schema=obj(repo_args, ["owner", "repo"]), **read), repository),
        (new_tool("core.github.issues", description="Issues of a repository.", input_schema=obj({**repo_args, "state": state, "limit": limit}, ["owner", "repo"]), **read), issues),
        (new_tool("core.github.pulls", description="Pull requests of a repository.", input_schema=obj({**repo_args, "state": state, "limit": limit}, ["owner", "repo"]), **read), pulls),
        (new_tool("core.github.workflow_runs", description="Recent GitHub Actions runs.", input_schema=obj({**repo_args, "limit": limit}, ["owner", "repo"]), **read), runs),
    ]
