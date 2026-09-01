from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from pallaquino_cli.core import (
    STAGES, acquire_lock, analyze_risk, build_repository_map, create_archive,
    make_checkpoint, read_json, release_lock, resume, route_request, stack_status,
    validate_all, validate_pipeline, validate_registry,
)

ROOT = Path(__file__).resolve().parents[1]


class FrameworkTests(unittest.TestCase):
    def test_all_validators_pass(self) -> None:
        report = validate_all(ROOT)
        self.assertTrue(report["ok"], report)

    def test_pipeline_is_exact_and_linear_on_success(self) -> None:
        rows = read_json(ROOT / "pipeline/pipeline_definition.json")["stages"]
        self.assertEqual([x["id"] for x in rows], STAGES)
        self.assertTrue(validate_pipeline(ROOT)["ok"])
        for index, row in enumerate(rows[:-1]):
            self.assertEqual(row["success_to"], rows[index + 1]["id"])
            if row["id"] != "REQUEST":
                self.assertIn(row["failure_return_to"], STAGES)

    def test_registry_references_resolve(self) -> None:
        self.assertTrue(validate_registry(ROOT)["ok"])
        registry = read_json(ROOT / "registry/agents.json")["agents"]
        self.assertGreaterEqual(len(registry), 59)
        self.assertTrue(all((ROOT / row["path"]).is_file() for row in registry))

    def test_expansion_profiles_and_catalog_resolve(self) -> None:
        agents = {row["id"] for row in read_json(ROOT / "registry/agents.json")["agents"]}
        skills = {row["id"] for row in read_json(ROOT / "registry/skills.json")["skills"]}
        technologies = {row["id"] for row in read_json(ROOT / "registry/technology_catalog.json")["technologies"]}
        profiles = read_json(ROOT / "registry/stack_profiles.json")["profiles"]
        self.assertGreaterEqual(len(skills), 90)
        self.assertGreaterEqual(len(technologies), 44)
        self.assertEqual(len(profiles), 6)
        for profile in profiles:
            self.assertTrue(set(profile["technologies"]).issubset(technologies))
            self.assertTrue(set(profile["agents"]).issubset(agents))
            self.assertTrue(set(profile["skills"]).issubset(skills))
            self.assertEqual(profile["version_status"], "VERIFY_BEFORE_USE")

    def test_expansion_routing_goldens(self) -> None:
        cases = read_json(ROOT / "evaluation/stack_routing/golden.json")["cases"]
        for case in cases:
            routed = route_request(ROOT, case["request"])
            selected_agents = {row["id"] for row in routed["agents"]}
            selected_skills = {row["id"] for row in routed["skills"]}
            self.assertTrue(set(case["required_agents"]).issubset(selected_agents), case)
            self.assertTrue(set(case["required_skills"]).issubset(selected_skills), case)

    def test_risk_goldens_and_monotonicity(self) -> None:
        cases = ["docs", "public API", "authorization with personal data", "delete production database"]
        levels = [analyze_risk(x)["level"] for x in cases]
        self.assertEqual(levels, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])

    def test_routing_goldens(self) -> None:
        cases = read_json(ROOT / "evaluation/routing_golden.json")["cases"]
        for case in cases:
            routed = route_request(ROOT, case["request"])
            agents = {x["id"] for x in routed["agents"]}; skills = {x["id"] for x in routed["skills"]}
            self.assertTrue(set(case["required_agents"]).issubset(agents), case)
            self.assertTrue(set(case["required_skills"]).issubset(skills), case)
            self.assertFalse(set(case["forbidden_agents"]) & agents, case)

    def test_file_locks_enforce_owner_and_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "execution").mkdir()
            (root / "execution/file_locks.json").write_text('{"schema_version":1,"locks":[],"audit":[]}', encoding="utf-8")
            lock = acquire_lock(root, "src/service.py", "agent-a", "T-1")
            self.assertEqual(lock["owner"], "agent-a")
            with self.assertRaises(RuntimeError): acquire_lock(root, "src/../src/service.py", "agent-b", "T-2")
            with self.assertRaises(ValueError): acquire_lock(root, "../outside", "agent-a", "T-1")
            self.assertTrue(release_lock(root, "src/service.py", "agent-a"))

    def test_repository_map_detects_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); target = root / "repo"; output = root / "out"
            target.mkdir(); output.mkdir(); (target / "app.py").write_text("print('ok')", encoding="utf-8")
            result = build_repository_map(target, output)
            self.assertIn("app.py", result["entrypoints"])
            self.assertIn("Python", result["technologies"])

    def test_checkpoint_checksum_and_corrupt_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "continuity/state").mkdir(parents=True)
            (root / "continuity/state/PIPELINE_STATE.md").write_text("- Current stage: TEST\n", encoding="utf-8")
            first = make_checkpoint(root, "T-1")
            self.assertEqual(resume(root)["status"], "RECOVERED")
            newest = root / "continuity/checkpoints/99999999T999999Z.json"; newest.write_text("{}", encoding="utf-8")
            recovered = resume(root)
            self.assertEqual(recovered["state"]["task"], "T-1")
            self.assertIn(str(newest), recovered["invalid_skipped"])
            self.assertTrue(Path(first["path"]).exists())

    def test_stack_snapshot_is_current(self) -> None:
        status = stack_status(ROOT)
        self.assertTrue(status["ok"], status)
        self.assertTrue(all(x["source"].startswith("https://") for x in status["entries"]))

    def test_release_archive_is_safe_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "PALLAQUINO_autonomous_engineering_os.zip"
            report = create_archive(ROOT, archive)
            self.assertTrue(report["integrity"], report)
            self.assertTrue(archive.with_suffix(".sha256").exists())
            with zipfile.ZipFile(archive) as zf:
                names = zf.namelist()
                self.assertIn(f"{ROOT.name}/manifest.json", names)
                self.assertIsNone(zf.testzip())
                self.assertFalse(any(".git/" in name or ".." in Path(name).parts for name in names))


if __name__ == "__main__":
    unittest.main()
