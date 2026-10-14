"""MCP 2026-07-28 client and reference server: stdio and Streamable HTTP conformance, compatibility and failures.

Servers used: examples/mcp_servers/quality_server.py over stdio (a real subprocess) and McpServer instances over
in-process Streamable HTTP on 127.0.0.1. These verify this client against the 2026-07-28 rules as implemented by
the PALLAQUINO reference server; interoperability with third-party servers is reported separately
(docs/evaluation/MCP_CONFORMANCE_REPORT.md).
"""
from __future__ import annotations

import http.client
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "mcp_servers"))

import quality_server  # noqa: E402
from pallaquino_cli.mcp import protocol as p  # noqa: E402
from pallaquino_cli.mcp.client import McpClient, McpError  # noqa: E402
from pallaquino_cli.mcp.netpolicy import NetworkPolicy, NetworkPolicyError, check_url  # noqa: E402
from pallaquino_cli.mcp.server import McpHttpServer, McpServer, ToolResult  # noqa: E402
from pallaquino_cli.mcp.transports import HttpTransport, StdioTransport  # noqa: E402

SERVER = ["python", str(ROOT / "examples" / "mcp_servers" / "quality_server.py")]
LOOPBACK = NetworkPolicy(allow_http_loopback=True)


def stdio(*flags: str, **kwargs) -> McpClient:
    return McpClient(StdioTransport(SERVER + list(flags)), **kwargs)


def raw_post(url: str, body: dict, headers: dict) -> tuple[int, dict | None]:
    parts = url.split("/", 3); host, port = parts[2].split(":")
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    conn.request("POST", "/" + parts[3], body=json.dumps(body), headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **headers})
    resp = conn.getresponse(); data = resp.read(); conn.close()
    return resp.status, json.loads(data) if data else None


def modern_body(method: str, params: dict | None = None, version: str = p.PROTOCOL_VERSION) -> dict:
    return p.request(1, method, p.with_meta(params, p.request_meta(version, {"name": "t", "version": "1"}, {})))


