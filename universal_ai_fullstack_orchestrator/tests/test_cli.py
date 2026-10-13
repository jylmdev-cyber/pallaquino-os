from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pallaquino_cli.__main__ import main  # noqa: E402


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([sys.executable, "-m", "pallaquino_cli", *args], cwd=ROOT, env=env, text=True, capture_output=True, check=False)

    def test_help(self) -> None:
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pallaquino", proc.stdout)

    def test_validate_json(self) -> None:
        proc = self.run_cli("validate", "--root", str(ROOT), "--json", "--integrity-only")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(json.loads(proc.stdout)["ok"])

    def test_invalid_root_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            proc = self.run_cli("status", "--root", temp, "--json")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("not a PALLAQUINO root", json.loads(proc.stdout)["error"])

    def test_security_audit_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = self.run_cli("security", "audit", "--target", temp, "--json")
            self.assertEqual(clean.returncode, 0, clean.stdout)
            Path(temp, "config.py").write_text('API_KEY = "' + "Z" * 24 + '"\n', encoding="utf-8")
            dirty = self.run_cli("security", "--target", temp, "--json")
            self.assertEqual(dirty.returncode, 1)
            self.assertEqual(json.loads(dirty.stdout)["findings"][0]["kind"], "credential_assignment")
            self.assertNotIn("Z" * 24, dirty.stdout)

    def test_init_dry_run_and_list_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            proc = self.run_cli("init", "--target", temp, "--dry-run", "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr); self.assertTrue(json.loads(proc.stdout)["dry_run"])
            self.assertEqual(list(Path(temp).iterdir()), [])
        agents = self.run_cli("agents")
        self.assertEqual(agents.returncode, 0, agents.stderr)
        self.assertNotIn("{'id'", agents.stdout); self.assertIn("backend_engineer\tbackend", agents.stdout)

    def test_risk_json(self) -> None:
        proc = self.run_cli("risk", "--root", str(ROOT), "--json", "delete", "production", "database")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["level"], "CRITICAL")

    def test_init_is_idempotent_and_preserves_existing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp); first = self.run_cli("init", "--root", str(ROOT), "--target", str(target), "--json")
            second = self.run_cli("init", "--root", str(ROOT), "--target", str(target), "--json")
            self.assertEqual(first.returncode, 0, first.stderr); self.assertEqual(second.returncode, 0, second.stderr)
            self.assertGreater(json.loads(first.stdout)["copied"], 0); self.assertEqual(json.loads(second.stdout)["copied"], 0)


class CliInProcessTests(unittest.TestCase):
    """Drive main() directly; state-writing commands run against a throwaway initialized project."""

    def call(self, *args: str) -> tuple[int, str]:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(args))
        return code, buffer.getvalue()

    def test_every_command_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / ".pallaquino"
            self.assertEqual(self.call("init", "--root", str(ROOT), "--target", temp, "--json")[0], 0)
            for args in (["status"], ["plan"], ["pipeline"], ["skills"], ["graph"], ["resume"],
                         ["validate", "--integrity-only"], ["risk", "add", "login"], ["analyze", "--target", temp],
                         ["checkpoint", "--task", "T-1"], ["handoff", "--next-action", "review"], ["security", "--target", str(project / "docs")]):
                code, out = self.call(*args, "--root", str(project), "--json")
                self.assertEqual(code, 0, (args, out)); self.assertIsInstance(json.loads(out), (dict, list))
            self.assertEqual(json.loads(self.call("resume", "--root", str(project), "--json")[1])["status"], "RECOVERED")
            for command, key in (("doctor", "capabilities"), ("stack", "entries")):  # exit 1 when the snapshot is stale
                code, out = self.call(command, "--root", str(project), "--json")
                self.assertIn(code, (0, 1)); self.assertIn(key, json.loads(out))
            code, out = self.call("identity", "--name", "Ada Dev", "--email", "ada@example.com", "--root", str(project), "--json")
            self.assertEqual(code, 1)  # temp project is not a Git repository
            self.assertEqual(json.loads(out)["expected"]["name"], "Ada Dev")
            self.assertEqual(self.call("identity", "--name", "Solo", "--root", str(project), "--json")[0], 1)
            code, _ = self.call("status", "--root", temp)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()

