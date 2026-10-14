"""Deterministic, offline provider for tests and simulations. Every response is labelled simulated."""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from .base import ProviderError, ProviderRequest, ProviderResponse, Usage, parse_structured

Responder = Callable[[ProviderRequest], Any]


class MockProvider:
    """Scripted responses keyed by `request.metadata['task_key']` or `['agent']`, else a neutral default.

    `failures` injects normalized errors for the first N calls of a key (e.g. {"T03": ["rate_limit", "timeout"]}) so
    retry, timeout and fallback behaviour is exercised without any network.
    """

    name = "mock"
    boundary = "local"

    def __init__(self, responses: dict[str, Any] | None = None, *, failures: dict[str, list[str]] | None = None,
                 default: Any | None = None, report_usage: bool = True, delay_seconds: float = 0.0, configured: bool = True):
        self.responses = responses or {}; self.failures = {k: list(v) for k, v in (failures or {}).items()}
        self.default = default; self.report_usage = report_usage; self.delay_seconds = delay_seconds; self.configured = configured
        self.calls: list[dict[str, Any]] = []

    def capabilities(self) -> dict[str, Any]:
        return {"structured_output": True, "tools": False, "streaming": False, "boundary": self.boundary, "simulated": True}

    def validate_config(self) -> dict[str, Any]:
        return {"ok": self.configured, "provider": self.name, "detail": "deterministic offline provider" if self.configured else "disabled"}

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        if not self.configured: raise ProviderError("not_configured", "mock provider disabled", provider=self.name)
        key = request.metadata.get("task_key") or request.metadata.get("agent") or "default"
        self.calls.append({"key": key, "agent": request.metadata.get("agent"), "prompt_chars": len(request.prompt)})
        pending = self.failures.get(key)
        if pending:
            kind = pending.pop(0)
            if kind == "slow": time.sleep(request.timeout_seconds + 0.05); raise ProviderError("timeout", "simulated slow response", provider=self.name)
            raise ProviderError(kind, "simulated failure", provider=self.name, retry_after=0.0 if kind == "rate_limit" else None)
        if self.delay_seconds: time.sleep(self.delay_seconds)
        script = self.responses.get(key, self.responses.get(request.metadata.get("agent", ""), self.default))
        value = script(request) if callable(script) else script
        if value is None:
            value = {"status": "completed", "summary": f"SIMULATED: {request.metadata.get('agent')} produced no changes", "findings": [], "file_changes": []}
        text = value if isinstance(value, str) else json.dumps(value)
        structured = parse_structured(self.name, text) if request.json_output else None
        usage = Usage(len(request.prompt) // 4, len(text) // 4, verified=True, cost_estimated=0.0) if self.report_usage else Usage()
        return ProviderResponse(self.name, "mock-deterministic", text, structured, usage, latency_ms=0.0, simulated=True)
