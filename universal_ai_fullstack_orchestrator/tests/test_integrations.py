"""Integration adapters: filesystem confinement, Git (read-only plus governed stage), SQLite read-only, GitHub stub."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from pallaquino_cli.integrations import database, filesystem, git, github
from pallaquino_cli.memory import MemoryStore
from pallaquino_cli.tools.gateway import ToolGateway
from pallaquino_cli.tools.permissions import PermissionGateway
from pallaquino_cli.tools.registry import ToolRegistry

FAKE_TOKEN = "gh" + "p_" + "B" * 36


class AdapterCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "ws"; self.workspace.mkdir()
        self.store = MemoryStore(Path(self.tmp.name) / "m.db", "proj"); self.addCleanup(self.store.close)
        self.registry = ToolRegistry(); self.permissions = PermissionGateway(self.store)
        for tool, executor in filesystem.tools() + git.tools() + database.tools(): self.registry.register(tool, executor)
        self.gateway = ToolGateway(self.registry, self.permissions, self.store, workspace=self.workspace)

    def call(self, tool_id, args=None, **kwargs):
        return self.gateway.call(tool_id, args or {}, **kwargs)


class FilesystemTest(AdapterCase):
    def test_read_search_list_and_stat(self):
        (self.workspace / "src").mkdir(); (self.workspace / "src" / "a.py").write_bytes(b"x = 1  # TODO\n")
        read = self.call("core.files.read", {"path": "src/a.py"})
        self.assertEqual(read["result"]["text"], "x = 1  # TODO\n"); self.assertEqual(len(read["result"]["structured"]["sha256"]), 64)
        self.assertEqual(self.call("core.files.search", {"query": "TODO"})["result"]["structured"]["matches"][0]["path"], "src/a.py")
        self.assertEqual([f["path"] for f in self.call("core.files.list")["result"]["structured"]["files"]], ["src/a.py"])
        self.assertTrue(self.call("core.files.stat", {"path": "src"})["result"]["structured"]["is_dir"])

    def test_confinement_and_sensitive_files(self):
        outside = Path(self.tmp.name) / "secret.txt"; outside.write_text("outside", encoding="utf-8")
        for path in ("../secret.txt", str(outside), "/etc/passwd", "C:\\Windows\\win.ini", "src/../../secret.txt"):
            with self.subTest(path=path):
                outcome = self.call("core.files.read", {"path": path})
                self.assertEqual((outcome["status"], outcome["error_kind"]), ("DENIED", "permission_denied"))
        (self.workspace / ".env").write_text("API_KEY=x\n", encoding="utf-8"); (self.workspace / "id_rsa").write_text("k", encoding="utf-8")
        for path in (".env", "id_rsa", ".git/config"):
            with self.subTest(path=path): self.assertEqual(self.call("core.files.read", {"path": path})["status"], "DENIED")
        (self.workspace / "bin.dat").write_bytes(b"\0\1\2")
        self.assertEqual(self.call("core.files.read", {"path": "bin.dat"})["status"], "FAILED")
        self.assertTrue(any(e["event_type"] == "policy_violation" for e in self.store.list_events()))

    def test_symbolic_links_never_escape(self):
        outside = Path(self.tmp.name) / "outside"; outside.mkdir(); (outside / "loot.txt").write_text("loot", encoding="utf-8")
        try:
            os.symlink(outside, self.workspace / "link", target_is_directory=True); os.symlink(outside / "loot.txt", self.workspace / "loot.txt")
        except (OSError, NotImplementedError): self.skipTest("this host cannot create symbolic links")
        self.assertEqual(self.call("core.files.read", {"path": "loot.txt"})["status"], "DENIED")
        self.assertEqual(self.call("core.files.read", {"path": "link/loot.txt"})["status"], "DENIED")
        self.assertEqual(self.call("core.files.list")["result"]["structured"]["files"], [], "walks do not follow links")

    def test_writes_are_governed_atomic_and_secret_free(self):
        self.assertEqual(self.call("core.files.write", {"path": "a.txt", "content": "v1"})["status"], "DENIED", "writes need a grant")
        self.permissions.grant("core.files.write", operations=["WRITE_OPERATION"], registry=self.registry)
        first = self.call("core.files.write", {"path": "docs/a.txt", "content": "v1"})
        self.assertEqual(first["status"], "COMPLETED"); self.assertEqual((self.workspace / "docs" / "a.txt").read_text(encoding="utf-8"), "v1")
        stale = self.call("core.files.write", {"path": "docs/a.txt", "content": "v2", "expected_sha256": "0" * 64})
        self.assertEqual(stale["status"], "DENIED"); self.assertIn("write conflict", stale["error"])
        self.assertEqual(self.call("core.files.write", {"path": "docs/a.txt", "content": "v3", "expected_sha256": first["result"]["structured"]["sha256"]})["status"], "COMPLETED")
        self.assertEqual(self.call("core.files.write", {"path": "docs/a.txt", "content": "x", "create_only": True})["status"], "FAILED")
        self.assertEqual(self.call("core.files.write", {"path": "cfg.py", "content": f"token = '{FAKE_TOKEN}'"})["status"], "DENIED")
        self.assertEqual(self.call("core.files.write", {"path": ".env", "content": "A=1"})["status"], "DENIED")


@unittest.skipIf(shutil.which("git") is None, "git is not installed")
class GitTest(AdapterCase):
    def setUp(self):
        super().setUp()
        run = lambda *a: subprocess.run(["git", "-C", str(self.workspace), *a], check=True, capture_output=True)
        run("init", "-q", "-b", "main"); run("config", "user.name", "tester"); run("config", "user.email", "t@example.com")
        (self.workspace / "a.txt").write_text("one\n", encoding="utf-8"); run("add", "a.txt"); run("commit", "-q", "-m", "first commit")
        (self.workspace / "a.txt").write_text("two\n", encoding="utf-8"); (self.workspace / "new.txt").write_text("n\n", encoding="utf-8")

    def test_read_only_inspection(self):
        status = self.call("core.git.status")["result"]["structured"]
        self.assertFalse(status["clean"]); self.assertEqual(sorted(c["path"] for c in status["changes"]), ["a.txt", "new.txt"])
        self.assertIn("+two", self.call("core.git.diff")["result"]["text"])
        self.assertEqual(self.call("core.git.log")["result"]["structured"]["commits"][0]["subject"], "first commit")
        self.assertTrue(self.call("core.git.branches")["result"]["structured"]["branches"][0]["current"])
        self.assertIn("first commit", self.call("core.git.show", {"revision": "HEAD"})["result"]["text"])

    def test_a_workspace_without_git_is_a_fact_not_a_failure(self):
        plain = Path(self.tmp.name) / "plain"; plain.mkdir()
        gateway = ToolGateway(self.registry, self.permissions, self.store, workspace=plain)
        status = gateway.call("core.git.status", {}); log = gateway.call("core.git.log", {})
        self.assertEqual((status["status"], status["result"]["structured"]["repository"]), ("COMPLETED", False))
        self.assertEqual(log["result"]["structured"], {"repository": False, "commits": []})

    def test_option_injection_and_governed_stage(self):
        self.assertEqual(self.call("core.git.show", {"revision": "--output=/tmp/x"})["status"], "DENIED")
        self.assertEqual(self.call("core.git.diff", {"path": "../outside"})["status"], "DENIED")
        self.assertEqual(self.call("core.git.stage", {"paths": ["a.txt"]})["status"], "DENIED", "staging needs a grant")
        self.permissions.grant("core.git.stage", operations=["WRITE_OPERATION"], registry=self.registry)
        self.assertEqual(self.call("core.git.stage", {"paths": ["a.txt"]})["status"], "COMPLETED")
        self.assertIn("a.txt", self.call("core.git.diff", {"staged": True, "stat_only": True})["result"]["text"])


class SqliteTest(AdapterCase):
    def setUp(self):
        super().setUp()
        conn = sqlite3.connect(self.workspace / "app.db"); conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.executemany("INSERT INTO users (name) VALUES (?)", [("ana",), ("luis",)]); conn.commit(); conn.close()

    def test_inspection_and_read_only_queries(self):
        self.assertEqual(self.call("core.sqlite.tables", {"database": "app.db"})["result"]["structured"]["tables"], ["users"])
        schema = self.call("core.sqlite.schema", {"database": "app.db", "table": "users"})["result"]["structured"]["users"]
        self.assertEqual([c["name"] for c in schema["columns"]], ["id", "name"])
        rows = self.call("core.sqlite.query", {"database": "app.db", "sql": "SELECT name FROM users WHERE id > ? ORDER BY id", "params": [0], "max_rows": 1})
        self.assertEqual(rows["result"]["structured"], {"columns": ["name"], "rows": [["ana"]], "truncated": True})

    def test_writes_are_refused_by_sqlite_itself(self):
        for sql in ("DELETE FROM users", "DROP TABLE users", "INSERT INTO users (name) VALUES ('x')", "ATTACH DATABASE 'x.db' AS x",
                    "PRAGMA journal_mode=DELETE", "CREATE TABLE t (a)", "WITH x AS (SELECT 1) UPDATE users SET name = 'y'"):
            with self.subTest(sql=sql):
                outcome = self.call("core.sqlite.query", {"database": "app.db", "sql": sql})
                self.assertIn(outcome["status"], ("DENIED", "FAILED")); self.assertNotEqual(outcome["status"], "COMPLETED")
        conn = sqlite3.connect(self.workspace / "app.db"); self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 2); conn.close()
        self.assertEqual(self.call("core.sqlite.query", {"database": "../m.db", "sql": "SELECT 1"})["status"], "DENIED")
        (self.workspace / "notes.txt").write_text("x", encoding="utf-8")
        self.assertEqual(self.call("core.sqlite.tables", {"database": "notes.txt"})["status"], "DENIED")


class GithubStub(BaseHTTPRequestHandler):
    seen: list = []
    def log_message(self, *a): pass
    def do_GET(self):
        GithubStub.seen.append({"path": self.path, "auth": self.headers.get("Authorization")})
        routes = {"/repos/acme/app": {"full_name": "acme/app", "description": "d", "default_branch": "main", "visibility": "public", "open_issues_count": 1, "pushed_at": "x"},
                  "/repos/acme/app/issues?state=open&per_page=20": [{"number": 7, "title": "Bug", "state": "open", "user": {"login": "u"}, "labels": [{"name": "bug"}]}]}
        body = routes.get(self.path)
        status = 200 if body is not None else 404 if "private" not in self.path else 401
        data = json.dumps(body if body is not None else {"message": "nope"}).encode()
        self.send_response(status); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)


class GithubTest(AdapterCase):
    def test_read_only_adapter_with_credential_reference(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), GithubStub); threading.Thread(target=server.serve_forever, daemon=True).start(); self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        config = {"api_url": f"http://127.0.0.1:{server.server_address[1]}", "credential_ref": "env:TEST_GH", "network": {"allow_http_loopback": True}}
        for tool, executor in github.tools(config, lambda ref: FAKE_TOKEN if ref == "env:TEST_GH" else None): self.registry.register(tool, executor)
        repo = self.call("core.github.repository", {"owner": "acme", "repo": "app"})
        self.assertEqual(repo["result"]["structured"]["full_name"], "acme/app")
        self.assertEqual(self.call("core.github.issues", {"owner": "acme", "repo": "app"})["result"]["structured"]["issues"][0]["labels"], ["bug"])
        self.assertEqual(GithubStub.seen[0]["auth"], f"Bearer {FAKE_TOKEN}", "the token goes only to the configured API host")
        self.assertNotIn(FAKE_TOKEN, json.dumps(self.store.list_events()))
        self.assertEqual(self.call("core.github.repository", {"owner": "acme", "repo": "private"})["error_kind"], "auth")
        self.assertEqual(self.call("core.github.repository", {"owner": "../x", "repo": "y"})["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
