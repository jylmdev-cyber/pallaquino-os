#!/usr/bin/env python3
"""Public entry point for the repository-local Git identity configurator."""

from __future__ import annotations

import runpy
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "universal_ai_fullstack_orchestrator"
    / "scripts"
    / "configure_git_identity.py"
)

if __name__ == "__main__":
    runpy.run_path(str(SCRIPT), run_name="__main__")

