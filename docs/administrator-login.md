# Administrator sign-in

Local development uses a username and password. Production uses Cloudflare Access with an explicit administrator email allowlist. An orange-cloud DNS proxy or a bot challenge alone does not authenticate an administrator.

## First local start

Run `make dev`, then open `/login`. Read `.runtime/product/administrator-setup-code` on the server and enter it alongside your chosen username and password. The code is removed after the account is created. Passwords need at least 12 characters and are stored using salted scrypt hashes.

The installation wizard similarly creates a username/password account after verifying its one-time bootstrap code. Use that account to resume the private setup service. Production dashboard sign-in uses the owner email configured in the wizard.

## Production

The wizard writes `admin_emails` into the product configuration using the owner email. The API verifies Cloudflare's JWT signature, issuer, audience, expiration and subject on every request. Only a human identity whose email is in `admin_emails` may create an administrator session. Service identities still need a mailbox-scoped key and cannot create administrator sessions.

There is no production password fallback. Dashboard sign-out also signs out of Cloudflare Access. An opaque HttpOnly, Secure, SameSite=Strict cookie retains the session for up to 12 hours. Writes require the configured same origin. Password resets invalidate existing password sessions; removing an allowed Cloudflare administrator takes effect on subsequent requests.

## Existing installations: migrate before deployment

Before deploying this version, add `admin_emails` to the production state `config.json` with the authorized owner email(s). Preserve the existing Cloudflare team, audience, policies and tunnel protection. A missing/empty administrator allowlist denies dashboard sign-in. Do not deploy first and repair access afterward.

Old operator bearer tokens and token-backed browser sessions are no longer accepted by the HTTP API. Existing scoped mailbox keys continue working. Remove old operator-token files from the server and saved credential downloads after validating the new sign-in. They are no longer generated or included in new downloads.

For a local account reset, run on the trusted server:

```sh
python -m hermesaki.administrators --state /state --username admin
```

The command prompts privately for a new password and signs out existing sessions. It does not bypass production Cloudflare authorization. On a local checkout, set `PYTHONPATH=src` and use `.runtime/product` for the state directory.

For an existing private installation wizard that used an owner credential, run the same reset command with `--setup` and point `--state` at the wizard’s state directory. This creates its username/password account and invalidates its old setup sessions.

## Local design preview

The fictional walkthrough on port 19195 uses username `admin` and password `local-preview-only`. These are mock credentials only; they do not access a real installation. The preview is separate from the real authentication backend.

Cloudflare validation follows the [application token requirements](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/).
