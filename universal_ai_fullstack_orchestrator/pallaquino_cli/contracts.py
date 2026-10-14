"""Agent and skill contracts v2 (ADR-0008): derivation from registry facts, validation and controlled loading."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .core import read_json, result, sha256_file

CONTRACT_VERSION = 2
AGENT_CONTRACTS = "registry/agent_contracts.json"
SKILL_CONTRACTS = "registry/skill_contracts.json"
GOLDEN_FILES = ["evaluation/routing_golden.json", "evaluation/stack_routing/golden.json"]

# Deny by default: a tool absent from a contract is not authorized. Governed tools may only appear under
# approval_required, so even an authorized agent needs explicit human approval (HUMAN_APPROVAL_POLICY.md).
TOOL_TIERS = {
    "read_repository": "read", "search_repository": "read", "read_registry": "read",
    "run_tests": "execute", "run_linters": "execute", "run_build": "execute", "run_security_scan": "execute",
    "network_read": "network",
    "write_files": "write", "git_commit": "write",
    "deploy": "governed", "infrastructure_apply": "governed", "release_publish": "governed", "git_push": "governed",
    "database_migration_apply": "governed", "secrets_access": "governed",
}
NETWORK_CATEGORIES = {"governance", "release", "integration", "ai", "platform"}
REQUIRED_AGENT_FIELDS = ["id", "contract_version", "name", "description", "version", "capabilities", "inputs", "outputs", "dependencies",
                         "tools", "risk_limit", "activation", "success_criteria", "test_cases", "source_digest", "curation"]
REQUIRED_SKILL_FIELDS = ["id", "contract_version", "name", "description", "version", "capabilities", "inputs", "outputs", "dependencies",
                         "tools", "risk_level", "activation", "success_criteria", "test_cases", "source_digest", "curation"]
CURATED_FIELDS = ["name", "description", "inputs", "outputs", "success_criteria", "tools"]

UNIVERSAL_INPUTS = ["task scope and acceptance criteria", "risk classification and required gates", "repository map and reserved files"]
UNIVERSAL_OUTPUTS = ["evidence record for every executed check", "residual risks, confidence and next pipeline stage"]
UNIVERSAL_SUCCESS = ["no unexecuted check is reported as passed", "stays within its risk limit and authorized tools"]
# Category templates: derived, not curated; contracts built from them carry curation="derived".
AGENT_TEMPLATES = {
    "architecture": (["current architecture and domain map", "non-functional requirements"], ["architecture decision or ADR with options and trade-offs", "updated component boundaries"], ["decision states options, trade-offs and reversal path"]),
    "backend": (["API and domain contracts", "authorization rules"], ["service changes with tests", "updated API contract"], ["contract and authorization tests pass", "failure paths are handled explicitly"]),
    "frontend": (["UI requirements and design tokens", "API contracts consumed"], ["component changes with tests", "accessibility notes"], ["accessibility and component tests pass", "no direct database access from the client"]),
    "mobile": (["platform targets and offline requirements", "API contracts consumed"], ["mobile architecture or code changes", "offline and sync behaviour notes"], ["offline, sync and permission paths are tested"]),
    "data": (["schema, data volumes and retention rules", "migration constraints"], ["schema or pipeline changes", "migration and rollback plan"], ["migrations are reversible or staged expand/contract", "data integrity checks pass"]),
    "security": (["threat model and trust boundaries", "changed attack surface"], ["findings ranked by severity with evidence", "required mitigations"], ["every finding cites a reproducible location", "no secret value is printed"]),
    "quality": (["acceptance criteria and changed files", "existing test suite"], ["tests or review findings", "coverage and gap report"], ["new behaviour has a failing-then-passing test", "flaky or skipped tests are reported"]),
    "operations": (["service level objectives and runbooks", "deployment topology"], ["operational changes, alerts or runbook updates", "rollback procedure"], ["rollback is documented and rehearsable", "alerts map to user-visible symptoms"]),
    "platform": (["environment matrix and infrastructure state", "deployment requirements"], ["infrastructure or pipeline changes", "plan output for review"], ["infrastructure changes are planned before applied", "least-privilege access is preserved"]),
    "ai": (["model, provider capabilities and budget", "evaluation datasets"], ["prompt, retrieval or evaluation changes", "evaluation results"], ["evaluation results are reproducible", "retrieved content is treated as untrusted data"]),
    "domain": (["business rules and domain glossary", "regulatory constraints"], ["domain rule review or implementation guidance", "invariants to test"], ["domain invariants are expressed as tests"]),
    "governance": (["policies, registries and change manifests", "approval records"], ["compliance findings", "required approvals"], ["every finding names the controlling policy"]),
    "execution": (["task graph and file locks", "agent outputs"], ["integrated results and updated task states", "conflict report"], ["no two agents edit a reserved file concurrently"]),
    "integration": (["external API and event contracts", "retry and idempotency rules"], ["integration code or contract changes", "compatibility notes"], ["contract and idempotency tests pass"]),
    "context": (["context budget and pinned items", "task-relevant files"], ["selected context with omissions recorded"], ["mandatory context fits the budget"]),
    "continuity": (["checkpoints, handoff and continuity state"], ["checkpoint and provider-neutral handoff"], ["recovery succeeds from the newest valid checkpoint"]),
    "documentation": (["implemented behaviour and decisions"], ["updated documentation separating implemented, experimental and planned"], ["documentation matches observed behaviour"]),
    "framework": (["framework registries, policies and validators"], ["framework changes with validators updated"], ["all framework validators pass"]),
    "pipeline": (["pipeline definition and gate results"], ["stage transitions and remediation routing"], ["failed gates return to their declared stage"]),
    "product": (["user problem, goals and constraints"], ["specification with acceptance criteria"], ["acceptance criteria are testable"]),
    "release": (["change manifests, evidence and version policy"], ["release manifest, changelog and verified artifact"], ["artifact is reproducible and verified before publication"]),
    "risk": (["request, changed files and domain factors"], ["risk level with factors and required gates"], ["risk classification is monotonic and justified"]),
    "design": (["user flows and accessibility requirements"], ["interaction and visual design guidance"], ["designs meet accessibility requirements"]),
}
SKILL_TEMPLATE = (["scoped task and declared technologies", "verified stack versions"], ["specialized guidance applied to the task", "risks, compatibility constraints and evidence commands"],
                  ["guidance is limited to the declared scope", "versions come from the verified stack registry"])


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*\n+(.+?)(?:\n\s*\n|\Z)", text, re.M | re.S)
    return " ".join(match.group(1).split()) if match else ""


def _title(text: str) -> str:
    match = re.search(r"^# (.+)$", text, re.M)
    return re.sub(r"^PALLAQUINO agent:\s*", "", match.group(1).strip()) if match else ""


def _registry(root: Path) -> dict[str, Any]:
    load = lambda rel, key: read_json(root / rel)[key]
    goldens = []
    for rel in GOLDEN_FILES:
        if (root / rel).is_file():
            goldens.extend((f"{rel}#{index}", case) for index, case in enumerate(load(rel, "cases")))
    return {"agents": load("registry/agents.json", "agents"), "skills": load("registry/skills.json", "skills"),
            "rules": load("registry/routing_rules.json", "rules"), "profiles": load("registry/stack_profiles.json", "profiles"),
            "packs": load("registry/domain_packs.json", "packs"), "coverage": load("registry/agent_skill_coverage.json", "coverage"), "goldens": goldens}


def _agent_tools(agent: dict[str, Any]) -> dict[str, list[str]]:
    allowed = ["read_repository", "search_repository", "read_registry", "run_tests", "run_linters", "run_build", "run_security_scan"]
    if agent["category"] in NETWORK_CATEGORIES: allowed.append("network_read")
    if agent["can_write_code"]: allowed += ["write_files", "git_commit"]
    approval = []
    if agent["can_deploy"]: approval += ["deploy", "infrastructure_apply"]
    if agent["category"] == "release": approval += ["release_publish", "git_push"]
    if agent["category"] == "data" and agent["can_write_code"]: approval.append("database_migration_apply")
    return {"allowed": allowed, "approval_required": approval}


def _activation(registry: dict[str, Any], key: str, item_id: str) -> dict[str, list[str]]:
    return {"routing_rules": [r["id"] for r in registry["rules"] if item_id in r.get(key, [])],
            "profiles": [p["id"] for p in registry["profiles"] if item_id in p.get(key, [])],
            "domain_packs": [p["id"] for p in registry["packs"] if item_id in p.get(key, [])],
            "technologies": [c["technology"] for c in registry["coverage"] if item_id in c.get(key, [])]}


def derive_contracts(root: Path, existing: dict[str, dict[str, dict[str, Any]]] | None = None) -> dict[str, list[dict[str, Any]]]:
    """Rebuild contracts from registry facts; curated fields of existing curated contracts are preserved."""
    registry = _registry(root); existing = existing or {"agents": {}, "skills": {}}
    agents, skills = [], []
    for agent in registry["agents"]:
        text = (root / agent["path"]).read_text(encoding="utf-8")
        inputs, outputs, success = AGENT_TEMPLATES.get(agent["category"], ([], [], []))
        contract = {"id": agent["id"], "contract_version": CONTRACT_VERSION, "name": _title(text) or agent["id"], "description": _section(text, "Mission"),
                    "version": agent["version"], "capabilities": agent["capabilities"], "inputs": inputs + UNIVERSAL_INPUTS, "outputs": outputs + UNIVERSAL_OUTPUTS,
                    "dependencies": {"skills": agent["required_skills"], "technologies": agent["technologies"]}, "tools": _agent_tools(agent),
                    "risk_limit": agent["risk_limit"], "activation": {**_activation(registry, "agents", agent["id"]), "domains": agent["domains"]},
                    "success_criteria": success + UNIVERSAL_SUCCESS, "test_cases": [ref for ref, case in registry["goldens"] if agent["id"] in case.get("required_agents", [])],
                    "source_digest": sha256_file(root / agent["path"]), "curation": "derived"}
        agents.append(_merge_curated(contract, existing["agents"].get(agent["id"])))
    required_by = {s["id"]: [a["id"] for a in registry["agents"] if s["id"] in a["required_skills"]] for s in registry["skills"]}
    for skill in registry["skills"]:
        text = (root / skill["path"]).read_text(encoding="utf-8")
        contract = {"id": skill["id"], "contract_version": CONTRACT_VERSION, "name": _title(text) or skill["id"], "description": _section(text, "Specialized guidance"),
                    "version": skill["version"], "capabilities": skill["capabilities"], "inputs": list(SKILL_TEMPLATE[0]), "outputs": list(SKILL_TEMPLATE[1]),
                    "dependencies": {"skills": skill["dependencies"], "conflicts": skill["conflicts"], "technologies": skill["technologies"]},
                    "tools": {"allowed": [], "approval_required": []}, "risk_level": skill["risk_level"],
                    "activation": {**_activation(registry, "skills", skill["id"]), "required_by_agents": required_by[skill["id"]], "tags": skill["tags"]},
                    "success_criteria": list(SKILL_TEMPLATE[2]), "test_cases": [ref for ref, case in registry["goldens"] if skill["id"] in case.get("required_skills", [])],
                    "source_digest": sha256_file(root / skill["path"]), "curation": "derived"}
        skills.append(_merge_curated(contract, existing["skills"].get(skill["id"])))
    return {"agents": agents, "skills": skills}


def _merge_curated(derived: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    if not current or current.get("curation") != "curated":
        return derived
    return {**derived, **{field: current[field] for field in CURATED_FIELDS if field in current}, "curation": "curated"}


def load_contract_files(root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    out: dict[str, dict[str, dict[str, Any]]] = {"agents": {}, "skills": {}}
    for kind, rel in (("agents", AGENT_CONTRACTS), ("skills", SKILL_CONTRACTS)):
        if (root / rel).is_file():
            out[kind] = {c.get("id"): c for c in read_json(root / rel)["contracts"]}
    return out


def _is_reachable(contract: dict[str, Any]) -> bool:
    activation = contract.get("activation", {})
    return any(activation.get(key) for key in ("routing_rules", "profiles", "domain_packs", "technologies", "required_by_agents"))


def contract_errors(root: Path) -> list[str]:
    try:
        registry = _registry(root); contracts = load_contract_files(root)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"cannot load contracts: {exc}"]
    errors: list[str] = []
    golden_refs = dict(registry["goldens"]); rule_ids = {r["id"] for r in registry["rules"]}
    profile_ids = {p["id"] for p in registry["profiles"]}; pack_ids = {p["id"] for p in registry["packs"]}
    for kind, rows, fields, golden_key in (("agents", registry["agents"], REQUIRED_AGENT_FIELDS, "required_agents"), ("skills", registry["skills"], REQUIRED_SKILL_FIELDS, "required_skills")):
        found = contracts[kind]
        if not found: errors.append(f"no {kind} contracts; run scripts/build_contracts.py --write"); continue
        for extra in sorted(set(found) - {r["id"] for r in rows}): errors.append(f"{kind} contract {extra} has no registry entry")
        for row in rows:
            contract = found.get(row["id"]); label = f"{kind[:-1]} {row['id']}"
            if contract is None: errors.append(f"{label} has no contract"); continue
            missing = [f for f in fields if f not in contract]
            if missing: errors.append(f"{label} contract missing {missing}"); continue
            if contract["contract_version"] != CONTRACT_VERSION: errors.append(f"{label} contract_version must be {CONTRACT_VERSION}")
            for field in ("description", "inputs", "outputs", "success_criteria"):
                if not contract[field]: errors.append(f"{label} contract has empty {field}")
            if contract["curation"] not in ("derived", "curated"): errors.append(f"{label} curation must be derived or curated")
            if contract["version"] != row["version"]: errors.append(f"{label} contract version {contract['version']} != registry {row['version']}")
            if contract["capabilities"] != row["capabilities"]: errors.append(f"{label} capabilities drifted from registry")
            expected_skills = row["required_skills"] if kind == "agents" else row["dependencies"]
            if contract["dependencies"].get("skills") != expected_skills: errors.append(f"{label} skill dependencies drifted from registry")
            if contract["source_digest"] != sha256_file(root / row["path"]): errors.append(f"{label} source changed since its contract was built ({row['path']})")
            errors += _tool_errors(label, contract["tools"], row if kind == "agents" else None)
            activation = contract["activation"]
            errors += [f"{label} unknown routing rule {x}" for x in activation.get("routing_rules", []) if x not in rule_ids]
            errors += [f"{label} unknown profile {x}" for x in activation.get("profiles", []) if x not in profile_ids]
            errors += [f"{label} unknown domain pack {x}" for x in activation.get("domain_packs", []) if x not in pack_ids]
            for ref in contract["test_cases"]:
                case = golden_refs.get(ref)
                if case is None: errors.append(f"{label} test case {ref} does not exist")
                elif row["id"] not in case.get(golden_key, []): errors.append(f"{label} test case {ref} does not require it")
    return errors


def _tool_errors(label: str, tools: Any, agent: dict[str, Any] | None) -> list[str]:
    if not isinstance(tools, dict) or set(tools) != {"allowed", "approval_required"}: return [f"{label} tools must declare allowed and approval_required"]
    errors = [f"{label} unknown tool {t}" for t in tools["allowed"] + tools["approval_required"] if t not in TOOL_TIERS]
    errors += [f"{label} governed tool {t} must be approval_required" for t in tools["allowed"] if TOOL_TIERS.get(t) == "governed"]
    errors += [f"{label} {t} under approval_required is not a governed tool" for t in tools["approval_required"] if TOOL_TIERS.get(t) not in (None, "governed")]
    if agent is None:
        if tools["allowed"] or tools["approval_required"]: errors.append(f"{label} skills cannot grant tools")
        return errors
    if not agent["can_write_code"]: errors += [f"{label} cannot hold write tool {t} (can_write_code is false)" for t in tools["allowed"] if TOOL_TIERS.get(t) == "write"]
    if not agent["can_deploy"]: errors += [f"{label} cannot request {t} (can_deploy is false)" for t in tools["approval_required"] if t in ("deploy", "infrastructure_apply")]
    return errors


def validate_contracts(root: Path) -> dict[str, Any]:
    errors = contract_errors(root)
    if errors: return result("validate_contracts", False, errors)
    contracts = load_contract_files(root)
    return result("validate_contracts", True, [f"{len(contracts['agents'])} agent and {len(contracts['skills'])} skill contracts valid"])


def contracts_report(root: Path) -> dict[str, Any]:
    """Coverage report: validity plus agents/skills that can never be selected or have no test case."""
    contracts = load_contract_files(root); errors = contract_errors(root)
    report: dict[str, Any] = {"ok": not errors, "errors": errors}
    for kind, rows in contracts.items():
        values = list(rows.values())
        report[kind] = {"total": len(values), "curated": sum(c.get("curation") == "curated" for c in values),
                        "derived": sum(c.get("curation") == "derived" for c in values),
                        "unreachable": sorted(c["id"] for c in values if not _is_reachable(c)),
                        "untested": sorted(c["id"] for c in values if not c.get("test_cases"))}
    return report


def load_contract(root: Path, item_id: str, allow_deprecated: bool = False) -> dict[str, Any]:
    """Controlled loading: return a contract and its body only if the source is unchanged and the entry is active."""
    registry = _registry(root); contracts = load_contract_files(root)
    for kind, rows in (("agents", registry["agents"]), ("skills", registry["skills"])):
        row = next((r for r in rows if r["id"] == item_id), None)
        if row is None: continue
        contract = contracts[kind].get(item_id)
        if contract is None: raise LookupError(f"{item_id} has no contract")
        if row.get("deprecated") and not allow_deprecated: raise LookupError(f"{item_id} is deprecated; use {row.get('superseded_by')}")
        path = root / row["path"]
        if sha256_file(path) != contract["source_digest"]: raise ValueError(f"{row['path']} changed since its contract was built; rebuild and review contracts")
        return {"kind": kind[:-1], "contract": contract, "body": path.read_text(encoding="utf-8"), "verified": True}
    raise LookupError(f"unknown agent or skill: {item_id}")
