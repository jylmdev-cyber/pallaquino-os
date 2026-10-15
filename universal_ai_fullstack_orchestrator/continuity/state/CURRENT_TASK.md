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
- Status (2026-10-14): owner-approved and published. PR #8 merged (`b9ec3ea`) after green CI. GitHub Pages enabled with the Actions source;
  the Academy workflow was run with `deploy=true` (run 38655034166, both jobs green), and the live site was checked (pages 200, unknown
  path 404, search index served, terminal replay working). Follow-up PAL-012-F1 (simulator) merged as PR #10 (`fc42622`) and redeployed
  (run 38655943918). Session closed 2026-10-14; see `continuity/HANDOFF.json`.
  - `academy/`: 64 content pages, including 46 lessons in 9 routes, 10 quizzes, 2 terminal challenges, the mandatory first-install
    tutorial, practice, reference (generated), video scripts and the English entry page.
  - Every taught command is checked against the real CLI parser (133 commands).
  - Real outputs: 17 framework commands plus 7 example-project commands, recorded from a clean clone.
  - Local checks: `npm run ci` green (`evidence/docs_validation-2026-10-14T23-14-58+00-00.json`); in-browser axe sweep
    (`evidence/accessibility_browser-2026-10-14T23-20-00+00-00.json`); framework suite 242 green
    (`evidence/test-2026-10-14T23-16-55+00-00.json`).
  - Documentation audit: 11 findings. H-6, a non-ASCII Git identity defect on Windows in `core.run_git`, was fixed separately by PAL-013
    (PR #9).
- Acceptance (request §25), with the evidence for each:
  1. Local installation documented. Every step was executed in a clean clone and a fresh project.
  2. Taught commands exist. 133 commands are checked against argparse by `validate-content`.
  3. Navigation works. Links are validated, and the live site was checked by hand.
  4. Search works. A Pagefind query on the live site returned 12 results.
  5. Responsive. Axe sweep at 375 px, with no horizontal overflow.
  6. Dark mode works. Axe sweep in the dark and light themes.
  7. Exercises give feedback. Quiz and terminal component tests.
  8. The simulator runs nothing dangerous. Blocked commands and operators are tested, and there is no shell or backend.
  9. Local progress persists. Unit tests, plus the live site: a completed lesson survived navigation; the test data was then cleared.
  10. Internal links validated. 11448 links.
  11. Versions and capabilities distinguished. Lesson `since` and `status` fields and the versions page.
  12. Accessible components. axe in jsdom and in the browser; the only remaining finding is the upstream H-11.
  13. The static build succeeds. 127 pages, locally and in CI.
  14. No paid services. GitHub Pages is free and nothing else is external.
  15. A maintenance guide exists: `docs/learning/MAINTENANCE.md`.
- Confidence: high for content accuracy, local, CI and live verification. User testing has not been run (protocol only).
