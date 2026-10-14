# Assumptions

- The requested portable root is `universal_ai_fullstack_orchestrator/` inside the provided workspace. Confidence: high.
- “Maintain previously defined agents/skills” is interpreted from the categories and additions in the supplied master request because the workspace was empty. Confidence: high.
- Python 3.11+ standard library is an acceptable portability baseline; verified stack guidance remains independent of the host runtime. Confidence: high.
- PAL-005: the request left mode and autonomy as placeholders; BROWNFIELD with STANDARD autonomy was selected as the closest listed mode for evolving an existing framework, adding UPDATE_PALLAQUINO gates. Confidence: high.
- PAL-005: `.pallaquino/` in the main checkout is an untracked self-install identical to the tracked framework except `tests/`; the tracked source is canonical and the self-install was not modified. Confidence: high.
- PAL-005: Phase 1 ships as minor version 0.3.0 (new commands and flags, backward-compatible contracts). Confidence: medium.
- PAL-011:
  - the conceptual structure of request section 18 is mapped onto subpackages of `pallaquino_cli`, as ADR-0010 did, so no public path
    moves. Confidence: high.
  - the stdlib-only dependency policy outranks adopting the official MCP SDK v2. A stdlib client of the 2026-07-28 wire protocol is
    built, with an optional interoperability test against the SDK (ADR-0014). Confidence: high.
  - "Do not implement OAuth from scratch" is read as "no custom cryptography and no reinvented flows": only the client steps the MCP
    specification requires are implemented, with stdlib primitives (ADR-0016). Confidence: medium.
  - Writing reports to the framework's git-ignored `logs/reports/` instance state does not count as modifying the analysed repository.
    Confidence: high.
