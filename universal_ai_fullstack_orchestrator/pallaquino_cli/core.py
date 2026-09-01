from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "0.1.0"
EXPECTED_AUTHOR = "jimdev"
EXPECTED_EMAIL = "jylmdev@gmail.com"
STALE_DAYS = 30
STAGES = [
    "REQUEST", "CONTINUITY_RECOVERY", "CAPABILITY_DETECTION", "REPOSITORY_ANALYSIS",
    "REPOSITORY_MAP", "STACK_VERSION_AUDIT", "RISK_ANALYSIS", "PLAN",
    "DOMAIN_IDENTIFICATION", "TASK_GRAPH", "AGENT_SELECTION", "SKILL_SELECTION",
    "CONTEXT_PREPARATION", "DELEGATION", "IMPLEMENTATION", "INTEGRATION",
    "MIGRATION_SAFETY", "TEST", "TEST_GAP_ANALYSIS", "LINT_TYPECHECK", "BUILD",
    "SECURITY_CHECK", "ADVERSARIAL_REVIEW", "CODE_REVIEW", "SPECIFICATION_DRIFT",
    "ACCEPTANCE_VALIDATION", "DOCUMENTATION", "ROLLBACK_READINESS", "STATE_UPDATE",
    "GIT_COMMIT", "CHECKPOINT", "HANDOFF",
]
CONTINUITY_FILES = [
    "PROJECT_STATE", "CURRENT_TASK", "TASK_BOARD", "ARCHITECTURE_STATE",
    "TECH_STACK_STATE", "TEST_STATUS", "KNOWN_ISSUES", "PIPELINE_STATE",
    "ASSUMPTIONS", "OPEN_QUESTIONS", "EXTERNAL_DEPENDENCIES", "TECHNICAL_DEBT",
]
GOVERNANCE_FILES = [
    "PALLAQUINO_BRANDING_POLICY.md", "GIT_AUTHORSHIP_POLICY.md",
    "TECH_STACK_VERSION_POLICY.md", "AUTONOMY_POLICY.md", "POLICY_HIERARCHY.md",
    "PROMPT_INJECTION_DEFENSE.md", "DESTRUCTIVE_ACTION_POLICY.md",
    "DEPENDENCY_POLICY.md", "HUMAN_APPROVAL_POLICY.md", "DEPRECATION_POLICY.md",
]
RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
REQUIRED_AGENT_FIELDS = {
    "id", "category", "domains", "capabilities", "technologies", "required_skills",
    "can_write_code", "can_review", "can_deploy", "risk_limit", "context_weight",
    "provider_neutral", "version", "last_reviewed", "deprecated", "superseded_by", "path",
}
REQUIRED_SKILL_FIELDS = {
    "id", "category", "tags", "domains", "technologies", "capabilities",
    "context_weight", "risk_level", "dependencies", "conflicts", "provider_neutral",
    "version", "last_reviewed", "deprecated", "superseded_by", "path",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def framework_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def result(name: str, ok: bool, details: Iterable[str] = ()) -> dict[str, Any]:
    return {"validator": name, "ok": ok, "details": list(details)}


def git_repository_root(root: Path) -> Path:
    current = root.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return current


def run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    repository = git_repository_root(root)
    return subprocess.run(
        ["git", "-c", f"safe.directory={repository.as_posix()}", *args],
        cwd=repository, text=True, capture_output=True, check=False,
    )


def detect_capabilities(root: Path, persist: bool = True) -> dict[str, Any]:
    commands = {
        "shell": os.environ.get("COMSPEC") or os.environ.get("SHELL"),
        "git": shutil.which("git"), "python": sys.executable,
        "node": shutil.which("node"), "dotnet": shutil.which("dotnet"),
        "docker": shutil.which("docker"), "docker_compose": shutil.which("docker"),
        "database_clients": next((shutil.which(x) for x in ("psql", "sqlite3", "mysql") if shutil.which(x)), None),
        "zip_creation": "stdlib:zipfile",
    }
    facts: dict[str, dict[str, Any]] = {
        "filesystem": {"available": root.exists(), "evidence": str(root.resolve())},
        "file_editing": {"available": os.access(root, os.W_OK), "evidence": "os.access"},
        "internet": {"available": None, "evidence": "not safely detectable offline"},
        "browser": {"available": None, "evidence": "provider/tool dependent"},
        "mcp": {"available": None, "evidence": "provider/tool dependent"},
        "subagents": {"available": None, "evidence": "provider/tool dependent"},
        "parallel_execution": {"available": None, "evidence": "provider/tool dependent"},
    }
    for key, value in commands.items():
        facts[key] = {"available": bool(value), "evidence": str(value or "not found")}
    payload = {"schema_version": 1, "detected_at": utc_now(), "provider": "unknown", "capabilities": facts}
    if persist:
        target = root / "runtime" / "capabilities.json"
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def _iter_repository_files(root: Path) -> list[Path]:
    ignored = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "dist"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in ignored for part in path.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.as_posix().casefold())


