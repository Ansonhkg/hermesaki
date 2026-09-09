# Implementation evidence

Recorded 2026-09-09 (Europe/London). Component digests are in `components.lock.json`. No CI is installed.

## Verified

- macOS Apple Silicon / Docker Desktop: source compilation and Ruff checks pass; 16 unit/security/recovery tests pass.
- Real local Stalwart 0.16.19 and Roundcube 1.7.4: two successive seeds retain one welcome fixture; TLS IMAP login and attachment bytes match; MCP folder/search/read/attachment requests pass; cross-mailbox reads are denied.
- API send queue submits through SMTP. An external-shaped recipient is captured in Mailpit. Local mail reaches the second Stalwart mailbox.
- Roundcube login, compose and reply forms deliver through the actual webmail server. The reply returns to the first inbox. Local login UI was also opened for visual inspection.
- A real local HTTP receiver verifies the webhook signature. Inbound polling creates a draft, and a send without draft approval is rejected.
- Full encrypted snapshot restoration starts a second isolated Compose project and passes the real-service integration suite. Original services are restarted and preserved.
- A clean captured-mail staging installation runs on Ubuntu 24.04 x86-64. The Linux bind-mount ownership failure was fixed in setup, and its integration suite passes.
- Both staging web hostnames redirect anonymous requests to Cloudflare Access. Temporary authorized service credentials reach both pages and list MCP tools. Temporary policies and the service credential were deleted afterward; owner-only policies remain.
- Staging HTTP ports bind to loopback. Its mail container does not publish SMTP. The existing live mailbox and public SMTP service were not replaced.

Commands: `make unit`, `make integration`, `make restore-test`, and authenticated/unauthenticated HTTPS staging checks. Local test logs are generated outside Git; no mailbox bodies or secrets are included here.

## Acceptance mapping

| Gates | Evidence/status |
| --- | --- |
| A01-A08 | Local implementation and tests above. A03 is HTTP form end-to-end coverage, not a full JavaScript browser automation suite. |
| A09 | Captured-mail Linux staging passes. The distinct public production provisioning command still requires rehearsal. |
| A10 | Staging Access gates and authorized MCP verified; production JWT validation and public SMTP topology require the production rehearsal. |
| A11 | Production rejects development identity configuration in unit tests. |
| A12-A13 | Restart and separate-stack encrypted restore pass. |
| A14 | Schema guard and preservation procedure implemented; actual version-changing upgrade/rollback rehearsal pending. |
| A15 | Local suite runs, with nonzero failure exit. No CI. |
| B01 | Scoped API/MCP implemented; inbox creation, reading, deletion/revocation and sending tested. |
| B02 | Stable incoming/send events implemented. DSN interpretation exists; an external DSN delivery rehearsal is pending. |
| B03-B04 | Signed HTTP integration, bounded retries/dead letters, concurrent idempotency and crash recovery tested. |
| B05 | Injected-clock failure tests cover rejection, outage, duplication and out-of-order events. |
| B06 | Local indexing regression and preserved upstream transport regression recorded; no raw production message fixture imported. |
| B07-B08 | Metadata operator view, drafts and explicit approval gate implemented and exercised. |

This is a working reusable implementation with captured-mail staging, not a declaration that every public-production release gate has passed. Production SMTP activation, DNS alignment, certificate renewal operations and a real version-changing upgrade remain explicit checks.

## TypeScript SDK, CLI and real onboarding (2026-09-09)

The implementation accompanying this record passes local developer criteria C01-C12 on macOS Apple Silicon, Node 22 and Docker Desktop. Commands run locally; no CI added.

- `make test`: 17 Python tests, four SDK contract tests, upstream integration and the real SDK/CLI/MCP mail flow pass. Coverage includes attachments, threaded replies via CLI, idempotent concurrent sends, conflicting payloads, expiry, revocation, cross-mailbox denial and external-shaped recipients captured in Mailpit.
- `make browser-test`: real owner authentication, denied login, backend failure and retry, inbox creation, mailbox token issuance, actual MCP folder access, queued SMTP sample arrival/read, confirmed deletion and mobile overflow checks pass. Local/session storage remain empty. Desktop/mobile visual inspection also completed.
- `make clean-test`: a separate freshly provisioned Compose stack passes the SDK/CLI/MCP and browser flows. Restart plus the upstream seed/mail suite pass afterward. Temporary services are removed; original runtime is preserved.
- `make restore-test`: a stopped encrypted snapshot restores into a separate mail/API/webmail stack and passes upstream integration. Original services resume. The rehearsal no longer publishes unnecessary host ports, avoiding collision with the landing preview.
- A transient post-restart transport disconnect was observed. The upstream test harness now retries only reads or requests carrying an idempotency key, at most three attempts; other mutations are never retried automatically. Persistent failures still fail the suite.
- TypeScript package builds and packs with declarations and an executable CLI. Credentials are not printed by token issuance; they are written to a new 0600 file. The package is available from this private workspace, not published on npm.
- Ruff and Git whitespace checks pass. Runtime credentials/logs/screenshots remain ignored. Local logs are `.runtime/local-acceptance.log`, `.runtime/clean-acceptance.log` and `.runtime/restore-acceptance.log`.

The real UI is `/ui/onboarding/live.html` on the API origin. It uses owner and mailbox bearer tokens in tab memory; production also requires the existing Cloudflare Access gate. The local sample-send route requires admin and explicitly rejects non-development mode. SMTP acceptance is not presented as recipient delivery; the UI waits for actual mailbox arrival.

This completes the local developer milestone, not public-production acceptance. Public SMTP provisioning, live DNS/mail authentication, renewal operations, external delivery and version-changing upgrade/rollback still need the recorded production rehearsals.
