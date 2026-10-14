"""Regression tests for the PAL-005 (0.3.0) audit findings; each class names the finding it locks down."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from pallaquino_cli import core
from pallaquino_cli.core import (
    FrameworkRootNotFound, acquire_lock, analyze_risk, create_archive, create_handoff,
    git_identity_status, init_target, load_git_identity, read_json, redact, release_lock,
    resolve_root, resume, route_request, scan_secrets, set_git_identity, validate_all,
    validate_git_authorship, validate_task_graph,
)

ROOT = Path(__file__).resolve().parents[1]
# Assembled at runtime so this source file never contains a secret-shaped literal.
FAKE_AWS_KEY = "AKIA" + "Q" * 16
FAKE_GITHUB_TOKEN = "ghp_" + "a1B2" * 9


def snapshot(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


class ClassifierBoundaryTests(unittest.TestCase):
    """Finding: substring matching made 'product' production and 'authors' authentication (HIGH)."""

    def test_risk_goldens(self) -> None:
        for case in read_json(ROOT / "evaluation/risk_golden.json")["cases"]:
            self.assertEqual(analyze_risk(case["request"])["level"], case["level"], case)

    def test_short_routing_keywords_need_whole_tokens(self) -> None:
        routed = route_request(ROOT, "improve storage layout and compose purpose")
        self.assertEqual(routed["matched_rules"], [])
        self.assertIn("ai_rag", {m["rule"] for m in route_request(ROOT, "build a RAG assistant")["matched_rules"]})

    def test_plural_and_accented_terms_still_match(self) -> None:
        self.assertIn("payments", analyze_risk("refund payments")["matched_factors"])
        self.assertIn("authentication", analyze_risk("agregar autenticación")["matched_factors"])
        self.assertIn("django_auth", {m["rule"] for m in route_request(ROOT, "add authentication to Django")["matched_rules"]})


class InitIsolationTests(unittest.TestCase):
    """Finding: init copied the framework's own task, checkpoints and evidence into every new project."""

    def test_new_project_starts_clean_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = init_target(ROOT, Path(temp))
            project = Path(temp) / ".pallaquino"
            self.assertGreater(report["copied"], 0)
            self.assertGreater(report["excluded_source_state"], 0)
            self.assertFalse(list((project / "continuity").glob("checkpoints/*.json")))
            self.assertFalse(list(project.glob("evidence/*.json")))
            self.assertFalse(list(project.glob("changes/*.json")))
            self.assertTrue((project / "evidence/README.md").is_file())
            self.assertIn("- ID: none", (project / "continuity/state/CURRENT_TASK.md").read_text(encoding="utf-8"))
            self.assertEqual(read_json(project / "planning/task_graph.json")["tasks"], [])
            self.assertEqual(resume(project)["status"], "RECONSTRUCTED")
            self.assertTrue(validate_all(project, include_environment=False)["ok"])

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = init_target(ROOT, Path(temp), dry_run=True)
            self.assertTrue(report["dry_run"]); self.assertEqual(report["copied"], 0); self.assertGreater(report["planned"], 0)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_existing_installation_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            legacy = Path(temp) / ".pallaquino/continuity/state/CURRENT_TASK.md"
            legacy.parent.mkdir(parents=True); legacy.write_text("# Current task\n\n- ID: LEGACY-1\n", encoding="utf-8")
            init_target(ROOT, Path(temp))
            self.assertIn("LEGACY-1", legacy.read_text(encoding="utf-8"))

    def test_refuses_to_install_inside_framework_source(self) -> None:
        with self.assertRaises(ValueError):
            init_target(ROOT, ROOT, dry_run=True)

    def test_reinit_from_inside_initialized_project_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            init_target(ROOT, Path(temp)); project = Path(temp) / ".pallaquino"; before = snapshot(project)
            self.assertTrue(init_target(project, Path(temp))["already_initialized"])
            self.assertEqual(snapshot(project), before)


