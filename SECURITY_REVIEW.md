# Jimmy security, privacy, and launch review

Review date: 2026-11-28

This is an engineering review of the current code and observed deployment. It is not a penetration test, legal opinion, or compliance certification.

## Changes made in this review

- Anonymous conversation IDs now contain 256 bits of browser-generated randomness. Chat creation validates the token; history read/delete reject invalid or legacy IDs as not found.
- Public chat requests are limited to 20 requests per minute per backend process/client IP, reject declared bodies larger than 16 KiB, cap user text at 4,000 characters and custom instructions at 2,000 characters, and stop waiting for provider failover after 80 seconds.
- CORS no longer enables credentials or wildcard methods/headers. Responses receive `nosniff`, no-store, referrer, framing, permissions, and HSTS headers.
- History loading now avoids a duplicate database connection/query. SQLite queries remain parameterized.
- Backend test-only packages are separated into `requirements-dev.txt`; the production Docker image no longer installs them.
- A plain-language privacy information page is available at `/privacy.html`.

The in-memory throttle is best-effort: it resets on restart and is not shared across multiple instances. The request-size check relies on `Content-Length`; provider-side quotas and an edge/WAF limit are still needed for robust abuse control.

## Findings and status

| Severity | Finding | Status |
| --- | --- | --- |
| High | Earlier anonymous session IDs had only 32 bits of entropy while granting read/delete access to a conversation. | Fixed for newly created sessions. Old short-ID records are no longer accessible through the API; the browser shows a notice and lets the user remove stale entries from the local list. Old database rows are not automatically purged. |
| High | The deployed backend uses local SQLite on a free Render service, with no durable disk or backup. Data can be lost on restart/redeploy/instance replacement. | Unresolved infrastructure risk. Use managed durable storage and tested backups before handling valuable or regulated data. |
| High | No account identity or owner authentication exists; a session token is a bearer capability. | By design for the current anonymous app. Do not use shared devices for sensitive chats; add authenticated ownership if private/team use is required. |
| Medium | Anonymous public inference endpoints can incur provider costs or abuse. | Basic process-local throttling added. A shared limiter, edge protection, quotas, and abuse monitoring are still needed for production scale. |
| Medium | Provider processing and retention varies by configured provider, account, and plan. | Disclosed in the privacy page; operator must confirm the actual deployment provider/tier and publish provider terms. |
| Medium | `pip-audit` on the local Python 3.10 workspace found 17 advisories against transitive `filelock 4.1.0`. The backend image uses Python 3.11; `requirements.txt` now requires `filelock>=4.2.1` on Python 3.11+. | Intended runtime minimum is declared, but the updated dependency tree was not verified: there is no Docker CLI here and the requirement-resolution audit did not finish. Re-run `pip-audit` against the production image. |
| Medium | No service-operator contact address or privacy-request process is published. | Unresolved. Operator must provide these details and obtain jurisdiction-specific legal review before public launch. |
| Medium | Free Render services can sleep after inactivity, causing a slow first request. | Hosting limitation; use always-on paid service or a suitable production platform for predictable latency. |
| Low | External Google Fonts introduced third-party requests and delayed styling. | Removed; system font stack is used. |

## Launch requirements not verifiable from this repository

- Durable database/storage, automated backups, retention schedule, and tested restore procedure.
- Confirm provider account/tier, provider data-processing terms, and regional processing requirements.
- Add shared rate limits, request/body limits at the edge, monitoring/alerting, and cost quotas.
- Supply operator privacy contact and have the privacy notice and India DPDP obligations reviewed by qualified counsel. The 2025 Act/Rules have staged commencement; this review makes no compliance claim.
- Configure deployment-level security/cache headers for the Render Static Site and verify after deployment. The repository currently has no Render Blueprint, and the frontend is deployed as a dashboard-managed static service.
- Configure a durable service plan and verify production logs, backups, and alert routing.

## Performance baseline

Before this review, a mobile Lighthouse run on the live frontend measured: Performance 93, Accessibility 95, Best Practices 100, SEO 100; FCP 1.8 s, LCP 3.0 s, CLS 0, TBT 0 ms. It flagged muted text contrast and about 85 KiB of unused JavaScript on the initial route. A post-change measurement is recorded in the task summary after deployment; Lighthouse scores vary by run and hosting cold starts.
