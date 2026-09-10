# Local product walkthrough

Run `npm ci`, `npm run demo`, then in another terminal `npm run demo:prepare`. Open http://127.0.0.1:19195. The viewer automatically loads prepared captures. No recording controls or production credentials are needed.

This uses a committed copy of Demo Walkthrough 0.4.0. The original library remains unchanged. `demo/` owns the adapter, fictional service responses and preparation. The real setup and onboarding HTML/JavaScript are served locally. Only loopback is bound; no mail provider is called. Prepared captures live in ignored `.runtime/demo/recordings.json`.

## Coverage

| Actor | Journey | Screens / branches | Status |
| --- | --- | --- | --- |
| Owner | First installation | Claim, domain, protection plan, service plan, signing, verification, completion | Captured real forms; provider/deployment results simulated |
| Owner | Agent onboarding | Invalid sign-in and retry, empty inbox list, create mailbox, issue read-only token | Captured real forms with fictional responses |
| Agent | Mail access | Connect through mock MCP, receive and read fictional message | Captured UI; not proof of real delivery |
| Owner | Retire access | Revoke token, explicit email confirmation, delete inbox | Captured UI with fictional responses |
| Operator | Delivery dashboard | Jobs, deliveries, audit, retries | Existing product; not part of this replay |
| Mailbox user | Roundcube | Sign-in, compose, folders | Separate upstream UI; not part of this replay |
| Owner | Recovery / provider failures | Restart, restore, real Cloudflare login, blocked SMTP | Covered by previous tests; not replayed here |

The graph includes the invalid-login/retry alternative and optional token revocation before deletion. Captures check visible UI outcomes only. The setup demo deliberately labels verification results as simulated. Read-only send denial is a backend contract tested separately; there is no send control in this onboarding UI.

## Live sign-in

Use `/ui/onboarding/live.html` or `/onboarding`. The operator credential is distinct from Cloudflare Access login. Upload the JSON credentials file downloaded during setup, or enter its `operator_token`. Authentication has not been bypassed or replaced by the demo.
