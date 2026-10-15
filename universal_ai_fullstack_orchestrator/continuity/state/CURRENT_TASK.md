# Current task

- ID: PAL-014
- Objective: publish PALLAQUINO 0.5.1, a patch release with the PAL-013 fix for audit H-6 (non-ASCII Git identity on Windows).
- Approval: the repository owner asked for it on 2026-10-14 ("publica la versión 0.5.1 con el arreglo de H-6"). That covers the release
  pull request, the merge after green CI, the tag `v0.5.1` and the GitHub Release with the ZIP and SHA-256.
- Mode: MAINTENANCE (patch release). Autonomy: STANDARD.
- Base: `main` at `b8c1ab7`; branch `release/0.5.1`.
- Scope:
  - version 0.5.1 in core, package, pyproject and manifest;
  - release notes, release record, migration note and changelog;
  - CITATION, the release checklist and the framework README, which the 0.5.0 release had left at 0.4.0;
  - academy version texts, generated data and recorded transcripts;
  - reproducible ZIP rebuilt and verified.
- Out of scope: new features; framework behaviour beyond the H-6 fix already merged in PAL-013.
- Risk: LOW. Only the decoding of Git output changes in code, and that change was already merged and tested in PAL-013.
- Gates (local, Windows 11, Python 3.11.15, Node 24.15.0):
  - 243 tests OK, 6 skipped (`evidence/test-2026-10-15T00-08-18+00-00.json`);
  - compileall (`evidence/lint_typecheck-2026-10-15T00-06-44+00-00.json`);
  - integrity validation (`evidence/integrity-2026-10-15T00-06-45+00-00.json`);
  - secret scan, 0 findings (`evidence/security_check-2026-10-15T00-06-48+00-00.json`);
  - architecture fitness (`evidence/architecture_fitness-2026-10-15T00-06-49+00-00.json`);
  - academy `npm run ci` (`evidence/docs_validation-2026-10-15T00-08-59+00-00.json`).
- Status: DONE and published. PR #12 merged (`4e77c50`) after green CI; annotated tag `v0.5.1` on the release head `4df790f`; GitHub Release "PALLAQUINO 0.5.1" published 2026-10-15T00:13:04Z with the ZIP (SHA-256 `38238b6855625e2d7aeeda8cfc5bbd309669657f6bef1a4d620b0e9969a9e7d4`) and `.sha256`, marked latest; downloaded assets checksum OK; academy redeployed (run 38658770613).
- Session closed 2026-10-15 UTC with gates on `c20b2be` (see TEST_STATUS). Next action: Q-8 (PAL-015).
- Previous task PAL-012 (academy) is closed. Its §25 acceptance evidence is in pull request #11 and `changes/PAL-012.json`.
- Confidence: high
