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

## First-run delivery, 2026-09-09

The first-boot run used a fresh disposable Debian/Python container, no mounted data, no external network, and the documented `make setup`. Chromium rendered actual responses from its loopback listener through the test relay. The owner proof used real HTTP, including anonymous/reused credentials, takeover attempts and restart. Neither result represents full product completion.

Local setup verification commands:

- `make unit`: 31 tests passed after adding Cloudflare plan, conflict, checkpoint, uncertain-write and credential-rotation coverage.
- `make setup-browser-test`: real local setup form, validation, reconnect and mobile checks passed.
- `make setup-security-test`: actual one-time owner HTTP checks passed.
- `make setup-clean-test`: clean Linux startup plus actual first-run screenshot.
- `make setup-provider-browser-test`: matching provider forms passed against an explicitly injected upstream fixture. This does not prove live Cloudflare compatibility or deployment.

Artifacts are under `.runtime/evidence/`, outside Git.

Outstanding: live scoped provider credentials, full private mail-service/connector deployment through the wizard, public DNS/TLS/SMTP verification, both complete clean-install journeys, restart/restore and authorized migration rehearsals. A Cloudflare account/user token-permission lookup through the available plugin returned unauthorized; resource-management access does not supply a credential to the reusable installer.

## Setup control plane and live resource verification (2026-09-09)

- Standalone owner bootstrap, shared forms/API, provider credential replacement, exact-plan Cloudflare apply, persisted checkpoints, isolated subdomain zone resolution and actionable conflicts implemented.
- Local verification: 35 Python unit tests; first-run browser and provider-form browser suites pass. Provider-form failure tests use an explicitly labelled upstream fixture.
- Live verification: real Cloudflare isolated resources were created; an acknowledged tunnel checkpoint was interrupted and resumed; repeat planning returned reuse; a deliberate test-only DNS conflict halted apply. All pre-existing domain records compared unchanged before/after. Private raw records and screenshots remain outside Git under `.runtime/evidence`.
- Read-only host preflight now reports Docker/Compose, platform, public-IP classification, port binding, external SMTP TCP connectivity and PTR. External inbound verification is explicitly pending. Unit probes of resolved/failure states are simulations; actual host checks were also performed separately.
- Full wizard service deployment, complete clean-install journeys, external mail, certificate renewal, edge authorization, completion handover and recovery/migration acceptance are still pending. Do not treat this checkpoint as a completed self-hosted installer.

## 2026-09-10: fresh runtime implementation checkpoint

- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -q`: 46 tests passed.
- `make setup-provider-browser-test`: real browser with explicit Cloudflare fixture; required web/mail confirmations, DNS/service plan, credential replacement and no browser credential persistence passed.
- `docker build -f docker/api/Dockerfile -t hermesaki-setup-api:test .`: passed without a host-built TypeScript artifact.
- `.venv/bin/python scripts/verify_setup_runtime.py`: real isolated Stalwart bootstrap, first-mailbox TLS login and folders, public DKIM export, certificate replacement verified on the wire, repeated sync and repeated deployment passed. No published ports; runtime network has no external delivery.
- Separate real DNS-01 certificate issuance and ACME renewal dry-run succeeded on an isolated authorized subdomain. The actual private deployment identity and certificate state remain outside Git. This does not prove a full public clean installation.
- Private artifacts: `.runtime/evidence/setup-runtime-final.log`, `setup-service-plan-fixture.png`, `setup-build.log`, `acme-public-check.log`.
- Full public installation and completed setup handover are still pending.

### Live web-hostname regression

Live HTTPS verification exposed that nested web names on test subdomains were outside Cloudflare's default certificate coverage. New setup flows now persist flat, certificate-covered web names; existing saved plans retain their names. A real isolated web plan successfully created the corresponding protected endpoints, and the service planner verified the Access redirect. The real browser/HTTP test rejected a deliberately invalid service-plan confirmation. Unit coverage is now 47 tests.

Full public clean-install verification needs a separate available mail endpoint because the existing production SMTP address is occupied.

### Same-host reinstall, 2026-09-10

Performed an owner-authorized replacement from a fresh encrypted snapshot on the
existing VPS. An offline restore passed before cutover. Restored into a new
runtime directory, recreated production containers against that data, and retained
the original runtime. Switch completed in 13.87 seconds. All three existing domains,
five folders and four INBOX message UIDs matched. Real browser login succeeded;
webmail still redirected anonymous public requests through Cloudflare Access.
A scoped MCP-core send was submitted for the authorized test recipient, with
read-only sending denied and the temporary write token revoked. This was not a
remote MCP-through-Access test, nor proof of external inbox placement.
Private evidence is under `.runtime/reinstall`. Clean setup forms/API completion
and final handover remain outstanding; this does not establish 100% acceptance.

### Completion gate implementation

Added a fail-closed completion endpoint, persisted handover, disabled setup
mutations after completion, normal-operation links, and public mail DNS lookups.
60 unit tests pass, including denial of incomplete/stale proofs, exact-plan and
owner enforcement, live recheck invocation and persistence of retired setup.
Both setup and provider browser regression suites pass. The completion test uses
an explicit verification fixture. Full public setup acceptance is still pending.

### External network verifier

Added owner-authenticated challenge/download and result/upload routes, with the
same controls in setup forms. The helper observes an external SMTP greeting and
forward/reverse DNS, ties its signed result to the current plan, expires after
15 minutes, and consumes results once. Same-host/private-source checks cannot
pass. Network results expire and outbound SMTP is rechecked during verification.
65 tests and both browser regression suites passed.

Ran the helper from an existing independent VPS against the production SMTP
address. Public SMTP and the mail hostname's forward/reverse DNS passed. Outbound
SMTP from the mail VPS also passed. Captured results and explicitly simulated
failure responses are saved separately in the private evidence directory.

The remote-agent verification attempt found a real permission blocker: the
current setup credential can list Access service tokens but creation was denied.
No service token or policy was created by that failed attempt. The account API
credential needs Access: Service Tokens Write for this path. External email and
remote-agent verification remain incomplete.

### Independent public setup journeys, 2026-09-10

Completed two independent installations on isolated test subdomains and separate
empty data directories on the existing host. The first used the HTTP setup API;
the second used the app forms, including credential downloads, signed external
network probe upload, received-message upload, and scoped MCP verification.
Both returned the persisted `complete` state after all eleven required checks
passed, then rejected further setup changes. The original production mailbox
remained running. Both external messages passed SPF, DKIM and DMARC and received
matching replies. Gmail placed the new test-domain messages in spam; inbox
placement is not guaranteed by these checks.

The normal operator page and form-based creation of a read-only agent mailbox
were exercised through Cloudflare Access, including a real MCP connection.
Temporary Access service credentials and policies were removed after testing.
A cached PTR on the independent probe host correctly produced a pending result;
clearing that host's DNS cache and rerunning the real probe resolved it.

Testing also found an unavailable default log-file directory in the mail
container and an owner-status loading race in the setup form. Fresh provisioning
now selects container console logging, preserving custom tracers, and the form
waits for owner status before enabling connection. The operator page links to
real inbox onboarding and shows service health.

Validation: 84 unit tests pass, and the setup browser regression passes. Changes
were pushed to the private repository with no CI. Actual screenshots, private
HTTP transcripts and received originals remain under `.runtime/evidence`.
These results cover the journeys described above; they do not establish that
every release acceptance check has passed.