def build_repository_map(target: Path, output_root: Path | None = None) -> dict[str, Any]:
    files = _iter_repository_files(target)
    suffixes: dict[str, int] = {}
    for path in files:
        suffixes[path.suffix.lower() or "[none]"] = suffixes.get(path.suffix.lower() or "[none]", 0) + 1
    technology_patterns = {
        "Python": {".py", ".pyi"}, "JavaScript/TypeScript": {".js", ".ts", ".tsx", ".vue"},
        ".NET": {".cs", ".fs", ".csproj", ".sln"}, "SQL": {".sql"}, "Documentation": {".md"},
    }
    technologies = [name for name, exts in technology_patterns.items() if any(p.suffix.lower() in exts for p in files)]
    entry_names = {"main.py", "app.py", "manage.py", "Program.cs", "package.json", "pyproject.toml", "Dockerfile", "__main__.py"}
    entries = [str(p.relative_to(target)).replace("\\", "/") for p in files if p.name in entry_names]
    tests = [str(p.relative_to(target)).replace("\\", "/") for p in files if "test" in p.name.lower() or "tests" in p.parts]
    configs = [str(p.relative_to(target)).replace("\\", "/") for p in files if p.name in {"pyproject.toml", "package.json", "docker-compose.yml", "compose.yml", ".env.example"} or p.suffix.lower() in {".yaml", ".yml", ".toml"}]
    modules = sorted({str(p.relative_to(target).parts[0]) for p in files if len(p.relative_to(target).parts) > 1})
    payload = {
        "schema_version": 1, "generated_at": utc_now(), "root": str(target.resolve()),
        "modules": [{"id": m, "path": m, "owner": "unassigned"} for m in modules],
        "paths": [str(p.relative_to(target)).replace("\\", "/") for p in files], "owners": {},
        "technologies": technologies, "entrypoints": entries, "apis": [], "database_models": [],
        "tests": tests, "dependencies": [], "runtime_services": [], "configuration": configs,
        "statistics": {"files": len(files), "extensions": suffixes},
    }
    destination = output_root or target
    atomic_json(destination / "repository" / "REPOSITORY_MAP.json", payload)
    md = ["# Repository map", "", f"Generated: {payload['generated_at']}", f"Root: `{payload['root']}`", f"Files: {len(files)}", "", "## Technologies", ""]
    md.extend(f"- {x}" for x in technologies or ["None detected"])
    md.extend(["", "## Entrypoints", ""])
    md.extend(f"- `{x}`" for x in entries or ["None detected"])
    (destination / "repository" / "REPOSITORY_MAP.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return payload


def analyze_risk(text: str) -> dict[str, Any]:
    normalized = text.casefold()
    factor_terms = {
        "authentication": ["authentication", "auth", "login", "autenticación"],
        "authorization": ["authorization", "roles", "permission", "autorización"],
        "payments": ["payment", "pago", "billing"], "financial_data": ["financial", "financiero", "accounting"],
        "personal_data": ["personal data", "pii", "datos personales"], "database_migrations": ["migration", "migración", "schema"],
        "public_api": ["public api", "api pública"], "infrastructure": ["infrastructure", "infraestructura", "terraform"],
        "production": ["production", "producción", "prod"], "external_integrations": ["integration", "integración", "webhook"],
        "data_deletion": ["delete", "deletion", "borrar", "eliminar", "drop table", "drop database"],
        "security": ["security", "vulnerability", "seguridad", "cve"],
    }
    factors = [factor for factor, terms in factor_terms.items() if any(term in normalized for term in terms)]
    high = {"authentication", "authorization", "payments", "financial_data", "personal_data", "database_migrations", "security"}
    medium = {"public_api", "infrastructure", "external_integrations"}
    level = "LOW"
    if set(factors) & medium:
        level = "MEDIUM"
    if set(factors) & high or "production" in factors or "data_deletion" in factors:
        level = "HIGH"
    if "production" in factors and "data_deletion" in factors or "drop database" in normalized or "destroy infrastructure" in normalized:
        level = "CRITICAL"
    gates = {
        "LOW": ["TEST", "LINT_TYPECHECK", "CODE_REVIEW"],
        "MEDIUM": ["TEST", "INTEGRATION", "LINT_TYPECHECK", "BUILD", "CODE_REVIEW"],
        "HIGH": ["TEST", "INTEGRATION", "E2E", "BUILD", "SECURITY_CHECK", "CODE_REVIEW", "ROLLBACK_READINESS"],
        "CRITICAL": ["ALL_TESTS", "SECURITY_AUDIT", "MIGRATION_SAFETY", "ROLLBACK_READINESS", "HUMAN_APPROVAL"],
    }[level]
    return {"level": level, "matched_factors": factors, "required_gates": gates, "rationale": f"Detected {len(factors)} governed factor(s); risk is monotonic.", "confidence": "high" if factors else "medium"}


def route_request(root: Path, text: str) -> dict[str, Any]:
    rules = read_json(root / "registry" / "routing_rules.json")["rules"]
    normalized = text.casefold()
    matched = []
    agent_scores: dict[str, int] = {}
    skill_scores: dict[str, int] = {}
    for rule in rules:
        hits = sum(1 for word in rule["keywords"] if word.casefold() in normalized)
        if not hits:
            continue
        matched.append({"rule": rule["id"], "hits": hits})
        for agent in rule["agents"]:
            agent_scores[agent] = agent_scores.get(agent, 0) + hits
        for skill in rule["skills"]:
            skill_scores[skill] = skill_scores.get(skill, 0) + hits
    sort = lambda items: [{"id": key, "score": score} for key, score in sorted(items.items(), key=lambda x: (-x[1], x[0]))]
    return {"matched_rules": matched, "agents": sort(agent_scores), "skills": sort(skill_scores), "confidence": "high" if matched else "low"}


def validate_registry(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        agents = read_json(root / "registry" / "agents.json")["agents"]
        skills = read_json(root / "registry" / "skills.json")["skills"]
        routes = read_json(root / "registry" / "routing_rules.json")["rules"]
        read_json(root / "registry" / "stack_versions_verified.json")
        read_json(root / "registry" / "capabilities.json")
        read_json(root / "registry" / "modes.json")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result("validate_registry", False, [f"cannot load registry: {exc}"])
    agent_ids = [a.get("id") for a in agents]
    skill_ids = [s.get("id") for s in skills]
    if len({str(x).casefold() for x in agent_ids}) != len(agent_ids): errors.append("duplicate agent ID")
    if len({str(x).casefold() for x in skill_ids}) != len(skill_ids): errors.append("duplicate skill ID")
    for row in agents:
        missing = REQUIRED_AGENT_FIELDS - row.keys()
        if missing: errors.append(f"agent {row.get('id')} missing {sorted(missing)}")
        if row.get("risk_limit") not in RISK_ORDER: errors.append(f"agent {row.get('id')} invalid risk_limit")
        if row.get("path") and not (root / row["path"]).is_file(): errors.append(f"agent file missing: {row['path']}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(row.get("version", ""))): errors.append(f"agent {row.get('id')} invalid semantic version")
        if row.get("deprecated") and not row.get("superseded_by"): errors.append(f"deprecated agent {row.get('id')} has no replacement")
        for sid in row.get("required_skills", []):
            if sid not in skill_ids: errors.append(f"agent {row.get('id')} references unknown skill {sid}")
    for row in skills:
        missing = REQUIRED_SKILL_FIELDS - row.keys()
        if missing: errors.append(f"skill {row.get('id')} missing {sorted(missing)}")
        if row.get("risk_level") not in RISK_ORDER: errors.append(f"skill {row.get('id')} invalid risk_level")
        if row.get("path") and not (root / row["path"]).is_file(): errors.append(f"skill file missing: {row['path']}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(row.get("version", ""))): errors.append(f"skill {row.get('id')} invalid semantic version")
        if row.get("deprecated") and not row.get("superseded_by"): errors.append(f"deprecated skill {row.get('id')} has no replacement")
        for sid in row.get("dependencies", []) + row.get("conflicts", []):
            if sid not in skill_ids: errors.append(f"skill {row.get('id')} references unknown skill {sid}")
    for rule in routes:
        for aid in rule.get("agents", []):
            if aid not in agent_ids: errors.append(f"route {rule.get('id')} unknown agent {aid}")
        for sid in rule.get("skills", []):
            if sid not in skill_ids: errors.append(f"route {rule.get('id')} unknown skill {sid}")
    try:
        stack = read_json(root / "registry" / "stack_versions_verified.json")["entries"]
        forbidden = re.compile(r"(?i)(alpha|beta|rc|preview|canary|nightly|experimental)")
        for entry in stack:
            datetime.fromisoformat(entry["verified_at"])
            if forbidden.search(str(entry.get("version", ""))) or forbidden.search(str(entry.get("support", ""))):
                errors.append(f"stack {entry.get('technology')} is prerelease")
            if not str(entry.get("source", "")).startswith("https://"):
                errors.append(f"stack {entry.get('technology')} has no official HTTPS source")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"invalid stack registry: {exc}")
    return result("validate_registry", not errors, errors or [f"{len(agents)} agents and {len(skills)} skills resolve"])


def validate_pipeline(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        rows = read_json(root / "pipeline" / "pipeline_definition.json")["stages"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result("validate_pipeline", False, [str(exc)])
    ids = [row.get("id") for row in rows]
    if ids != STAGES: errors.append("pipeline order differs from strict contract")
    known = set(ids)
    for index, row in enumerate(rows):
        expected = ids[index + 1] if index + 1 < len(ids) else None
        if row.get("success_to") != expected: errors.append(f"{row.get('id')} invalid success transition")
        failure = row.get("failure_return_to")
        if row.get("id") != "REQUEST" and failure not in known: errors.append(f"{row.get('id')} invalid failure return")
    return result("validate_pipeline", not errors, errors or [f"{len(rows)} stages and failure loops valid"])


def validate_continuity(root: Path) -> dict[str, Any]:
    missing = [f"continuity/state/{name}.md" for name in CONTINUITY_FILES if not (root / "continuity" / "state" / f"{name}.md").is_file()]
    for extra in ("continuity/CHECKPOINT_PROTOCOL.md", "continuity/HANDOFF_PROTOCOL.md"):
        if not (root / extra).is_file(): missing.append(extra)
    return result("validate_continuity", not missing, missing or [f"{len(CONTINUITY_FILES)} state files present"])


def validate_governance(root: Path) -> dict[str, Any]:
    missing = [f for f in GOVERNANCE_FILES if not (root / "governance" / f).is_file()]
    return result("validate_governance", not missing, missing or [f"{len(GOVERNANCE_FILES)} governance policies present"])


def validate_git_authorship(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    probe = run_git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        return result("validate_git_authorship", False, ["not a Git repository"])
    name = run_git(root, "config", "--local", "--get", "user.name").stdout.strip()
    email = run_git(root, "config", "--local", "--get", "user.email").stdout.strip()
    if name != EXPECTED_AUTHOR: errors.append(f"local user.name is {name!r}, expected {EXPECTED_AUTHOR!r}")
    if email != EXPECTED_EMAIL: errors.append(f"local user.email is {email!r}, expected {EXPECTED_EMAIL!r}")
    log = run_git(root, "log", "--format=%an <%ae>%n%B", "--all")
    if log.returncode == 0:
        forbidden = re.compile(r"Co-authored-by:\s*(Claude|ChatGPT|Gemini|Grok|Mistral|Copilot)", re.I)
        if forbidden.search(log.stdout): errors.append("forbidden AI co-author trailer found")
    return result("validate_git_authorship", not errors, errors or ["local identity and history satisfy policy"])


def validate_task_graph(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    try: tasks = read_json(root / "planning" / "task_graph.json")["tasks"]
    except (OSError, ValueError, KeyError, TypeError) as exc: return result("validate_task_graph", False, [str(exc)])
    required = {"id", "title", "domain", "dependencies", "blocked_by", "parallelizable", "priority", "risk", "agents", "skills", "files", "acceptance_criteria", "quality_gates"}
    ids = [t.get("id") for t in tasks]
    if len(set(ids)) != len(ids): errors.append("duplicate task ID")
    by_id = set(ids)
    graph: dict[str, list[str]] = {}
    for task in tasks:
        missing = required - task.keys()
        if missing: errors.append(f"task {task.get('id')} missing {sorted(missing)}")
        deps = task.get("dependencies", []) + task.get("blocked_by", [])
        graph[str(task.get("id"))] = deps
        for dep in deps:
            if dep not in by_id: errors.append(f"task {task.get('id')} unknown dependency {dep}")
    visiting: set[str] = set(); visited: set[str] = set()
    def visit(node: str) -> None:
        if node in visiting: errors.append(f"cycle at {node}"); return
        if node in visited: return
        visiting.add(node)
        for dep in graph.get(node, []): visit(dep)
        visiting.remove(node); visited.add(node)
    for node in graph: visit(node)
    return result("validate_task_graph", not errors, errors or [f"{len(tasks)} tasks form a DAG"])


def validate_repository_map(root: Path) -> dict[str, Any]:
    fields = {"modules", "paths", "owners", "technologies", "entrypoints", "apis", "database_models", "tests", "dependencies", "runtime_services", "configuration"}
    try: data = read_json(root / "repository" / "REPOSITORY_MAP.json")
    except (OSError, ValueError, TypeError) as exc: return result("validate_repository_map", False, [str(exc)])
    missing = sorted(fields - data.keys())
    return result("validate_repository_map", not missing, [f"missing {x}" for x in missing] or ["repository map schema valid"])


def validate_context(root: Path) -> dict[str, Any]:
    try: data = read_json(root / "context" / "context_state.json")
    except (OSError, ValueError, TypeError) as exc: return result("validate_context", False, [str(exc)])
    errors = []
    if not isinstance(data.get("budget"), int) or data["budget"] <= 0: errors.append("budget must be positive integer")
    if not isinstance(data.get("used"), int) or data.get("used", 0) < 0: errors.append("used must be non-negative integer")
    if data.get("used", 0) > data.get("budget", 0): errors.append("used exceeds budget")
    if not {"policy", "user_request", "decisions"}.issubset(set(data.get("pinned", []))): errors.append("critical context is not pinned")
    return result("validate_context", not errors, errors or ["context budget and pinned items valid"])


def validate_risk(root: Path) -> dict[str, Any]:
    errors = []
    cases = [("documentation typo", "LOW"), ("public API integration", "MEDIUM"), ("role-based login authorization", "HIGH"), ("delete production database", "CRITICAL")]
    for text, expected in cases:
        actual = analyze_risk(text)["level"]
        if actual != expected: errors.append(f"{text!r}: {actual}, expected {expected}")
    return result("validate_risk", not errors, errors or [f"{len(cases)} golden classifications pass"])


def validate_cli(root: Path) -> dict[str, Any]:
    errors = []
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    commands = ["init", "status", "doctor", "analyze", "plan", "agents", "skills", "pipeline", "checkpoint", "handoff", "resume", "validate", "stack", "risk", "graph"]
    for command in commands:
        proc = subprocess.run([sys.executable, "-m", "pallaquino_cli", command, "--help"], cwd=root, env=env, text=True, capture_output=True, check=False)
        if proc.returncode != 0: errors.append(f"{command} --help exited {proc.returncode}")
    return result("validate_cli", not errors, errors or [f"{len(commands)} CLI commands respond to --help"])


VALIDATORS = [validate_registry, validate_pipeline, validate_continuity, validate_governance, validate_git_authorship, validate_task_graph, validate_repository_map, validate_context, validate_risk, validate_cli]


def validate_all(root: Path) -> dict[str, Any]:
    checks = [validator(root) for validator in VALIDATORS]
    return {"ok": all(item["ok"] for item in checks), "checks": checks, "version": VERSION}


def stack_status(root: Path) -> dict[str, Any]:
    data = read_json(root / "registry" / "stack_versions_verified.json")
    today = datetime.now(timezone.utc).date()
    rows = []
    for entry in data["entries"]:
        verified = datetime.fromisoformat(entry["verified_at"]).date()
        age = (today - verified).days
        row = dict(entry); row["age_days"] = age; row["status"] = "STALE" if age > data.get("stale_after_days", STALE_DAYS) else "VERIFIED"
        rows.append(row)
    return {"entries": rows, "ok": all(x["status"] == "VERIFIED" for x in rows)}


def acquire_lock(root: Path, file_path: str, owner: str, task: str, ttl_minutes: int = 60) -> dict[str, Any]:
    target = (root / file_path).resolve()
    try: target.relative_to(root.resolve())
    except ValueError: raise ValueError("lock path escapes framework root")
    state_path = root / "execution" / "file_locks.json"
    state = read_json(state_path)
    key = str(target).casefold()
    for lock in state["locks"]:
        if lock["normalized_path"] == key and lock["owner"] != owner:
            raise RuntimeError(f"file already reserved by {lock['owner']}")
        if lock["normalized_path"] == key:
            return lock
    lock = {"path": file_path.replace("\\", "/"), "normalized_path": key, "owner": owner, "task": task, "acquired_at": utc_now(), "ttl_minutes": ttl_minutes}
    state["locks"].append(lock); state.setdefault("audit", []).append({"event": "acquire", **lock})
    atomic_json(state_path, state)
    return lock


def release_lock(root: Path, file_path: str, owner: str) -> bool:
    state_path = root / "execution" / "file_locks.json"; state = read_json(state_path)
    key = str((root / file_path).resolve()).casefold(); before = len(state["locks"])
    for lock in state["locks"]:
        if lock["normalized_path"] == key and lock["owner"] != owner: raise RuntimeError("only lock owner may release")
    state["locks"] = [x for x in state["locks"] if x["normalized_path"] != key]
    if len(state["locks"]) != before:
        state.setdefault("audit", []).append({"event": "release", "path": file_path, "owner": owner, "timestamp": utc_now()}); atomic_json(state_path, state); return True
    return False


def make_checkpoint(root: Path, task: str = "UNSPECIFIED") -> dict[str, Any]:
    state = (root / "continuity" / "state" / "PIPELINE_STATE.md").read_text(encoding="utf-8")
    match = re.search(r"Current stage:\s*([A-Z_]+)", state)
    payload: dict[str, Any] = {"schema_version": 1, "timestamp": utc_now(), "task": task, "stage": match.group(1) if match else "REQUEST", "git_head": None, "git_diff": "RECONSTRUCTED: unavailable", "evidence": [], "confidence": "medium"}
    git = run_git(root, "rev-parse", "HEAD")
    if git.returncode == 0: payload["git_head"] = git.stdout.strip()
    diff = run_git(root, "status", "--short")
    if diff.returncode == 0: payload["git_diff"] = diff.stdout.splitlines()
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode(); payload["checksum"] = hashlib.sha256(canonical).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = root / "continuity" / "checkpoints" / f"{stamp}.json"; atomic_json(path, payload); payload["path"] = str(path)
    return payload


def verify_checkpoint(data: dict[str, Any]) -> bool:
    checksum = data.get("checksum"); candidate = {k: v for k, v in data.items() if k not in {"checksum", "path"}}
    return checksum == hashlib.sha256(json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def resume(root: Path) -> dict[str, Any]:
    candidates = sorted((root / "continuity" / "checkpoints").glob("*.json"), reverse=True) if (root / "continuity" / "checkpoints").exists() else []
    invalid = []
    for path in candidates:
        try: data = read_json(path)
        except (ValueError, OSError): invalid.append(str(path)); continue
        if verify_checkpoint(data): return {"status": "RECOVERED", "checkpoint": str(path), "state": data, "invalid_skipped": invalid}
        invalid.append(str(path))
    return {"status": "RECONSTRUCTED", "checkpoint": None, "state": {"stage": "REQUEST", "confidence": "low"}, "invalid_skipped": invalid}


def create_handoff(root: Path) -> dict[str, Any]:
    recovery = resume(root)
    payload = {"schema_version": 1, "timestamp": utc_now(), "requested": "See CURRENT_TASK.md", "implemented": "See Git diff and change manifests", "missing": ["Unresolved items in OPEN_QUESTIONS.md"], "assumed": ["See ASSUMPTIONS.md"], "unverified": ["See TEST_STATUS.md"], "breakage_risks": ["See KNOWN_ISSUES.md and risk state"], "current": recovery["state"], "next_action": "Resume at the next strict pipeline stage", "confidence": "medium"}
    atomic_json(root / "continuity" / "HANDOFF.json", payload); return payload


def init_target(source: Path, target: Path) -> dict[str, Any]:
    target.mkdir(parents=True, exist_ok=True); copied = []; skipped = []
    for src in _iter_repository_files(source):
        rel = src.relative_to(source)
        if any(part in {"__pycache__", ".git", "tests"} for part in rel.parts): continue
        dst = target / ".pallaquino" / rel
        if dst.exists(): skipped.append(str(dst)); continue
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst); copied.append(str(dst))
    return {"copied": len(copied), "skipped": len(skipped), "target": str(target.resolve())}


def create_archive(root: Path, archive: Path) -> dict[str, Any]:
    exclusions = {".git", "__pycache__", ".pytest_cache", ".env", "dist"}
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _iter_repository_files(root):
            rel = path.relative_to(root)
            if any(part in exclusions for part in rel.parts) or path.resolve() == archive.resolve() or path.suffix == ".sha256": continue
            zf.write(path, (Path(root.name) / rel).as_posix())
    with zipfile.ZipFile(archive, "r") as zf:
        bad = zf.testzip(); names = zf.namelist()
        traversal = [n for n in names if Path(n).is_absolute() or ".." in Path(n).parts or "\\" in n]
    digest = sha256_file(archive)
    sidecar = archive.with_suffix(".sha256"); sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return {"archive": str(archive), "sha256_file": str(sidecar), "sha256": digest, "entries": len(names), "integrity": bad is None and not traversal, "bad_entry": bad, "unsafe_paths": traversal}
