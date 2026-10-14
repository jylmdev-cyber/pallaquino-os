"""Outbound network policy for remote MCP servers, OAuth endpoints and HTTP adapters (SSRF defence).

Rules: HTTPS only (plain HTTP solely to loopback when the connection explicitly allows it, for local servers);
no credentials or fragments in URLs; every resolved address is checked and private, loopback, link-local
(including cloud metadata at 169.254.169.254), multicast, reserved and unspecified addresses are refused unless the
policy allows them; the connection is then pinned to the checked address so a DNS answer cannot change between the
check and the connect (rebinding). Redirects are never followed by the transport; callers decide.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class NetworkPolicyError(PermissionError):
    """A destination was refused by the network policy."""


@dataclass(frozen=True)
class NetworkPolicy:
    allow_loopback: bool = False
    allow_private: bool = False
    allow_http_loopback: bool = False
    allowed_hosts: frozenset[str] = field(default_factory=frozenset)
    max_response_bytes: int = 4 * 1024 * 1024
    timeout_seconds: float = 30.0

    @classmethod
    def from_config(cls, data: dict | None) -> "NetworkPolicy":
        data = data or {}
        return cls(allow_loopback=bool(data.get("allow_loopback")), allow_private=bool(data.get("allow_private")),
                   allow_http_loopback=bool(data.get("allow_http_loopback")), allowed_hosts=frozenset(h.lower() for h in data.get("allowed_hosts", [])),
                   max_response_bytes=int(data.get("max_response_bytes", 4 * 1024 * 1024)), timeout_seconds=float(data.get("timeout_seconds", 30.0)))

    def to_config(self) -> dict:
        return {"allow_loopback": self.allow_loopback, "allow_private": self.allow_private, "allow_http_loopback": self.allow_http_loopback,
                "allowed_hosts": sorted(self.allowed_hosts), "max_response_bytes": self.max_response_bytes, "timeout_seconds": self.timeout_seconds}


def _address_problem(address: ipaddress._BaseAddress, policy: NetworkPolicy) -> str | None:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped: address = address.ipv4_mapped
    if address.is_loopback: return None if policy.allow_loopback or policy.allow_http_loopback else "loopback"
    if address.is_link_local: return "link-local (includes cloud metadata endpoints)"
    if address.is_unspecified or address.is_multicast or address.is_reserved: return "unspecified, multicast or reserved"
    if address.is_private or (isinstance(address, ipaddress.IPv4Address) and address in ipaddress.ip_network("100.64.0.0/10")):
        return None if policy.allow_private else "private network"
    return None


def check_url(url: str, policy: NetworkPolicy, *, resolve: bool = True) -> tuple[str, str, int, str | None]:
    """Validate a URL; return (scheme, host, port, pinned_ip). Raises NetworkPolicyError."""
    if not isinstance(url, str) or len(url) > 2048: raise NetworkPolicyError("URL must be a string of at most 2048 characters")
    parts = urlsplit(url)
    scheme = parts.scheme.lower(); host = (parts.hostname or "").lower()
    if scheme not in ("https", "http"): raise NetworkPolicyError(f"scheme {scheme or '(none)'!r} is not allowed; use https")
    if not host: raise NetworkPolicyError("URL has no host")
    if parts.username or parts.password: raise NetworkPolicyError("credentials in URLs are not allowed")
    if parts.fragment: raise NetworkPolicyError("URL fragments are not allowed")
    if policy.allowed_hosts and host not in policy.allowed_hosts: raise NetworkPolicyError(f"host {host} is not in the allowed hosts")
    port = parts.port or (443 if scheme == "https" else 80)
    try: literal = ipaddress.ip_address(host)
    except ValueError: literal = None
    if not resolve and literal is None:
        if scheme == "http" and host != "localhost": raise NetworkPolicyError("plain http is only allowed to loopback")
        return scheme, host, port, None
    try: infos = [ipaddress.ip_address(info[4][0].split("%")[0]) for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)] if literal is None else [literal]
    except (socket.gaierror, UnicodeError) as exc: raise NetworkPolicyError(f"cannot resolve {host}: {exc}") from None
    if not infos: raise NetworkPolicyError(f"{host} resolved to no address")
    for address in infos:
        problem = _address_problem(address, policy)
        if problem: raise NetworkPolicyError(f"{host} resolves to {address}, a {problem} address; refused by the network policy")
    if scheme == "http" and not (policy.allow_http_loopback and all(a.is_loopback for a in infos)):
        raise NetworkPolicyError("plain http is only allowed to loopback servers explicitly configured with allow_http_loopback")
    return scheme, host, port, str(infos[0])


def same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme.lower(), (pa.hostname or "").lower(), pa.port or (443 if pa.scheme == "https" else 80)) == \
           (pb.scheme.lower(), (pb.hostname or "").lower(), pb.port or (443 if pb.scheme == "https" else 80))
