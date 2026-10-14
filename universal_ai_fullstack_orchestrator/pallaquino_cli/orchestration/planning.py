"""PALLAQUINO Task Planning Engine: intent_result -> validated plan (DAG of tasks). Planning never executes.

Steps come from a fixed library composed per intent and detected technology. Each task is assigned either to the
pipeline-stage role declared in pipeline_definition.json or to the router's best in-domain agent, and is checked
against that agent's contract v2: every tool the task needs must be allowed, governed tools force human approval,
and the agent's risk_limit must cover the task risk.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts import load_contract
from ..core import RISK_ORDER, read_json
from .intent import analyze_intent
from .models import CONTRACT_VERSION, TASK_TRANSITIONS, canonical_digest, new_id, new_task, utc_now
from .routing import detect_domains, select_agents

TOKENS_PER_CONTEXT_WEIGHT = 1500  # planning estimate only; real usage comes from providers
FRONTEND_TECH = {"nuxt", "react", "nextjs", "angular", "flutter", "react_native", "swiftui"}
BACKEND_TECH = {"django", "laravel", "spring_boot", "dotnet", "nodejs", "python", "go", "php", "java", "kotlin"}
DATABASE_TECH = {"postgresql", "mysql", "sql_server", "mongodb", "redis", "clickhouse", "opensearch"}

STEPS: dict[str, dict[str, Any]] = {
    "discover": {"title": "Analyze the existing project structure", "caps": ["analyze", "map"], "domains": ["repository"], "stage": "REPOSITORY_ANALYSIS",
                 "executor": {"kind": "internal", "op": "repository_analysis"}, "tools": ["read_repository"], "minutes": 2, "read_only": True,
                 "acceptance": ["repository map lists languages, entrypoints, tests and configuration"]},
    "explore": {"title": "Trace the runtime paths relevant to the request", "caps": ["trace"], "domains": ["repository"], "tools": ["read_repository", "search_repository"],
                "minutes": 10, "read_only": True, "acceptance": ["every claim cites a file and line"]},
    "design": {"title": "Design the change: components, contracts and risks", "caps": ["design"], "domains": ["architecture"], "tools": ["read_repository"], "minutes": 15,
               "read_only": True, "acceptance": ["design names the affected modules, contracts and failure paths"]},
    "decision": {"title": "Compare options and record an ADR", "caps": ["compare", "adr"], "domains": ["architecture"], "tools": ["read_repository", "write_files"], "minutes": 15,
                 "resources": ["docs/adr"], "acceptance": ["ADR records options, trade-offs and the reversal path"]},
    "data_model": {"title": "Define the data model and migrations", "caps": ["schema", "migration"], "domains": ["database"], "tools": ["read_repository", "write_files"], "minutes": 20,
                   "resources": ["migrations"], "acceptance": ["migration is reversible or staged expand/contract"]},
    "migration_safety": {"title": "Review migration safety and rollback", "caps": ["migration", "rollback"], "domains": ["database"], "tools": ["read_repository"], "minutes": 10,
                         "read_only": True, "acceptance": ["rollback path is documented and rehearsable"]},
    "backend": {"title": "Implement services and endpoints", "caps": ["code"], "domains": ["api"], "tools": ["read_repository", "write_files"], "minutes": 30,
                "resources": ["@backend"], "acceptance": ["server-side behaviour is implemented with explicit error handling"]},
    "frontend": {"title": "Implement the user interface", "caps": ["code"], "domains": ["web", "ux"], "tools": ["read_repository", "write_files"], "minutes": 30,
                 "resources": ["@frontend"], "acceptance": ["UI is accessible and consumes the documented API"]},
    "reproduce": {"title": "Reproduce the defect with a failing test", "caps": ["test"], "domains": ["testing"], "tools": ["read_repository", "write_files", "run_tests"], "minutes": 15,
                  "resources": ["@tests"], "acceptance": ["a test fails because of the reported defect"]},
    "fix": {"title": "Fix the defect", "caps": ["code"], "domains": ["code"], "tools": ["read_repository", "write_files"], "minutes": 20, "resources": ["@backend"],
            "acceptance": ["the reproducing test passes"]},
    "characterize": {"title": "Pin current behaviour with characterization tests", "caps": ["test"], "domains": ["testing"], "tools": ["read_repository", "write_files", "run_tests"],
                     "minutes": 15, "resources": ["@tests"], "acceptance": ["characterization tests pass before the refactor"]},
    "refactor": {"title": "Refactor without changing behaviour", "caps": ["code"], "domains": ["code"], "tools": ["read_repository", "write_files"], "minutes": 25, "resources": ["@backend"],
                 "acceptance": ["characterization tests still pass"]},
    "profile": {"title": "Measure the baseline and locate bottlenecks", "caps": ["profile", "benchmark"], "domains": ["performance"], "tools": ["read_repository", "run_tests"], "minutes": 15,
                "read_only": True, "acceptance": ["baseline is reproducible"]},
    "optimize": {"title": "Optimize the measured bottleneck", "caps": ["code"], "domains": ["performance", "code"], "tools": ["read_repository", "write_files"], "minutes": 25,
                 "resources": ["@backend"], "acceptance": ["benchmark improves against the recorded baseline"]},
    "tests": {"title": "Write automated tests for the change", "caps": ["test"], "domains": ["testing"], "tools": ["read_repository", "write_files"], "minutes": 20,
              "resources": ["@tests"], "acceptance": ["new tests fail without the change and pass with it"]},
    "verify": {"title": "Run the project's test suite", "caps": ["test", "validate"], "domains": ["testing"], "stage": "TEST", "executor": {"kind": "command", "command": None},
               "tools": ["run_tests"], "minutes": 5, "read_only": True, "acceptance": ["test command exits 0"]},
    "security_review": {"title": "Security review of the change", "caps": ["threat_model", "review"], "domains": ["security"], "tools": ["read_repository", "run_security_scan"],
                        "minutes": 15, "read_only": True, "review": True, "acceptance": ["findings are ranked by severity with reproducible locations"]},
    "code_review": {"title": "Independent code review", "caps": ["review"], "domains": ["code"], "stage": "CODE_REVIEW", "tools": ["read_repository"], "minutes": 10,
                    "read_only": True, "review": True, "acceptance": ["every finding has a failure scenario or is a labelled suggestion"]},
    "docs": {"title": "Update documentation", "caps": ["write"], "domains": ["documentation"], "stage": "DOCUMENTATION", "tools": ["read_repository", "write_files"], "minutes": 10,
             "resources": ["README.md", "docs"], "acceptance": ["documentation matches implemented behaviour"]},
    "pipeline": {"title": "Automate build and test in CI", "caps": ["build"], "domains": ["deployment"], "tools": ["read_repository", "write_files"], "minutes": 20,
                 "resources": [".github/workflows"], "acceptance": ["the pipeline definition is valid and runs the test suite"]},
    "deploy": {"title": "Deploy (requires human approval)", "caps": ["deploy"], "domains": ["deployment"], "tools": ["read_repository", "deploy"], "minutes": 10,
               "acceptance": ["deployment has an approved scope and rollback path"]},
    "migration_apply": {"title": "Apply the migration (requires human approval)", "caps": ["migration"], "domains": ["database"], "tools": ["read_repository", "database_migration_apply"],
                        "minutes": 10, "acceptance": ["migration applied with backup and rollback evidence"]},
    "release_prep": {"title": "Prepare release notes and version", "caps": ["version", "manifest"], "domains": ["release"], "tools": ["read_repository", "write_files"], "minutes": 15,
                     "resources": ["CHANGELOG.md"], "acceptance": ["changelog and version follow the versioning policy"]},
    # 0.5.0 tool steps: executed through the tool execution gateway, never by the model.
    "git_inspect": {"title": "Inspect Git state and recent history", "caps": ["analyze"], "domains": ["repository"], "tools": ["read_repository"], "minutes": 2,
                    "read_only": True, "executor": {"kind": "tool", "requirements": [
                        {"provides": "git_status", "capabilities": ["GIT_READ"], "arguments": {}},
                        {"provides": "git_history", "capabilities": ["GIT_READ"], "arguments": {"max_count": 10}}]},
                    "acceptance": ["branch, working-tree state and recent commits come from git itself"]},
    "quality_scan": {"title": "Scan the codebase for quality issues", "caps": ["analyze"], "domains": ["repository"], "tools": ["read_repository"], "minutes": 3,
                     "read_only": True, "executor": {"kind": "tool", "requirements": [
                         {"provides": "quality_scan", "capabilities": ["FILE_READ"], "arguments": {"root": "{workspace}"},
                          "fallback": {"provides": "code_search", "capabilities": ["FILE_READ"], "arguments": {"query": "TODO", "max_matches": 200}}}]},
                     "acceptance": ["every reported issue names a file and comes from a tool call"]},
    "report": {"title": "Consolidate findings into a technical report", "caps": ["write"], "domains": ["documentation"], "tools": ["read_repository"], "minutes": 2,
               "read_only": True, "executor": {"kind": "internal", "op": "technical_report"},
               "acceptance": ["every report section cites the tool call or task that produced it"]},
    "release_publish": {"title": "Publish the release (requires human approval)", "caps": ["version"], "domains": ["release"], "tools": ["read_repository", "release_publish"],
                        "minutes": 5, "acceptance": ["release published only with explicit approval"]},
}
ORDER = list(STEPS)
DEPS: dict[str, list[str]] = {
    "explore": ["discover"], "design": ["discover", "explore"], "decision": ["design"], "data_model": ["design"], "migration_safety": ["data_model"],
    "backend": ["design", "data_model"], "frontend": ["design", "backend"], "reproduce": ["discover"], "fix": ["reproduce"],
    "characterize": ["discover"], "refactor": ["characterize"], "profile": ["discover"], "optimize": ["profile"],
    "tests": ["backend", "frontend", "fix", "refactor", "optimize", "data_model"],
    "verify": ["tests", "fix", "refactor", "optimize", "backend", "frontend", "data_model", "pipeline", "reproduce", "characterize"],
    "security_review": ["backend", "frontend", "data_model", "fix"], "code_review": ["verify", "security_review"], "docs": ["code_review"],
    "pipeline": ["discover"], "deploy": ["verify", "pipeline", "code_review"], "migration_apply": ["migration_safety", "verify"],
    "release_prep": ["verify"], "release_publish": ["release_prep", "code_review"],
    "git_inspect": ["discover"], "quality_scan": ["discover"], "report": ["discover", "explore", "git_inspect", "quality_scan"],
}
TOOL_STEP_TERMS = {"git_inspect": ["git", "commit", "branch", "rama"], "quality_scan": ["quality", "calidad", "lint", "code smell"],
                   "report": ["report", "informe", "reporte"]}


def _steps_for(intent: dict[str, Any]) -> list[str]:
    names = {i["intent"] for i in intent["intents"]}; techs = set(intent["technologies"]); high = RISK_ORDER[intent["risk"]["level"]] >= RISK_ORDER["HIGH"]
    steps = {"discover"}
    frontend = bool(names & {"FRONTEND_DEVELOPMENT"} or techs & FRONTEND_TECH)
    backend = bool(names & {"API_DEVELOPMENT"} or techs & (BACKEND_TECH | DATABASE_TECH)) or not frontend
    if names & {"FEATURE_IMPLEMENTATION", "API_DEVELOPMENT", "FRONTEND_DEVELOPMENT"}:
        steps |= {"design", "tests", "verify", "code_review", "docs"}
        if techs & DATABASE_TECH or "DATABASE_MIGRATION" in names: steps.add("data_model")
        if backend and names & {"FEATURE_IMPLEMENTATION", "API_DEVELOPMENT"}: steps.add("backend")
        if frontend: steps.add("frontend")
    if "BUG_FIX" in names: steps |= {"reproduce", "fix", "verify", "code_review"}
    if "CODE_REFACTOR" in names: steps |= {"characterize", "refactor", "verify", "code_review"}
    if "SECURITY_AUDIT" in names: steps.add("security_review")
    if "TEST_GENERATION" in names: steps |= {"tests", "verify"}
    if "DATABASE_MIGRATION" in names: steps |= {"design", "data_model", "migration_safety", "verify", "migration_apply"}
    if "DOCUMENTATION" in names: steps.add("docs")
    if "PERFORMANCE_OPTIMIZATION" in names: steps |= {"profile", "optimize", "verify", "code_review"}
    if "DEVOPS_AUTOMATION" in names:
        steps |= {"pipeline", "verify"}
        if "deploy" in intent["permissions_required"]["approval_required"]: steps |= {"deploy", "code_review"}
    if "RELEASE_PREPARATION" in names: steps |= {"verify", "release_prep", "release_publish", "code_review"}
    if "ARCHITECTURE_DESIGN" in names: steps |= {"design", "decision"}
    if "PROJECT_DISCOVERY" in names:
        text = intent.get("request", "").casefold()
        tool_steps = {step for step, terms in TOOL_STEP_TERMS.items() if any(term in text for term in terms)}
        if tool_steps & {"git_inspect", "quality_scan"}: steps |= tool_steps  # tools explore; no simulated exploration is planned
        elif len(names) == 1: steps.add("explore")
    if high and steps & {"backend", "frontend", "data_model", "fix"}: steps.add("security_review")
    return [s for s in ORDER if s in steps]


def detect_test_command(workspace: Path | None) -> list[str] | None:
    if workspace is None or not workspace.is_dir(): return None
    if (workspace / "tests").is_dir() and any((workspace / "tests").glob("test*.py")): return ["python", "-m", "unittest", "discover", "-s", "tests"]
    package = workspace / "package.json"
    if package.is_file():
        import json
        try:
            if "test" in json.loads(package.read_text(encoding="utf-8")).get("scripts", {}): return ["npm", "test"]
        except ValueError: return None
    return None


def _stage_agents(root: Path) -> dict[str, list[str]]:
    return {s["id"]: s.get("agents", []) for s in read_json(root / "pipeline" / "pipeline_definition.json")["stages"]}


def resolve_tools(task: dict[str, Any], platform: Any) -> None:
    """Pick concrete registered tools for a tool task with the tool router (permissions checked for the task's agent)."""
    grants = set(task["permissions"]["allowed"]) | set(task["permissions"]["approval_required"]); resolved = []
    for requirement in task["executor"]["requirements"]:
        choice = None
        for option in (requirement, requirement.get("fallback")):
            if not option: continue
            routed = platform.route(option["capabilities"], provides=option.get("provides"), principal={"kind": "agent", "id": task["agent"] or "?"}, agent_grants=grants)
            if routed["selected"]:
                best = routed["selected"][0]
                choice = {"tool_id": best["tool_id"], "arguments": option.get("arguments", {}), "provides": option.get("provides"), "fallback": option is not requirement,
                          "needs_approval": best["needs_approval"], "reasons": best["reasons"], "excluded": routed["excluded"][:5]}
                break
        resolved.append(choice or {"tool_id": None, "provides": requirement.get("provides"), "missing": True})
    task["executor"]["resolved"] = resolved


def build_plan(root: Path, request: str, *, workspace: Path | None = None, intent: dict[str, Any] | None = None, history: Any = None, platform: Any = None) -> dict[str, Any]:
    intent = intent or analyze_intent(root, request, workspace=workspace)
    risk = intent["risk"]["level"]; techs = intent["technologies"]; extra_domains = detect_domains(root, request)
    stage_agents = _stage_agents(root); keys = _steps_for(intent); test_command = detect_test_command(workspace)
    tasks: list[dict[str, Any]] = []; ids = {key: f"T{index + 1:02d}" for index, key in enumerate(keys)}
    for key in keys:
        spec = STEPS[key]
        deps = [ids[d] for d in DEPS.get(key, []) if d in ids] or ([ids["discover"]] if key != "discover" else [])
        executor = dict(spec.get("executor") or {"kind": "agent"})
        if key == "verify": executor["command"] = test_command
        task_risk = "LOW" if spec.get("read_only") and key in ("discover", "explore") else risk
        resources = [r.replace("@", "area:") if r.startswith("@") else r for r in spec.get("resources", [])]
        task = new_task(ids[key], spec["title"], objective=f"{spec['title']} for: {request}", intent=intent["primary_intent"], capabilities=spec["caps"],
                        domains=sorted(set(spec["domains"]) | (set(extra_domains) if key in ("backend", "design", "security_review", "fix") else set())),
                        executor=executor, tools=spec["tools"], acceptance_criteria=spec["acceptance"], dependencies=deps, resources=resources,
                        risk=task_risk, stage=spec.get("stage"), estimated_minutes=spec["minutes"])
        task["step"] = key; task["review"] = bool(spec.get("review")); task["idempotency_key"] = canonical_digest([intent["request_id"], key])[:16]
        role = next((a for a in stage_agents.get(spec.get("stage") or "", [])), None)
        if role:
            task["agent"] = role; task["routing"] = {"method": "pipeline_stage_role", "stage": spec["stage"]}
        else:
            selection = select_agents(root, capabilities=spec["caps"], domains=task["domains"], technologies=techs, risk=task_risk, request=request, limit=1, history=history)
            if selection["selected"]:
                best = selection["selected"][0]; task["agent"] = best["id"]
                task["routing"] = {"method": "router", "score": best["score"], "reasons": best["reasons"], "alternatives": [r["id"] for r in selection["redundant"]][:3]}
            else:
                task["routing"] = {"method": "router", "missing_capabilities": selection["missing_capabilities"], "fallback": selection["fallback"]}
        task["status"] = "PLANNED"; task["history"].append({"from": "CREATED", "to": "PLANNED", "at": utc_now(), "reason": "planned"})
        tasks.append(task)
    plan = {"contract": "plan", "version": CONTRACT_VERSION, "plan_id": new_id("plan"), "request_id": intent["request_id"], "created_at": utc_now(),
            "request": request, "workspace": str(workspace) if workspace else None, "intent": intent, "tasks": tasks, "revisions": [
                {"revision": 1, "at": utc_now(), "reason": "initial plan", "changes": [t["task_id"] for t in tasks]}]}
    plan["validation"] = validate_plan(root, plan)
    if platform is not None:
        for task in tasks:
            if task["executor"]["kind"] == "tool" and task["agent"]: resolve_tools(task, platform)
    for task in tasks:
        if task["executor"]["kind"] != "tool": continue
        for entry in task["executor"].get("resolved") or [{"missing": True, "provides": r.get("provides")} for r in task["executor"]["requirements"]]:
            if entry.get("missing"): plan["validation"]["warnings"].append(f"{task['task_id']}: no registered tool provides {entry.get('provides')}; resolved again at run time")
            elif entry.get("fallback"): plan["validation"]["warnings"].append(f"{task['task_id']}: using fallback tool {entry['tool_id']} for {task['executor']['requirements'][0].get('provides')}")
    plan["dag"] = analyze_dag(tasks) if plan["validation"]["dag_ok"] else None
    plan["approvals_required"] = [t["task_id"] for t in tasks if t["requires_approval"]]
    agent_tasks = [t for t in tasks if t["executor"]["kind"] == "agent"]
    plan["estimates"] = {"agent_tasks": len(agent_tasks), "tokens_estimated": len(agent_tasks) * 3 * TOKENS_PER_CONTEXT_WEIGHT,
                         "minutes_estimated": sum(t["estimated_minutes"] for t in tasks),
                         "cost": "unverified: no provider pricing is configured; providers report actual usage at run time"}
    plan["status"] = "PLANNED" if plan["validation"]["ok"] else "INVALID"
    return plan


def analyze_dag(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Topological order, parallel levels and the critical path weighted by estimated minutes."""
    by_id = {t["task_id"]: t for t in tasks}; indegree = {t["task_id"]: len(t["dependencies"]) for t in tasks}
    children: dict[str, list[str]] = {tid: [] for tid in by_id}
    for t in tasks:
        for dep in t["dependencies"]: children[dep].append(t["task_id"])
    level = sorted(tid for tid, d in indegree.items() if d == 0); order: list[str] = []; levels: list[list[str]] = []
    while level:
        levels.append(level); order += level; nxt = []
        for tid in level:
            for child in children[tid]:
                indegree[child] -= 1
                if indegree[child] == 0: nxt.append(child)
        level = sorted(nxt)
    finish: dict[str, float] = {}; parent: dict[str, str | None] = {}
    for tid in order:
        deps = by_id[tid]["dependencies"]; best = max(deps, key=lambda d: finish[d], default=None)
        finish[tid] = (finish[best] if best else 0) + by_id[tid]["estimated_minutes"]; parent[tid] = best
    end = max(finish, key=finish.get) if finish else None; path = []
    while end: path.append(end); end = parent[end]
    return {"order": order, "levels": levels, "max_parallelism": max((len(l) for l in levels), default=0), "critical_path": path[::-1],
            "critical_minutes": max(finish.values(), default=0)}


def find_cycle(tasks: list[dict[str, Any]]) -> list[str] | None:
    graph = {t["task_id"]: t["dependencies"] for t in tasks}; state: dict[str, int] = {}; stack: list[str] = []
    def visit(node: str) -> list[str] | None:
        state[node] = 1; stack.append(node)
        for dep in graph.get(node, []):
            if state.get(dep) == 1: return stack[stack.index(dep):] + [dep]
            if state.get(dep) is None and dep in graph:
                found = visit(dep)
                if found: return found
        state[node] = 2; stack.pop(); return None
    for node in graph:
        if state.get(node) is None:
            found = visit(node)
            if found: return found
    return None


def _reachable(tasks: list[dict[str, Any]]) -> dict[str, set[str]]:
    deps = {t["task_id"]: set(t["dependencies"]) for t in tasks}; memo: dict[str, set[str]] = {}
    def up(tid: str) -> set[str]:
        if tid not in memo:
            memo[tid] = set()
            for d in deps.get(tid, ()): memo[tid] |= {d} | up(d)
        return memo[tid]
    return {tid: up(tid) for tid in deps}


def validate_plan(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    tasks = plan["tasks"]; errors: list[str] = []; warnings: list[str] = []; ids = [t["task_id"] for t in tasks]
    if len(set(ids)) != len(ids): errors.append("duplicate task IDs")
    known = set(ids)
    for t in tasks:
        errors += [f"{t['task_id']} depends on unknown task {d}" for d in t["dependencies"] if d not in known]
    cycle = find_cycle(tasks)
    if cycle: errors.append("dependency cycle: " + " -> ".join(cycle))
    agents = {a["id"]: a for a in read_json(root / "registry" / "agents.json")["agents"]}
    for t in tasks:
        tid = t["task_id"]
        if t["status"] not in TASK_TRANSITIONS: errors.append(f"{tid} has unknown status {t['status']}")
        if not t["acceptance_criteria"]: errors.append(f"{tid} has no acceptance criteria")
        if t["executor"]["kind"] == "command" and not t["executor"].get("command"):
            warnings.append(f"{tid}: no test command detected in the workspace; the task will fail until one exists")
        if not t["agent"]:
            errors.append(f"{tid}: no registered agent provides {t['routing'].get('missing_capabilities')}; {t['routing'].get('fallback', {}).get('decompose', '')}"); continue
        agent = agents.get(t["agent"])
        if agent is None: errors.append(f"{tid}: agent {t['agent']} is not registered"); continue
        try: contract = load_contract(root, t["agent"])["contract"]
        except (LookupError, ValueError) as exc: errors.append(f"{tid}: agent {t['agent']} cannot be loaded: {exc}"); continue
        allowed, approval = set(contract["tools"]["allowed"]), set(contract["tools"]["approval_required"])
        unauthorized = [tool for tool in t["tools"] if tool not in allowed | approval]
        if unauthorized: errors.append(f"{tid}: agent {t['agent']} is not authorized for {unauthorized}")
        t["permissions"] = {"allowed": sorted(set(t["tools"]) & allowed), "approval_required": sorted(set(t["tools"]) & approval)}
        t["requires_approval"] = bool(t["permissions"]["approval_required"])
        if t["requires_approval"] and t["status"] == "PLANNED":
            t["status"] = "WAITING_APPROVAL"; t["history"].append({"from": "PLANNED", "to": "WAITING_APPROVAL", "at": utc_now(), "reason": f"governed tools {t['permissions']['approval_required']}"})
        if RISK_ORDER[agent["risk_limit"]] < RISK_ORDER[t["risk"]]: errors.append(f"{tid}: agent {t['agent']} risk_limit {agent['risk_limit']} is below task risk {t['risk']}")
        t["skills"] = contract["dependencies"]["skills"]
    if not cycle:
        reach = _reachable(tasks); writers = [t for t in tasks if "write_files" in t["tools"]]
        for i, a in enumerate(writers):
            for b in writers[i + 1:]:
                shared = set(a["resources"]) & set(b["resources"])
                if shared and a["task_id"] not in reach[b["task_id"]] and b["task_id"] not in reach[a["task_id"]]:
                    warnings.append(f"{a['task_id']} and {b['task_id']} both write {sorted(shared)} without ordering; resource locks will serialize them")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "dag_ok": not cycle and not any("unknown task" in e for e in errors), "checked_at": utc_now()}
