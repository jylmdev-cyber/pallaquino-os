"""Optional interoperability check: PALLAQUINO's stdlib client against a server built with the official MCP Python SDK v2.

Skipped unless `mcp>=2` (the SDK line that speaks 2026-07-28) is importable. PALLAQUINO never installs it: run
`pip install "mcp>=2"` in an isolated environment and then this test. The result is recorded in
docs/evaluation/MCP_CONFORMANCE_REPORT.md.
"""
from __future__ import annotations

import importlib.metadata as md
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from pallaquino_cli.mcp.client import McpClient
from pallaquino_cli.mcp.transports import StdioTransport


def sdk_version() -> str | None:
    try: return md.version("mcp")
    except md.PackageNotFoundError: return None


SDK = sdk_version()
SERVER = textwrap.dedent('''
    from mcp.server import MCPServer

    mcp = MCPServer("Interop")


    @mcp.tool()
    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b


    if __name__ == "__main__":
        mcp.run()
''')


@unittest.skipUnless(SDK and int(SDK.split(".")[0]) >= 2, f"official MCP SDK >= 2 not installed (found {SDK})")
class OfficialSdkInteropTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.server = Path(self.tmp.name) / "server.py"; self.server.write_text(SERVER, encoding="utf-8")

    def client(self, mode: str) -> McpClient:
        client = McpClient(StdioTransport([sys.executable, str(self.server)]), mode=mode, timeout=30); self.addCleanup(client.close); return client

    def test_modern_discovery_list_and_call(self):
        client = self.client("auto"); info = client.connect()
        self.assertEqual((info["era"], info["protocol_version"]), ("modern", "2026-07-28"))
        tools = {t["name"]: t for t in client.list_tools()}
        self.assertIn("add", tools)
        result = client.call_tool("add", {"a": 1, "b": 2}, tool=tools["add"])
        self.assertFalse(result["is_error"]); self.assertIn("3", result["text"] + str(result["structured"]))

    def test_legacy_handshake_against_a_dual_era_server(self):
        client = self.client("legacy"); info = client.connect()
        self.assertEqual(info["era"], "legacy")
        self.assertIn("3", client.call_tool("add", {"a": 1, "b": 2})["text"])


if __name__ == "__main__":
    unittest.main()
