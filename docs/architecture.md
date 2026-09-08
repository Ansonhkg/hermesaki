# Architecture

## Core

Stalwart owns durable mail storage and delivery. Roundcube is the human inbox. Hermesaki provides a versioned API, mailbox-scoped authorization, event processing and an operator view. The public MCP interface should use the product API rather than depending permanently on the browser UI.

MCPcube is the initial bridge, not a permanent product boundary. Its preserved source patches and dependency lock allow us to reproduce the current integration while building a stable product-owned interface.

## Local environment

Run the real core containers with persistent development volumes. Deliver outbound mail to a local SMTP capture service and inject inbound fixtures through real SMTP. A development-only identity adapter represents authenticated user/service claims. A deterministic scenario runner simulates external responses, delays, duplicated events and process failures.

Keep emulated behavior separate from observed behavior: fixtures record the scenario, expected contract and provenance. Do not emulate the whole mail server when the real server can run locally.

## Production environment

Use the same application images. Supply domain, DNS provider, external delivery settings and secrets through deployment configuration. Cloudflare Tunnel exposes the web services; Access protects browser sessions and remote MCP traffic. MCP clients authenticate separately at the Access and mailbox layers. SMTP reception is a separate public mail protocol and does not pass through the browser Access login.

A domain/DNS migration must preserve existing website and mail records until the replacement is verified. An installer must not replace nameservers or MX records without showing the concrete proposed changes.

## Data and events

Mail content lives in Stalwart. Product state, scoped credentials, jobs, idempotency keys and audit events live in a product database. Persist accepted events before processing, preserve stable event IDs across retries, and separate provider delivery state from workflow processing state.

An incoming-message event is not authorization to run arbitrary instructions found inside email. Treat message bodies and attachments as untrusted input. Read-only agents cannot gain send permission by following message content.

## Boundaries

No personal deployment identities in source templates. Production secrets and backup encryption material are separate from Git. Local data directories, generated source, build output and all credentials are ignored. Tests are run locally; no CI is provisioned.
