"""Provider abstraction (ADR-0012): Ollama adapter against a local stub server, fallback policy and budgets.

The stub implements the documented Ollama endpoints (GET /api/tags, POST /api/chat). It verifies this client
against those shapes; it does not prove compatibility with a live Ollama build, which needs Ollama installed.
"""
from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pallaquino_cli.providers import Budget, MockProvider, OllamaProvider, ProviderError, ProviderRequest
from pallaquino_cli.providers.router import DEFAULT_CONFIG, complete_with_fallback, select, validate_config


class Stub(BaseHTTPRequestHandler):
    mode = "ok"; models = ["llama3.1:latest"]; last_body: dict = {}

    def log_message(self, *args) -> None: pass

    def _send(self, code: int, payload: object, headers: dict | None = None) -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        for k, v in (headers or {}).items(): self.send_header(k, v)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        self._send(200, {"models": [{"name": m} for m in Stub.models]})

    def do_POST(self) -> None:
        Stub.last_body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        mode = Stub.mode
        if mode == "auth": return self._send(401, {"error": "unauthorized"})
        if mode == "missing_model": return self._send(404, {"error": "model not found"})
        if mode == "rate_limit": return self._send(429, {"error": "slow down"}, {"Retry-After": "2"})
        if mode == "server_error": return self._send(503, {"error": "overloaded"})
        if mode == "slow": time.sleep(1.5)
        content = "not json at all" if mode == "invalid" else json.dumps({"status": "completed", "summary": "ok"})
        payload = {"message": {"role": "assistant", "content": content}, "done": True}
        if mode != "no_usage": payload.update(prompt_eval_count=21, eval_count=9)
        self._send(200, payload)


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:  # the timeout test abandons connections on purpose
        pass


class OllamaAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = QuietServer(("127.0.0.1", 0), Stub); threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown(); cls.server.server_close()

    def setUp(self) -> None:
        Stub.mode = "ok"; Stub.models = ["llama3.1:latest"]; self.provider = OllamaProvider("llama3.1", self.url)

    def request(self, timeout: float = 5) -> ProviderRequest:
        return ProviderRequest("system", "prompt", timeout_seconds=timeout, metadata={"task_key": "t"})

    def test_available_provider_returns_structured_output_and_verified_usage(self) -> None:
        self.assertTrue(self.provider.validate_config()["ok"])
        response = self.provider.complete(self.request())
        self.assertEqual(response.structured, {"status": "completed", "summary": "ok"}); self.assertFalse(response.simulated)
        self.assertEqual((response.usage.input_tokens, response.usage.output_tokens, response.usage.verified), (21, 9, True))
        self.assertFalse(response.usage.cost_verified)
        self.assertEqual((Stub.last_body["format"], Stub.last_body["stream"], Stub.last_body["messages"][0]["role"]), ("json", False, "system"))
        self.assertEqual(self.provider.boundary, "local")

    def test_errors_are_normalized(self) -> None:
        for mode, kind in (("auth", "auth"), ("missing_model", "not_configured"), ("rate_limit", "rate_limit"), ("server_error", "unavailable"), ("invalid", "invalid_response")):
            Stub.mode = mode
            with self.assertRaises(ProviderError) as caught: self.provider.complete(self.request())
            self.assertEqual(caught.exception.kind, kind, mode)
        Stub.mode = "rate_limit"
        with self.assertRaises(ProviderError) as caught: self.provider.complete(self.request())
        self.assertEqual(caught.exception.retry_after, 2.0); self.assertTrue(caught.exception.retryable)

    def test_timeout(self) -> None:
        Stub.mode = "slow"
        with self.assertRaises(ProviderError) as caught: self.provider.complete(self.request(timeout=0.3))
        self.assertEqual(caught.exception.kind, "timeout")

    def test_unknown_usage_is_reported_as_unverified(self) -> None:
        Stub.mode = "no_usage"; usage = self.provider.complete(self.request()).usage
        self.assertIsNone(usage.input_tokens); self.assertFalse(usage.verified); self.assertIn("unverified", usage.to_dict()["status"])

    def test_unconfigured_model_and_unreachable_server(self) -> None:
        Stub.models = ["other:latest"]; self.assertFalse(self.provider.validate_config()["ok"])
        self.assertEqual(OllamaProvider("llama3.1", "http://127.0.0.1:1").validate_config()["ok"], False)

    def test_remote_endpoint_is_marked_remote(self) -> None:
        self.assertEqual(OllamaProvider("m", "https://gpu.example.com:11434").boundary, "remote")


