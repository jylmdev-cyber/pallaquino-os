# Technology stack state

- Status: VERIFIED (2026-10-14 from official primary sources; stale after 30 days)
- Runtime baseline: Python 3.14.8, Node.js 24.21.0 LTS, .NET 10.0.13 and SDK 10.0.402
- Application baseline: Django 5.2.18 LTS, Nuxt 4.6.1, PostgreSQL 18.6, TypeScript 6.0.3
- Platform baseline: Docker Engine 29.9.0, Compose 5.6.0, Ubuntu 26.04.1 LTS
- Compatibility exceptions: TypeScript 6.0.3 over 7.0.2 (vue-tsc needs the TS 6 JS API until TS 7.1); Python 3.14.8 over 3.15.0 (Django 6.1.2 declares Python 3.12-3.14)
- Rejected prereleases: .NET 11 (release candidate)
- Next re-verification due: 2026-11-13
- Confidence: high
