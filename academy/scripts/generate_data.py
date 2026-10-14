#!/usr/bin/env python3
"""Generate the academy's data from PALLAQUINO's sources of truth (read-only).

    python academy/scripts/generate_data.py           # write academy/src/data/generated/*.json
    python academy/scripts/generate_data.py --check   # exit 1 if the committed files are out of date (CI)

Sources: the real argparse parser (`pallaquino_cli.__main__.parser`), the agent and skill registries and their v2 contracts, the
pipeline definition, the builtin tool contracts, the plugin manifest vocabulary and the registries of technologies, stack profiles,
modes and domain packs. Nothing is imported from plugins and no command is executed. The output is deterministic, with no
timestamps, so `--check` can compare it byte for byte.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ACADEMY = Path(__file__).resolve().parents[1]
FRAMEWORK = ACADEMY.parent / "universal_ai_fullstack_orchestrator"
OUT = ACADEMY / "src" / "data" / "generated"
sys.path.insert(0, str(FRAMEWORK))

from pallaquino_cli import __version__  # noqa: E402
from pallaquino_cli.__main__ import parser as cli_parser  # noqa: E402


def read(rel: str):
    return json.loads((FRAMEWORK / rel).read_text(encoding="utf-8"))


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)): return value
    if isinstance(value, (list, tuple)): return [_plain(v) for v in value]
    return str(value)


def cli() -> dict:
    top = cli_parser()
    sub_action = next(a for a in top._actions if isinstance(a, argparse._SubParsersAction))
    helps = {a.dest: a.help for a in sub_action._choices_actions}
    commands = []
    for name, sub in sub_action.choices.items():
        arguments = []
        for action in sub._actions:
            if isinstance(action, argparse._HelpAction): continue
            arguments.append({"name": action.dest, "flags": list(action.option_strings), "positional": not action.option_strings,
                              "help": action.help, "required": bool(getattr(action, "required", False)) if action.option_strings else action.nargs not in ("?", "*", argparse.REMAINDER),
                              "choices": _plain(action.choices) if action.choices else None, "nargs": _plain(action.nargs),
                              "default": None if action.default in (None, argparse.SUPPRESS) or isinstance(action.default, Path) or action.default == [] else _plain(action.default),
                              "takes_value": not isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._CountAction))})
        commands.append({"name": name, "help": helps.get(name), "arguments": arguments})
    commands.sort(key=lambda c: c["name"])
    return {"program": "pallaquino", "module": "python -m pallaquino_cli", "version": __version__, "commands": commands,
            "exit_codes": {"0": "completado / correcto", "1": "fallo o error", "2": "raíz del framework no encontrada", "3": "esperando aprobación o en pausa",
                           "4": "cancelado", "5": "permiso denegado (pasarela de herramientas)"}}


def agents() -> list[dict]:
    contracts = {c["id"]: c for c in read("registry/agent_contracts.json")["contracts"]}
    rows = []
    for agent in read("registry/agents.json")["agents"]:
        c = contracts.get(agent["id"], {})
        rows.append({"id": agent["id"], "name": c.get("name", agent["id"]), "description": c.get("description", ""), "category": agent["category"],
                     "domains": agent["domains"], "capabilities": agent["capabilities"], "technologies": agent.get("technologies", []),
                     "risk_limit": agent["risk_limit"], "can_write_code": agent.get("can_write_code"), "can_review": agent.get("can_review"),
                     "can_deploy": agent.get("can_deploy"), "skills": agent.get("required_skills", []), "inputs": c.get("inputs", []),
                     "outputs": c.get("outputs", []), "success_criteria": c.get("success_criteria", []),
                     "tools_allowed": c.get("tools", {}).get("allowed", []), "tools_approval": c.get("tools", {}).get("approval_required", []),
                     "pipeline_stages": c.get("activation", {}).get("pipeline_stages", []), "curation": c.get("curation"),
                     "deprecated": agent.get("deprecated", False)})
    return sorted(rows, key=lambda r: r["id"])


def skills() -> list[dict]:
    contracts = {c["id"]: c for c in read("registry/skill_contracts.json")["contracts"]}
    rows = []
    for skill in read("registry/skills.json")["skills"]:
        c = contracts.get(skill["id"], {})
        rows.append({"id": skill["id"], "name": c.get("name", skill["id"]), "description": c.get("description", ""), "category": skill["category"],
                     "domains": skill.get("domains", []), "capabilities": skill.get("capabilities", []), "technologies": skill.get("technologies", []),
                     "risk_level": skill.get("risk_level"), "tags": skill.get("tags", []), "inputs": c.get("inputs", []), "outputs": c.get("outputs", []),
                     "dependencies": skill.get("dependencies", []), "curation": c.get("curation"), "deprecated": skill.get("deprecated", False)})
    return sorted(rows, key=lambda r: r["id"])


def pipeline() -> dict:
    data = read("pipeline/pipeline_definition.json")
    stages = [{k: _plain(v) for k, v in stage.items()} for stage in data["stages"]]
    return {"name": data["name"], "stages": sorted(stages, key=lambda s: (s.get("order") or 0, s["id"]))}


def tools() -> dict:
    from pallaquino_cli.extensions.manifest import PLUGIN_TYPES
    from pallaquino_cli.integrations import database, filesystem, git, github
    from pallaquino_cli.tools.contracts import CAPABILITIES, OPERATIONS
    builtin = filesystem.tools() + git.tools() + database.tools() + github.tools({}, lambda ref: None)
    rows = [{"tool_id": t["tool_id"], "description": t["description"], "capabilities": t["capabilities"], "operation": t["operation"],
             "risk": t["risk"], "approval": t["approval"], "provides": t.get("provides", []),
             "default_enabled": not t["tool_id"].startswith("core.github."),
             "arguments": sorted((t["input_schema"].get("properties") or {}).keys()), "required": t["input_schema"].get("required", [])}
            for t, _ in builtin]
    return {"capabilities": CAPABILITIES, "operations": OPERATIONS, "plugin_types": PLUGIN_TYPES, "builtin": sorted(rows, key=lambda r: r["tool_id"])}


def catalogs() -> dict:
    return {"technologies": sorted(({"id": t["id"], "category": t.get("category"), "status": t.get("selection_status")} for t in read("registry/technology_catalog.json")["technologies"]), key=lambda t: t["id"]),
            "profiles": [{"id": p["id"], "technologies": p.get("technologies", []), "agents": p.get("agents", [])} for p in read("registry/stack_profiles.json")["profiles"]],
            "modes": [{"id": m["id"], "autonomy": m.get("autonomy"), "description": m.get("description")} for m in read("registry/modes.json")["modes"]],
            "domain_packs": [{"id": p["id"], "agents": p.get("agents", []), "skills": p.get("skills", [])} for p in read("registry/domain_packs.json")["packs"]]}


def build() -> dict[str, object]:
    data = {"cli": cli(), "agents": agents(), "skills": skills(), "pipeline": pipeline(), "tools": tools(), "catalogs": catalogs()}
    data["meta"] = {"framework_version": __version__, "source": "universal_ai_fullstack_orchestrator", "counts": {
        "commands": len(data["cli"]["commands"]), "agents": len(data["agents"]), "skills": len(data["skills"]), "pipeline_stages": len(data["pipeline"]["stages"]),
        "builtin_tools": len(data["tools"]["builtin"]), "technologies": len(data["catalogs"]["technologies"]), "profiles": len(data["catalogs"]["profiles"])}}
    return data


def render(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def main() -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--check", action="store_true", help="fail if committed data differs from the sources of truth")
    check = args.parse_args().check
    stale = []
    for name, value in build().items():
        path = OUT / f"{name}.json"; text = render(value)
        if check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text: stale.append(path.name)
        else:
            OUT.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8", newline="\n")
    if check and stale:
        print(f"academy data is out of date: {stale}; run python academy/scripts/generate_data.py", file=sys.stderr); return 1
    print("academy data " + ("up to date" if check else f"written to {OUT.relative_to(ACADEMY.parent)}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