class RootResolutionTests(unittest.TestCase):
    """Finding: a non-editable install resolved the root to site-packages and every command failed."""

    def test_environment_variable_and_explicit_root(self) -> None:
        with mock.patch.dict(os.environ, {core.ROOT_ENV: str(ROOT)}):
            self.assertEqual(resolve_root(), ROOT)
        with tempfile.TemporaryDirectory() as temp, self.assertRaises(FrameworkRootNotFound):
            resolve_root(Path(temp))

    def test_discovers_initialized_project_from_cwd_when_package_has_no_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            init_target(ROOT, Path(temp)); nested = Path(temp) / "src/app"; nested.mkdir(parents=True)
            empty = Path(temp) / "site-packages"; empty.mkdir()
            with mock.patch.object(core, "framework_root", return_value=empty), mock.patch.dict(os.environ, {}, clear=False), tempfile.TemporaryDirectory() as unrelated:
                os.environ.pop(core.ROOT_ENV, None)
                self.assertEqual(resolve_root(cwd=nested), (Path(temp) / ".pallaquino").resolve())
                with self.assertRaises(FrameworkRootNotFound):
                    resolve_root(cwd=Path(unrelated))


class SecretHandlingTests(unittest.TestCase):
    """Finding: fitness counted 4 rules but enforced one weak regex; evidence stored raw command output."""

    def test_scan_reports_location_and_kind_but_never_the_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "settings.py").write_text(f'AWS = "{FAKE_AWS_KEY}"\npassword = "changeme-example"\n', encoding="utf-8")
            (root / ".env").write_text(f"GITHUB_TOKEN={FAKE_GITHUB_TOKEN}\n", encoding="utf-8")
            (root / ".env.example").write_text("API_KEY=replace-with-your-key\n", encoding="utf-8")
            report = scan_secrets(root)
            self.assertFalse(report["ok"])
            kinds = {(f["path"], f["kind"]) for f in report["findings"]}
            self.assertIn(("settings.py", "aws_access_key_id"), kinds)
            self.assertIn((".env", "github_token"), kinds)
            self.assertFalse(any(f["path"] == ".env.example" for f in report["findings"]))
            self.assertNotIn(FAKE_AWS_KEY, json.dumps(report)); self.assertNotIn(FAKE_GITHUB_TOKEN, json.dumps(report))

    def test_tracked_text_has_no_control_characters(self) -> None:
        # Regression: a shell "\a" escape once wrote a BEL byte into CHANGELOG.md.
        repo = ROOT.parent
        names = subprocess.run(["git", "-C", str(repo), "ls-files"], capture_output=True, text=True, check=True).stdout.splitlines()
        bad = [name for name in names if Path(name).suffix.lower() not in {".zip", ".png", ".jpg", ".gif", ".webp"}
               and any(b < 32 and b not in (9, 10, 13) for b in (repo / name).read_bytes())]
        self.assertEqual(bad, [])

    def test_redact_masks_values_and_keeps_keys(self) -> None:
        text = redact(f"export API_KEY=abcdef123456\ntoken: '{FAKE_GITHUB_TOKEN}'\nkey={FAKE_AWS_KEY}")
        self.assertIn("API_KEY=[REDACTED]", text)
        self.assertNotIn("abcdef123456", text); self.assertNotIn(FAKE_GITHUB_TOKEN, text); self.assertNotIn(FAKE_AWS_KEY, text)
        self.assertEqual(redact('password = "changeme-example"'), 'password = "changeme-example"')

    def test_framework_tree_is_clean_and_fitness_is_honest(self) -> None:
        self.assertTrue(scan_secrets(ROOT)["ok"], scan_secrets(ROOT)["findings"])
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/architecture_fitness.py")], text=True, capture_output=True, check=False)
        report = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(report["enforced"], ["no_secrets"])
        self.assertEqual(len(report["enforced"]) + len(report["not_enforced"]), report["rules"])


