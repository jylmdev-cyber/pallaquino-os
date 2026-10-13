from __future__ import annotations

import contextlib
import fnmatch
import functools
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

VERSION = "0.3.0"
ROOT_ENV = "PALLAQUINO_ROOT"
# Default commit identity; each project may override it in IDENTITY_FILE (see GIT_AUTHORSHIP_POLICY.md).
EXPECTED_AUTHOR = "jimdev"
EXPECTED_EMAIL = "jylmdev@gmail.com"
IDENTITY_FILE = "governance/git_identity.json"
EMAIL_PATTERN = re.compile(r"[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+")
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
# Checks whose result depends on the host (Git config, clock) rather than on repository content.
ENVIRONMENT_VALIDATORS = {"validate_git_authorship"}
# Per-project files that `init` must regenerate instead of copying from the framework's own state.
DEFAULT_INSTANCE_STATE = [
    "PROJECT_CONTEXT.md", "continuity/HANDOFF.json", "continuity/checkpoints/*",
    "continuity/state/*.md", "evidence/*.json", "changes/*.json", "runtime/capabilities.json",
    "risk/risk_state.json", "execution/file_locks.json", "execution/.file_locks.mutex",
    "context/context_state.json", "repository/REPOSITORY_MAP.json", "repository/REPOSITORY_MAP.md",
    "planning/task_graph.json", "planning/execution_plan.json",
]
CONTINUITY_TITLES = {
    "PROJECT_STATE": "Project state", "CURRENT_TASK": "Current task", "TASK_BOARD": "Task board",
    "ARCHITECTURE_STATE": "Architecture state", "TECH_STACK_STATE": "Technology stack state",
    "TEST_STATUS": "Test status", "KNOWN_ISSUES": "Known issues", "PIPELINE_STATE": "Pipeline state",
    "ASSUMPTIONS": "Assumptions", "OPEN_QUESTIONS": "Open questions",
    "EXTERNAL_DEPENDENCIES": "External dependencies", "TECHNICAL_DEBT": "Technical debt",
}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----"),
    "aws_access_key_id": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"),
    "llm_api_key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "slack_token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}
