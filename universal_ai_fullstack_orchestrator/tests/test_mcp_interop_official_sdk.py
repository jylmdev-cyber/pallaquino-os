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
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True); self.addCleanup(self.tmp.cleanup)
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

    def test_pallaquino_client_against_official_streamable_http_server(self):
        import socket, subprocess, time
        with socket.socket() as probe: probe.bind(("127.0.0.1", 0)); port = probe.getsockname()[1]
        http_server = self.server.with_name("http_server.py")
        http_server.write_text(SERVER.replace("mcp.run()", f'mcp.run(transport="streamable-http", host="127.0.0.1", port={port})'), encoding="utf-8")
        proc = subprocess.Popen([sys.executable, str(http_server)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proc.wait, 10); self.addCleanup(proc.terminate)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with socket.socket() as s:
                if s.connect_ex(("127.0.0.1", port)) == 0: break
            time.sleep(0.2)
        from pallaquino_cli.mcp.netpolicy import NetworkPolicy
        from pallaquino_cli.mcp.transports import HttpTransport
        client = McpClient(HttpTransport(f"http://127.0.0.1:{port}/mcp", policy=NetworkPolicy(allow_http_loopback=True)), timeout=30); self.addCleanup(client.close)
        info = client.connect()
        self.assertEqual((info["era"], info["protocol_version"]), ("modern", "2026-07-28"))
        tools = {t["name"]: t for t in client.list_tools()}
        self.assertIn("3", str(client.call_tool("add", {"a": 1, "b": 2}, tool=tools["add"])))


@unittest.skipUnless(SDK and int(SDK.split(".")[0]) >= 2, f"official MCP SDK >= 2 not installed (found {SDK})")
class OfficialSdkClientInteropTest(unittest.TestCase):
    """The official SDK client against PALLAQUINO's reference server (stdio and Streamable HTTP)."""

    QUALITY = Path(__file__).resolve().parents[1] / "examples" / "mcp_servers" / "quality_server.py"

    def exercise(self, target) -> dict:
        import anyio
        from mcp import Client
        seen: dict = {}
        async def main() -> None:
            async with Client(target) as client:
                seen["version"] = client.protocol_version
                seen["tools"] = sorted(t.name for t in (await client.list_tools()).tools)
                seen["echo"] = (await client.call_tool("echo", {"message": "hola"})).structured_content
                seen["resource"] = (await client.read_resource("quality://rules")).contents[0].text
                seen["prompt"] = (await client.get_prompt("review_checklist", {"module": "core"})).messages[0].content.text
        anyio.run(main)
        return seen

    def check(self, seen: dict) -> None:
        self.assertEqual(seen["version"], "2026-07-28")
        self.assertEqual(seen["tools"], ["confirm_action", "echo", "long_job", "quality_scan", "slow"])
        self.assertEqual(seen["echo"], {"echo": "hola"})
        self.assertIn("TODO/FIXME", seen["resource"]); self.assertIn("Review core", seen["prompt"])

    def test_official_client_against_pallaquino_stdio_server(self):
        from mcp import StdioServerParameters
        self.check(self.exercise(StdioServerParameters(command=sys.executable, args=[str(self.QUALITY)])))

    def test_official_client_against_pallaquino_http_server(self):
        sys.path.insert(0, str(self.QUALITY.parent))
        import quality_server
        from pallaquino_cli.mcp.server import McpHttpServer
        with McpHttpServer(quality_server.build()) as server:
            self.check(self.exercise(server.url))


if __name__ == "__main__":
    unittest.main()