class FallbackAndBudgetTests(unittest.TestCase):
    def config(self, **fallback) -> dict:
        config = json.loads(json.dumps(DEFAULT_CONFIG)); config["providers"] = {"mock": {"enabled": True}, "ollama": {"enabled": True, "model": "m"}}
        config["fallback"].update(fallback); return config

    def test_fallback_to_an_authorized_local_provider(self) -> None:
        primary = MockProvider(failures={"t": ["unavailable"]}); secondary = MockProvider({"t": {"status": "completed", "summary": "from secondary"}})
        secondary.name = "ollama"
        response, trail = complete_with_fallback(self.config(order=["ollama"]), {"mock": primary, "ollama": secondary}, ProviderRequest("s", "p", metadata={"task_key": "t"}))
        self.assertEqual(response.structured["summary"], "from secondary"); self.assertEqual([t.get("error") or "ok" for t in trail], ["unavailable", "ok"])

    def test_fallback_is_denied_without_authorization(self) -> None:
        primary = MockProvider(failures={"t": ["unavailable"]}); secondary = MockProvider(); secondary.name = "ollama"
        with self.assertRaises(ProviderError): complete_with_fallback(self.config(order=[]), {"mock": primary, "ollama": secondary}, ProviderRequest("s", "p", metadata={"task_key": "t"}))
        self.assertEqual(secondary.calls, [])

    def test_fallback_never_moves_data_to_a_remote_provider_by_default(self) -> None:
        config = self.config(order=["ollama"]); config["privacy"]["local_only"] = False
        primary = MockProvider(failures={"t": ["unavailable"]}); remote = MockProvider(); remote.name = "ollama"; remote.boundary = "remote"
        with self.assertRaises(ProviderError): complete_with_fallback(config, {"mock": primary, "ollama": remote}, ProviderRequest("s", "p", metadata={"task_key": "t"}))
        self.assertEqual(remote.calls, [])
        config["fallback"]["allow_cross_boundary"] = True
        response, _ = complete_with_fallback(config, {"mock": MockProvider(failures={"t": ["unavailable"]}), "ollama": remote}, ProviderRequest("s", "p", metadata={"task_key": "t"}))
        self.assertTrue(response.simulated)

    def test_privacy_policy_filters_remote_providers(self) -> None:
        remote = MockProvider(); remote.boundary = "remote"; remote.name = "ollama"
        decisions = select(self.config(order=["ollama"]), {"mock": MockProvider(), "ollama": remote})
        self.assertEqual([d["eligible"] for d in decisions], [True, False]); self.assertIn("local_only", decisions[1]["reason"])

    def test_non_availability_errors_do_not_fall_back(self) -> None:
        secondary = MockProvider(); secondary.name = "ollama"
        with self.assertRaises(ProviderError) as caught:
            complete_with_fallback(self.config(order=["ollama"]), {"mock": MockProvider(failures={"t": ["auth"]}), "ollama": secondary}, ProviderRequest("s", "p", metadata={"task_key": "t"}))
        self.assertEqual(caught.exception.kind, "auth"); self.assertEqual(secondary.calls, [])

    def test_budgets_cap_calls_and_count_unverified_usage(self) -> None:
        budget = Budget(max_calls=2, scope="task")
        for _ in range(2): complete_with_fallback(self.config(), {"mock": MockProvider(report_usage=False)}, ProviderRequest("s", "p"), budgets=[budget])
        with self.assertRaises(ProviderError) as caught: complete_with_fallback(self.config(), {"mock": MockProvider()}, ProviderRequest("s", "p"), budgets=[budget])
        self.assertEqual(caught.exception.kind, "budget_exceeded"); self.assertFalse(caught.exception.retryable)
        self.assertEqual(budget.to_dict()["unverified_calls"], 2)

    def test_no_eligible_provider_is_reported(self) -> None:
        no_json = MockProvider(); no_json.capabilities = lambda: {"structured_output": False}
        decisions = select(self.config(), {"mock": no_json}); self.assertEqual(decisions[0]["reason"], "no structured output")
        config = self.config(); config["providers"]["mock"]["enabled"] = False
        with self.assertRaises(ProviderError) as caught: complete_with_fallback(config, {"mock": MockProvider()}, ProviderRequest("s", "p"))
        self.assertEqual(caught.exception.kind, "not_configured"); self.assertIn("not enabled", str(caught.exception))

    def test_describe_and_doctor_read_project_configuration(self) -> None:
        import tempfile
        from pathlib import Path
        from pallaquino_cli.core import atomic_json
        from pallaquino_cli.providers.router import describe, doctor, load_config
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
            root = Path(temp); self.assertEqual(load_config(root)["default"], "mock")  # no file: safe defaults
            responses = root / "responses.json"; responses.write_text('{"t": {"status": "completed", "summary": "scripted"}}', encoding="utf-8")
            config = self.config(); config["providers"]["mock"]["responses_file"] = "responses.json"; config["providers"]["ollama"] = {"enabled": False, "model": "m"}
            atomic_json(root / "governance/providers.json", config)
            self.assertEqual([(r["name"], r["enabled"]) for r in describe(root)], [("mock", True), ("ollama", False)])
            report = doctor(root); self.assertTrue(report["ok"]); self.assertEqual(report["checks"][1]["detail"], "disabled in governance/providers.json")
            from pallaquino_cli.providers.router import build_provider
            scripted = build_provider("mock", config["providers"]["mock"], root)
            self.assertEqual(scripted.complete(ProviderRequest("s", "p", metadata={"task_key": "t"})).structured["summary"], "scripted")

    def test_invalid_configuration_is_rejected(self) -> None:
        config = self.config(order=["ghost"]); config["providers"]["openai"] = {"enabled": True}
        errors = validate_config(config)
        self.assertIn("fallback provider ghost is not configured", errors); self.assertIn("no adapter for provider openai; available adapters: mock, ollama", errors)


if __name__ == "__main__":
    unittest.main()
