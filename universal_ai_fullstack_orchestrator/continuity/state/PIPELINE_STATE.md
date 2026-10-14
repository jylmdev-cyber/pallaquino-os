# Pipeline state

- Status: PAL-012 published (PR #8 merged, GitHub Pages deployed 2026-10-14); PAL-013 merged (PR #9)
- Updated: 2026-10-14
- Confidence: high
- Current stage: HANDOFF
- Last confirmed stage: HANDOFF
- Gates:
  - passed locally:
    - TEST: academy 29 vitest tests; framework 242 tests;
    - LINT_TYPECHECK: `astro check` and `vue-tsc`;
    - DOCS_VALIDATION: content, 133 CLI commands, 11448 internal links;
    - ACCESSIBILITY: axe on the built pages, plus an in-browser sweep in both themes and on mobile;
    - BUILD: 127 static pages;
    - SECURITY_CHECK: secret scan 0 findings over 645 files; fitness 0 violations; `npm audit` 0 vulnerabilities.
  - CODE_REVIEW: self-review only.
- Failed gates remediated:
  - breadcrumb links to section pages without an index (found by validate-links);
  - heading order and empty table headers (axe);
  - dark-theme contrast 4.49:1 (in-browser axe);
  - non-focusable scroll regions;
  - Windows 11 reported as "Windows 10" in transcript labels;
  - a rehype plugin incompatible with Astro 7's default Markdown processor, replaced by a MarkdownContent override.
- Mode and autonomy: GREENFIELD component in a BROWNFIELD repository, STANDARD
- Checkpoint: generated for PAL-012
- Handoff: `continuity/HANDOFF.json`
- Next: merge PAL-012-F1 (simulator fix) and redeploy the Academy with the manual workflow, both with owner approval; run the user-testing
  protocol; next stack re-verification due 2026-11-13
