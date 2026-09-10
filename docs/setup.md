# First-run setup (in development)

Run `make setup` on a machine with Python 3.10 or newer. No existing mail configuration or Python packages are required. Open `http://127.0.0.1:19200`.

For a remote VPS, forward the private listener using `ssh -L 19200:127.0.0.1:19200 <server>`. Do not expose this bootstrap listener to the public internet. Cloudflare web protection can be provisioned from the wizard. The bootstrap listener stays private.

Read `.runtime/setup/bootstrap-token` privately on the server. In the form, generate and save a new owner credential before claiming the installation. The bootstrap credential is consumed once. Reconnect using the saved owner credential. Keep downloaded credential files private; the browser does not persist them. Losing the HTTP claim response does not lose the client-generated owner credential.

## Agent API

Use `Authorization: Bearer <credential>` in headers, never in URLs. JSON requests use `Content-Type: application/json`.

1. `GET /v1/setup/status` returns whether an owner exists, without secrets.
2. Generate a fresh owner credential from at least 32 cryptographically random bytes, encoded as URL-safe base64 or hex. Save it privately before sending the claim.
3. `POST /v1/setup/claim` with bootstrap authorization and `{"owner_token":"<new-owner-credential>"}` claims the instance once.
4. With owner authorization, `GET /v1/setup` exposes configuration, pending checks and next actions.
5. `PUT /v1/setup/configuration` accepts exactly `domain`, `server_ip` and `owner_email` (the domain may be a subdomain of an authorized Cloudflare zone). Repeating the same request is safe; settings persist across restart.

The forms call these exact endpoints. The state database contains credential hashes, not plaintext owner credentials. Back up the private setup directory alongside the product state, and retain the owner credential separately.

## Cloudflare planning

After saving domain settings, the same UI and API can validate a provider credential using `PUT /v1/setup/cloudflare` with `{"token":"<provider-token>"}`. It checks the active zone and reads DNS, Access applications and Tunnels. A valid credential is saved in a private 0600 file in the 0700 setup directory, not in the database or API response. Replacement validates first and atomically replaces the previous credential. The secret is not encrypted against someone with access to the host account; protect the state directory and backups.

`POST /v1/setup/plan` refreshes the plan, and `GET /v1/setup` returns the last plan. Changing domain configuration discards the stale plan. Compatible existing DNS, owner-only Access policies and tunnel routes are reused. Differing settings produce explicit conflicts; planning never overwrites them. Write permissions remain unverified until a real authorized mutation is exercised. To authorize exactly the saved plan, call `POST /v1/setup/apply` with `{"confirm_plan_id":"<saved-plan-id>"}` or confirm the displayed plan in the form. The service rechecks remote state before the first mutation, creates and verifies Access gates before routes/DNS, preserves unrelated resources, and checkpoints acknowledged operations. A changed plan requires review. An operation with an unknown outcome stops for review rather than risking duplicate writes. Configuration and plan replacement are locked once provisioning starts. A new provider credential can still be validated and saved without changing the approved plan or completed steps. This first plan applies web protection. A separate service plan below deploys the connector and mail.

## Current boundary

The wizard supports owner claim, Cloudflare provisioning and an explicitly approved fresh-mail deployment. It does not yet run the full public verification/completion handover. A running stack remains `complete:false`. Existing `make dev` and the configured production migration path remain separate. Public clean-install acceptance is pending.

Run setup tests with `PYTHONPATH=src python3 -m unittest discover -s tests -p test_setup.py -v`.

Run `make setup-browser-test` for the isolated real browser flow. Screenshots are saved under `.runtime/evidence/` and contain only fictional setup data.

## Host prerequisites

The form's **Check this server** action and `POST /v1/setup/preflight` run the same read-only host checks. Results persist and appear on `GET /v1/setup` as `host_preflight`. Changing configuration invalidates them. The checks cover Linux, Docker/Compose, a global IP, local port-25 binding, an outbound TCP connection to an external MX, and PTR. No email is sent. Inbound reachability remains pending until independently checked from another host; a successful local bind cannot prove it. Do not stop an existing mail service to make a check pass.