class GeneratorSafetyTests(unittest.TestCase):
    """Finding: scaffold/expand generators overwrote all policies, registries and state with no confirmation."""

    def test_generators_are_dry_run_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "framework"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            before = snapshot(copy)
            for script in ("scripts/scaffold_framework.py", "scripts/expand_catalog.py"):
                proc = subprocess.run([sys.executable, str(copy / script)], text=True, capture_output=True, check=False)
                self.assertEqual(proc.returncode, 0, proc.stderr); self.assertIn("DRY RUN", proc.stdout)
            self.assertEqual(snapshot(copy), before)

    def test_scaffold_write_preserves_verified_stack_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp) / "framework"
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns("__pycache__", "tests"))
            registry = copy / "registry/stack_versions_verified.json"; before = registry.read_bytes()
            proc = subprocess.run([sys.executable, str(copy / "scripts/scaffold_framework.py"), "--write"], text=True, capture_output=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(registry.read_bytes(), before)


class LockTests(unittest.TestCase):
    """Finding: lock TTL was never enforced, release accepted any path, keys embedded absolute host paths."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name); (self.root / "execution").mkdir()
        self.state = self.root / "execution/file_locks.json"
        self.state.write_text('{"schema_version":1,"locks":[],"audit":[]}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_expired_lock_is_reclaimable_and_audited(self) -> None:
        acquire_lock(self.root, "src/a.py", "agent-a", "T-1", ttl_minutes=5)
        data = read_json(self.state)
        data["locks"][0]["acquired_at"] = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        self.state.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(acquire_lock(self.root, "src/a.py", "agent-b", "T-2")["owner"], "agent-b")
        self.assertIn("expire", [event["event"] for event in read_json(self.state)["audit"]])

    def test_keys_are_relative_and_release_is_confined(self) -> None:
        lock = acquire_lock(self.root, "src\\B.py", "agent-a", "T-1")
        self.assertEqual(lock["normalized_path"], "src/b.py")
        with self.assertRaises(RuntimeError): acquire_lock(self.root, "src/b.py", "agent-b", "T-2")  # same file on every OS
        with self.assertRaises(ValueError): acquire_lock(self.root, "..\\outside", "agent-a", "T-1")
        self.assertNotIn(str(self.root).casefold(), self.state.read_text(encoding="utf-8").casefold())
        with self.assertRaises(ValueError): release_lock(self.root, "../outside", "agent-a")
        self.assertTrue(release_lock(self.root, "src/b.py", "agent-a"))
        self.assertFalse((self.root / "execution/.file_locks.mutex").exists())

    def test_concurrent_processes_never_lose_reservations(self) -> None:
        code = "import sys; from pathlib import Path; from pallaquino_cli.core import acquire_lock; acquire_lock(Path(sys.argv[1]), f'src/f{sys.argv[2]}.py', f'agent-{sys.argv[2]}', 'T')"
        env = {**os.environ, "PYTHONPATH": str(ROOT)}
        workers = [subprocess.Popen([sys.executable, "-c", code, str(self.root), str(n)], env=env) for n in range(8)]
        self.assertEqual([w.wait(timeout=60) for w in workers], [0] * 8)
        self.assertEqual(len(read_json(self.state)["locks"]), 8)

    def test_legacy_absolute_keys_are_migrated(self) -> None:
        legacy = {"path": "src/c.py", "normalized_path": str((self.root / "src/c.py").resolve()).casefold(), "owner": "agent-a", "task": "T-1", "acquired_at": core.utc_now(), "ttl_minutes": 60}
        self.state.write_text(json.dumps({"schema_version": 1, "locks": [legacy], "audit": []}), encoding="utf-8")
        with self.assertRaises(RuntimeError): acquire_lock(self.root, "src/c.py", "agent-b", "T-2")
        self.assertTrue(release_lock(self.root, "src/c.py", "agent-a"))


class EnvironmentValidatorTests(unittest.TestCase):
    """Finding: the suite failed in any clone without the maintainer's local Git identity."""

    def git(self, repo: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)

    def test_git_authorship_policy_in_isolated_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp); self.git(repo, "init", "--quiet")
            self.assertFalse(validate_git_authorship(repo)["ok"])
            self.git(repo, "config", "--local", "user.name", core.EXPECTED_AUTHOR)
            self.git(repo, "config", "--local", "user.email", core.EXPECTED_EMAIL)
            self.git(repo, "commit", "--allow-empty", "--quiet", "-m", "chore: initial")
            self.assertTrue(validate_git_authorship(repo)["ok"])
            self.git(repo, "commit", "--allow-empty", "--quiet", "-m", "chore: second\n\nCo-authored-by: " + "Claude <x@example.com>")
            self.assertFalse(validate_git_authorship(repo)["ok"])

    def test_identity_is_configurable_per_project_with_jimdev_default(self) -> None:
        self.assertEqual((load_git_identity(ROOT)["name"], load_git_identity(ROOT)["email"]), (core.EXPECTED_AUTHOR, core.EXPECTED_EMAIL))
        with tempfile.TemporaryDirectory() as temp:
            init_target(ROOT, Path(temp)); project = Path(temp) / ".pallaquino"
            self.assertEqual(load_git_identity(project)["name"], "jimdev")  # new projects inherit the default
            self.git(Path(temp), "init", "--quiet")
            set_git_identity(project, "Ada Dev", "ada@example.com")
            self.assertFalse(validate_git_authorship(project)["ok"])
            status = git_identity_status(project, apply_local=True)
            self.assertTrue(status["matches"]); self.assertEqual(status["local"], {"name": "Ada Dev", "email": "ada@example.com"})
            self.assertTrue(validate_git_authorship(project)["ok"])
            with self.assertRaises(ValueError): set_git_identity(project, "Ada", "not-an-email")
            (project / core.IDENTITY_FILE).write_text('{"name": "", "email": "x"}', encoding="utf-8")
            self.assertFalse(validate_all(project, include_environment=False)["ok"])

    def test_scopes_are_labelled(self) -> None:
        report = validate_all(ROOT)
        scopes = {check["validator"]: check["scope"] for check in report["checks"]}
        self.assertEqual(scopes["validate_git_authorship"], "environment")
        self.assertEqual(scopes["validate_registry"], "integrity")


