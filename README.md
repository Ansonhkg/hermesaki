# Hermesaki

![Hermesaki: Your mail. Your agents. Your server.](landing/assets/repo-thumbnail-creature-v2.png)

Self-hosted email for people and agents. Stalwart stores and delivers mail, Roundcube provides the browser inbox, and Hermesaki adds a scoped API, MCP, durable sends, webhooks and an operator view.

## Run locally

Requires Docker Compose, Python 3.12+, Node.js 22+, Git and authenticated `gh`. Tested on Apple Silicon with Docker Desktop; the mail core also has captured-mail Linux staging evidence.

```sh
make dev          # build pinned images and provision the isolated stack
make seed         # fictional Alice and Bob accounts, mail and attachments
make test         # unit tests plus real mail/API/MCP/webmail integration
make restore-test # restore a complete encrypted snapshot into another stack
```

| Open | Address |
| --- | --- |
| Agent onboarding | http://localhost:19100/ui/onboarding/live.html |
| Browser inbox | http://localhost:19180 |
| Operator and API | http://localhost:19100 |
| Captured outbound mail | http://localhost:19125 |
| MCP endpoint | http://localhost:19100/mcp |

`make credentials` displays the fictional webmail passwords locally. The operator token is in `.runtime/product/operator-token`; paste it into the operator page. Alice's development API token is in `.runtime/product/alice-token`. These files are ignored by Git. Development tokens expire after 30 days; mint replacements with the operator API.

Local mail, API and workers have no external network route. Only the loopback web proxy has a bridge network. Mail addressed outside the local domain goes to Mailpit, including addresses that look real. Production uses a separate Compose file with explicit SMTP egress.

## TypeScript SDK, CLI and onboarding

[Developer guide](docs/typescript.md): SDK examples, CLI commands, mailbox tokens and real onboarding. Run `make browser-test` for the UI flow and `make clean-test` to rehearse a fresh isolated install. The separate landing-page mock remains available for visual previews.

## Use the API and MCP

See [API and authentication](docs/api.md) for examples, mailbox tokens, idempotent sending, confirmation and client configuration. The product MCP endpoint shares the API authorization layer. The pinned MCPcube plugin and compatibility patch remain available in the webmail image, but the default product uses its own MCP endpoint.

Messages and attachments stay in Stalwart. Queued message content and mailbox credentials are encrypted in SQLite. The operator view exposes delivery metadata, attempts and audit history without message bodies. Incoming mail creates a deterministic draft; it is never sent automatically.

## Operate it

- [Deployment](docs/deployment.md): separate staging setup, DNS, TLS and Cloudflare Access.
- [Backup and upgrades](docs/operations.md): encrypted snapshots and non-destructive recovery.
- [Events and simulation](docs/events.md): delivery semantics, signatures and local failure tests.
- [Acceptance evidence](docs/evidence.md): passed checks and remaining release gates.
- [Architecture](docs/architecture.md) and [acceptance criteria](docs/acceptance.md).

The local product is implemented and exercised. A captured-mail staging deployment also runs on Linux behind Cloudflare Access. Public SMTP routing and a version-changing upgrade rehearsal remain release gates. Do not treat local tests as proof of public deliverability or Cloudflare policy correctness.

No CI, automatic deployment, live credentials or real mailbox fixtures are included. Upstream components retain their licenses; image versions and source revisions are recorded in `components.lock.json`.

## Landing page

Run `make landing` and open http://localhost:19190. A two-section page featuring the Hermesaki messenger, a short workflow and setup links.

## First-run setup preview

Run `make setup` to claim an unconfigured installation and save its domain settings through the app or the same agent API. Infrastructure provisioning is still pending. See [setup documentation](docs/setup.md) for credentials, private access and verification boundaries.
