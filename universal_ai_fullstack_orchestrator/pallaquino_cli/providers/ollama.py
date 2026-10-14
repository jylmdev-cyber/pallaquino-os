"""Ollama adapter for local models over its HTTP API (standard library only).

Endpoints used: GET /api/tags (model discovery) and POST /api/chat with `stream: false` and `format: "json"`.
Token counts come from the response fields `prompt_eval_count` and `eval_count`; local inference has no
billing, so cost is reported as 0.0 estimated and never as a verified charge.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from typing import Any

from .base import ProviderError, ProviderRequest, ProviderResponse, Usage, parse_structured


class OllamaProvider:
    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434", *, timeout_seconds: float = 120.0):
        self.model = model; self.base_url = base_url.rstrip("/"); self.timeout_seconds = timeout_seconds
        host = self.base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        # Data leaves the machine unless the endpoint is loopback; privacy routing relies on this flag.
        self.boundary = "local" if host in ("127.0.0.1", "localhost", "::1", "[::1]") else "remote"

    def _request(self, method: str, path: str, body: dict[str, Any] | None, timeout: float) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response: payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            kind = {401: "auth", 403: "auth", 404: "not_configured", 429: "rate_limit"}.get(exc.code, "unavailable" if exc.code >= 500 else "invalid_response")
            raise ProviderError(kind, f"HTTP {exc.code}: {detail}", provider=self.name, retry_after=float(exc.headers.get("Retry-After") or 0) or None) from None
        except (socket.timeout, TimeoutError):
            raise ProviderError("timeout", f"no response within {timeout}s", provider=self.name) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)): raise ProviderError("timeout", f"no response within {timeout}s", provider=self.name) from None
            raise ProviderError("unavailable", f"cannot reach {self.base_url}: {exc.reason}", provider=self.name) from None
        try: return json.loads(payload)
        except ValueError: raise ProviderError("invalid_response", "server returned non-JSON payload", provider=self.name) from None

    def capabilities(self) -> dict[str, Any]:
        return {"structured_output": True, "tools": False, "streaming": False, "boundary": self.boundary, "simulated": False, "model": self.model}

    def validate_config(self) -> dict[str, Any]:
        try: tags = self._request("GET", "/api/tags", None, min(self.timeout_seconds, 5.0))
        except ProviderError as exc: return {"ok": False, "provider": self.name, "error": exc.kind, "detail": str(exc)}
        models = [m.get("name") for m in tags.get("models", []) if isinstance(m, dict)]
        found = self.model in models or f"{self.model}:latest" in models
        return {"ok": found, "provider": self.name, "models": models, "detail": "model available" if found else f"model {self.model} not pulled"}

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        body = {"model": self.model, "stream": False, "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.prompt}],
                "options": {"num_predict": request.max_output_tokens}}
        if request.json_output: body["format"] = "json"
        started = time.perf_counter()
        payload = self._request("POST", "/api/chat", body, min(request.timeout_seconds, self.timeout_seconds))
        latency = (time.perf_counter() - started) * 1000
        message = payload.get("message") if isinstance(payload, dict) else None
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ProviderError("invalid_response", "response has no message.content", provider=self.name)
        text = message["content"]
        prompt_tokens, output_tokens = payload.get("prompt_eval_count"), payload.get("eval_count")
        reported = isinstance(prompt_tokens, int) and isinstance(output_tokens, int)
        usage = Usage(prompt_tokens if reported else None, output_tokens if reported else None, verified=reported, cost_estimated=0.0)
        structured = parse_structured(self.name, text) if request.json_output else None
        return ProviderResponse(self.name, self.model, text, structured, usage, latency_ms=latency, simulated=False)
