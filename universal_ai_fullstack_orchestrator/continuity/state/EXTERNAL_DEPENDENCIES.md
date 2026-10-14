# External dependencies

- Runtime dependency: Python 3.11 or newer.
- Framework code dependencies: Python standard library only (0.5.0 adds `tomllib`, `importlib.metadata`, `http.client`, `ssl`, `secrets`).
- Operational integrations (Git, browser, Docker, databases, MCP) are detected and adapted at runtime; none is silently assumed.
- MCP: target specification revision 2026-07-28, consulted on 2026-10-14 at https://modelcontextprotocol.io/specification/2026-07-28.
  Legacy servers (2025-11-25 and earlier) are reachable only through the explicit `initialize` fallback.
- MCP Python SDK: not a dependency.
  - PyPI `mcp` 2.3.0 (2026-10-02) is the stable line that speaks 2026-07-28; this host has 1.26.0, which supports up to 2025-11-25.
  - `tests/test_mcp_interop_official_sdk.py` runs only when `mcp>=2` is installed; on 2026-10-14 it passed 5/5 with `mcp` 2.3.0 installed
    in an isolated scratch venv (owner-approved download).
- Optional: `keyring` (OS credential store) when `PALLAQUINO_USE_KEYRING=1`; never required.
