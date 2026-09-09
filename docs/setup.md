# First-run setup (in development)

Run `make setup` on a machine with Python 3.10 or newer. No existing mail configuration or Python packages are required. Open `http://127.0.0.1:19200`.

For a remote VPS, forward the private listener using `ssh -L 19200:127.0.0.1:19200 <server>`. Do not expose this bootstrap listener to the public internet. Production Tunnel and Access provisioning is still pending.

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

`POST /v1/setup/plan` refreshes the plan, and `GET /v1/setup` returns the last plan. Changing domain configuration discards the stale plan. Compatible existing DNS, owner-only Access policies and tunnel routes are reused. Differing settings produce explicit conflicts; planning never overwrites them. Write permissions remain unverified until a real authorized mutation is exercised. To authorize exactly the saved plan, call `POST /v1/setup/apply` with `{"confirm_plan_id":"<saved-plan-id>"}` or confirm the displayed plan in the form. The service rechecks remote state before the first mutation, creates and verifies Access gates before routes/DNS, preserves unrelated resources, and checkpoints acknowledged operations. A changed plan requires review. An operation with an unknown outcome stops for review rather than risking duplicate writes. Configuration and plan replacement are locked once provisioning starts. A new provider credential can still be validated and saved without changing the approved plan or completed steps. This is a web-protection operation only; it does not yet start the connector or deploy mail services.

## Current boundary

This first slice supports authenticated owner claim, configuration and an explicitly incomplete draft. It can plan and apply Cloudflare web-protection resources. It does **not** deploy mail, start the connector, execute end-to-end verification or mark setup complete. Mail and end-to-end infrastructure checks stay pending. Existing `make dev` and the configured production deployment path are unchanged. Do not infer production readiness from the first-run UI.

Run setup tests with `PYTHONPATH=src python3 -m unittest discover -s tests -p test_setup.py -v`.

Run `make setup-browser-test` for the isolated real browser flow. Screenshots are saved under `.runtime/evidence/` and contain only fictional setup data.

## Host prerequisites

The form's **Check this server** action and `POST /v1/setup/preflight` run the same read-only host checks. Results persist and appear on `GET /v1/setup` as `host_preflight`. Changing configuration invalidates them. The checks cover Linux, Docker/Compose, a global IP, local port-25 binding, an outbound TCP connection to an external MX, and PTR. No email is sent. Inbound reachability remains pending until independently checked from another host; a successful local bind cannot prove it. Do not stop an existing mail service to make a check pass.

`GET /v1/setup` also returns `missing_prerequisites`, `validation_failures`, `operations` and `next_action`. A conflict or uncertain write has a distinct state. Configured web resources do not imply a connected tunnel or working mail deployment.

## Isolated live checks

Keep a saved plan/settings bundle and its progress in a private evidence directory. Never point verification at the live mail domain. `scripts/verify_setup_cloudflare.py --evidence-dir <private-directory> --confirm-isolated-domain <test-subdomain>` requires `HERMESAKI_SETUP` injected privately. It verifies an already provisioned test plan, temporarily changes its test webmail CNAME to exercise conflict refusal, and restores the original value. It rejects a primary-zone test domain and requires exact domain confirmation. It compares all pre-existing records from `live-dns-before.json`; preserve that snapshot from before provisioning.

`packages/client/test/setup-live-state.mjs <private-live-plan.json>` uses the injected credential only for real provider reads and captures a fresh setup UI/API journey. The evidence rendering scripts display captured results; they do not execute checks themselves or establish acceptance.
