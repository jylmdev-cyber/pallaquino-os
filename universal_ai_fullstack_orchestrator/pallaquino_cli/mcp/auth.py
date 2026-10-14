"""Credential manager and OAuth 2.1 client plumbing for remote MCP servers (ADR-0016).

Credentials are referenced, never embedded: configuration stores `credential_ref` values such as `env:GITHUB_TOKEN`
(stdio servers and adapters read credentials from the environment, as the specification recommends) or
`vault:<server>` (tokens obtained through OAuth). The vault keys every token by (project, server, issuer) and never
hands a token to another server or issuer. It uses the OS keyring when the optional `keyring` package is present;
otherwise a JSON file outside the workspace protected only by OS file permissions (it is not encrypted, and this
is reported by `describe()`). Tokens never reach logs, events, prompts or tool arguments.

OAuth follows the MCP 2026-07-28 authorization flow: protected resource metadata (RFC 9728, from the
`WWW-Authenticate` challenge or the well-known URIs), authorization server metadata (RFC 8414 / OpenID Connect
discovery in the specified order, with exact issuer validation), PKCE S256, the `resource` parameter (RFC 8707),
issuer validation of the authorization response (RFC 9207) and step-up scope union. Only standard-library HTTP,
hashing and randomness are used; there is no custom cryptography. Dynamic Client Registration (deprecated in
2026-07-28) is not implemented: clients are pre-registered or use a Client ID Metadata Document URL.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from .netpolicy import NetworkPolicy
from .transports import TransportError, http_exchange


class AuthError(RuntimeError):
    """Normalized authentication error; `kind` is one of not_configured, discovery, invalid_issuer, pkce_unsupported,
    state_mismatch, authorization_denied, token_error, expired, insufficient_scope, wrong_audience."""

    def __init__(self, kind: str, message: str):
        super().__init__(message); self.kind = kind


# -- credential store -------------------------------------------------------------------------------------
def _default_vault_dir() -> Path:
    return Path(os.environ.get("PALLAQUINO_CREDENTIALS_DIR") or Path.home() / ".pallaquino" / "credentials")


class CredentialStore:
    def __init__(self, project: str, *, vault_dir: Path | None = None, use_keyring: bool | None = None):
        self.project = project; self.vault_dir = Path(vault_dir or _default_vault_dir()); self._lock = threading.Lock()
        self.keyring = None
        if use_keyring is not False:
            try:
                import keyring  # optional; never required
                self.keyring = keyring if use_keyring or os.environ.get("PALLAQUINO_USE_KEYRING") == "1" else None
            except ImportError: self.keyring = None

    def describe(self) -> dict[str, Any]:
        backend = "os-keyring" if self.keyring else "file"
        return {"backend": backend, "location": None if self.keyring else str(self.vault_dir),
                "protection": "OS keyring" if self.keyring else "OS file permissions only (not encrypted); prefer env: references or install keyring"}

    def _file(self) -> Path:
        return self.vault_dir / f"{self.project}.json"

    def _load(self) -> dict[str, Any]:
        try: return json.loads(self._file().read_text(encoding="utf-8"))
        except (OSError, ValueError): return {}

    def _save(self, data: dict[str, Any]) -> None:
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        path = self._file(); tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        if os.name == "posix": os.chmod(tmp, 0o600)
        os.replace(tmp, path)

    @staticmethod
    def _key(server: str, issuer: str) -> str:
        return f"{server}|{issuer}"

    def put_token(self, server: str, issuer: str, token: dict[str, Any]) -> str:
        key = self._key(server, issuer)
        with self._lock:
            if self.keyring: self.keyring.set_password(f"pallaquino:{self.project}", key, json.dumps(token))
            else: data = self._load(); data[key] = token; self._save(data)
        return f"vault:{server}"

    def get_token(self, server: str, issuer: str) -> dict[str, Any] | None:
        key = self._key(server, issuer)
        with self._lock:
            if self.keyring:
                raw = self.keyring.get_password(f"pallaquino:{self.project}", key); return json.loads(raw) if raw else None
            return self._load().get(key)

    def delete(self, server: str, issuer: str | None = None) -> int:
        with self._lock:
            if self.keyring:
                if issuer is None: return 0
                try: self.keyring.delete_password(f"pallaquino:{self.project}", self._key(server, issuer)); return 1
                except Exception: return 0
            data = self._load(); doomed = [k for k in data if k.split("|", 1)[0] == server and (issuer is None or k == self._key(server, issuer))]
            for k in doomed: del data[k]
            if doomed: self._save(data)
            return len(doomed)

    def resolve(self, ref: str | None, *, server: str, issuer: str | None = None) -> str | None:
        """Resolve a credential reference to a secret for one server. Unknown schemes are refused."""
        if not ref: return None
        scheme, _, name = ref.partition(":")
        if scheme == "env":
            if not re.fullmatch(r"[A-Z_][A-Z0-9_]{0,100}", name): raise AuthError("not_configured", f"invalid environment variable name in {ref!r}")
            return os.environ.get(name)
        if scheme == "vault":
            if name != server: raise AuthError("wrong_audience", f"credential {ref} belongs to server {name}, not {server}")
            token = self.get_token(server, issuer or "")
            return token.get("access_token") if token else None
        raise AuthError("not_configured", f"unsupported credential reference scheme {scheme!r}")


# -- OAuth discovery and flow -----------------------------------------------------------------------------
def parse_www_authenticate(header: str | None) -> dict[str, str]:
    if not header: return {}
    _, _, rest = header.partition(" ")
    return {k.lower(): v for k, v in re.findall(r'(\w+)="([^"]*)"', rest)}


def canonical_resource(url: str) -> str:
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc: raise AuthError("discovery", f"{url!r} is not an absolute URI")
    path = parts.path.rstrip("/") if parts.path not in ("", "/") else ""
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _get_json(url: str, policy: NetworkPolicy) -> dict[str, Any] | None:
    try: status, _, body = http_exchange(url, policy=policy, headers={"Accept": "application/json"})
    except TransportError: return None
    if status != 200: return None
    try: data = json.loads(body)
    except ValueError: return None
    return data if isinstance(data, dict) else None


def protected_resource_urls(mcp_url: str) -> list[str]:
    parts = urlsplit(mcp_url); origin = f"{parts.scheme}://{parts.netloc}"; path = parts.path.rstrip("/")
    urls = [f"{origin}/.well-known/oauth-protected-resource{path}"] if path else []
    return urls + [f"{origin}/.well-known/oauth-protected-resource"]


def authorization_server_urls(issuer: str) -> list[str]:
    parts = urlsplit(issuer); origin = f"{parts.scheme}://{parts.netloc}"; path = parts.path.rstrip("/")
    if path: return [f"{origin}/.well-known/oauth-authorization-server{path}", f"{origin}/.well-known/openid-configuration{path}", f"{origin}{path}/.well-known/openid-configuration"]
    return [f"{origin}/.well-known/oauth-authorization-server", f"{origin}/.well-known/openid-configuration"]


def discover(mcp_url: str, *, policy: NetworkPolicy, challenge: str | None = None) -> dict[str, Any]:
    """Protected resource metadata, then authorization server metadata with exact issuer and PKCE checks."""
    params = parse_www_authenticate(challenge)
    candidates = [params["resource_metadata"]] if params.get("resource_metadata") else protected_resource_urls(mcp_url)
    resource_meta = next((m for m in (_get_json(u, policy) for u in candidates) if m), None)
    if resource_meta is None: raise AuthError("discovery", f"no protected resource metadata for {mcp_url}")
    if resource_meta.get("resource") and canonical_resource(resource_meta["resource"]) != canonical_resource(mcp_url) and \
            not canonical_resource(mcp_url).startswith(canonical_resource(resource_meta["resource"])):
        raise AuthError("wrong_audience", f"metadata describes resource {resource_meta['resource']}, not {mcp_url}")
    servers = resource_meta.get("authorization_servers") or []
    if not servers: raise AuthError("discovery", "protected resource metadata lists no authorization server")
    issuer = servers[0]
    for url in authorization_server_urls(issuer):
        meta = _get_json(url, policy)
        if meta is None: continue
        if meta.get("issuer") != issuer: raise AuthError("invalid_issuer", f"metadata at {url} claims issuer {meta.get('issuer')!r}, expected {issuer!r}")
        if "S256" not in (meta.get("code_challenge_methods_supported") or []): raise AuthError("pkce_unsupported", f"{issuer} does not advertise PKCE S256; refusing to proceed")
        scopes = params.get("scope", "").split() or resource_meta.get("scopes_supported") or []
        return {"resource": canonical_resource(mcp_url), "resource_metadata": resource_meta, "issuer": issuer, "as_metadata": meta, "scopes": scopes}
    raise AuthError("discovery", f"no authorization server metadata for {issuer}")


@dataclass
class PendingAuthorization:
    server: str; issuer: str; resource: str; client_id: str; redirect_uri: str; scopes: list[str]
    state: str; verifier: str; authorization_url: str; as_metadata: dict[str, Any] = field(repr=False, default_factory=dict)
    created: float = field(default_factory=time.time)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
    return verifier, challenge


def start_authorization(server: str, discovery: dict[str, Any], *, client_id: str, redirect_uri: str, extra_scopes: list[str] | None = None,
                        previous_scopes: list[str] | None = None) -> PendingAuthorization:
    """Build the authorization URL (PKCE S256, state, resource). Scopes are the union of previous and challenged scopes (step-up)."""
    meta = discovery["as_metadata"]; endpoint = meta.get("authorization_endpoint")
    if not endpoint: raise AuthError("discovery", "authorization server metadata has no authorization_endpoint")
    scopes = sorted(set(previous_scopes or []) | set(discovery.get("scopes") or []) | set(extra_scopes or []))
    verifier, challenge = pkce_pair(); state = secrets.token_urlsafe(24)
    query = {"response_type": "code", "client_id": client_id, "redirect_uri": redirect_uri, "code_challenge": challenge, "code_challenge_method": "S256",
             "state": state, "resource": discovery["resource"]}
    if scopes: query["scope"] = " ".join(scopes)
    return PendingAuthorization(server, discovery["issuer"], discovery["resource"], client_id, redirect_uri, scopes, state, verifier,
                                f"{endpoint}?{urlencode(query)}", meta)


def validate_callback(pending: PendingAuthorization, params: dict[str, str]) -> str:
    """RFC 9207 issuer validation and state check before the code is sent anywhere. Returns the code."""
    supported = bool(pending.as_metadata.get("authorization_response_iss_parameter_supported"))
    iss = params.get("iss")
    if iss is not None and iss != pending.issuer: raise AuthError("invalid_issuer", "authorization response issuer does not match the recorded issuer")
    if iss is None and supported: raise AuthError("invalid_issuer", "authorization server advertises iss but the response omitted it")
    if not secrets.compare_digest(params.get("state", ""), pending.state): raise AuthError("state_mismatch", "authorization response state does not match")
    if params.get("error"): raise AuthError("authorization_denied", f"authorization denied: {params.get('error')}")
    if not params.get("code"): raise AuthError("authorization_denied", "authorization response has no code")
    return params["code"]


def _token_request(meta: dict[str, Any], form: dict[str, str], policy: NetworkPolicy) -> dict[str, Any]:
    endpoint = meta.get("token_endpoint")
    if not endpoint: raise AuthError("discovery", "authorization server metadata has no token_endpoint")
    try: status, _, body = http_exchange(endpoint, method="POST", body=urlencode(form).encode("ascii"), policy=policy,
                                         headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    except TransportError as exc: raise AuthError("token_error", f"token endpoint unreachable: {exc}") from None
    try: data = json.loads(body)
    except ValueError: data = {}
    if status != 200 or not data.get("access_token"): raise AuthError("token_error", f"token request failed (HTTP {status}, {data.get('error', 'no access_token')})")
    if str(data.get("token_type", "bearer")).lower() != "bearer": raise AuthError("token_error", f"unsupported token type {data.get('token_type')}")
    expires_in = data.get("expires_in")
    return {"access_token": data["access_token"], "refresh_token": data.get("refresh_token"), "scope": data.get("scope", form.get("scope", "")),
            "expires_at": time.time() + float(expires_in) if isinstance(expires_in, (int, float)) else None, "token_type": "Bearer"}


def complete_authorization(pending: PendingAuthorization, callback: dict[str, str], store: CredentialStore, *, policy: NetworkPolicy) -> dict[str, Any]:
    code = validate_callback(pending, callback)
    token = _token_request(pending.as_metadata, {"grant_type": "authorization_code", "code": code, "redirect_uri": pending.redirect_uri,
                                                 "client_id": pending.client_id, "code_verifier": pending.verifier, "resource": pending.resource}, policy)
    token.update({"issuer": pending.issuer, "resource": pending.resource, "client_id": pending.client_id, "token_endpoint": pending.as_metadata.get("token_endpoint"),
                  "revocation_endpoint": pending.as_metadata.get("revocation_endpoint")})
    ref = store.put_token(pending.server, pending.issuer, token)
    return {"credential_ref": ref, "issuer": pending.issuer, "scopes": token["scope"].split(), "expires_at": token["expires_at"]}


def bearer_provider(store: CredentialStore, server: str, issuer: str, *, policy: NetworkPolicy, skew: float = 30.0):
    """Return a callable giving `Bearer <token>` for this server and issuer only, refreshing when allowed."""
    def header() -> str | None:
        token = store.get_token(server, issuer)
        if not token: return None
        if token.get("expires_at") and token["expires_at"] - skew < time.time():
            if not token.get("refresh_token") or not token.get("token_endpoint"): raise AuthError("expired", f"token for {server} expired; re-authorize")
            fresh = _token_request({"token_endpoint": token["token_endpoint"]}, {"grant_type": "refresh_token", "refresh_token": token["refresh_token"],
                                                                                  "client_id": token.get("client_id", ""), "resource": token.get("resource", "")}, policy)
            token.update({k: v for k, v in fresh.items() if v is not None}); store.put_token(server, issuer, token)
        return f"Bearer {token['access_token']}"
    return header


def revoke(store: CredentialStore, server: str, issuer: str, *, policy: NetworkPolicy | None = None) -> dict[str, Any]:
    """Delete the local token; also call the RFC 7009 revocation endpoint when advertised and a policy is given."""
    token = store.get_token(server, issuer); remote = None
    if token and token.get("revocation_endpoint") and policy is not None:
        try:
            status, _, _ = http_exchange(token["revocation_endpoint"], method="POST", policy=policy, headers={"Content-Type": "application/x-www-form-urlencoded"},
                                         body=urlencode({"token": token.get("refresh_token") or token["access_token"], "client_id": token.get("client_id", "")}).encode("ascii"))
            remote = status == 200
        except TransportError: remote = False
    return {"deleted": store.delete(server, issuer), "remote_revoked": remote}


def loopback_authorize(server: str, discovery: dict[str, Any], store: CredentialStore, *, client_id: str, policy: NetworkPolicy, timeout: float = 300.0,
                       open_url: Any = None, previous_scopes: list[str] | None = None) -> dict[str, Any]:
    """Native-app flow (RFC 8252): a one-shot callback listener on 127.0.0.1, the URL shown to the user (or passed
    to `open_url`), then issuer/state validation and the PKCE token exchange. Nothing is persisted but the token."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from urllib.parse import parse_qsl
    received: dict[str, str] = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            received.update(dict(parse_qsl(urlsplit(self.path).query)))
            body = b"PALLAQUINO received the authorization response. You can close this window."
            self.send_response(200); self.send_header("Content-Type", "text/plain"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    listener = HTTPServer(("127.0.0.1", 0), Callback); listener.timeout = timeout
    try:
        redirect_uri = f"http://127.0.0.1:{listener.server_address[1]}/callback"
        pending = start_authorization(server, discovery, client_id=client_id, redirect_uri=redirect_uri, previous_scopes=previous_scopes)
        if open_url: open_url(pending.authorization_url)
        else: print(f"Open this URL to authorize {server}:\n{pending.authorization_url}", flush=True)
        deadline = time.time() + timeout
        while not received and time.time() < deadline: listener.handle_request()
        if not received: raise AuthError("authorization_denied", "no authorization response before the timeout")
        return complete_authorization(pending, received, store, policy=policy)
    finally: listener.server_close()
