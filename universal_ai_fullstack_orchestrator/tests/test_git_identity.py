from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/configure_git_identity.py"


class GitIdentityTests(unittest.TestCase):
    def test_configures_only_repository_local_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp) / "repository"
            repository.mkdir()
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)

            configured = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repository",
                    str(repository),
                    "--name",
                    "Example Contributor",
                    "--email",
                    "contributor@example.com",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            payload = json.loads(configured.stdout)
            self.assertEqual(payload["scope"], "local")
            self.assertEqual(payload["after"]["name"], "Example Contributor")
            self.assertEqual(payload["after"]["email"], "contributor@example.com")

            shown = subprocess.run(
                [sys.executable, str(SCRIPT), "--repository", str(repository), "--show"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(shown.returncode, 0, shown.stderr)
            current = json.loads(shown.stdout)
            self.assertEqual(current["name"], "Example Contributor")
            self.assertEqual(current["email"], "contributor@example.com")

    def test_rejects_incomplete_or_invalid_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repository = Path(temp)
            subprocess.run(["git", "init", "--quiet", str(repository)], check=True)
            incomplete = subprocess.run(
                [sys.executable, str(SCRIPT), "--repository", str(repository), "--name", "Only Name"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(incomplete.returncode, 2)
            invalid = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--repository",
                    str(repository),
                    "--name",
                    "Name",
                    "--email",
                    "not-an-email",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(invalid.returncode, 2)

