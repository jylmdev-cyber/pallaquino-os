"""PALLAQUINO Provider Abstraction Layer: provider contract, normalized errors, usage accounting and budgets (ADR-0012)."""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any, Protocol

ERROR_KINDS = {"not_configured", "auth", "rate_limit", "timeout", "unavailable", "invalid_response", "budget_exceeded", "cancelled"}
RETRYABLE = {"rate_limit", "timeout", "unavailable"}


class ProviderError(RuntimeError):
    """Every adapter raises this normalized error; `kind` drives retry and fallback decisions."""

    def __init__(self, kind: str, message: str, *, provider: str = "", retry_after: float | None = None):
        if kind not in ERROR_KINDS: raise ValueError(f"unknown provider error kind {kind}")
        super().__init__(f"{provider or 'provider'}: {kind}: {message}")
        self.kind = kind; self.provider = provider; self.retry_after = retry_after

    @property
    def retryable(self) -> bool:
        return self.kind in RETRYABLE


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    verified: bool = False          # True only when the provider itself reported the counts
    cost_estimated: float | None = None
    cost_verified: bool = False     # True only for a billed amount reported by the provider

    def to_dict(self) -> dict[str, Any]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "verified": self.verified,
                "cost_estimated": self.cost_estimated, "cost_verified": self.cost_verified,
                "status": "verified" if self.verified else "unverified: provider did not report usage"}


@dataclass
class ProviderRequest:
    system: str
    prompt: str
    json_output: bool = True
    max_output_tokens: int = 2048
    timeout_seconds: float = 60.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProviderResponse:
    provider: str
    model: str
    text: str
    structured: Any
    usage: Usage
    latency_ms: float
    simulated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"provider": self.provider, "model": self.model, "structured": self.structured, "usage": self.usage.to_dict(),
                "latency_ms": round(self.latency_ms, 2), "simulated": self.simulated}


class Provider(Protocol):
    name: str
    boundary: str  # "local" (data stays on this machine) or "remote"

    def capabilities(self) -> dict[str, Any]: ...
    def validate_config(self) -> dict[str, Any]: ...
    def complete(self, request: ProviderRequest) -> ProviderResponse: ...


def parse_structured(provider: str, text: str) -> Any:
    """Structured output must be a JSON object; anything else is an invalid response, never guessed at."""
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`"); candidate = candidate[candidate.find("{"):] if "{" in candidate else candidate
    try: value = json.loads(candidate)
    except ValueError as exc: raise ProviderError("invalid_response", f"response is not valid JSON ({exc})", provider=provider) from None
    if not isinstance(value, dict): raise ProviderError("invalid_response", "structured response must be a JSON object", provider=provider)
    return value


class Budget:
    """Caps calls, tokens and estimated cost for one scope (execution, task, provider or project).

    Calls with unreported usage still count as calls; their tokens are tracked as unknown so a budget can never
    be satisfied by missing data. Exceeding a cap raises a non-retryable budget_exceeded error before the call.
    """

    def __init__(self, *, max_calls: int | None = None, max_tokens: int | None = None, max_cost: float | None = None, scope: str = "execution"):
        self.max_calls = max_calls; self.max_tokens = max_tokens; self.max_cost = max_cost; self.scope = scope
        self.calls = 0; self.tokens = 0; self.cost = 0.0; self.unverified_calls = 0; self._lock = threading.Lock()

    def check(self) -> None:
        with self._lock:
            if self.max_calls is not None and self.calls >= self.max_calls: raise ProviderError("budget_exceeded", f"{self.scope} call budget {self.max_calls} exhausted")
            if self.max_tokens is not None and self.tokens >= self.max_tokens: raise ProviderError("budget_exceeded", f"{self.scope} token budget {self.max_tokens} exhausted")
            if self.max_cost is not None and self.cost >= self.max_cost: raise ProviderError("budget_exceeded", f"{self.scope} cost budget {self.max_cost} exhausted")

    def record(self, usage: Usage) -> None:
        with self._lock:
            self.calls += 1
            if usage.input_tokens is None or usage.output_tokens is None: self.unverified_calls += 1
            else: self.tokens += usage.input_tokens + usage.output_tokens
            if usage.cost_estimated: self.cost += usage.cost_estimated

    def to_dict(self) -> dict[str, Any]:
        return {"scope": self.scope, "calls": self.calls, "tokens": self.tokens, "cost_estimated": round(self.cost, 6), "unverified_calls": self.unverified_calls,
                "limits": {"max_calls": self.max_calls, "max_tokens": self.max_tokens, "max_cost": self.max_cost}}
