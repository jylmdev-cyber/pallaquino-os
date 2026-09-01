# Known issues

- Stack snapshot becomes STALE after 2026-09-30 and must be re-verified.
- Internet/browser/MCP/subagent availability remains provider-session dependent; local detection records unknown rather than claiming availability.
- Docker is installed on the host, but no container workload was required or started.
- No database clients were detected in the current environment.
- GitHub remote is not configured; owner/repository URLs and the dynamic CI badge must be added after repository creation.
- Confidence: high
