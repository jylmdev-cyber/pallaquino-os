# Pipeline state

- Status: PAL-014 (release 0.5.1) gates green locally; publication approved (PR, merge after green CI, tag `v0.5.1`, GitHub Release)
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
- Session-close gates on `fc42622` (2026-10-14, local, with evidence): TEST 243 OK, 6 skipped; LINT_TYPECHECK (compileall); integrity validation;
  SECURITY_CHECK (secret scan); architecture fitness; release ZIP integrity; academy `npm run ci`. Not run here: the full `validate` with
  the Git identity (environment; local identity unset in this checkout, applied in CI).
- Next: publish 0.5.1 as approved, redeploy the academy, then PAL-015 (user testing); stack re-verification due 2026-11-13
