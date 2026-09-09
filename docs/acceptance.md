# Acceptance criteria

## Definition of done

On a clean supported machine, a developer can clone the repository, start the local product, run all tests without external mail or paid services, deploy the same core to a configured server, and restore it from a backup. No undocumented server edits or manual database fixes are allowed.

Every criterion below is pending until backed by evidence from this repository. Existing live-deployment checks are recorded separately in baseline.md. A passing repository-foundation check is not a product release.

## Release 0.1: reproducible self-hosted email

| ID | Acceptance criterion | Required local evidence |
| --- | --- | --- |
| A01 | `make dev` starts real Stalwart, Roundcube, the product API and MCP service with health checks. Configuration is templated; images and dependencies are pinned. | Fresh-volume startup on every advertised platform; log of versions and health checks. |
| A02 | `make seed` creates fictional accounts, folders, messages and attachments. Running setup or seed again does not duplicate or overwrite user data. | Two successive setup/seed runs with identical expected results. |
| A03 | A test user can sign in to Roundcube, read a seeded message, compose a message and receive a reply. | End-to-end test through the real browser inbox and SMTP/IMAP services. |
| A04 | Local outbound delivery is captured locally by default. A local run cannot accidentally send to real recipients. | External-destination test stays in the capture inbox; external delivery requires explicit production configuration. |
| A05 | MCP can list folders, search mail, read a message and retrieve an attachment using a mailbox-scoped identity. | Protocol-level tests through the same MCP interface clients use. |
| A06 | Read-only credentials cannot send, edit, flag, move or delete mail. Mailbox A cannot access mailbox B. Expired and revoked tokens fail. | Negative authorization tests, including direct tool calls. |
| A07 | Optional write access can send and reply in the correct thread; destructive operations require explicit confirmation. | Opt-in fixture tests; denied and expired confirmations produce no mutation. |
| A08 | Configuration and secrets are external to images and Git. Logs redact passwords, tokens and message contents by default. | Repository/image scan and representative failure-log inspection. |
| A09 | A documented deployment command starts the same versions on a fresh server. Setup validates DNS, TLS, mail ports and access configuration. | Staging deployment transcript; remaining external prerequisites clearly reported. |
| A10 | The production browser inbox and remote MCP endpoints are protected by Cloudflare Access, with no direct public HTTP origin. Public SMTP remains available for mail delivery. | Unauthenticated edge tests, authenticated user/service tests, direct-origin denial check. |
| A11 | Local authentication simulation is explicitly development-only and cannot be enabled by production configuration. | Production startup rejects the development auth adapter. Real Cloudflare behavior is checked in staging. |
| A12 | Restarting or recreating containers preserves messages, accounts, settings and authorization data. | Restart/recreate test comparing data and successful login. |
| A13 | Backup includes mail data, database, configuration and required encryption material; restore works on an empty instance. | Restore test proves messages, attachments, settings and access are recoverable. Backup confidentiality is tested/documented. |
| A14 | Upgrade and rollback have documented data/schema handling. A rollback never silently discards post-backup data. | Local upgrade rehearsal and explicit rollback rehearsal with fixtures. |
| A15 | `make test` runs the automated local suite and returns nonzero on failures. No GitHub Actions or other CI is required. | Saved local test report, with environment and component versions. |

## Release 0.2: agent email workflows

| ID | Acceptance criterion | Required evidence |
| --- | --- | --- |
| B01 | A versioned API creates and manages inboxes, reads mail, and sends/replies using scoped credentials. MCP uses the same authorization rules. | API contract and cross-mailbox denial tests. |
| B02 | Incoming, delivery, bounce and failure events have stable IDs and a documented versioned schema. | Real local SMTP scenarios plus synthetic fixture tests. |
| B03 | Webhook delivery is signed and retried with bounded backoff; exhausted deliveries are visible and replayable. | Invalid-signature, timeout, retry-exhaustion and replay tests. |
| B04 | Duplicate events and repeated send requests do not produce duplicate replies. Queue restart cannot silently lose accepted work. | Idempotency, concurrent duplicate and process-crash tests. |
| B05 | A local scenario runner reproduces delayed mail, temporary rejection, permanent bounce, provider outage, duplicate events and out-of-order events without production dependencies. | Deterministic scenario tests with a controllable clock and fixed identifiers. |
| B06 | Sanitized production incidents can be added as fixtures without real personal data, tokens, headers carrying credentials or attachments. | Fixture validation and at least one reproduced-and-fixed regression. |
| B07 | Operators can inspect message delivery state, workflow attempts, last error and audit history without exposing message bodies by default. | API/UI tests for success, failure and recovery paths. |
| B08 | An inbound fixture can trigger an agent workflow that produces a draft; sending requires explicitly configured write permission and workflow policy. | End-to-end workflow test with a deterministic agent stub. |

## External checks that local tests cannot replace

Staging checks cover Cloudflare policies, public DNS, certificate validation, DKIM/SPF/DMARC alignment, and external send/receive. Sender reputation and recipient spam placement are monitored observations, not guarantees made by the local emulator.

## Release evidence format

Record commit, host platform, component digests, test command, scenario, result, and artifact path. Mark untested criteria as pending. Do not mark a release complete based only on a running container or a successful build.

## Out of scope for the first releases

Hosted billing, public signup, automatic bulk outreach, multi-region availability and full AgentMail API compatibility. A self-hosted agent email product does not imply drop-in compatibility with another vendor's API.

## Local developer product: TypeScript and real onboarding

| ID | Acceptance criterion | Evidence command |
| --- | --- | --- |
| C01 | One documented setup starts mail, capture, API, webmail and real onboarding. | `make dev`, `make clean-test` |
| C02 | Owner-authenticated onboarding creates an inbox and issues a scoped token; mock UI remains separate. | `make browser-test` |
| C03 | A real MCP connection check verifies both credentials and mailbox access. | `make browser-test`, `make client-live` |
| C04 | TypeScript SDK supports typed inbox, token, read, send and reply operations and actionable errors. | `make client-test`, `make client-live` |
| C05 | CLI uses the SDK, writes new tokens to private files, and supports inbox/read/send/reply operations. | `make client-live` |
| C06 | SDK, CLI and MCP read real local mail and attachments; replies preserve threading. | `make client-live`, `make integration` |
| C07 | Read-only, cross-mailbox, expired and revoked credentials are denied. | `make unit`, `make client-live` |
| C08 | Failure/retry scenarios preserve idempotency and do not send externally. | `make unit`, `make client-test`, `make client-live` |
| C09 | Restarts and isolated encrypted restoration preserve mail and authorization. | `make clean-test`, `make restore-test` |
| C10 | Desktop/mobile onboarding exercises real loading, error/retry, empty and success states. | `make browser-test` plus visual inspection |
| C11 | Fresh local data can complete the client and browser flow without CI. | `make clean-test` |
| C12 | Documentation and private repository include reproducible build, usage and test commands. | `docs/typescript.md`, `Makefile` |

Production gates A09/A10/A14 and the external checks remain separate from completion of C01-C12. This milestone does not add public signup, hosted billing or an AI reasoning provider.
