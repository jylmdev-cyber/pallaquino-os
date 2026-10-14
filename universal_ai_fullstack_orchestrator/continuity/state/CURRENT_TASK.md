# Current task

- ID: PAL-012
- Objective: build the PALLAQUINO Interactive Learning Academy, a static learning portal with tutorials, a terminal simulator, visual
  walkthroughs, quizzes and local progress, so a user goes from "I do not know PALLAQUINO" to using and extending it. Per the academy
  master request.
- Mode: GREENFIELD component inside a BROWNFIELD repository
- Autonomy: STANDARD. No push, publication or deployment without explicit owner approval.
- Base: `main` at `d4a2af3` (0.5.0 published 2026-10-14); branch `feat/academy`.
- Scope:
  - audit of the existing documentation;
  - ADR for the portal stack;
  - `academy/` (Astro + Starlight + Vue 3 + TypeScript), with content generated from the framework's sources of truth (CLI parser,
    registries, contracts, builtin tools);
  - the first functional increment (request §23): landing, navigation, installation guide, first-commands tutorial, terminal simulator,
    agent/skill explorer, interactive flow diagram, quiz, local progress, search and dark mode;
  - learning paths with real lessons only;
  - docs-as-code validation;
  - CI workflow;
  - deployment guide with no automatic publication.
- Out of scope: real command execution from the browser, accounts or backends, recorded videos (scripts and storyboards only), English
  content beyond the prepared structure.
- Risk: MEDIUM. The portal is new and independent of the Python core. The main risk is teaching features that do not exist; it is
  mitigated by generated data and command validation.
- Acceptance: the 15 criteria of request §25.
- Status (2026-10-14): implemented and verified locally on `feat/academy`; not pushed, not deployed (both need owner approval).
  - `academy/`: 64 content pages, including 46 lessons in 9 routes, 10 quizzes, 2 terminal challenges, the mandatory first-install
    tutorial, practice, reference (generated), video scripts and the English entry page.
  - Every taught command is checked against the real CLI parser (133 commands).
  - Real outputs: 17 framework commands plus 7 example-project commands, recorded from a clean clone.
  - Local checks: `npm run ci` green (`evidence/docs_validation-2026-10-14T23-14-58+00-00.json`); in-browser axe sweep
    (`evidence/accessibility_browser-2026-10-14T23-20-00+00-00.json`); framework suite 242 green
    (`evidence/test-2026-10-14T23-16-55+00-00.json`).
  - Documentation audit: 11 findings. H-6, a non-ASCII Git identity defect on Windows in `core.run_git`, is not fixed here (core out of
    scope) and is proposed as a separate task.
- Confidence: high for content accuracy and local verification; deployment and user testing not performed
