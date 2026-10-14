"""OAuth 2.1 plumbing and credential manager against a local stub authorization server and a protected MCP server.

The stub implements RFC 8414 metadata, PKCE S256, RFC 8707 resource checks, RFC 9207 `iss` and token refresh. It
verifies this client against those rules; it is not a real identity provider (see MCP_CONFORMANCE_REPORT.md).
"""
from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from pallaquino_cli.mcp import auth
from pallaquino_cli.mcp.auth import AuthError, CredentialStore
from pallaquino_cli.mcp.client import McpClient, McpError
from pallaquino_cli.mcp.netpolicy import NetworkPolicy
from pallaquino_cli.mcp.server import McpHttpServer, McpServer
from pallaquino_cli.mcp.transports import HttpTransport

POLICY = NetworkPolicy(allow_http_loopback=True)


class AuthServer:
    def __init__(self, *, pkce=True, wrong_issuer=False, send_iss=True):
        self.codes: dict = {}; self.tokens: set = set(); self.revoked: list = []; self.requests: list = []; outer = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def send(self, status, payload=None, headers=None):
                body = json.dumps(payload).encode() if payload is not None else b""
                self.send_response(status)
                for k, v in (headers or {}).items(): self.send_header(k, v)
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_GET(self):
                url = urlsplit(self.path); outer.requests.append(url.path)
                if url.path == "/.well-known/oauth-authorization-server":
                    meta = {"issuer": "https://evil.example" if wrong_issuer else outer.issuer, "authorization_endpoint": f"{outer.issuer}/authorize",
                            "token_endpoint": f"{outer.issuer}/token", "revocation_endpoint": f"{outer.issuer}/revoke",
                            "authorization_response_iss_parameter_supported": send_iss}
                    if pkce: meta["code_challenge_methods_supported"] = ["S256"]
                    return self.send(200, meta)
                if url.path == "/authorize":
                    q = {k: v[0] for k, v in parse_qs(url.query).items()}
                    assert q["code_challenge_method"] == "S256" and q["resource"] and q["response_type"] == "code"
                    code = f"code-{len(outer.codes)}"; outer.codes[code] = q
                    params = {"code": code, "state": q["state"]}
                    if send_iss: params["iss"] = outer.issuer
                    return self.send(302, None, {"Location": f"{q['redirect_uri']}?{urlencode(params)}"})
                self.send(404, {"error": "not_found"})
            def do_POST(self):
                form = {k: v[0] for k, v in parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode()).items()}
                if self.path == "/revoke": outer.revoked.append(form["token"]); return self.send(200, {})
                if form["grant_type"] == "refresh_token":
                    token = f"at-{len(outer.tokens)}"; outer.tokens.add(token); return self.send(200, {"access_token": token, "token_type": "Bearer", "expires_in": 3600})
                request = outer.codes.pop(form.get("code"), None)
                challenge = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).decode().rstrip("=")
                if request is None or challenge != request["code_challenge"] or form.get("resource") != request["resource"]:
                    return self.send(400, {"error": "invalid_grant"})
                token = f"at-{len(outer.tokens)}"; outer.tokens.add(token)
                self.send(200, {"access_token": token, "token_type": "Bearer", "expires_in": 1, "refresh_token": "rt-1", "scope": request.get("scope", "")})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler); self.issuer = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()


def browser(url: str) -> None:
    threading.Thread(target=lambda: urllib.request.urlopen(url, timeout=5).read(), daemon=True).start()  # follows the redirect to the loopback callback


class OAuthCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.store = CredentialStore("proj", vault_dir=Path(self.tmp.name) / "vault", use_keyring=False)

    def protected_server(self, as_server: AuthServer, *, required_scope=None) -> McpHttpServer:
        mcp = McpServer("protected")
        @mcp.tool("echo", "echo", {"type": "object", "properties": {"m": {"type": "string"}}})
        def echo(args, ctx): return {"m": args.get("m")}
        holder = {}
        def check(header):
            meta = f'resource_metadata="{holder["url"]}/.well-known/oauth-protected-resource/mcp"'
            if not header or not header.startswith("Bearer ") or header[7:] not in as_server.tokens: return False, f'Bearer {meta}, scope="tools:read"'
            if required_scope: return False, f'Bearer error="insufficient_scope", scope="{required_scope}", {meta}'
            return True, None
        http_server = McpHttpServer(mcp, auth=check, resource_metadata={"resource": "", "authorization_servers": [as_server.issuer], "scopes_supported": ["tools:read"]})
        holder["url"] = f"http://127.0.0.1:{http_server.httpd.server_address[1]}"
        http_server.resource_metadata["resource"] = http_server.url
        http_server.start(); self.addCleanup(http_server.stop)
        return http_server


