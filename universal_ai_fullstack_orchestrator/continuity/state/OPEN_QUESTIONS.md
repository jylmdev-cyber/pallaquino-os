# Open questions

- Q-4 (PAL-011, 2026-10-14), not blocking the candidate. May the official MCP Python SDK (`mcp>=2`, PyPI) be installed in an isolated
  scratch environment to run `tests/test_mcp_interop_official_sdk.py`? It is a download of third-party code, so it needs explicit approval.
- Q-5 (PAL-011, 2026-10-14). Publishing 0.5.0 (push `feat/v0.5.0-extensions`, pull request, tag `v0.5.0`, GitHub Release) needs explicit
  approval (request sections 24 and 26).
- Resolved on 2026-10-13T14:59Z by the repository owner in the PAL-005 session:
  - Q-1 RESOLVED: keep `jimdev <jylmdev@gmail.com>` as this repository's and the default identity; make it configurable per project (`governance/git_identity.json`, ADR-0007).
  - Q-2 RESOLVED: the prohibition of AI co-author trailers stays.
  - Q-3 APPROVED: push branch `claude/pallaquino-engineering-os-c7d622`, open the Pull Request and publish tag `v0.3.0`. Scope is exactly these three actions; merging and a GitHub Release were not requested.
  - 2026-10-13: owner approved creating the `v0.3.0` GitHub Release and enabling Auto-fix on PR #3.
  - 2026-10-14: owner approved merging PR #3 and publishing 0.3.1 (tag `v0.3.1` and GitHub Release).
  - 2026-10-14: owner approved publishing the PAL-006 pull request and releasing 0.3.2 (merge, tag `v0.3.2` and GitHub Release).
  - 2026-10-14: owner approved publishing 0.4.0: merge PR #5, push `feat/v0.4.0-orchestration`, open its pull request, and after green CI merge it, tag `v0.4.0` and publish the GitHub Release. Done: PR #6 merged (`4ffde70`), tag `v0.4.0`, release verified.
