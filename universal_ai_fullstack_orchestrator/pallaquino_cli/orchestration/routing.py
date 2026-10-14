"""PALLAQUINO Agent Routing Engine: explainable, reproducible agent selection over contracts v2.

Score (0-100) = capability coverage 40 + domain overlap 25 + technology coverage 15 + routing-rule signal 10
+ project preference +/-5 - context cost, plus a history term that is applied only when the agent has at least
MIN_HISTORY verified, non-simulated runs (simulated runs never become success rates). Hard filters: deprecated
entries, risk_limit below the task risk, missing skill dependencies, and project exclusions. Ties break by agent
ID, so identical inputs always give identical selections.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ..contracts import load_contract_files
from ..core import RISK_ORDER, contains_term, read_json, route_request

WEIGHTS = {"capability": 40, "domain": 25, "technology": 15, "routing_signal": 10, "preference": 5, "history": 5}
MIN_HISTORY = 5
PREFERENCES_PATH = "governance/routing_preferences.json"
# Where a capability is usually owned; used only to break ties between candidates that both provide it.
CAPABILITY_DOMAINS = {"design": ["architecture"], "adr": ["architecture"], "compare": ["architecture"], "threat_model": ["security"],
                      "audit": ["security", "governance"], "schema": ["database"], "migration": ["database"], "rollback": ["database", "deployment"],
                      "test": ["testing"], "coverage": ["testing"], "write": ["documentation"], "verify": ["documentation"],
                      "deploy": ["deployment"], "build": ["deployment"], "version": ["release"], "manifest": ["release"],
                      "analyze": ["repository"], "map": ["repository"], "trace": ["repository"], "accessibility": ["ux", "web"]}
GENERIC_DOMAINS = {"code", "domain", "quality", "testing", "architecture", "repository", "documentation"}
# Domains implied by each intent, used by request-level matching.
INTENT_DOMAINS = {"PROJECT_DISCOVERY": ["repository"], "ARCHITECTURE_DESIGN": ["architecture"], "FEATURE_IMPLEMENTATION": [], "BUG_FIX": ["code"],
                  "CODE_REFACTOR": ["code"], "SECURITY_AUDIT": ["security"], "TEST_GENERATION": ["testing"], "DATABASE_MIGRATION": ["database"],
                  "API_DEVELOPMENT": ["api"], "FRONTEND_DEVELOPMENT": ["web", "ux"], "DOCUMENTATION": ["documentation"], "PERFORMANCE_OPTIMIZATION": ["performance"],
                  "DEVOPS_AUTOMATION": ["deployment", "infrastructure"], "RELEASE_PREPARATION": ["release"]}


def load_preferences(root: Path) -> dict[str, list[str]]:
    path = root / PREFERENCES_PATH
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {"prefer": list(data.get("prefer", [])), "exclude": list(data.get("exclude", []))}


def _agents(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str]]:
    registry = read_json(root / "registry" / "agents.json")["agents"]
    skills = {s["id"]: s for s in read_json(root / "registry" / "skills.json")["skills"]}
    active_skills = {sid for sid, s in skills.items() if not s.get("deprecated")}
    return registry, load_contract_files(root)["agents"], active_skills


def score_agents(root: Path, *, capabilities: Iterable[str], domains: Iterable[str] = (), technologies: Iterable[str] = (), risk: str = "LOW",
                 request: str = "", preferences: dict[str, list[str]] | None = None, history: Any = None) -> dict[str, Any]:
    capabilities = sorted(set(capabilities)); domains = sorted(set(domains)); technologies = sorted(set(technologies))
    preferences = preferences or load_preferences(root); registry, contracts, active_skills = _agents(root)
    signalled = {a["id"] for a in route_request(root, request)["agents"]} if request else set()
    ranked, rejected = [], []
    for agent in registry:
        aid = agent["id"]; contract = contracts.get(aid)
        if agent.get("deprecated"): rejected.append({"id": aid, "reason": f"deprecated (use {agent.get('superseded_by')})"}); continue
        if contract is None: rejected.append({"id": aid, "reason": "no contract"}); continue
        if aid in preferences["exclude"]: rejected.append({"id": aid, "reason": "excluded by project preferences"}); continue
        if RISK_ORDER[agent["risk_limit"]] < RISK_ORDER.get(risk, 0): rejected.append({"id": aid, "reason": f"risk_limit {agent['risk_limit']} below task risk {risk}"}); continue
        missing = [s for s in agent["required_skills"] if s not in active_skills]
        if missing: rejected.append({"id": aid, "reason": f"missing skill dependencies {missing}"}); continue
        caps = set(agent["capabilities"]); covered = sorted(caps & set(capabilities))
        if capabilities and not covered: continue  # not a candidate: no requested capability
        breakdown = {
            "capability": WEIGHTS["capability"] * (len(covered) / len(capabilities) if capabilities else 0),
            "domain": WEIGHTS["domain"] * (len(set(agent["domains"]) & set(domains)) / len(domains) if domains else 0),
            "technology": WEIGHTS["technology"] * (len(set(contract["activation"].get("technologies", [])) & set(technologies)) / len(technologies) if technologies else 0),
            "routing_signal": WEIGHTS["routing_signal"] if aid in signalled else 0,
            "preference": WEIGHTS["preference"] if aid in preferences["prefer"] else 0,
            "context_cost": -float(agent.get("context_weight", 3)),
            "history": 0.0,
        }
        history_note = "no history store"
        if history is not None:
            stats = history.agent_history(aid)
            if stats["verified_runs"] >= MIN_HISTORY:
                breakdown["history"] = WEIGHTS["history"] * (stats["success_rate"] - 0.5) * 2; history_note = f"{stats['verified_runs']} verified runs"
            else: history_note = f"insufficient verified history ({stats['verified_runs']} < {MIN_HISTORY}); not scored"
        score = round(sum(breakdown.values()), 2)
        ranked.append({"id": aid, "score": score, "covers": covered, "domains": agent["domains"], "category": agent["category"],
                       "breakdown": {k: round(v, 2) for k, v in breakdown.items()}, "history": history_note,
                       "tools": contract["tools"], "risk_limit": agent["risk_limit"]})
    ranked.sort(key=lambda r: (-r["score"], r["id"]))
    return {"capabilities": capabilities, "domains": domains, "technologies": technologies, "risk": risk, "ranked": ranked, "rejected": rejected, "weights": WEIGHTS}


def select_agents(root: Path, *, capabilities: Iterable[str], domains: Iterable[str] = (), technologies: Iterable[str] = (), risk: str = "LOW",
                  request: str = "", limit: int | None = None, preferences: dict[str, list[str]] | None = None, history: Any = None) -> dict[str, Any]:
    """Cover each requested capability with its best in-domain agent; report gaps instead of inventing agents.

    Capabilities are covered in a fixed order. An agent already selected keeps covering a later capability when it
    has it, so the set stays minimal; otherwise the candidate whose domains match the task or the capability's
    domain hint wins, then the higher score, then the lower ID.
    """
    scored = score_agents(root, capabilities=capabilities, domains=domains, technologies=technologies, risk=risk, request=request, preferences=preferences, history=history)
    wanted = scored["capabilities"]; task_domains = set(scored["domains"]); by_id = {r["id"]: r for r in scored["ranked"]}
    size = limit or (1 if len(wanted) <= 2 and RISK_ORDER.get(risk, 0) <= 1 else 3 if len(wanted) <= 4 else 6)
    chosen: list[str] = []; reasons: dict[str, list[str]] = {}; missing: list[str] = []; redundant: list[dict[str, Any]] = []
    for cap in wanted:
        hint = task_domains | set(CAPABILITY_DOMAINS.get(cap, ()))
        if any(cap in by_id[a]["covers"] for a in chosen):
            reasons[next(a for a in chosen if cap in by_id[a]["covers"])].append(f"also covers {cap}"); continue
        candidates = [r for r in scored["ranked"] if cap in r["covers"]]
        if not candidates: missing.append(cap); continue
        # In-domain first, then fewest specialist domains foreign to the task (a mobile or ERP specialist should not
        # win generic work), then score, then ID.
        candidates.sort(key=lambda r: (not (set(r["domains"]) & hint), len(set(r["domains"]) - hint - GENERIC_DOMAINS), -r["score"], r["id"]))
        best = candidates[0]
        if len(chosen) >= size: missing.append(cap); continue
        chosen.append(best["id"]); in_domain = bool(set(best["domains"]) & hint)
        reasons[best["id"]] = [f"covers {cap}" + ("" if in_domain else " (no in-domain candidate)"),
                               f"score {best['score']} ({', '.join(f'{k} {v}' for k, v in best['breakdown'].items() if v)})"]
        redundant += [{"id": r["id"], "reason": f"lower-ranked candidate for {cap}"} for r in candidates[1:3]]
    selected = [{**by_id[a], "reasons": reasons[a]} for a in chosen]
    redundant = [r for r in redundant if r["id"] not in chosen]
    fallback: dict[str, Any] = {}
    if missing:
        partial = [r["id"] for r in scored["ranked"] if r["id"] not in {s["id"] for s in selected}][:3]
        fallback = {"limitation": f"no selected agent provides {missing}", "alternatives": partial,
                    "decompose": "split the task so each part needs only capabilities the registry provides",
                    "authorization": "adding a capability requires an approved registry change (new or extended agent contract)"}
    return {"selected": selected, "missing_capabilities": missing, "fallback": fallback, "redundant": redundant[:10],
            "rejected": scored["rejected"], "weights": scored["weights"], "reproducible_inputs": {k: scored[k] for k in ("capabilities", "domains", "technologies", "risk")}}


DOMAIN_SYNONYMS = {"identity": ["authentication", "autenticación", "login", "roles", "rbac", "oauth", "sso", "permissions", "permisos"],
                   "payments": ["payment", "pago", "billing", "facturación"], "inventory": ["inventario", "stock"], "mobile": ["android", "ios", "móvil"],
                   "privacy": ["personal data", "datos personales", "pii", "gdpr"], "database": ["postgresql", "mysql", "sql server", "mongodb"]}


def detect_domains(root: Path, text: str) -> list[str]:
    """Registry domains named in the request (or by a synonym); only domains some agent declares are returned."""
    normalized = text.casefold()
    known = {d for a in read_json(root / "registry" / "agents.json")["agents"] for d in a["domains"]}
    found = {d for d in known if contains_term(normalized, d.replace("_", " "))}
    found |= {d for d, words in DOMAIN_SYNONYMS.items() if d in known and any(contains_term(normalized, w) for w in words)}
    return sorted(found)


def match_request(root: Path, text: str, *, workspace: Path | None = None) -> dict[str, Any]:
    from .intent import analyze_intent
    intent = analyze_intent(root, text, workspace=workspace)
    domains = sorted({d for item in intent["intents"] for d in INTENT_DOMAINS[item["intent"]]} | set(detect_domains(root, text)))
    selection = select_agents(root, capabilities=intent["required_capabilities"], domains=domains, technologies=intent["technologies"], risk=intent["risk"]["level"], request=text)
    return {"request": text, "intent": {k: intent[k] for k in ("primary_intent", "intents", "technologies", "required_capabilities", "risk")}, **selection}
