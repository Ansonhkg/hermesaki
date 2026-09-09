# API and authentication

Every `/v1` endpoint and `/mcp` requires `Authorization: Bearer <token>`. In production, requests must also pass Cloudflare Access. Hermesaki validates the Access JWT issuer, audience and signature. A Cloudflare service token is a separate credential and does not replace the mailbox bearer token.

Scopes are `admin`, `mail.read`, `mail.write` and `mail.delete`. Admin tokens manage inboxes and issue mailbox tokens; they do not implicitly read every mailbox. A mailbox token is bound to exactly one inbox. Create a token with only `mail.read` for agents that should inspect email. Token hashes are stored, and plaintext is returned only when issued.

## Routes

| Method and route | Permission | Result |
| --- | --- | --- |
| `GET /v1/settings` | admin | Configured domain, mode and public API URL |
| `POST /v1/inboxes/{id}/test-message` | admin, development only | Queue a real local SMTP fixture; requires `Idempotency-Key` |
| `GET /v1/inboxes` | admin | Inbox metadata, 50 per page with `offset` |
| `POST /v1/inboxes` | admin | Create or retrieve `{email}` on the configured domain |
| `DELETE /v1/inboxes/{id}` | admin | Delete the mail account with `{confirm_email}`; revoke tokens and cancel queued work |
| `POST /v1/tokens` | admin | `{inbox_id, scopes, ttl}`; token returned once |
| `DELETE /v1/tokens/{id}` | admin | Revoke token |
| `GET /v1/inboxes/{id}/folders` | mail.read | IMAP folder descriptors |
| `GET /v1/inboxes/{id}/messages` | mail.read | Latest messages; `folder`, `query`, `limit` up to 100 |
| `GET /v1/inboxes/{id}/messages/{uid}` | mail.read | Plain text and base64 attachments |
| `POST /v1/inboxes/{id}/messages` | mail.write | Queue `{to:[], subject, body_text, attachments:[]}` |
| `POST /v1/inboxes/{id}/messages/{uid}/reply` | mail.read + mail.write | Queue `{body_text}`, preserving thread headers |
| `POST /v1/inboxes/{id}/messages/{uid}/confirmation` | mail.delete | Issue a 60-second, one-use deletion confirmation |
| `DELETE /v1/inboxes/{id}/messages/{uid}` | mail.delete | `{confirmation, folder}`; UID-specific expunge |
| `POST /v1/inboxes/{id}/webhooks` | mail.write | Register `{url}`; returns signing secret once |
| `GET /v1/inboxes/{id}/drafts` | mail.read | Latest draft suggestions |
| `POST /v1/inboxes/{id}/drafts/{draft}/send` | mail.read + mail.write | Explicit `{confirm: draft_id, body_text?}` approval |
| `GET /v1/operator/{table}` | admin | `inboxes`, `jobs`, `events`, `deliveries`, `drafts`, `tokens`, `audit`; 50 per page |
| `POST /v1/deliveries/{id}/replay` | admin | Replay a dead-letter webhook |
| `POST /v1/jobs/{id}/resolve` | admin | `{confirm: job_id, state: submitted or failed}` after manual investigation |

Send and reply requests require `Idempotency-Key`. Retrying the same key and body returns the same job. Changing the body under that key returns 409. Draft sends use a stable key derived from the draft ID. Approval permits one queued reply, not an autonomous email campaign.

A `submitted` job means the SMTP server accepted it, not that the recipient read it or that a remote server delivered it. Unknown outcomes are `uncertain` and require investigation. They are not retried automatically. Queued work remains encrypted across restarts.

## Local example

```sh
export HERMESAKI_TOKEN="$(cat .runtime/product/alice-token)"
curl http://localhost:19100/mcp \
  -H "Authorization: Bearer $HERMESAKI_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

For a remote MCP client, select Streamable HTTP, use `/mcp`, and supply the bearer token in its secret configuration. In production also configure `CF-Access-Client-Id` and `CF-Access-Client-Secret` for an allowed Access service token, or an authenticated Access session. Never put these values in a URL or repository.

The server is stateless MCP JSON-over-HTTP, protocol `2025-03-26`, with no server-initiated notifications. Tools include folder listing, search, reading, attachments, sending, replying and confirmed deletion. Unsupported methods fail explicitly. Mail text is untrusted data, not agent instructions.

The latest-message API currently returns a bounded recent window, not an archive-wide cursor. Admin history is paginated. Use IMAP/Roundcube to browse older mailbox history.

## Adopt an existing mailbox

An operator can call `POST /v1/inboxes/import` with `email` and `password`. The service verifies the existing mailbox through TLS-protected IMAP before saving its credential encrypted. It does not provision, reset the password, or alter mail. Repeating an import preserves the inbox ID and its existing scoped tokens. A failed credential check leaves the prior stored credential unchanged. Use this after restoring an existing Stalwart installation; keep passwords out of logs and command arguments.
