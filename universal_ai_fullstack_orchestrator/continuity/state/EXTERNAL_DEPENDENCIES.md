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
- Academy (`academy/`, not part of the framework runtime):
  - Node.js 22.12 or newer;
  - npm dependencies pinned in `academy/package.json` and `package-lock.json`: astro 7.3.8, @astrojs/starlight 0.42.6, @astrojs/vue 7.0.3,
    vue 3.5.44; dev: typescript 6.0.3, vitest 5.0.4, vue-tsc 3.3.13, jsdom 30.1.2, axe-core 4.14.0;
  - `npm audit`: 0 vulnerabilities on 2026-10-14.
- Hosting: GitHub Pages (free; source GitHub Actions) at https://jylmdev-cyber.github.io/pallaquino-os/, enabled 2026-10-14.
- GitHub Actions used by `academy.yml`: checkout@v7, setup-python@v7, setup-node@v7, upload-pages-artifact@v5, deploy-pages@v5 (latest
  majors, checked on 2026-10-14).
