"""Provider configuration, selection and authorized fallback.

Selection filters configured providers by requirements (structured output, privacy boundary) and orders them by
preference. Fallback is attempted only for availability errors, only to providers listed in `fallback.order`,
and never from a local provider to a remote one unless `fallback.allow_cross_boundary` is true, so sensitive data
is not moved to another service without explicit permission.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import Budget, Provider, ProviderError, ProviderRequest, ProviderResponse
from .mock import MockProvider
from .ollama import OllamaProvider

CONFIG_PATH = "governance/providers.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1, "default": "mock",
    "providers": {"mock": {"enabled": True}, "ollama": {"enabled": False, "model": "llama3.1", "base_url": "http://127.0.0.1:11434"}},
    "fallback": {"order": [], "allow_cross_boundary": False},
    "privacy": {"local_only": True},
    "budgets": {"execution": {"max_calls": 200, "max_tokens": 400000, "max_cost": None}, "task": {"max_calls": 12}},
}
FALLBACK_ERRORS = {"unavailable", "rate_limit", "timeout", "not_configured"}


def load_config(root: Path) -> dict[str, Any]:
    path = Path(root) / CONFIG_PATH
    if not path.is_file(): return json.loads(json.dumps(DEFAULT_CONFIG))
    config = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_config(config)
    if errors: raise ValueError(f"{CONFIG_PATH}: " + "; ".join(errors))
    return config


def validate_config(config: dict[str, Any]) -> list[str]:
    errors = []
    providers = config.get("providers", {})
    if not isinstance(providers, dict) or not providers: errors.append("providers must be a non-empty object")
    if config.get("default") not in providers: errors.append("default must name a configured provider")
    for name in config.get("fallback", {}).get("order", []):
        if name not in providers: errors.append(f"fallback provider {name} is not configured")
    for name in providers:
        if name not in ("mock", "ollama"): errors.append(f"no adapter for provider {name}; available adapters: mock, ollama")
    return errors


def build_provider(name: str, settings: dict[str, Any], root: Path | None = None) -> Provider:
    if name == "mock":
        responses = None
        if settings.get("responses_file"):  # scripted, deterministic simulation (e.g. the reference scenario)
            path = Path(settings["responses_file"]); path = path if path.is_absolute() or root is None else Path(root) / path
            responses = json.loads(path.read_text(encoding="utf-8"))
        return MockProvider(responses, configured=bool(settings.get("enabled", True)))
    if name == "ollama": return OllamaProvider(settings["model"], settings.get("base_url", "http://127.0.0.1:11434"), timeout_seconds=float(settings.get("timeout_seconds", 120)))
    raise ValueError(f"no adapter for provider {name}")


def describe(root: Path) -> list[dict[str, Any]]:
    config = load_config(root); rows = []
    for name, settings in config["providers"].items():
        provider = build_provider(name, settings, root)
        rows.append({"name": name, "enabled": bool(settings.get("enabled")), "default": name == config["default"], "boundary": provider.boundary,
                     "capabilities": provider.capabilities()})
    return rows


def doctor(root: Path, providers: dict[str, Provider] | None = None) -> dict[str, Any]:
    config = load_config(root); checks = []
    for name, settings in config["providers"].items():
        if not settings.get("enabled"): checks.append({"provider": name, "ok": False, "detail": "disabled in governance/providers.json"}); continue
        provider = (providers or {}).get(name) or build_provider(name, settings, root)
        checks.append({**provider.validate_config(), "provider": name, "boundary": provider.boundary})
    default_ok = any(c["provider"] == config["default"] and c["ok"] for c in checks)
    return {"ok": default_ok, "default": config["default"], "checks": checks}


def select(config: dict[str, Any], providers: dict[str, Provider], *, structured_output: bool = True, preferred: str | None = None) -> list[dict[str, Any]]:
    """Ordered candidate list with the reason each provider was kept or rejected."""
    local_only = bool(config.get("privacy", {}).get("local_only", True))
    order = [preferred or config["default"]] + [n for n in config.get("fallback", {}).get("order", []) if n != (preferred or config["default"])]
    decisions = []
    for name in order:
        settings = config["providers"].get(name, {}); provider = providers.get(name)
        if provider is None or not settings.get("enabled"): decisions.append({"provider": name, "eligible": False, "reason": "not enabled"}); continue
        caps = provider.capabilities()
        if structured_output and not caps.get("structured_output"): decisions.append({"provider": name, "eligible": False, "reason": "no structured output"}); continue
        if local_only and provider.boundary != "local": decisions.append({"provider": name, "eligible": False, "reason": "privacy.local_only forbids remote providers"}); continue
        decisions.append({"provider": name, "eligible": True, "reason": "preferred" if name == order[0] else "authorized fallback", "boundary": provider.boundary})
    return decisions


def complete_with_fallback(config: dict[str, Any], providers: dict[str, Provider], request: ProviderRequest, *,
                           budgets: list[Budget] = (), preferred: str | None = None) -> tuple[ProviderResponse, list[dict[str, Any]]]:
    allow_cross = bool(config.get("fallback", {}).get("allow_cross_boundary", False))
    decisions = select(config, providers, structured_output=request.json_output, preferred=preferred)
    candidates = [d for d in decisions if d["eligible"]]
    if not candidates: raise ProviderError("not_configured", "no eligible provider: " + "; ".join(f"{d['provider']}: {d['reason']}" for d in decisions))
    trail: list[dict[str, Any]] = []; first_boundary = candidates[0]["boundary"]; last_error: ProviderError | None = None
    for index, candidate in enumerate(candidates):
        name = candidate["provider"]
        if index and candidate["boundary"] != first_boundary and not allow_cross:
            trail.append({"provider": name, "skipped": f"fallback across the {first_boundary}->{candidate['boundary']} boundary is not authorized"}); continue
        for budget in budgets: budget.check()
        try:
            response = providers[name].complete(request)
        except ProviderError as exc:
            trail.append({"provider": name, "error": exc.kind}); last_error = exc
            if exc.kind not in FALLBACK_ERRORS: raise
            continue
        for budget in budgets: budget.record(response.usage)
        trail.append({"provider": name, "ok": True}); return response, trail
    assert last_error is not None
    raise last_error
