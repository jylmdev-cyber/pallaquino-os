"""Semantic Versioning 2.0.0 parsing, precedence and range checks (`>=0.5.0,<0.6.0`, `^1.2`, `~1.2.3`, `==1.0.0`)."""
from __future__ import annotations

import re
from functools import total_ordering

_VERSION = re.compile(r"^(0|[1-9]\d*)(?:\.(0|[1-9]\d*))?(?:\.(0|[1-9]\d*))?(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")
_COMPARATOR = re.compile(r"^(>=|<=|==|!=|>|<|\^|~|=)?\s*(.+)$")


@total_ordering
class Version:
    __slots__ = ("major", "minor", "patch", "pre")

    def __init__(self, text: str, *, strict: bool = False):
        """`strict` requires MAJOR.MINOR.PATCH (plugin versions); ranges may abbreviate (`^1.2`)."""
        match = _VERSION.match(text.strip()) if isinstance(text, str) else None
        if not match or (strict and (match.group(2) is None or match.group(3) is None)): raise ValueError(f"invalid semantic version {text!r}")
        self.major, self.minor, self.patch = (int(match.group(i) or 0) for i in (1, 2, 3))
        self.pre = tuple(int(p) if p.isdigit() else p for p in match.group(4).split(".")) if match.group(4) else ()

    def _key(self):
        # A pre-release has lower precedence than its release; numeric identifiers sort below alphanumeric ones.
        pre = tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in self.pre)
        return (self.major, self.minor, self.patch, 0 if self.pre else 1, pre)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self._key() == other._key()

    def __lt__(self, other: "Version") -> bool:
        return self._key() < other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}" + ("-" + ".".join(map(str, self.pre)) if self.pre else "")


def _expand(op: str, version: Version) -> list[tuple[str, Version]]:
    if op == "^":
        upper = Version(f"{version.major + 1}.0.0") if version.major else Version(f"0.{version.minor + 1}.0") if version.minor else Version(f"0.0.{version.patch + 1}")
        return [(">=", version), ("<", upper)]
    if op == "~": return [(">=", version), ("<", Version(f"{version.major}.{version.minor + 1}.0"))]
    return [("==" if op in ("", "=") else op, version)]


def parse_range(spec: str) -> list[tuple[str, Version]]:
    if not isinstance(spec, str) or not spec.strip(): raise ValueError("empty version range")
    clauses: list[tuple[str, Version]] = []
    for part in spec.split(","):
        match = _COMPARATOR.match(part.strip())
        if not match: raise ValueError(f"invalid version comparator {part!r}")
        clauses += _expand(match.group(1) or "", Version(match.group(2)))
    return clauses


def satisfies(version: str | Version, spec: str) -> bool:
    current = version if isinstance(version, Version) else Version(version)
    checks = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b,
              "==": lambda a, b: a == b, "!=": lambda a, b: a != b}
    return all(checks[op](current, bound) for op, bound in parse_range(spec))
