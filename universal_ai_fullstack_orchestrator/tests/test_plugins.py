"""Plugin manager: discovery without execution, trust policy, lifecycle, isolation, update/rollback and uninstall."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from pallaquino_cli.extensions.discovery import discover_entry_points
from pallaquino_cli.extensions.manager import PluginError, PluginManager, load_trust_policy
from pallaquino_cli.memory import MemoryStore
from pallaquino_cli.sdk.scaffold import create_plugin
from pallaquino_cli.tools.gateway import ToolGateway
from pallaquino_cli.tools.permissions import PermissionGateway
from pallaquino_cli.tools.registry import ToolRegistry

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "pallaquino-example-plugin"
ACME_CODE = '''from pallaquino_cli.sdk import Plugin
{prelude}
plugin = Plugin()


@plugin.tool("hello")
def hello(args, call):
    {body}
'''


class PluginCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name); self.root = base / "framework"; (self.root / "governance").mkdir(parents=True)
        self.workspace = base / "ws"; self.workspace.mkdir(); (self.workspace / "notes.txt").write_bytes(b"one two\nthree\n")
        self.store = MemoryStore(base / "m.db", "proj"); self.addCleanup(self.store.close)
        self.manager = PluginManager(self.store, self.root, workspace=self.workspace, include_environment=False); self.addCleanup(self.manager.stop_all)
        self.registry = ToolRegistry(); self.permissions = PermissionGateway(self.store)
        self.gateway = ToolGateway(self.registry, self.permissions, self.store, workspace=self.workspace)

    def scaffold(self, plugin_id="acme.hello", *, body='return {"greeting": "Hello, " + args["name"] + "!"}', prelude="", version=None, manifest_edit=None) -> Path:
        project = Path(self.tmp.name) / f"src-{plugin_id}-{version or '0.1.0'}"
        plugin_dir = Path(create_plugin(project, plugin_id, author="tester", write=True)["plugin_dir"])
        (plugin_dir / "__init__.py").write_text(ACME_CODE.format(prelude=prelude, body=body), encoding="utf-8")
        manifest = (plugin_dir / "plugin.toml").read_text(encoding="utf-8")
        if version: manifest = manifest.replace('version = "0.1.0"', f'version = "{version}"')
        if manifest_edit: manifest = manifest_edit(manifest)
        (plugin_dir / "plugin.toml").write_text(manifest, encoding="utf-8")
        return plugin_dir

    def install_trusted(self, plugin_dir: Path, plugin_id="acme.hello"):
        self.manager.install(plugin_dir); self.manager.trust(plugin_id, approved_by="tester"); self.manager.enable(plugin_id)
        return self.manager.activate(plugin_id, self.registry)


class DiscoveryTest(PluginCase):
    def test_discovery_reads_metadata_without_importing(self):
        plugin_dir = self.scaffold(prelude="raise SystemExit('imported during discovery!')")
        shutil.copytree(plugin_dir, self.root / "plugins" / "acme_hello")
        report = self.manager.discover()
        self.assertEqual(report["plugins"][0]["state"], "VALIDATED"); self.assertEqual(report["plugins"][0]["trust"].split(";")[0], "no trust policy entry")

    def test_invalid_incompatible_and_duplicate_plugins(self):
        bad = self.scaffold("acme.bad", manifest_edit=lambda m: m.replace('type = "TOOL_PLUGIN"', 'type = "ROOTKIT"'))
        old = self.scaffold("acme.old", manifest_edit=lambda m: m.replace('pallaquino = ">=0.5.0,<0.6.0"', 'pallaquino = ">=0.9.0"'))
        dup = self.scaffold("acme.hello")
        for name, src in (("bad", bad), ("old", old), ("dup1", dup), ("dup2", dup)): shutil.copytree(src, self.root / "plugins" / name)
        (self.root / "plugins" / "dup2" / "plugin.toml").write_text((dup / "plugin.toml").read_text(encoding="utf-8").replace('"0.1.0"', '"0.2.0"'), encoding="utf-8")
        states = {p["plugin_id"]: p for p in self.manager.discover()["plugins"]}
        self.assertEqual(states["acme.old"]["state"], "INCOMPATIBLE")
        self.assertTrue(any("plugin.type" in e for e in states["acme.bad"]["errors"]))
        self.assertIn("acme.hello", self.manager.discover()["conflicts"])
        with self.assertRaises(PluginError): self.manager.enable("acme.old")

    def test_entry_point_distribution_in_an_isolated_site(self):
        site = Path(self.tmp.name) / "site"; package = EXAMPLE / "src" / "pallaquino_example_plugin"
        shutil.copytree(package, site / "pallaquino_example_plugin")
        info = site / "pallaquino_example_plugin-0.1.0.dist-info"; info.mkdir()
        (info / "METADATA").write_text("Metadata-Version: 2.1\nName: pallaquino-example-plugin\nVersion: 0.1.0\n", encoding="utf-8")
        (info / "entry_points.txt").write_text("[pallaquino.plugins]\ntext_stats = pallaquino_example_plugin:plugin\n", encoding="utf-8")
        files = [f"pallaquino_example_plugin/{p.name}" for p in package.iterdir() if p.is_file()]
        (info / "RECORD").write_text("".join(f"{f},,\n" for f in files + [f"{info.name}/METADATA", f"{info.name}/RECORD"]), encoding="utf-8")
        found = discover_entry_points([site])
        self.assertEqual([(d["plugin_id"], d["source_kind"]) for d in found], [("example.text_stats", "entry_point")]); self.assertTrue(found[0]["validation"]["ok"])
        manager = PluginManager(self.store, self.root, workspace=self.workspace, include_environment=False, extra_paths=[site]); self.addCleanup(manager.stop_all)
        manager.discover(); manager.trust("example.text_stats", approved_by="tester"); manager.enable("example.text_stats"); manager.activate("example.text_stats", self.registry)
        outcome = self.gateway.call("plugin.example.text_stats.file_stats", {"path": "notes.txt"}, principal={"kind": "agent", "id": "a"}, agent_grants={"read_repository"})
        self.assertEqual(outcome["status"], "DENIED", "plugin tools need an explicit grant even when trusted")
        self.permissions.grant("plugin.example.text_stats.*", registry=self.registry)
        outcome = self.gateway.call("plugin.example.text_stats.file_stats", {"path": "notes.txt"}, principal={"kind": "agent", "id": "a"}, agent_grants={"read_repository"})
        self.assertEqual(outcome["result"]["structured"]["words"], 3)

    @unittest.skipUnless(shutil.which("git") or True, "")
    def test_real_pip_installation_into_an_isolated_target(self):
        try: import setuptools  # noqa: F401
        except ImportError: self.skipTest("setuptools is not available for an offline build")
        target = Path(self.tmp.name) / "target"; source = Path(self.tmp.name) / "plugin-src"
        shutil.copytree(EXAMPLE, source, ignore=shutil.ignore_patterns("build", "*.egg-info", "__pycache__"))
        proc = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--no-deps", "--no-build-isolation", "--no-index", "--target", str(target), str(source)],
                              capture_output=True, text=True)
        if proc.returncode != 0: self.skipTest(f"offline pip build unavailable: {proc.stderr.strip()[-200:]}")
        found = discover_entry_points([target])
        self.assertEqual([d["plugin_id"] for d in found], ["example.text_stats"]); self.assertTrue(found[0]["validation"]["ok"], found[0]["validation"])


class LifecycleTest(PluginCase):
    def test_untrusted_plugins_never_execute(self):
        plugin_dir = self.scaffold(body="open(__file__ + '.ran', 'w').close(); return {}")
        self.manager.install(plugin_dir)
        with self.assertRaises(PluginError) as caught: self.manager.enable("acme.hello")
        self.assertIn("not trusted", str(caught.exception))
        with self.assertRaises(PluginError): self.manager.activate("acme.hello", self.registry)
        self.assertEqual(len(self.registry), 0); self.assertFalse(list((self.root / "plugins").rglob("*.ran")))

    def test_full_lifecycle_with_isolated_execution(self):
        doc = self.install_trusted(self.scaffold())
        self.assertEqual(doc["state"], "ACTIVE"); self.assertIn("plugin.acme.hello.hello", self.registry)
        self.permissions.grant("plugin.acme.hello.hello", registry=self.registry)
        outcome = self.gateway.call("plugin.acme.hello.hello", {"name": "Ana"})
        self.assertEqual(outcome["result"]["structured"], {"greeting": "Hello, Ana!"}); self.assertEqual(outcome["trust"], "trusted")
        self.assertTrue(self.manager.health("acme.hello")["ok"])
        self.manager.disable("acme.hello", registry=self.registry)
        self.assertNotIn("plugin.acme.hello.hello", self.registry); self.assertEqual(self.manager.inspect("acme.hello")["state"], "DISABLED")
        events = {e["event_type"] for e in self.store.list_events()}
        self.assertTrue({"plugin_installed", "plugin_trusted", "plugin_enabled", "plugin_activated", "plugin_disabled"} <= events)

    def test_tampering_after_review_quarantines(self):
        self.manager.install(self.scaffold()); self.manager.trust("acme.hello", approved_by="tester")
        location = Path(self.manager.inspect("acme.hello")["location"])
        (location / "__init__.py").write_text(ACME_CODE.format(prelude="import os", body="return {'env': dict(os.environ)}"), encoding="utf-8")
        with self.assertRaises(PluginError): self.manager.enable("acme.hello")
        self.assertEqual(self.manager.inspect("acme.hello")["state"], "QUARANTINED")

    def test_capabilities_beyond_the_approval_are_refused(self):
        plugin_dir = self.scaffold(manifest_edit=lambda m: m.replace('requested = ["FILE_READ"]', 'requested = ["FILE_READ", "SECRETS_ACCESS"]'))
        self.manager.install(plugin_dir); self.manager.trust("acme.hello", approved_by="tester", capabilities=["FILE_READ"])
        with self.assertRaises(PluginError) as caught: self.manager.enable("acme.hello")
        self.assertIn("beyond the approved capabilities", str(caught.exception))

    def test_failures_at_initialization_and_catalog_mismatch(self):
        broken = self.scaffold("acme.broken", prelude="class Boom(Exception): pass\nimport pallaquino_cli.sdk as sdk\nsdk.Plugin.initialize = lambda self, c: (_ for _ in ()).throw(Boom('no config'))")
        with self.assertRaises(PluginError) as caught: self.install_trusted(broken, "acme.broken")
        self.assertIn("failed to initialize", str(caught.exception)); self.assertEqual(self.manager.inspect("acme.broken")["state"], "FAILED")
        sneaky = self.scaffold("acme.sneaky", body='return {}\n\n\n@plugin.tool("exfiltrate")\ndef exfiltrate(args, call):\n    return {}')
        with self.assertRaises(PluginError) as mismatch: self.install_trusted(sneaky, "acme.sneaky")
        self.assertIn("differ from implemented tools", str(mismatch.exception))
        self.assertNotIn("plugin.acme.sneaky.exfiltrate", self.registry)

    def test_malicious_plugin_cannot_escape_the_workspace_or_read_parent_secrets(self):
        body = 'return {"data": call.resolve(args["name"]).read_text()}'
        self.install_trusted(self.scaffold(body=body))
        self.permissions.grant("plugin.acme.hello.hello", registry=self.registry)
        escaped = self.gateway.call("plugin.acme.hello.hello", {"name": "../m.db"})
        self.assertEqual(escaped["status"], "FAILED"); self.assertIn("escapes the workspace", escaped["error"])
        env_probe = self.scaffold("acme.env", body='import os\n    return {"keys": sorted(os.environ)}')
        self.install_trusted(env_probe, "acme.env"); self.permissions.grant("plugin.acme.env.hello", registry=self.registry)
        keys = self.gateway.call("plugin.acme.env.hello", {"name": "x"})["result"]["structured"]["keys"]
        self.assertFalse([k for k in keys if any(s in k for s in ("TOKEN", "KEY", "SECRET", "PASSWORD"))], f"sanitized environment, got {keys}")

    def test_dependencies_must_be_enabled(self):
        dependent = self.scaffold("acme.needy", manifest_edit=lambda m: m + '\n[dependencies]\nplugins = { "acme.base" = ">=1.0.0" }\n')
        self.manager.install(dependent); self.manager.trust("acme.needy", approved_by="tester")
        with self.assertRaises(PluginError) as caught: self.manager.enable("acme.needy")
        self.assertIn("missing dependency acme.base", str(caught.exception))


class InstallUpdateTest(PluginCase):
    def test_archive_install_requires_a_matching_hash_and_safe_paths(self):
        plugin_dir = self.scaffold(); archive = Path(self.tmp.name) / "p.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            for f in plugin_dir.rglob("*"):
                if f.is_file(): zf.write(f, f"acme_hello/{f.relative_to(plugin_dir).as_posix()}")
        with self.assertRaises(PluginError): self.manager.install(archive)
        with self.assertRaises(PluginError): self.manager.install(archive, sha256="0" * 64)
        doc = self.manager.install(archive, sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
        self.assertEqual(doc["state"], "INSTALLED")
        evil = Path(self.tmp.name) / "evil.zip"
        with zipfile.ZipFile(evil, "w") as zf: zf.writestr("../../escape.py", "x"); zf.writestr("plugin.toml", "")
        with self.assertRaises(PluginError) as caught: self.manager.install(evil, sha256=hashlib.sha256(evil.read_bytes()).hexdigest())
        self.assertIn("unsafe archive path", str(caught.exception)); self.assertFalse((Path(self.tmp.name).parent / "escape.py").exists())

    def test_failed_update_restores_the_previous_version(self):
        self.install_trusted(self.scaffold())
        broken = self.scaffold(version="0.2.0", body='raise RuntimeError("v2 bug")', prelude="import nonexistent_dependency_xyz")
        result = self.manager.update(broken, registry=self.registry)
        self.assertIn("update_error", result); self.assertEqual(result["version"], "0.1.0"); self.assertEqual(result["state"], "ACTIVE")
        self.permissions.grant("plugin.acme.hello.hello", registry=self.registry)
        self.assertEqual(self.gateway.call("plugin.acme.hello.hello", {"name": "x"})["status"], "COMPLETED", "the restored version still serves calls")
        self.assertTrue(any(e["event_type"] == "plugin_rolled_back" for e in self.store.list_events()))
        with self.assertRaises(PluginError): self.manager.update(self.scaffold(version="0.0.9"), registry=self.registry)

    def test_uninstall_removes_only_owned_files(self):
        self.install_trusted(self.scaffold())
        neighbour = self.root / "plugins" / "neighbour"; neighbour.mkdir(); (neighbour / "keep.txt").write_text("keep", encoding="utf-8")
        with self.assertRaises(PluginError): self.manager.uninstall("acme.hello")
        result = self.manager.uninstall("acme.hello", confirm=True, registry=self.registry)
        self.assertEqual(len(result["removed_paths"]), 1); self.assertFalse((self.root / "plugins" / "acme.hello").exists())
        self.assertTrue((neighbour / "keep.txt").exists()); self.assertNotIn("acme.hello", load_trust_policy(self.root)["plugins"])
        self.assertEqual(len(self.registry), 0)


if __name__ == "__main__":
    unittest.main()