`GET /v1/setup` also returns `missing_prerequisites`, `validation_failures`, `operations` and `next_action`. A conflict or uncertain write has a distinct state. Configured web resources do not imply a connected tunnel or working mail deployment.

## Isolated live checks

Keep a saved plan/settings bundle and its progress in a private evidence directory. Never point verification at the live mail domain. `scripts/verify_setup_cloudflare.py --evidence-dir <private-directory> --confirm-isolated-domain <test-subdomain>` requires `HERMESAKI_SETUP` injected privately. It verifies an already provisioned test plan, temporarily changes its test webmail CNAME to exercise conflict refusal, and restores the original value. It rejects a primary-zone test domain and requires exact domain confirmation. It compares all pre-existing records from `live-dns-before.json`; preserve that snapshot from before provisioning.

`packages/client/test/setup-live-state.mjs <private-live-plan.json>` uses the injected credential only for real provider reads and captures a fresh setup UI/API journey. The evidence rendering scripts display captured results; they do not execute checks themselves or establish acceptance.

`python3 scripts/verify_setup_restart.py --state <new-private-directory> --settings <private-settings.json> --confirm-isolated-domain <unused-test-subdomain>` runs a real crash/restart verification with `HERMESAKI_SETUP` injected privately. It creates isolated web-protection resources, kills a child setup process after its tunnel checkpoint commits, reopens the same state and resumes the same plan. A repeated apply compares resource IDs and checks the retained credential. The output explicitly keeps full setup incomplete. Test resources and private state remain available for inspection; the script refuses to reuse an existing state directory or primary zone. It does not touch the production inbox or prove full mail deployment.

## Fresh mail service plan