# Quoted `key = "value"` in any file, or unquoted ENV-style `API_KEY=value`; only group "value" is redacted.
SECRET_ASSIGNMENTS = [
    re.compile(r"(?i)(?P<key>\b[\w.-]*(?:api[_-]?key|secret|password|passwd|token|private[_-]?key)\b)"
               r"(?P<sep>\s*[:=]\s*)(?P<quote>['\"])(?P<value>[^\s'\"]{8,})(?P=quote)"),
    re.compile(r"(?m)^\s*(?:export\s+)?(?P<key>[A-Z0-9_]*(?:API_?KEY|SECRET|PASSWORD|PASSWD|TOKEN|PRIVATE_?KEY)[A-Z0-9_]*)"
               r"(?P<sep>\s*=\s*)(?P<quote>)(?P<value>[^\s'\"#()\[\]{}]{8,})(?=\s|$)"),
]
SECRET_PLACEHOLDERS = re.compile(r"(?i)(example|placeholder|changeme|redacted|dummy|your[_-]|<|\{|xxxx|\*\*\*)")
SCAN_SUFFIXES = {".py", ".json", ".md", ".toml", ".yml", ".yaml", ".txt", ".cfg", ".ini", ".env", ".sh", ".ps1", ".cmd", ".js", ".ts", ".vue", ".cs", ".java", ".go", ".php", ".rb", ".sql", ".xml", ".properties"}
SCAN_MAX_BYTES = 1024 * 1024
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class FrameworkRootNotFound(LookupError):
    """No PALLAQUINO framework root could be resolved from flags, environment or working directory."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def framework_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_framework_root(path: Path) -> bool:
    return (path / "manifest.json").is_file() and (path / "registry").is_dir()


def resolve_root(explicit: Path | None = None, cwd: Path | None = None) -> Path:
    """Resolve the framework root: --root, then $PALLAQUINO_ROOT, then the package checkout, then cwd discovery."""
    if explicit is not None:
        candidate = explicit.resolve()
    elif os.environ.get(ROOT_ENV):
        candidate = Path(os.environ[ROOT_ENV]).resolve()
    elif is_framework_root(framework_root()):
        return framework_root()
    else:
        start = (cwd or Path.cwd()).resolve()
        for folder in (start, *start.parents):
            for option in (folder / ".pallaquino", folder):
                if is_framework_root(option):
                    return option
        raise FrameworkRootNotFound(
            f"no PALLAQUINO root found from {start}; pass --root <dir>, set {ROOT_ENV}, "
            "or run inside a project initialized with `pallaquino init`"
        )
    if not is_framework_root(candidate):
        raise FrameworkRootNotFound(f"{candidate} is not a PALLAQUINO root (expected manifest.json and registry/)")
    return candidate


@functools.lru_cache(maxsize=2048)
def _term_pattern(term: str) -> re.Pattern[str]:
    # Whole-token match with an optional English/Spanish plural, so "prod" never matches "product".
    return re.compile(rf"(?<!\w){re.escape(term.casefold())}(?:s|es)?(?!\w)")


def contains_term(normalized: str, term: str) -> bool:
    return _term_pattern(term).search(normalized) is not None


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
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
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return payload


def _iter_repository_files(root: Path) -> list[Path]:
    # Mirrors the repository .gitignore so build outputs never reach archives, init copies or scans.
    ignored = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", ".venv", "venv", "dist", "build"}
    files: list[Path] = []
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if not path.is_file() or any(part in ignored or part.endswith(".egg-info") for part in parts):
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
    (destination / "repository" / "REPOSITORY_MAP.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    return payload


def redact(text: str) -> str:
    """Replace secret-shaped values with a typed marker before text is persisted or printed."""
    for kind, pattern in SECRET_PATTERNS.items():
        text = pattern.sub(f"[REDACTED:{kind}]", text)
    def mask(match: re.Match[str]) -> str:
        if SECRET_PLACEHOLDERS.search(match.group("value")) or match.group("value").startswith("[REDACTED"):
            return match.group(0)
        return f"{match.group('key')}{match.group('sep')}{match.group('quote')}[REDACTED]{match.group('quote')}"
    for pattern in SECRET_ASSIGNMENTS:
        text = pattern.sub(mask, text)
    return text


def _secret_kinds(line: str) -> list[str]:
    kinds = [kind for kind, pattern in SECRET_PATTERNS.items() if pattern.search(line)]
    for pattern in SECRET_ASSIGNMENTS:
        if any(not SECRET_PLACEHOLDERS.search(m.group("value")) for m in pattern.finditer(line)):
            kinds.append("credential_assignment")
    return kinds


def scan_secrets(target: Path) -> dict[str, Any]:
    """Read-only scan for committed secrets; findings carry path, line and kind but never the value."""
    findings: list[dict[str, Any]] = []
    scanned = 0
    for path in _iter_repository_files(target):
        name = path.name.casefold()
        if name.endswith(".example") or ".example." in name:
            continue
        if path.suffix.lower() not in SCAN_SUFFIXES and not name.startswith(".env"):
            continue
        try:
            if path.stat().st_size > SCAN_MAX_BYTES:
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:1024]:
            continue
        scanned += 1
        for number, line in enumerate(raw.decode("utf-8", errors="ignore").splitlines(), 1):
            for kind in _secret_kinds(line):
                findings.append({"path": path.relative_to(target).as_posix(), "line": number, "kind": kind})
    return {"ok": not findings, "target": str(target.resolve()), "files_scanned": scanned, "findings": findings}


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
    factors = [factor for factor, terms in factor_terms.items() if any(contains_term(normalized, term) for term in terms)]
    high = {"authentication", "authorization", "payments", "financial_data", "personal_data", "database_migrations", "security"}
    medium = {"public_api", "infrastructure", "external_integrations"}
    level = "LOW"
    if set(factors) & medium:
        level = "MEDIUM"
    if set(factors) & high or "production" in factors or "data_deletion" in factors:
        level = "HIGH"
    if "production" in factors and "data_deletion" in factors or contains_term(normalized, "drop database") or contains_term(normalized, "destroy infrastructure"):
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
        hits = sum(1 for word in rule["keywords"] if contains_term(normalized, word))
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
        technologies = read_json(root / "registry" / "technology_catalog.json")["technologies"]
        profiles = read_json(root / "registry" / "stack_profiles.json")["profiles"]
        compatibility = read_json(root / "registry" / "technology_compatibility.json")["rules"]
        domain_packs = read_json(root / "registry" / "domain_packs.json")["packs"]
        coverage = read_json(root / "registry" / "agent_skill_coverage.json")["coverage"]
        read_json(root / "registry" / "stack_versions_verified.json")
        read_json(root / "registry" / "capabilities.json")
        read_json(root / "registry" / "modes.json")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return result("validate_registry", False, [f"cannot load registry: {exc}"])
    agent_ids = [a.get("id") for a in agents]
    skill_ids = [s.get("id") for s in skills]
    technology_ids = [t.get("id") for t in technologies]
    if len({str(x).casefold() for x in agent_ids}) != len(agent_ids): errors.append("duplicate agent ID")
    if len({str(x).casefold() for x in skill_ids}) != len(skill_ids): errors.append("duplicate skill ID")
    if len({str(x).casefold() for x in technology_ids}) != len(technology_ids): errors.append("duplicate technology ID")
    for row in agents:
        missing = REQUIRED_AGENT_FIELDS - row.keys()
        if missing: errors.append(f"agent {row.get('id')} missing {sorted(missing)}")
        if row.get("risk_limit") not in RISK_ORDER: errors.append(f"agent {row.get('id')} invalid risk_limit")
        if row.get("path") and not (root / row["path"]).is_file(): errors.append(f"agent file missing: {row['path']}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(row.get("version", ""))): errors.append(f"agent {row.get('id')} invalid semantic version")
        if row.get("deprecated") and not row.get("superseded_by"): errors.append(f"deprecated agent {row.get('id')} has no replacement")
        for sid in row.get("required_skills", []):
            if sid not in skill_ids: errors.append(f"agent {row.get('id')} references unknown skill {sid}")
        for tid in row.get("technologies", []):
            if tid not in technology_ids: errors.append(f"agent {row.get('id')} references unknown technology {tid}")
    for row in skills:
        missing = REQUIRED_SKILL_FIELDS - row.keys()
        if missing: errors.append(f"skill {row.get('id')} missing {sorted(missing)}")
        if row.get("risk_level") not in RISK_ORDER: errors.append(f"skill {row.get('id')} invalid risk_level")
        if row.get("path") and not (root / row["path"]).is_file(): errors.append(f"skill file missing: {row['path']}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(row.get("version", ""))): errors.append(f"skill {row.get('id')} invalid semantic version")
        if row.get("deprecated") and not row.get("superseded_by"): errors.append(f"deprecated skill {row.get('id')} has no replacement")
        for sid in row.get("dependencies", []) + row.get("conflicts", []):
            if sid not in skill_ids: errors.append(f"skill {row.get('id')} references unknown skill {sid}")
        for tid in row.get("technologies", []):
            if tid not in technology_ids: errors.append(f"skill {row.get('id')} references unknown technology {tid}")
    for rule in routes:
        for aid in rule.get("agents", []):
            if aid not in agent_ids: errors.append(f"route {rule.get('id')} unknown agent {aid}")
        for sid in rule.get("skills", []):
            if sid not in skill_ids: errors.append(f"route {rule.get('id')} unknown skill {sid}")
    profile_ids = [profile.get("id") for profile in profiles]
    if len(set(profile_ids)) != len(profile_ids): errors.append("duplicate stack profile ID")
    for profile in profiles:
        for tid in profile.get("technologies", []):
            if tid not in technology_ids: errors.append(f"profile {profile.get('id')} unknown technology {tid}")
        for aid in profile.get("agents", []):
            if aid not in agent_ids: errors.append(f"profile {profile.get('id')} unknown agent {aid}")
        for sid in profile.get("skills", []):
            if sid not in skill_ids: errors.append(f"profile {profile.get('id')} unknown skill {sid}")
        for gate in profile.get("required_gates", []):
            if gate not in STAGES and not (root / "pipeline" / "gates" / f"{gate}.md").is_file(): errors.append(f"profile {profile.get('id')} missing gate {gate}")
        if profile.get("version_status") != "VERIFY_BEFORE_USE": errors.append(f"profile {profile.get('id')} must require version verification")
    for rule in compatibility:
        when = rule.get("when")
        if when != "profile_activation" and when not in technology_ids: errors.append(f"compatibility {rule.get('id')} unknown technology {when}")
        for tid in rule.get("requires", []):
            if tid not in technology_ids: errors.append(f"compatibility {rule.get('id')} unknown requirement {tid}")
    for pack in domain_packs:
        for aid in pack.get("agents", []):
            if aid not in agent_ids: errors.append(f"domain pack {pack.get('id')} unknown agent {aid}")
        for sid in pack.get("skills", []):
            if sid not in skill_ids: errors.append(f"domain pack {pack.get('id')} unknown skill {sid}")
    coverage_ids = [row.get("technology") for row in coverage]
    if set(coverage_ids) != set(technology_ids): errors.append("agent/skill coverage does not match technology catalog")
    for row in coverage:
        for aid in row.get("agents", []):
            if aid not in agent_ids: errors.append(f"coverage {row.get('technology')} unknown agent {aid}")
        for sid in row.get("skills", []):
            if sid not in skill_ids: errors.append(f"coverage {row.get('technology')} unknown skill {sid}")
    try:
        stack = read_json(root / "registry" / "stack_versions_verified.json")["entries"]
        forbidden = re.compile(r"(?i)(alpha|beta|rc|preview|canary|nightly|experimental)")
        for entry in stack:
            datetime.fromisoformat(entry["verified_at"])
            if forbidden.search(str(entry.get("version", ""))) or forbidden.search(str(entry.get("support", ""))):
                errors.append(f"stack {entry.get('technology')} is prerelease")
            if not str(entry.get("source", "")).startswith("https://"):
                errors.append(f"stack {entry.get('technology')} has no official HTTPS source")
            if entry.get("technology") not in technology_ids:
                errors.append(f"verified stack has uncatalogued technology {entry.get('technology')}")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"invalid stack registry: {exc}")
    return result("validate_registry", not errors, errors or [f"{len(agents)} agents, {len(skills)} skills, {len(technology_ids)} technologies and {len(profiles)} profiles resolve"])


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


def _identity_errors(name: Any, email: Any) -> list[str]:
    errors = []
    if not isinstance(name, str) or not name.strip() or any(ch in name for ch in "\r\n<>"): errors.append("identity name must be a non-empty single line without <>")
    if not isinstance(email, str) or not EMAIL_PATTERN.fullmatch(email): errors.append("identity email is not a valid address")
    return errors


def load_git_identity(root: Path) -> dict[str, Any]:
    """Expected commit identity for this project: governance/git_identity.json, else the jimdev default."""
    path = root / IDENTITY_FILE
    if not path.is_file():
        return {"name": EXPECTED_AUTHOR, "email": EXPECTED_EMAIL, "source": "default", "errors": []}
    try: data = read_json(path)
    except (OSError, ValueError) as exc: return {"name": EXPECTED_AUTHOR, "email": EXPECTED_EMAIL, "source": IDENTITY_FILE, "errors": [f"cannot read {IDENTITY_FILE}: {exc}"]}
    data = data if isinstance(data, dict) else {}
    return {"name": data.get("name"), "email": data.get("email"), "source": IDENTITY_FILE, "errors": _identity_errors(data.get("name"), data.get("email"))}


def set_git_identity(root: Path, name: str, email: str) -> dict[str, Any]:
    name = name.strip(); email = email.strip(); errors = _identity_errors(name, email)
    if errors: raise ValueError("; ".join(errors))
    atomic_json(root / IDENTITY_FILE, {"schema_version": 1, "name": name, "email": email})
    return load_git_identity(root)


def git_identity_status(root: Path, apply_local: bool = False) -> dict[str, Any]:
    """Compare the expected identity with the repository-local Git config; optionally set the local config only."""
    expected = load_git_identity(root)
    if expected["errors"]: raise ValueError("; ".join(expected["errors"]))
    if run_git(root, "rev-parse", "--is-inside-work-tree").returncode != 0:
        return {"ok": False, "expected": expected, "local": None, "matches": False, "applied": False, "error": "not a Git repository"}
    if apply_local:
        for key, value in (("user.name", expected["name"]), ("user.email", expected["email"])):
            if run_git(root, "config", "--local", key, value).returncode != 0: raise RuntimeError(f"cannot set local {key}")
    local = {"name": run_git(root, "config", "--local", "--get", "user.name").stdout.strip(), "email": run_git(root, "config", "--local", "--get", "user.email").stdout.strip()}
    matches = local == {"name": expected["name"], "email": expected["email"]}
    return {"ok": matches, "expected": expected, "local": local, "matches": matches, "applied": apply_local, "repository": str(git_repository_root(root))}


def validate_governance(root: Path) -> dict[str, Any]:
    missing = [f for f in GOVERNANCE_FILES if not (root / "governance" / f).is_file()]
    identity = load_git_identity(root)
    errors = missing + identity["errors"]
    return result("validate_governance", not errors, errors or [f"{len(GOVERNANCE_FILES)} governance policies present; identity from {identity['source']}"])


def validate_git_authorship(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    probe = run_git(root, "rev-parse", "--is-inside-work-tree")
    if probe.returncode != 0:
        return result("validate_git_authorship", False, ["not a Git repository"])
    expected = load_git_identity(root)
    if expected["errors"]: return result("validate_git_authorship", False, expected["errors"])
    name = run_git(root, "config", "--local", "--get", "user.name").stdout.strip()
    email = run_git(root, "config", "--local", "--get", "user.email").stdout.strip()
    if name != expected["name"]: errors.append(f"local user.name is {name!r}, expected {expected['name']!r} ({expected['source']})")
    if email != expected["email"]: errors.append(f"local user.email is {email!r}, expected {expected['email']!r} ({expected['source']})")
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
    try:
        agent_ids = {a["id"] for a in read_json(root / "registry" / "agents.json")["agents"]}
        skill_ids = {s["id"] for s in read_json(root / "registry" / "skills.json")["skills"]}
    except (OSError, ValueError, KeyError, TypeError):
        agent_ids = skill_ids = None
    graph: dict[str, list[str]] = {}
    for task in tasks:
        missing = required - task.keys()
        if missing: errors.append(f"task {task.get('id')} missing {sorted(missing)}")
        deps = task.get("dependencies", []) + task.get("blocked_by", [])
        graph[str(task.get("id"))] = deps
        for dep in deps:
            if dep not in by_id: errors.append(f"task {task.get('id')} unknown dependency {dep}")
        if agent_ids is not None:
            for aid in task.get("agents", []):
                if aid not in agent_ids: errors.append(f"task {task.get('id')} unknown agent {aid}")
            for sid in task.get("skills", []):
                if sid not in skill_ids: errors.append(f"task {task.get('id')} unknown skill {sid}")
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


CLI_COMMANDS = ["init", "status", "doctor", "analyze", "plan", "agents", "skills", "pipeline", "checkpoint", "handoff", "resume", "validate", "stack", "risk", "graph", "security", "identity"]
# Runs inside a child interpreter whose sys.path[0] is the validated root, so an extracted archive tests its own CLI.
_CLI_PROBE = """
import contextlib, io, json, sys
from pallaquino_cli.__main__ import parser
failed = []
for command in json.loads(sys.argv[1]):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            parser().parse_args([command, "--help"])
        failed.append(f"{command} --help did not exit")
    except SystemExit as exc:
        if exc.code not in (0, None): failed.append(f"{command} --help exited {exc.code}")