class ArchiveReproducibilityTests(unittest.TestCase):
    """Finding: identical content produced different archive SHA-256 values (mtime-dependent)."""

    def test_identical_content_yields_identical_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / "framework"; (tree / "cli").mkdir(parents=True)
            (tree / "manifest.json").write_text("{}\n", encoding="utf-8"); (tree / "cli/run").write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
            first = create_archive(tree, Path(temp) / "a/out.zip")
            os.utime(tree / "manifest.json", (1_900_000_000, 1_900_000_000))
            second = create_archive(tree, Path(temp) / "b/out.zip")
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual(Path(first["sha256_file"]).read_bytes(), f"{first['sha256']}  out.zip\n".encode("ascii"))
            with zipfile.ZipFile(Path(temp) / "a/out.zip") as zf:
                self.assertEqual(zf.getinfo("framework/cli/run").external_attr >> 16, 0o100755)
                self.assertEqual(zf.getinfo("framework/manifest.json").date_time, core.FIXED_ZIP_TIME)

    def test_build_outputs_and_env_files_are_never_packaged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / "build" / "framework"  # an ancestor named "build" must not hide the tree
            for rel in ("manifest.json", "build/lib/x.py", "pkg.egg-info/PKG-INFO", ".venv/bin/python", ".env.local", ".env.example"):
                (tree / rel).parent.mkdir(parents=True, exist_ok=True); (tree / rel).write_text("x\n", encoding="utf-8")
            create_archive(tree, Path(temp) / "out.zip")
            with zipfile.ZipFile(Path(temp) / "out.zip") as zf:
                self.assertEqual(sorted(zf.namelist()), ["framework/.env.example", "framework/manifest.json"])


class TaskGraphAndHandoffTests(unittest.TestCase):
    """Findings: graph accepted unknown agents/skills; handoff hardcoded empty 'missing'/'unverified' lists."""

    def test_task_graph_rejects_unknown_agents_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for rel, value in {"registry/agents.json": {"agents": [{"id": "qa"}]}, "registry/skills.json": {"skills": [{"id": "tests"}]},
                               "planning/task_graph.json": {"tasks": [{"id": "T", "title": "t", "domain": "d", "dependencies": [], "blocked_by": [], "parallelizable": False, "priority": "P0", "risk": "LOW", "agents": ["ghost"], "skills": ["tests"], "files": [], "acceptance_criteria": [], "quality_gates": []}]}}.items():
                (root / rel).parent.mkdir(parents=True, exist_ok=True); (root / rel).write_text(json.dumps(value), encoding="utf-8")
            details = validate_task_graph(root)["details"]
            self.assertIn("task T unknown agent ghost", details)

    def test_handoff_is_derived_from_recorded_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); state = root / "continuity/state"; state.mkdir(parents=True)
            (state / "CURRENT_TASK.md").write_text("# Current task\n\n- ID: T-9\n- Objective: ship it\n", encoding="utf-8")
            (state / "KNOWN_ISSUES.md").write_text("# Known issues\n\n- flaky network\n- Confidence: high\n", encoding="utf-8")
            (state / "PIPELINE_STATE.md").write_text("# Pipeline state\n\n- Next: run the release gate\n", encoding="utf-8")
            handoff = create_handoff(root, unverified=["load test"])
            self.assertEqual((handoff["task"], handoff["requested"]), ("T-9", "ship it"))
            self.assertEqual(handoff["breakage_risks"], ["flaky network"])
            self.assertEqual(handoff["next_action"], "run the release gate")
            self.assertEqual(handoff["missing"], ["NOT_RECORDED"]); self.assertEqual(handoff["unverified"], ["load test"])
            self.assertEqual(handoff["confidence"], "low")
            self.assertTrue((root / "continuity/HANDOFF.json").is_file())


if __name__ == "__main__":
    unittest.main()