After web resources are applied, `POST /v1/setup/services/plan` accepts `access_team` (the name before `.cloudflareaccess.com`), `first_mailbox` (an address on the configured domain), and `accept_acme_terms:true`. The forms use the same operation. Review the [Let's Encrypt subscriber agreement](https://letsencrypt.org/repository/) before accepting it.

The plan lists mail A/AAAA, MX, SPF and DMARC records, pinned services, the sole published SMTP port, private storage, certificate issuance/renewal, and the initial mailbox. Existing incompatible mail records or unowned runtime data block deployment. Compatible records are reused; unrelated TXT records are preserved. DKIM public keys are generated during mail bootstrap and reviewed in a second plan.

`POST /v1/setup/services/apply` requires exactly `{"confirm_plan_id":"<service-plan-id>"}`. The server rechecks the plan and host prerequisites before changes. State lives under the setup directory's private `installation/` directory, with a separate Compose project. It never adopts the existing production installation. Steps checkpoint certificate issuance, image builds, mail initialization, recovery-credential retirement, first mailbox verification and service startup. An uncertain DNS write halts unless an exact matching record can be reconciled. Process output is not returned to clients because upstream errors may contain credentials.

Certificates use the pinned official [Certbot Cloudflare DNS plugin](https://certbot-dns-cloudflare.readthedocs.io/en/stable/). A container checks for renewal every twelve hours. A private certificate-sync worker updates Stalwart and verifies the certificate actually served over IMAP before recording success. Full public issuance/renewal verification is still pending; local certificate replacement is covered by a real isolated mail test.

`POST /v1/setup/dkim/plan` retrieves only generated public signing records. `POST /v1/setup/dkim/apply` requires the exact returned plan ID. Conflicting DNS or changed keys block publication. Private signing keys are never returned. The pinned Stalwart version returns base64 public keys; the exporter also handles PEM and validates key encoding.

After services start, `POST /v1/setup/services/credentials` lets the authenticated owner download mailbox and operator credentials. Normal state responses never contain these values. The browser does not persist them. The operator UI and MCP use the protected operator hostname; Roundcube uses its own mailbox login. Setup still reports incomplete until the remaining public checks and completion gate are implemented and verified.

## Runtime regression test

Build the API image with `docker build -f docker/api/Dockerfile -t hermesaki-setup-api:test .`, then run `.venv/bin/python scripts/verify_setup_runtime.py`. It starts real Stalwart and Roundcube on an internal-only network, with no published ports or outgoing delivery. Cloudflare and the certificate authority are explicit local fixtures. It verifies fresh mailbox creation, TLS login, folders and idempotent retry. It tears down its containers and retains private state for inspection. This test is not evidence of a complete public installation.

For an explicit public certificate check, inject `HERMESAKI_SETUP` privately and run `python3 scripts/verify_setup_acme.py --domain <isolated-subdomain> --confirm-isolated-domain <same-subdomain> --email <owner-contact> --state <private-directory> --accept-acme-terms`. This creates and removes ACME challenge records, issues a real certificate, then runs renewal against the staging authority without replacing the production certificate. It refuses the zone apex and does not send email. Retain the state privately for inspection.

`POST /v1/setup/services/verify` and the installation check button report actual private mailbox/TLS, webmail, anonymous Access redirects, Docker-published ports, and saved DKIM/renewal checks. Public mail DNS, external mail, authenticated remote agent access and provider-network checks remain explicitly pending until their verification paths are completed. `POST /v1/setup/services/renewal-check` runs a real ACME dry-run. Replacing the Cloudflare credential invalidates the saved verification and renewal results and updates the privately mounted renewal credential.

New setups using a subdomain of a Cloudflare zone automatically choose single-label web names in that zone, such as `inbox-trial.example.com` and `hermesaki-trial.example.com` for mail domain `trial.example.com`. This keeps web endpoints within the default Cloudflare certificate coverage. The mail hostname remains `mail.trial.example.com` and uses its separately issued ACME certificate. Existing saved/provisioned plans retain their original hostnames. The service planner checks the actual HTTPS Access redirect before allowing deployment, so an unavailable certificate or incorrect Access team is reported before startup.

## Completion handover

`POST /v1/setup/complete` requires the exact service plan ID as
`confirm_plan_id`. It runs verification again rather than accepting saved or
caller-supplied success flags. Every required check must be present exactly once,
passed, and fresh. Pending, failed, missing or stale checks reject completion.
Successful completion persists across setup restarts and retires setup mutations.
The authenticated setup status returns the normal operator, webmail and MCP URLs
without secrets. Save operator and mailbox credentials before finishing.

The setup page exposes the same finish action only when verification is ready.
Public A/AAAA, MX, SPF and DMARC records now use actual resolver observations.
External mail, authenticated remote-agent and external network verification are
still pending in the current implementation, so this new gate does not yet make a
full fresh production setup completable. Tests of the gate use explicit verifier
fixtures and are not evidence that those public checks passed.

## External SMTP and DNS probe

After deployment, request `POST /v1/setup/network/challenge` as the owner, or use
**Download network challenge**. Keep the JSON private: it contains a short-lived
probe signing key. On another publicly addressed host with Hermesaki available,
run `python -m hermesaki.setup_network < challenge.json > result.json`, then POST
the result to `/v1/setup/network/result` or upload it through the same setup page.
The helper connects to public SMTP, reads its greeting, sends QUIT without mail,
and checks forward and reverse DNS. The setup service verifies the signature,
plan binding and expiry, then consumes the challenge. A failed observation stays
pending with a remedy. A check from the mail server's own IP or a private source
cannot pass. This is an owner-operated probe, not third-party attestation: the
owner must run the unmodified helper on the intended external machine.

During installation verification, accepted inbound observations expire after
24 hours and outbound SMTP is checked again from the installation host. Provider
credential replacement invalidates saved network results. None of these checks
establishes external email delivery or sender authentication; those remain separate.

Unattended Cloudflare Access verification also requires the setup API credential
to have **Access: Service Tokens Write** in the selected account. Listing service
tokens does not prove permission to create them. The deployed mailbox still
requires its own scoped token after Access authentication.