print(json.dumps(failed))
"""


def validate_cli(root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", _CLI_PROBE, json.dumps(CLI_COMMANDS)], cwd=root, env=env, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        return result("validate_cli", False, [f"CLI probe exited {proc.returncode}: {proc.stderr.strip()[-500:]}"])
    errors = json.loads(proc.stdout.strip().splitlines()[-1])
    return result("validate_cli", not errors, errors or [f"{len(CLI_COMMANDS)} CLI commands respond to --help"])


VALIDATORS = [validate_registry, validate_pipeline, validate_continuity, validate_governance, validate_git_authorship, validate_task_graph, validate_repository_map, validate_context, validate_risk, validate_cli]


def validate_all(root: Path, include_environment: bool = True) -> dict[str, Any]:
    """Run validators; `include_environment=False` keeps only checks that depend solely on repository content."""
    checks = []
    for validator in VALIDATORS:
        scope = "environment" if validator.__name__ in ENVIRONMENT_VALIDATORS else "integrity"
        if scope == "environment" and not include_environment:
            continue
        checks.append({**validator(root), "scope": scope})
    return {"ok": all(item["ok"] for item in checks), "checks": checks, "version": VERSION}


def stack_status(root: Path, today: date | None = None) -> dict[str, Any]:
    data = read_json(root / "registry" / "stack_versions_verified.json")
    today = today or datetime.now(timezone.utc).date()
    rows = []
    for entry in data["entries"]:
        verified = datetime.fromisoformat(entry["verified_at"]).date()
        age = (today - verified).days
        row = dict(entry); row["age_days"] = age; row["status"] = "STALE" if age > data.get("stale_after_days", STALE_DAYS) else "VERIFIED"
        rows.append(row)
    return {"entries": rows, "ok": all(x["status"] == "VERIFIED" for x in rows)}


def _lock_key(root: Path, file_path: str) -> str:
    # Root-relative and case-folded: stable across machines and never leaks absolute host paths.
    target = (root / file_path).resolve()
    try: return target.relative_to(root.resolve()).as_posix().casefold()
    except ValueError: raise ValueError("lock path escapes framework root") from None


@contextlib.contextmanager
def _lock_state(root: Path, timeout: float = 10.0, stale_after: float = 60.0) -> Iterator[dict[str, Any]]:
    """Serialize read-modify-write of file_locks.json across processes with an O_EXCL mutex file."""
    state_path = root / "execution" / "file_locks.json"; mutex = state_path.with_name(".file_locks.mutex")
    deadline = time.monotonic() + timeout
    while True:
        try:
            os.close(os.open(mutex, os.O_CREAT | os.O_EXCL | os.O_WRONLY)); break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - mutex.stat().st_mtime > stale_after: mutex.unlink(); continue
            if time.monotonic() > deadline: raise RuntimeError(f"lock registry busy: {mutex}") from None
            time.sleep(0.05)
    try:
        state = read_json(state_path)
        now = datetime.now(timezone.utc); kept = []
        for lock in state["locks"]:
            if Path(lock["normalized_path"]).is_absolute():  # written by <=0.2.1
                lock["normalized_path"] = _lock_key(root, lock["path"])
            expires = datetime.fromisoformat(lock["acquired_at"]) + timedelta(minutes=int(lock.get("ttl_minutes", 60)))
            if expires <= now: state.setdefault("audit", []).append({"event": "expire", "path": lock["path"], "owner": lock["owner"], "timestamp": utc_now()})
            else: kept.append(lock)
        state["locks"] = kept
        yield state
        atomic_json(state_path, state)
    finally:
        with contextlib.suppress(OSError): mutex.unlink()


def acquire_lock(root: Path, file_path: str, owner: str, task: str, ttl_minutes: int = 60) -> dict[str, Any]:
    key = _lock_key(root, file_path)
    with _lock_state(root) as state:
        for lock in state["locks"]:
            if lock["normalized_path"] == key and lock["owner"] != owner:
                raise RuntimeError(f"file already reserved by {lock['owner']}")
            if lock["normalized_path"] == key:
                return lock
        lock = {"path": file_path.replace("\\", "/"), "normalized_path": key, "owner": owner, "task": task, "acquired_at": utc_now(), "ttl_minutes": ttl_minutes}
        state["locks"].append(lock); state.setdefault("audit", []).append({"event": "acquire", **lock})
    return lock


def release_lock(root: Path, file_path: str, owner: str) -> bool:
    key = _lock_key(root, file_path)
    with _lock_state(root) as state:
        before = len(state["locks"])
        for lock in state["locks"]:
            if lock["normalized_path"] == key and lock["owner"] != owner: raise RuntimeError("only lock owner may release")
        state["locks"] = [x for x in state["locks"] if x["normalized_path"] != key]
        released = len(state["locks"]) != before
        if released: state.setdefault("audit", []).append({"event": "release", "path": file_path.replace("\\", "/"), "owner": owner, "timestamp": utc_now()})
    return released


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


def _state_text(root: Path, name: str) -> str:
    path = root / "continuity" / "state" / f"{name}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _md_field(text: str, label: str) -> str | None:
    match = re.search(rf"^- {re.escape(label)}:\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def _md_bullets(text: str) -> list[str]:
    return [line[2:].strip() for line in text.splitlines() if line.startswith("- ") and not line.startswith("- Confidence:")]


def create_handoff(root: Path, next_action: str | None = None, missing: Iterable[str] = (), unverified: Iterable[str] = ()) -> dict[str, Any]:
    """Build the handoff from recorded state; anything not recorded is marked NOT_RECORDED instead of assumed empty."""
    recovery = resume(root)
    current = _state_text(root, "CURRENT_TASK"); task = _md_field(current, "ID")
    manifest_path = root / "changes" / f"{task}.json" if task else None
    manifest = read_json(manifest_path) if manifest_path and manifest_path.is_file() else None
    implemented = (manifest.get("files_created", []) + manifest.get("files_modified", [])) if manifest else [f"NOT_RECORDED: no change manifest changes/{task}.json"]
    missing, unverified = list(missing), list(unverified)
    confidence = "low" if recovery["status"] != "RECOVERED" else ("high" if manifest and not unverified else "medium")
    payload = {
        "schema_version": 1, "timestamp": utc_now(), "task": task,
        "requested": _md_field(current, "Objective") or "NOT_RECORDED: CURRENT_TASK.md has no Objective",
        "implemented": implemented, "missing": missing or ["NOT_RECORDED"], "assumed": _md_bullets(_state_text(root, "ASSUMPTIONS")),
        "unverified": unverified or ["NOT_RECORDED"], "breakage_risks": _md_bullets(_state_text(root, "KNOWN_ISSUES")),
        "open_questions": _md_bullets(_state_text(root, "OPEN_QUESTIONS")), "current": recovery["state"],
        "next_action": next_action or _md_field(_state_text(root, "PIPELINE_STATE"), "Next") or "NOT_RECORDED: state the exact next action",
        "confidence": confidence,
    }
    atomic_json(root / "continuity" / "HANDOFF.json", payload); return payload


def instance_state_patterns(source: Path) -> list[str]:
    try: return list(read_json(source / "manifest.json").get("instance_state", DEFAULT_INSTANCE_STATE))
    except (OSError, ValueError, AttributeError): return list(DEFAULT_INSTANCE_STATE)


def is_instance_state(rel: str, patterns: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(rel, pattern) for pattern in patterns)


def fresh_instance_state(today: str | None = None) -> dict[str, str]:
    """Clean per-project state written by `init`, so a new project never inherits another project's history."""
    today = today or datetime.now(timezone.utc).date().isoformat()
    files: dict[str, str] = {}
    for name, title in CONTINUITY_TITLES.items():
        body = {"CURRENT_TASK": "- ID: none\n- Objective: record the first request here\n- Status: NOT_STARTED\n",
                "PIPELINE_STATE": "- Status: not_started\n- Current stage: REQUEST\n- Next: record the first request, then run doctor and analyze\n"}.get(name, "- Status: not_recorded\n")
        files[f"continuity/state/{name}.md"] = f"# {title}\n\n{body}- Updated: {today}\n- Confidence: low\n"
    files["PROJECT_CONTEXT.md"] = "# Project context\n\n- Mode: UNSET\n- Autonomy: STANDARD\n- Objective: UNSET\n- Non-goals: UNSET\n- Confidence: low\n"
    as_json = lambda value: json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    files["risk/risk_state.json"] = as_json({"schema_version": 1, "level": "LOW", "factors": [], "required_gates": ["TEST", "LINT_TYPECHECK", "CODE_REVIEW"], "confidence": "low", "analyzed_at": None})
    files["execution/file_locks.json"] = as_json({"schema_version": 1, "locks": [], "audit": []})
    files["context/context_state.json"] = as_json({"schema_version": 1, "budget": 100, "used": 0, "pinned": ["policy", "user_request", "decisions"], "loaded": [], "omitted": [], "summaries": []})
    files["repository/REPOSITORY_MAP.json"] = as_json({"schema_version": 1, "generated_at": None, "root": None, "modules": [], "paths": [], "owners": {}, "technologies": [], "entrypoints": [], "apis": [], "database_models": [], "tests": [], "dependencies": [], "runtime_services": [], "configuration": [], "statistics": {"files": 0, "extensions": {}}})
    files["repository/REPOSITORY_MAP.md"] = "# Repository map\n\nNot generated yet. Run `pallaquino analyze --target <repository>`.\n"
    files["planning/task_graph.json"] = as_json({"schema_version": 1, "tasks": []})
    files["planning/execution_plan.json"] = as_json({"schema_version": 1, "steps": []})
    return files