class StdioTest(unittest.TestCase):
    def setUp(self):
        self.client = stdio(extensions=[p.TASKS_EXTENSION]); self.addCleanup(self.client.close)

    def test_discover_negotiates_2026_without_initialize(self):
        info = self.client.connect()
        self.assertEqual((info["era"], info["protocol_version"]), ("modern", "2026-07-28"))
        self.assertEqual(info["server_info"]["name"], "pallaquino-quality-server")
        self.assertIn("tools", info["capabilities"]); self.assertIn(p.TASKS_EXTENSION, info["extensions"])

    def test_tools_resources_prompts_and_structured_results(self):
        tools = {t["name"]: t for t in self.client.list_tools()}
        self.assertEqual(sorted(tools), ["confirm_action", "echo", "long_job", "quality_scan", "slow"])
        self.assertTrue(all(len(t["definition_sha256"]) == 64 for t in tools.values()))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            Path(tmp, "a.py").write_text("# TODO fix\n" + "x" * 130 + "\n", encoding="utf-8")
            result = self.client.call_tool("quality_scan", {"root": tmp}, tool=tools["quality_scan"])
        self.assertFalse(result["is_error"]); self.assertEqual(result["structured"]["summary"], {"todo": 1, "long_line": 1, "large_file": 0})
        self.assertEqual(self.client.read_resource("quality://rules")[0]["mimeType"], "text/markdown")
        self.assertEqual(self.client.list_prompts()[0]["name"], "review_checklist")
        self.assertIn("Review core", self.client.get_prompt("review_checklist", {"module": "core"})["messages"][0]["content"]["text"])

    def test_invalid_arguments_are_rejected_client_side_and_server_side(self):
        tools = {t["name"]: t for t in self.client.list_tools()}
        with self.assertRaises(McpError) as caught: self.client.call_tool("quality_scan", {"root": 5}, tool=tools["quality_scan"])
        self.assertEqual(caught.exception.kind, "invalid_arguments")
        result = self.client.call_tool("quality_scan", {"root": 5})  # without the definition: the server reports a tool execution error
        self.assertTrue(result["is_error"]); self.assertIn("invalid arguments", result["text"])
        with self.assertRaises(McpError) as unknown: self.client.call_tool("nope", {})
        self.assertEqual(unknown.exception.code, p.INVALID_PARAMS)

    def test_multi_round_trip_input_is_denied_unless_authorized(self):
        with self.assertRaises(McpError) as caught: self.client.call_tool("confirm_action", {"action": "x"})
        self.assertEqual(caught.exception.code, p.MISSING_CLIENT_CAPABILITY, "the server may not ask for input the client did not declare")
        answering = stdio(capabilities={"elicitation": {}}); self.addCleanup(answering.close)
        with self.assertRaises(McpError) as denied: answering.call_tool("confirm_action", {"action": "x"})
        self.assertEqual(denied.exception.kind, "input_denied", "default handler denies every input request")
        seen = []
        result = answering.call_tool("confirm_action", {"action": "x"}, input_handler=lambda reqs: seen.append(reqs) or {"confirm": {"action": "accept", "content": {"ok": True}}})
        self.assertEqual(result["structured"], {"confirmed": True, "state": "round-1"}); self.assertEqual(list(seen[0]), ["confirm"])

    def test_cancellation_and_timeout(self):
        cancel = threading.Event(); threading.Timer(0.2, cancel.set).start(); started = time.monotonic()
        with self.assertRaises(McpError) as caught: self.client.call_tool("slow", {"seconds": 10}, cancel=cancel)
        self.assertEqual(caught.exception.kind, "cancelled"); self.assertLess(time.monotonic() - started, 3)
        with self.assertRaises(McpError) as timed: self.client.call_tool("slow", {"seconds": 10}, timeout=0.3)
        self.assertEqual(timed.exception.kind, "timeout")
        self.assertEqual(self.client.call_tool("echo", {"message": "still alive"})["structured"], {"echo": "still alive"})

    def test_tasks_extension_polls_to_completion(self):
        result = self.client.call_tool("long_job", {"seconds": 0.1})
        self.assertEqual(result["structured"], {"job": "done"}); self.assertEqual(result["task"]["status"], "completed")
        plain = stdio(); self.addCleanup(plain.close)
        self.assertIsNone(plain.call_tool("long_job", {"seconds": 0.05})["task"], "without the extension the server answers synchronously")

    def test_legacy_server_falls_back_to_initialize_only_in_auto_mode(self):
        legacy = stdio("--legacy"); self.addCleanup(legacy.close)
        info = legacy.connect()
        self.assertEqual((info["era"], info["protocol_version"]), ("legacy", "2025-11-25"))
        self.assertEqual(sorted(t["name"] for t in legacy.list_tools()), ["confirm_action", "echo", "long_job", "quality_scan", "slow"])
        self.assertEqual(legacy.call_tool("echo", {"message": "hi"})["structured"], {"echo": "hi"})
        strict = stdio("--legacy", mode="modern"); self.addCleanup(strict.close)
        with self.assertRaises(McpError): strict.connect()

    def test_non_protocol_stdout_is_reported_not_trusted(self):
        noisy = stdio("--noisy"); self.addCleanup(noisy.close)
        self.assertEqual(noisy.connect()["era"], "modern")
        self.assertTrue(any("non-JSON" in v for v in noisy.transport.protocol_violations))

    def test_server_exit_is_unavailable(self):
        dead = McpClient(StdioTransport(["python", "-c", "import sys; sys.exit(0)"]), timeout=3); self.addCleanup(dead.close)
        with self.assertRaises(McpError) as caught: dead.connect()
        self.assertIn(caught.exception.kind, ("unavailable", "timeout"))