class DiscoveryTest(OAuthCase):
    def test_discovery_order_issuer_and_pkce_checks(self):
        good = AuthServer(); self.addCleanup(good.stop); mcp = self.protected_server(good)
        found = auth.discover(mcp.url, policy=POLICY)
        self.assertEqual((found["issuer"], found["resource"], found["scopes"]), (good.issuer, mcp.url, ["tools:read"]))
        self.assertEqual(auth.authorization_server_urls("https://a.example/tenant1"), ["https://a.example/.well-known/oauth-authorization-server/tenant1",
                         "https://a.example/.well-known/openid-configuration/tenant1", "https://a.example/tenant1/.well-known/openid-configuration"])
        self.assertEqual(auth.protected_resource_urls("https://m.example/public/mcp"), ["https://m.example/.well-known/oauth-protected-resource/public/mcp",
                         "https://m.example/.well-known/oauth-protected-resource"])
        for kwargs, kind in (({"wrong_issuer": True}, "invalid_issuer"), ({"pkce": False}, "pkce_unsupported")):
            bad = AuthServer(**kwargs); self.addCleanup(bad.stop); server = self.protected_server(bad)
            with self.assertRaises(AuthError) as caught: auth.discover(server.url, policy=POLICY)
            self.assertEqual(caught.exception.kind, kind)
        with self.assertRaises(Exception): auth.discover("https://169.254.169.254/mcp", policy=NetworkPolicy())

    def test_authorization_request_and_callback_validation(self):
        good = AuthServer(); self.addCleanup(good.stop); found = auth.discover(self.protected_server(good).url, policy=POLICY)
        pending = auth.start_authorization("srv", found, client_id="https://pallaquino.example/client.json", redirect_uri="http://127.0.0.1:1/cb", previous_scopes=["files:read"])
        query = parse_qs(urlsplit(pending.authorization_url).query)
        self.assertEqual(query["code_challenge_method"], ["S256"]); self.assertEqual(query["resource"], [found["resource"]])
        self.assertEqual(query["scope"], ["files:read tools:read"], "step-up keeps previously granted scopes")
        for params, kind in (({"code": "c", "state": pending.state, "iss": "https://evil.example"}, "invalid_issuer"),
                             ({"code": "c", "state": pending.state}, "invalid_issuer"), ({"code": "c", "state": "other", "iss": good.issuer}, "state_mismatch"),
                             ({"error": "access_denied", "state": pending.state, "iss": good.issuer}, "authorization_denied")):
            with self.subTest(kind=kind), self.assertRaises(AuthError) as caught: auth.validate_callback(pending, params)
            self.assertEqual(caught.exception.kind, kind)


class FlowTest(OAuthCase):
    def test_end_to_end_authorization_refresh_and_revocation(self):
        as_server = AuthServer(); self.addCleanup(as_server.stop); mcp = self.protected_server(as_server)
        anonymous = McpClient(HttpTransport(mcp.url, policy=POLICY)); self.addCleanup(anonymous.close)
        with self.assertRaises(McpError) as caught: anonymous.connect()
        self.assertEqual(caught.exception.kind, "auth"); challenge = caught.exception.headers.get("www-authenticate")
        self.assertIn("resource_metadata", challenge)
        found = auth.discover(mcp.url, policy=POLICY, challenge=challenge)
        result = auth.loopback_authorize("srv", found, self.store, client_id="pallaquino-test", policy=POLICY, timeout=10, open_url=browser)
        self.assertEqual(result["credential_ref"], "vault:srv"); self.assertEqual(result["issuer"], as_server.issuer)
        header = auth.bearer_provider(self.store, "srv", as_server.issuer, policy=POLICY, skew=0)
        client = McpClient(HttpTransport(mcp.url, policy=POLICY, auth_header=header)); self.addCleanup(client.close)
        self.assertEqual(client.call_tool("echo", {"m": "hi"})["structured"], {"m": "hi"})
        time.sleep(1.1)  # the stub issues 1-second tokens: the next call refreshes transparently
        self.assertEqual(client.call_tool("echo", {"m": "again"})["structured"], {"m": "again"})
        self.assertEqual(len(as_server.tokens), 2)
        self.assertNotIn("at-", json.dumps(self.store.describe()))
        revoked = auth.revoke(self.store, "srv", as_server.issuer, policy=POLICY)
        self.assertEqual((revoked["deleted"], revoked["remote_revoked"]), (1, True)); self.assertIsNone(self.store.get_token("srv", as_server.issuer))

    def test_insufficient_scope_is_reported(self):
        as_server = AuthServer(); self.addCleanup(as_server.stop); mcp = self.protected_server(as_server, required_scope="files:write")
        as_server.tokens.add("at-x"); self.store.put_token("srv", as_server.issuer, {"access_token": "at-x"})
        client = McpClient(HttpTransport(mcp.url, policy=POLICY, auth_header=auth.bearer_provider(self.store, "srv", as_server.issuer, policy=POLICY))); self.addCleanup(client.close)
        with self.assertRaises(McpError) as caught: client.connect()
        self.assertEqual(caught.exception.status, 403); self.assertIn("insufficient_scope", caught.exception.headers["www-authenticate"])


class CredentialStoreTest(OAuthCase):
    def test_tokens_are_bound_to_server_and_issuer(self):
        self.store.put_token("alpha", "https://as-a.example", {"access_token": "t-alpha"})
        self.assertEqual(self.store.resolve("vault:alpha", server="alpha", issuer="https://as-a.example"), "t-alpha")
        self.assertIsNone(self.store.resolve("vault:alpha", server="alpha", issuer="https://as-b.example"), "never reused with another issuer")
        with self.assertRaises(AuthError): self.store.resolve("vault:alpha", server="beta")
        with self.assertRaises(AuthError): self.store.resolve("file:/etc/shadow", server="alpha")
        with self.assertRaises(AuthError): self.store.resolve("env:lower-case", server="alpha")
        self.assertEqual(self.store.describe()["backend"], "file"); self.assertIn("not encrypted", self.store.describe()["protection"])
        self.assertEqual(self.store.delete("alpha"), 1)


if __name__ == "__main__":
    unittest.main()