def init_target(source: Path, target: Path, dry_run: bool = False) -> dict[str, Any]:
    """Install the framework into <target>/.pallaquino without overwriting files or copying source instance state."""
    destination = (target / ".pallaquino").resolve()
    if destination == source.resolve():  # re-running init from inside an initialized project stays a no-op
        return {"copied": 0, "skipped": 0, "initialized_state": [], "excluded_source_state": 0, "target": str(target.resolve()), "dry_run": dry_run, "already_initialized": True}
    if source.resolve() in destination.parents:
        raise ValueError(f"refusing to initialize inside the framework source: {destination}")
    patterns = instance_state_patterns(source); copied = []; skipped = []; initialized = []; excluded = 0
    for src in _iter_repository_files(source):
        rel = src.relative_to(source)
        if any(part in {"__pycache__", ".git", "tests"} for part in rel.parts): continue
        if is_instance_state(rel.as_posix(), patterns): excluded += 1; continue
        dst = destination / rel
        if dst.exists(): skipped.append(str(dst)); continue
        if not dry_run: dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
        copied.append(str(dst))
    for rel, content in fresh_instance_state().items():
        dst = destination / rel
        if dst.exists(): skipped.append(str(dst)); continue
        if not dry_run: dst.parent.mkdir(parents=True, exist_ok=True); dst.write_text(content, encoding="utf-8", newline="\n")
        initialized.append(rel)
    payload = {"copied": 0 if dry_run else len(copied), "skipped": len(skipped), "initialized_state": initialized, "excluded_source_state": excluded, "target": str(target.resolve()), "dry_run": dry_run}
    if dry_run: payload["planned"] = len(copied)
    return payload


