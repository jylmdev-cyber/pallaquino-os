# Open questions

- None blocking. Resolved on 2026-10-14 by the repository owner ("SI HAZLO") in the PAL-011 session:
  - Q-4 APPROVED and done: `mcp` 2.3.0 installed in an isolated scratch venv; interop tests 5/5.
  - Q-5 APPROVED: publish 0.5.0: push `feat/v0.5.0-extensions`, open the pull request, merge after green CI, tag `v0.5.0` and publish the
    GitHub Release with the ZIP and SHA-256.
  - Q-6 APPROVED: correct the defective v0.4.0 release ZIP. Chosen option: a note on the v0.4.0 GitHub Release pointing to 0.5.0; the
    published tag and assets are not altered.
- Resolved on 2026-10-13T14:59Z by the repository owner in the PAL-005 session:
  - Q-1 RESOLVED: keep `jimdev <jylmdev@gmail.com>` as this repository's and the default identity; make it configurable per project (`governance/git_identity.json`, ADR-0007).
  - Q-2 RESOLVED: the prohibition of AI co-author trailers stays.
  - Q-3 APPROVED: push branch `claude/pallaquino-engineering-os-c7d622`, open the Pull Request and publish tag `v0.3.0`. Scope is exactly these three actions; merging and a GitHub Release were not requested.
  - 2026-10-13: owner approved creating the `v0.3.0` GitHub Release and enabling Auto-fix on PR #3.
  - 2026-10-14: owner approved merging PR #3 and publishing 0.3.1 (tag `v0.3.1` and GitHub Release).
  - 2026-10-14: owner approved publishing the PAL-006 pull request and releasing 0.3.2 (merge, tag `v0.3.2` and GitHub Release).
  - 2026-10-14: owner approved publishing 0.4.0: merge PR #5, push `feat/v0.4.0-orchestration`, open its pull request, and after green CI merge it, tag `v0.4.0` and publish the GitHub Release. Done: PR #6 merged (`4ffde70`), tag `v0.4.0`, release verified.
