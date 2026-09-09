# TypeScript SDK and CLI

Requires Node.js 22+. From this private repository, run `npm ci --ignore-scripts && npm run build`.
The workspace package is `@hermesaki/client`; it is not published to npm. Use the workspace import, or install a locally packed artifact in another project (`npm pack --workspace @hermesaki/client --pack-destination /private/path`). No Python SDK is needed. The mail backend still uses Python.

```ts
import { Hermesaki, HermesakiError } from '@hermesaki/client';

const mail = new Hermesaki({
  baseUrl: 'http://localhost:19100',
  token: process.env.HERMESAKI_TOKEN!,
});
const messages = await mail.listMessages('YOUR_INBOX_ID');
```

The SDK supports inbox creation/list/deletion, token creation/revocation, folders, messages, attachments, sending, threaded replies, operator pages, MCP and development test messages. It uses native fetch in Node and browsers. `HermesakiError` exposes `status` and `code`. Requests time out after 20 seconds by default (`timeoutMs` overrides this). Redirects are rejected so credentials do not follow an unexpected endpoint. Remote connections require HTTPS; loopback HTTP is allowed for development.

Send and reply require a caller-supplied idempotency key. Reuse it with the same payload when retrying. The client does not automatically retry mutations or uncertain sends. `submitted` means SMTP accepted a message, not recipient delivery.

```ts
await mail.send('YOUR_INBOX_ID', {
  to: ['bob@example.test'],
  subject: 'Hello',
  body_text: 'A local test.',
}, 'my-stable-request-id');
```

For production Cloudflare service authentication, add `access: {clientId, clientSecret}` from your secret manager. These are separate from the mailbox token. The real browser UI uses the authenticated Cloudflare session and same-origin requests.

## CLI

Use `npm run hermesaki -- help` or `npm exec -- hermesaki help` from the repository. The packed package provides the `hermesaki` binary.

```sh
export HERMESAKI_URL=http://localhost:19100
export HERMESAKI_TOKEN_FILE=.runtime/product/operator-token
npm run hermesaki -- create --email atlas@example.test
npm run hermesaki -- token --inbox YOUR_INBOX_ID --out .runtime/atlas-token

export HERMESAKI_TOKEN_FILE=.runtime/atlas-token
npm run hermesaki -- folders --inbox YOUR_INBOX_ID
npm run hermesaki -- messages --inbox YOUR_INBOX_ID
```

Token issuance writes to a new file with mode 0600, never stdout. It refuses to overwrite an existing file and revokes the issued token if saving fails. Other commands output JSON; message-read commands intentionally include requested mail content. Credentials are accepted from files or environment variables, not command arguments. Use `--scopes mail.read,mail.write` to enable sending, and `--ttl` to set token lifetime in seconds. Default access is read-only and the lifetime is 30 days.

Sending takes `--file` pointing to a JSON message and `--key` for idempotency. Replies take `--uid`, `--file` containing `body_text`, and `--key`. Delete requires the exact `--email`. Run `help` for the complete command list.

## Real onboarding

Open http://localhost:19100/ui/onboarding/live.html after `make dev`. Choose `.runtime/product/operator-token` in the owner token file input. Credentials stay in tab memory; reloading requires authentication again.

1. Create an address on the configured domain. Repeating the same address retrieves the existing inbox.
2. Issue a mailbox token and save it. Choose MCP, TypeScript, CLI or HTTP examples.
3. Check real MCP access. Locally, queue a test message through SMTP and read its body through MCP.
4. Manage existing inboxes, issue replacement tokens, revoke old ones and confirm deletion by typing the email.

Changing permissions means issuing a new scoped token and revoking the old one. Issuing a new token alone does not revoke other clients. Mailbox credentials and owner credentials are distinct. Owner tokens do not implicitly read all inboxes.

The preview at `/ui/onboarding/` remains explicitly mock-only. The real page does not accept preview-state switches. The local SMTP test endpoint requires an owner token, targets an existing mailbox and is disabled outside development. In production, send an actual message from your mail client and refresh the inbox instead.

## Local acceptance commands

- `make test`: Python/security/recovery tests, real upstream mail integration, SDK contract tests, real SDK/CLI/MCP flow.
- `make browser-test`: authenticated real browser onboarding with error/retry, send/read and mobile checks. Install Chromium once with `npx playwright install chromium`.
- `make clean-test`: fresh isolated provisioning and client/browser flows, followed by restart and upstream integration. Uses separate loopback ports 19130–19132 and its own temporary data. Preserves the existing runtime.
- `make restore-test`: encrypted snapshot restored into a separate mail stack.

All tests use fictional addresses and local outbound capture. No CI or automatic deployment is installed. These tests do not prove public DNS, Cloudflare policy correctness or public email deliverability.
