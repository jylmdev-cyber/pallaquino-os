from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy(); env["PYTHONPATH"] = str(ROOT)
        return subprocess.run([sys.executable, "-m", "pallaquino_cli", *args], cwd=ROOT, env=env, text=True, capture_output=True, check=False)

    def test_help(self) -> None:
        proc = self.run_cli("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("pallaquino", proc.stdout)

    def test_validate_json(self) -> None:
        proc = self.run_cli("validate", "--root", str(ROOT), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(json.loads(proc.stdout)["ok"])

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


if __name__ == "__main__":
    unittest.main()

