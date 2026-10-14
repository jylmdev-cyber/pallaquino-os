"""`pallaquino plugin create`: scaffold a plugin project from the reference layout (dry run by default, ADR-0006)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import __version__
from ..extensions.manifest import PLUGIN_ID, PLUGIN_TYPES

PYPROJECT = """[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "{dist}"
version = "0.1.0"
description = "{name}"
requires-python = ">=3.11"
authors = [{{name = "{author}"}}]

[project.entry-points."pallaquino.plugins"]
{short} = "{package}:plugin"

[tool.setuptools]
packages = ["{package}"]
package-dir = {{"" = "src"}}

[tool.setuptools.package-data]
{package} = ["plugin.toml"]
"""
README = """# {name}

PALLAQUINO plugin `{plugin_id}` ({plugin_type}).

    python -m unittest discover -s tests -v      # runs the plugin isolated, as PALLAQUINO does
    pallaquino plugin validate src/{package}
    pallaquino plugins install src/{package}     # copies it into the project; nothing runs yet
    pallaquino plugins trust {plugin_id}         # human review: approves this exact content hash
    pallaquino plugins enable {plugin_id}

Declare every tool in `src/{package}/plugin.toml` with its schema, capabilities and operation class; the host
refuses a plugin whose code and manifest disagree.
"""
MANIFEST = """manifest_version = 1

[plugin]
id = "{plugin_id}"
name = "{name}"
description = "{name}"
author = "{author}"
version = "0.1.0"
type = "{plugin_type}"

[compatibility]
pallaquino = ">={major}.{minor}.0,<{major}.{next_minor}.0"

[runtime]
entrypoint = "{package}:plugin"
isolation = "process"
timeout_seconds = 30

[permissions]
requested = ["FILE_READ"]

[[tools]]
name = "hello"
description = "Return a greeting."
capabilities = ["FILE_READ"]
operation = "READ_ONLY"
input_schema = {{ type = "object", additionalProperties = false, required = ["name"], properties = {{ name = {{ type = "string", maxLength = 100 }} }} }}
"""
CODE = '''"""{name}: a PALLAQUINO plugin."""
from pallaquino_cli.sdk import Plugin, ToolCall

plugin = Plugin()


@plugin.tool("hello")
def hello(args: dict, call: ToolCall) -> dict:
    return {{"greeting": "Hello, " + args["name"] + "!"}}
'''
TEST = '''import unittest
from pathlib import Path

from pallaquino_cli.sdk.testing import PluginHarness

PLUGIN = Path(__file__).resolve().parents[1] / "src" / "{package}"


class PluginTest(unittest.TestCase):
    def test_hello(self):
        with PluginHarness(PLUGIN) as harness:
            self.assertEqual(harness.call("hello", {{"name": "PALLAQUINO"}}), {{"greeting": "Hello, PALLAQUINO!"}})


if __name__ == "__main__":
    unittest.main()
'''
FILES = {"pyproject.toml": PYPROJECT, "README.md": README, "src/{package}/plugin.toml": MANIFEST, "src/{package}/__init__.py": CODE,
         "tests/test_plugin.py": TEST, "examples/README.md": "Usage examples for {plugin_id}.\n"}


def create_plugin(target: Path, plugin_id: str, *, name: str | None = None, author: str = "unknown", plugin_type: str = "TOOL_PLUGIN", write: bool = False) -> dict[str, Any]:
    if not PLUGIN_ID.match(plugin_id) or plugin_id.split(".")[0] in ("core", "mcp", "plugin", "pallaquino"): raise ValueError(f"invalid plugin ID {plugin_id!r}")
    if plugin_type not in PLUGIN_TYPES: raise ValueError(f"plugin type must be one of {PLUGIN_TYPES}")
    if any(c in (name or "") + author for c in '"\\\n'): raise ValueError("name and author must not contain quotes, backslashes or newlines")
    package = re.sub(r"[^a-z0-9_]", "_", plugin_id.replace(".", "_")); major, minor = (int(x) for x in __version__.split(".")[:2])
    values = {"plugin_id": plugin_id, "name": name or plugin_id, "author": author, "plugin_type": plugin_type, "package": package, "short": plugin_id.split(".")[-1],
              "dist": package.replace("_", "-"), "major": major, "minor": minor, "next_minor": minor + 1}
    target = Path(target); files = {rel.format(**values): body.format(**values) for rel, body in FILES.items()}
    existing = [rel for rel in files if (target / rel).exists()]
    if existing: raise FileExistsError(f"refusing to overwrite {existing}")
    if write:
        for rel, body in files.items():
            path = target / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(body, encoding="utf-8")
    return {"target": str(target), "written": write, "files": sorted(files), "plugin_dir": str(target / "src" / package)}