def _zip_date_time() -> tuple[int, int, int, int, int, int]:
    # Fixed (or SOURCE_DATE_EPOCH) timestamps make the archive depend only on content, not on checkout mtimes.
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if not epoch: return FIXED_ZIP_TIME
    stamp = datetime.fromtimestamp(max(int(epoch), 315532800), timezone.utc)
    return (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)


def create_archive(root: Path, archive: Path) -> dict[str, Any]:
    exclusions = {".git", "__pycache__", ".pytest_cache", ".env", "dist"}
    archive.parent.mkdir(parents=True, exist_ok=True); date_time = _zip_date_time()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in _iter_repository_files(root):
            rel = path.relative_to(root)
            if any(part in exclusions for part in rel.parts) or path.resolve() == archive.resolve() or path.suffix == ".sha256": continue
            if path.name.startswith(".env") and path.name != ".env.example": continue
            data = path.read_bytes()
            info = zipfile.ZipInfo((Path(root.name) / rel).as_posix(), date_time=date_time)
            info.create_system = 3; info.external_attr = (0o100755 if data.startswith(b"#!") else 0o100644) << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    with zipfile.ZipFile(archive, "r") as zf:
        bad = zf.testzip(); names = zf.namelist()
        traversal = [n for n in names if Path(n).is_absolute() or ".." in Path(n).parts or "\\" in n]
    digest = sha256_file(archive)
    sidecar = archive.with_suffix(".sha256"); sidecar.write_text(f"{digest}  {archive.name}\n", encoding="ascii", newline="\n")
    return {"archive": str(archive), "sha256_file": str(sidecar), "sha256": digest, "entries": len(names), "integrity": bad is None and not traversal, "bad_entry": bad, "unsafe_paths": traversal}