class HttpTest(unittest.TestCase):
    def serve(self, server: McpServer, **kwargs) -> McpHttpServer:
        http_server = McpHttpServer(server, **kwargs).start(); self.addCleanup(http_server.stop); return http_server

    def client(self, url: str, **kwargs) -> McpClient:
        client = McpClient(HttpTransport(url, policy=LOOPBACK), **kwargs); self.addCleanup(client.close); return client

    def test_streamable_http_with_required_headers(self):
        http_server = self.serve(quality_server.build())
        client = self.client(http_server.url, extensions=[p.TASKS_EXTENSION])
        self.assertEqual(client.connect()["protocol_version"], "2026-07-28")
        tools = {t["name"]: t for t in client.list_tools()}
        self.assertEqual(client.call_tool("echo", {"message": "hola"}, tool=tools["echo"])["structured"], {"echo": "hola"})
        sent = http_server.requests[-1]["headers"]
        self.assertEqual((sent["mcp-protocol-version"], sent["mcp-method"], sent["mcp-name"]), ("2026-07-28", "tools/call", "echo"))
        self.assertNotIn("mcp-session-id", sent)
        self.assertEqual(client.call_tool("long_job", {"seconds": 0.05})["task"]["status"], "completed")
        trace = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
        client.call_tool("echo", {"message": "t"}, tool=tools["echo"], meta={"traceparent": trace, "io.modelcontextprotocol/protocolVersion": "spoofed"})
        meta = http_server.requests[-1]["body"]["params"]["_meta"]
        self.assertEqual(meta["traceparent"], trace, "OpenTelemetry context travels in _meta")
        self.assertEqual(meta[p.META_PROTOCOL], "2026-07-28", "caller metadata cannot override protocol fields")

    def test_server_validation_rules(self):
        http_server = self.serve(quality_server.build(), allowed_origins={"https://app.example"})
        body = modern_body("tools/call", {"name": "echo", "arguments": {"message": "x"}})
        good = {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "echo"}
        self.assertEqual(raw_post(http_server.url, body, good)[0], 200)
        status, payload = raw_post(http_server.url, body, {**good, "Mcp-Name": "other"})
        self.assertEqual((status, payload["error"]["code"]), (400, p.HEADER_MISMATCH))
        self.assertEqual(raw_post(http_server.url, body, {"MCP-Protocol-Version": "2026-07-28"})[0], 400, "missing Mcp-Method")
        self.assertEqual(raw_post(http_server.url, body, {**good, "Origin": "https://evil.example"})[0], 403, "DNS-rebinding defence")
        status, payload = raw_post(http_server.url, modern_body("server/discover", {}, "1999-01-01"), {"MCP-Protocol-Version": "1999-01-01", "Mcp-Method": "server/discover"})
        self.assertEqual((status, payload["error"]["code"]), (400, p.UNSUPPORTED_PROTOCOL_VERSION)); self.assertEqual(payload["error"]["data"]["supported"], ["2026-07-28"])
        status, payload = raw_post(http_server.url, modern_body("nope/nope"), {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "nope/nope"})
        self.assertEqual((status, payload["error"]["code"]), (404, p.METHOD_NOT_FOUND))
        status, payload = raw_post(http_server.url, p.request(1, "tools/list", {}), {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"})
        self.assertEqual((status, payload["error"]["code"]), (400, p.INVALID_PARAMS), "requests without _meta are malformed")
        conn = http.client.HTTPConnection(*http_server.httpd.server_address[:2]); conn.request("GET", "/mcp")
        self.assertEqual(conn.getresponse().status, 405, "the GET stream endpoint no longer exists"); conn.close()

    def test_x_mcp_header_mirroring_and_invalid_tools_are_excluded(self):
        server = McpServer("headers")
        @server.tool("query", "q", {"type": "object", "properties": {"region": {"type": "string", "x-mcp-header": "Region"}, "sql": {"type": "string"}}})
        def query(args, ctx): return {"region": args.get("region")}
        @server.tool("broken", "b", {"type": "object", "properties": {"n": {"type": "number", "x-mcp-header": "N"}}})
        def broken(args, ctx): return {}
        http_server = self.serve(server); client = self.client(http_server.url)
        tools = {t["name"]: t for t in client.list_tools()}
        self.assertEqual(sorted(tools), ["query"]); self.assertTrue(any("broken" in w for w in client.warnings))
        self.assertEqual(client.call_tool("query", {"region": "Café", "sql": "select 1"}, tool=tools["query"])["structured"], {"region": "Café"})
        self.assertEqual(http_server.requests[-1]["headers"]["mcp-param-region"], p.encode_header_value("Café"))
        body = modern_body("tools/call", {"name": "query", "arguments": {"region": "eu"}})
        status, payload = raw_post(http_server.url, body, {"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": "query"})
        self.assertEqual((status, payload["error"]["code"]), (400, p.HEADER_MISMATCH), "a server rejects a missing Mcp-Param header")

    def test_progress_over_sse_and_cancellation_by_closing_the_stream(self):
        http_server = self.serve(quality_server.build()); client = self.client(http_server.url)
        tools = {t["name"]: t for t in client.list_tools()}; progress = []
        result = client.call_tool("slow", {"seconds": 0.3}, tool=tools["slow"], on_progress=progress.append)
        self.assertEqual(result["structured"], {"slept": 0.3}); self.assertTrue(progress, "notifications/progress arrived on the request's SSE stream")
        cancel = threading.Event(); threading.Timer(0.2, cancel.set).start()
        with self.assertRaises(McpError) as caught: client.call_tool("slow", {"seconds": 5}, tool=tools["slow"], cancel=cancel, on_progress=lambda m: None)
        self.assertEqual(caught.exception.kind, "cancelled")

    def test_version_mismatch_retries_or_fails_clearly(self):
        future = self.serve(McpServer("future", supported_versions=["2099-01-01"]))
        with self.assertRaises(McpError) as caught: self.client(future.url).connect()
        self.assertEqual(caught.exception.kind, "incompatible")
        legacy = self.serve(quality_server.build(era="legacy"))
        client = self.client(legacy.url)
        self.assertEqual(client.connect()["era"], "legacy", "a 400 without a modern error body means a legacy server")
        self.assertEqual(client.call_tool("echo", {"message": "x"})["structured"], {"echo": "x"})

    def test_malformed_and_oversized_responses(self):
        server = McpServer("bad")
        @server.tool("bad_output", "b", output_schema={"type": "object", "required": ["n"], "properties": {"n": {"type": "integer"}}})
        def bad_output(args, ctx): return ToolResult(content=[], structured={"n": "nope"})
        @server.tool("huge", "h")
        def huge(args, ctx): return {"blob": "x" * 200_000}
        http_server = self.serve(server)
        client = McpClient(HttpTransport(http_server.url, policy=NetworkPolicy(allow_http_loopback=True, max_response_bytes=50_000))); self.addCleanup(client.close)
        with self.assertRaises(McpError) as caught: client.call_tool("bad_output", {})
        self.assertEqual(caught.exception.code, p.INTERNAL_ERROR, "the reference server refuses to emit output that violates its schema")
        with self.assertRaises(McpError) as big: client.call_tool("huge", {})
        self.assertEqual(big.exception.kind, "invalid_response"); self.assertIn("exceeds", str(big.exception))

    def test_pagination_and_catalog_cache(self):
        server = McpServer("many", ttl_ms=60_000)
        for i in range(120): server.tool(f"t{i:03d}", f"tool {i}")(lambda args, ctx: {})
        http_server = self.serve(server); client = self.client(http_server.url)
        names = [t["name"] for t in client.list_tools()]
        self.assertEqual(len(names), 120); self.assertEqual(names, sorted(names), "deterministic order")
        lists = [r for r in http_server.requests if r["body"].get("method") == "tools/list"]
        self.assertEqual(len(lists), 3, "three pages of 50"); self.assertIn("cursor", lists[1]["body"]["params"])
        client.list_tools(); self.assertEqual(len([r for r in http_server.requests if r["body"].get("method") == "tools/list"]), 3, "ttlMs cache hit")
        client.list_tools(use_cache=False); self.assertEqual(len([r for r in http_server.requests if r["body"].get("method") == "tools/list"]), 6)

    def test_unreachable_server(self):
        client = McpClient(HttpTransport("http://127.0.0.1:9/mcp", policy=LOOPBACK), timeout=2); self.addCleanup(client.close)
        with self.assertRaises(McpError) as caught: client.connect()
        self.assertIn(caught.exception.kind, ("unavailable", "invalid_response", "timeout"))


class NetworkPolicyTest(unittest.TestCase):
    def test_ssrf_destinations_are_refused(self):
        for url in ("http://169.254.169.254/latest/meta-data", "https://10.0.0.5/mcp", "https://127.0.0.1/mcp", "https://[::ffff:127.0.0.1]/mcp",
                    "file:///etc/passwd", "gopher://x/", "https://user:pw@example.com/mcp", "https://example.com/mcp#frag", "http://example.com/mcp"):
            with self.subTest(url=url), self.assertRaises(NetworkPolicyError): check_url(url, NetworkPolicy())
        self.assertEqual(check_url("http://127.0.0.1:8000/mcp", LOOPBACK)[0], "http")
        with self.assertRaises(NetworkPolicyError): check_url("https://other.example/mcp", NetworkPolicy(allowed_hosts=frozenset({"mcp.example.com"})), resolve=False)


if __name__ == "__main__":
    unittest.main()
