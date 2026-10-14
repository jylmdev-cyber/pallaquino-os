"""Mandatory end-to-end scenario and the 0.4.0 CLI contract (compatibility with 0.3 commands)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pallaquino_cli.core import atomic_json, init_target, read_json

ROOT = Path(__file__).resolve().parents[1]


class ReferenceScenarioTests(unittest.TestCase):
    def test_offline_variant_passes_and_labels_simulated_stages(self) -> None:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/run_reference_scenario.py"), "--variant", "offline"], text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout[-3000:] + proc.stderr[-2000:])
        report = json.loads(proc.stdout)["reports"][0]
        self.assertTrue(all(report["checks"].values()), report["checks"])
        self.assertEqual(report["executed_for_real"], ["discover", "verify"])
        self.assertIn("backend", report["simulated"])

    def test_real_provider_variant_is_reported_not_simulated_when_unavailable(self) -> None:
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/run_reference_scenario.py"), "--variant", "real_provider"], text=True, capture_output=True, check=False)
        report = json.loads(proc.stdout)["reports"][0]
        if not report["executed"]:  # no authorized provider here: nothing may be faked
            self.assertIn("nothing was simulated", report["reason"]); self.assertEqual(proc.returncode, 1)
        else:
            self.assertTrue(report["ok"], report)


class CliContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.project = Path(self.temp.name) / "app"
        (self.project / "tests").mkdir(parents=True)
        (self.project / "app.py").write_text("def ping():\n    return 'pong'\n", encoding="utf-8")
        (self.project / "tests/test_app.py").write_text("import unittest\nimport app\n\nclass T(unittest.TestCase):\n    def test_ping(self):\n        self.assertEqual(app.ping(), 'pong')\n", encoding="utf-8")
        init_target(ROOT, self.project); self.framework = self.project / ".pallaquino"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def cli(self, *args: str) -> tuple[int, object]:
        proc = subprocess.run([sys.executable, "-m", "pallaquino_cli", *args, "--root", str(self.framework), "--json"], cwd=self.framework, text=True,
                              capture_output=True, check=False, env={**os.environ, "PYTHONPATH": str(self.framework)})
        return proc.returncode, json.loads(proc.stdout) if proc.stdout.strip() else {}

    def test_legacy_commands_keep_their_output(self) -> None:
        self.assertIn("steps", self.cli("plan")[1]); self.assertIn("pipeline_state", self.cli("status")[1])
        self.assertIn(self.cli("resume")[1]["status"], ("RECOVERED", "RECONSTRUCTED"))
        agents = self.cli("agents")[1]; self.assertIsInstance(agents, list); self.assertEqual(agents, self.cli("agents", "list")[1])
        self.assertIsInstance(self.cli("skills", "list")[1], list)

    def test_plan_run_status_report_memory_flow_and_exit_codes(self) -> None:
        code, plan = self.cli("plan", "fix the crash in the ping endpoint", "--workspace", str(self.project)); self.assertEqual(code, 0)
        self.assertEqual(plan["status"], "PLANNED")
        code, dry = self.cli("run", "--plan", plan["plan_id"], "--dry-run"); self.assertEqual(code, 0); self.assertTrue(dry["dry_run"])
        code, run = self.cli("run", "--plan", plan["plan_id"]); self.assertEqual((code, run["status"]), (0, "COMPLETED"))
        code, status = self.cli("status", "--execution", run["execution_id"]); self.assertEqual(code, 0); self.assertEqual(status["metrics"]["quality_gates"]["passed"], 1)
        self.assertIn(run["execution_id"], [e["execution_id"] for e in self.cli("executions", "list")[1]])
        report = self.cli("executions", "report", run["execution_id"])[1]; self.assertEqual(report["trace"]["request"]["text"], "fix the crash in the ping endpoint")
        code, exported = self.cli("executions", "export", run["execution_id"]); self.assertGreater(exported["exported"], 0)
        self.assertTrue(Path(exported["path"]).is_file())
        self.assertGreater(self.cli("memory", "search", "ping")[1]["count"], 0); self.assertTrue(self.cli("memory", "verify")[1]["ok"])
        self.assertEqual(self.cli("memory", "status")[1]["executions"], 1)
        self.assertEqual(self.cli("cancel", "--execution", run["execution_id"])[0], 1)  # already completed

    def test_approval_flow_and_waiting_exit_code(self) -> None:
        code, plan = self.cli("plan", "Prepare the release changelog", "--workspace", str(self.project))
        publish = plan["approvals_required"][0]
        code, run = self.cli("run", "--plan", plan["plan_id"]); self.assertEqual((code, run["status"]), (3, "WAITING_APPROVAL"))
        self.assertEqual(self.cli("approve", "--execution", run["execution_id"], "--task", publish)[0], 0)
        code, resumed = self.cli("resume", "--execution", run["execution_id"]); self.assertEqual((code, resumed["status"]), (0, "COMPLETED"))

    def test_invalid_plans_and_destructive_memory_operations_are_refused(self) -> None:
        config = read_json(self.framework / "governance/routing_preferences.json"); config["exclude"] = ["project_analyzer"]
        atomic_json(self.framework / "governance/routing_preferences.json", config)
        self.assertEqual(self.cli("memory", "purge", "--expired")[0], 1)  # needs --yes
        self.assertEqual(self.cli("memory", "purge", "--expired", "--yes")[1], {"purged": 0})
        self.assertEqual(self.cli("run", "--plan", "plan-doesnotexist")[0], 1)

    def test_providers_commands(self) -> None:
        listing = self.cli("providers", "list")[1]; self.assertEqual({p["name"] for p in listing}, {"mock", "ollama"})
        code, doctor = self.cli("providers", "doctor"); self.assertEqual(code, 0); self.assertTrue(doctor["ok"])
        self.assertIn("backend_engineer", [s["id"] for s in self.cli("agents", "match", "crear API REST")[1]["selected"]])


class InProcessOrchestrationCliTests(unittest.TestCase):
    """Drives main() directly so the CLI layer, observability and provider configuration are exercised in-process."""

    def setUp(self) -> None:
        import contextlib, io  # noqa: E401
        self.contextlib, self.io = contextlib, io
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.project = Path(self.temp.name) / "calc"
        import shutil
        shutil.copytree(ROOT / "evaluation/reference_scenario/fixture", self.project)
        init_target(ROOT, self.project); self.framework = self.project / ".pallaquino"
        config = read_json(self.framework / "governance/providers.json")
        config["providers"]["mock"]["responses_file"] = "evaluation/reference_scenario/responses.json"; atomic_json(self.framework / "governance/providers.json", config)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def call(self, *args: str) -> tuple[int, object]:
        from pallaquino_cli.__main__ import main
        out = self.io.StringIO()
        with self.contextlib.redirect_stdout(out), self.contextlib.redirect_stderr(self.io.StringIO()):
            code = main([*args, "--root", str(self.framework), "--json"])
        text = out.getvalue().strip()
        return code, json.loads(text) if text else None

    def test_full_cycle_with_observability(self) -> None:
        code, plan = self.call("plan", "add a multiply function to the calculator module with tests", "--workspace", str(self.project)); self.assertEqual(code, 0)
        self.assertTrue(self.call("run", "--plan", plan["plan_id"], "--dry-run")[1]["dry_run"])
        code, run = self.call("run", "--plan", plan["plan_id"], "--max-workers", "2"); self.assertEqual((code, run["status"]), (0, "COMPLETED"))
        eid = run["execution_id"]
        metrics = self.call("executions", "metrics", eid)[1]
        self.assertEqual(metrics["tasks_completed"], metrics["tasks_created"]); self.assertEqual(metrics["quality_gates"], {"passed": 1, "failed": 0})
        self.assertGreater(metrics["tokens_reported"], 0); self.assertFalse(metrics["cost_verified"]); self.assertEqual(metrics["simulated_tasks"], 5)
        trace = self.call("executions", "trace", eid)[1]["trace"]
        self.assertEqual([t["step"] for t in trace["tasks"]][0], "discover"); self.assertTrue(all(t["history"] for t in trace["tasks"]))
        out = Path(self.temp.name) / "events.jsonl"; exported = self.call("executions", "export", eid, "--output", str(out))[1]
        first = json.loads(out.read_text(encoding="utf-8").splitlines()[0]); self.assertEqual(first["trace_id"], eid); self.assertIn("severity_text", first)
        self.assertEqual(exported["exported"], len(out.read_text(encoding="utf-8").splitlines()))
        status = self.call("status", "--execution", eid)[1]; self.assertEqual(status["execution"]["status"], "COMPLETED")
        self.assertIn("def multiply", (self.project / "calc.py").read_text(encoding="utf-8"))

    def test_memory_commands(self) -> None:
        from pallaquino_cli.memory import MemoryStore
        store = MemoryStore.for_root(self.framework); record_id = store.put_record("decision", "adr", "ADR-1", {"text": "sqlite"}, "storage decision"); store.close()
        self.assertEqual(self.call("memory", "inspect", "--id", str(record_id))[1]["key"], "ADR-1")
        self.assertIn("recent", self.call("memory", "inspect")[1])
        self.assertEqual(self.call("memory", "search", "storage", "--category", "decision")[1]["count"], 1)
        self.assertEqual(self.call("memory", "delete", "--id", str(record_id))[0], 1)  # refused without --yes
        self.assertEqual(self.call("memory", "delete", "--id", str(record_id), "--yes")[1], {"deleted": True})
        self.assertEqual(self.call("memory", "status")[1]["records"], {})

    def test_control_commands_and_errors(self) -> None:
        code, plan = self.call("plan", "Prepare the release changelog", "--workspace", str(self.project))
        code, run = self.call("run", "--plan", plan["plan_id"]); eid = run["execution_id"]; self.assertEqual(code, 3)
        self.assertEqual(self.call("pause", "--execution", eid)[0], 0)
        self.assertEqual(self.call("cancel", "--execution", eid)[1]["status"], "CANCELLED")
        self.assertEqual(self.call("approve", "--execution", eid, "--task", "T01")[0], 1)  # T01 needs no approval
        self.assertEqual(self.call("executions", "report")[0], 1)  # missing ID
        self.assertEqual(self.call("agents", "match")[0], 1)       # missing text
        self.assertEqual(self.call("plan", "x", "--ai", "--workspace", str(self.project))[1]["intent"]["mode"], "ai_assisted")

    def test_provider_configuration_errors(self) -> None:
        from pallaquino_cli.providers.router import build_provider, load_config
        config = read_json(self.framework / "governance/providers.json"); config["default"] = "ghost"; atomic_json(self.framework / "governance/providers.json", config)
        with self.assertRaises(ValueError): load_config(self.framework)
        self.assertEqual(self.call("providers", "doctor")[0], 1)
        with self.assertRaises(ValueError): build_provider("openai", {})


if __name__ == "__main__":
    unittest.main()
