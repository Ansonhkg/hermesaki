# Events and local simulation

Event schema 1 contains `id`, `version`, `type`, `inbox_id`, `created_at`, and metadata-only `data`. Incoming IDs derive from inbox, IMAP UIDVALIDITY and UID. Repeated polls do not emit another event. A received message creates a draft with a stable event-derived identifier. The bundled agent is a deterministic draft stub, ready to replace with a model adapter; it does not claim to be an autonomous assistant.

`message.submitted` records SMTP acceptance. `message.failed` records explicit rejection. `message.uncertain` records an unconfirmed outcome. Incoming delivery-status reports produce `message.delivered`, `message.bounced` or `message.delayed` where the sender provides such reports. Remote servers do not always issue DSNs, so lack of a bounce is not proof of delivery.

A single worker holds an exclusive file lock. SQLite transactions claim jobs, and accepted work survives process restarts. A crash during SMTP produces an uncertain job rather than a blind resend. Exactly-once SMTP delivery is not promised. Webhooks are at least once, so consumers must deduplicate event IDs.

## Webhook signature

The signature is `v1=` followed by hex HMAC-SHA256 over `<timestamp>.<exact request bytes>`, using the registration secret. Headers are `X-Hermesaki-Timestamp` and `X-Hermesaki-Signature`. `verify_signature` checks both the signature and a default five-minute freshness window.

Delivery retries use bounded exponential backoff, up to the configured attempt limit. Exhausted records become `dead`, visible in the operator view and replayable through the admin API. Non-2xx responses and timeouts are failures. Redirects are not followed. Production requires HTTPS, explicitly allowed hosts and public resolved IPs; connections use the validated address to prevent DNS rebinding.

The development `receiver` service verifies signatures and records fixture IDs. It is absent from production Compose. Unit tests inject a clock and transport failure to cover delayed retries, temporary rejection, permanent rejection, outage, duplicate requests and crash recovery. Integration tests exercise actual SMTP, IMAP and HTTP. These are behavioral simulators around real mail services, not a fake replacement for Stalwart.

To add a regression, keep fixtures fictional and minimal. Never copy production bodies, attachments, authentication headers or real identities. The seed regression covers delayed search indexing: duplicate detection fetches Message-ID headers directly instead of relying on an immediately updated full-text index. The preserved MCPcube regression tests cover TLS transport settings. A production incident fixture must be reviewed for redaction before committing.
