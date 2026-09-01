#!/usr/bin/env python3
"""Configure and inspect a repository-local Git author identity.

This utility deliberately uses ``git config --local``. It never writes to the
global or system Git configuration.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def git(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={cwd.as_posix()}", "-C", str(cwd), *args],
        text=True,
        capture_output=True,
        check=check,
    )


def repository_root(candidate: Path) -> Path:
    candidate = candidate.expanduser().resolve()
    result = git("rev-parse", "--show-toplevel", cwd=candidate, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or f"Not a Git repository: {candidate}"
        raise ValueError(message)
    return Path(result.stdout.strip()).resolve()


def local_value(root: Path, key: str) -> str | None:
    result = git("config", "--local", "--get", key, cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def validate_identity(name: str, email: str) -> tuple[str, str]:
    name = name.strip()
    email = email.strip()
    if not name or any(char in name for char in "\r\n\x00"):
        raise ValueError("The name must be non-empty and contain no control lines.")
    if any(char in email for char in "\r\n\x00") or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("The email address is not valid.")
    return name, email


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Configure user.name and user.email only for one Git repository."
    )
    command.add_argument("--name", help="Git author name.")
    command.add_argument("--email", help="Git author email.")
    command.add_argument(
        "--repository",
        type=Path,
        default=Path.cwd(),
        help="Path inside the target repository (default: current directory).",
    )
    command.add_argument(
        "--show",
        action="store_true",
        help="Show the current repository-local identity without changing it.",
    )
    command.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show the requested change without writing it.",
    )
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = repository_root(args.repository)
        before = {
            "name": local_value(root, "user.name"),
            "email": local_value(root, "user.email"),
        }

        if args.show:
            if args.name or args.email or args.dry_run:
                raise ValueError("--show cannot be combined with identity changes.")
            print(json.dumps({"repository": str(root), "scope": "local", **before}, indent=2))
            return 0

        if not args.name or not args.email:
            raise ValueError("Both --name and --email are required unless --show is used.")

        name, email = validate_identity(args.name, args.email)
        requested = {"name": name, "email": email}
        if not args.dry_run:
            git("config", "--local", "user.name", name, cwd=root)
            git("config", "--local", "user.email", email, cwd=root)
            after = {
                "name": local_value(root, "user.name"),
                "email": local_value(root, "user.email"),
            }
            if after != requested:
                raise RuntimeError("Git did not persist the requested local identity.")
        else:
            after = before

        print(
            json.dumps(
                {
                    "repository": str(root),
                    "scope": "local",
                    "dry_run": args.dry_run,
                    "before": before,
                    "requested": requested,
                    "after": after,
                },
                indent=2,
            )
        )
        return 0
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

