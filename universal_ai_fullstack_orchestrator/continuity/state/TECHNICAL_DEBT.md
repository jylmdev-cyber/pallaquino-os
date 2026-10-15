# Technical debt

- The wheel does not package framework data; non-editable installs rely on root discovery (ADR-0004). Packaging data is required before PyPI publication.
- The release ZIP is committed to Git; attaching it only to GitHub Releases would keep the repository small.
- The repository analyzer provides conservative API/database detection; ecosystem-specific analyzers can extend it without changing the map schema.
- Numeric performance budgets remain product-specific by design and must be filled during product planning.
- Three fitness rules (domain_no_infrastructure, frontend_no_database, module_boundaries) have no analyzer.
- 0.5.0 (see docs/roadmap/ROADMAP_V050_TO_V060.md):
  - no `subscriptions/listen`;
  - no OS sandbox for plugins;
  - unencrypted file vault;
  - cooperative timeouts in builtin adapters;
  - no loaders for agent, skill and template plugin types;
  - the 0.4.0 scheduler persistence, FTS and HMAC items remain open.
- Academy (PAL-012):
  - the English edition is not translated;
  - video scripts have no recordings;
  - Django and Nuxt end-to-end tutorials await a verified run;
  - recorded transcripts must be re-captured each release;
  - the terminal simulator covers 24 recorded commands, and other combinations get an informative answer;
  - the a11y check in CI runs on jsdom (no contrast), so contrast is checked by hand in a browser;
  - `docs/learning/CONTENT_CATALOG.md` is a manual snapshot;
  - Starlight's search button keeps an accessible-name mismatch (H-11, upstream).
- Test-command detection covers only `tests/test*.py` and `package.json` scripts (audit H-7).
- `docs/DEMO.md` shows 0.3.0 figures (audit H-8).
- Release packaging includes `evidence/`, so any evidence record written between two builds changes the archive hash. That happened while
  building 0.5.1. Build twice in a row first, then record the evidence; alternatively, exclude records created after the build or package
  a fixed manifest of files.
- Continuity changes after a release (for example, recording the publication) make the repository framework tree differ from the
  published ZIP. That is expected, but it is not flagged anywhere.
