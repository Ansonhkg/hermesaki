# Deploy to a separate staging server

Production changes are intentionally explicit. Do not point this setup at an existing mail directory. The production Compose file is standalone and must never be merged with the development file.

1. Provision a clean Linux Docker host with sufficient disk and working outbound TCP 25. Set its PTR to `mail.<domain>`. Keep SSH restricted separately.
2. Create DNS: DNS-only `mail` A/AAAA, MX pointing to that hostname, SPF authorizing the sending host, DKIM from Stalwart's generated domain keys, and DMARC. Copy existing website records before changing nameservers. DNS and external connectivity checks cannot be emulated locally.
3. Create a Cloudflare Tunnel. Route an inbox hostname to `http://webmail:80` and an API hostname to `http://api:8000`. Add a final catch-all 404. Protect **both entire hostnames** with Access applications before publishing routes. Allow only your intended user identities and service tokens. There must be no bypass rule. The API application audience belongs in the product configuration.
4. Obtain a valid mail certificate, private key and CA chain for `mail.<domain>`. The mail API and Roundcube verify this hostname through a private Docker network alias. Store the tunnel token in a file outside Git.
5. Install Node.js 22+, clone this private repo, run `npm ci --ignore-scripts && npm run build` and `make prepare`, copy `production.example.json` outside Git, and set the domain, mail hostname, management URL, public API URL, Access team and API audience. Keep `dev_auth` false. Only add explicit webhook destinations.
6. Run first-time provisioning:

```sh
.venv/bin/python scripts/provision.py \
  --config /secure/production.json \
  --certificate /secure/mail-fullchain.pem \
  --private-key /secure/mail-key.pem \
  --ca /secure/ca-chain.pem \
  --tunnel-token-file /secure/tunnel-token
make deploy
```

Create the virtual environment with `python3 -m venv .venv` and install `requirements.txt` first. Provisioning builds the API, bootstraps Stalwart, installs the certificate, and removes recovery-admin environment access after provisioning. It never creates Alice/Bob in production or installs the capture route. `make deploy` validates configuration and basic DNS presence, builds pinned images, and starts the production services.

Only SMTP port 25 is published. API, IMAP, webmail and management HTTP have no published origin ports. The API additionally validates Access JWTs. Cloudflare's actual Access rules must be tested externally, particularly for webmail, whose gate is enforced at the tunnel edge.

## Required staging verification

Verify an unauthenticated request cannot enter either hostname, permitted identities can enter, disallowed identities cannot enter, the origin's HTTP/HTTPS ports refuse public traffic, and sending/receiving works with another mail provider. Check SPF, DKIM, DMARC, TLS and PTR. Verify token revocation and a service-token MCP session through Access. Record the transcript in the evidence document before marking A09/A10 complete.

Certificate renewal must replace the Stalwart certificate through its management API and be monitored. This release does not automate an ACME provider or domain registrar. Provisioning is implemented but has not yet been rehearsed against a fresh public staging server. A failed provisioning after Stalwart writes its config requires investigating that preserved state; the script refuses to overwrite it.

## Reuse the Access setup

`scripts/cloudflare_access.py --config /secure/access.json` prints a plan. Add `--apply` with `CLOUDFLARE_API_TOKEN` in the environment to create owner-only Access applications, preserve existing tunnel routes, and create proxied DNS records. It refuses conflicting existing policies/routes/records. The JSON requires `account_id`, `zone_id`, `tunnel_id`, `owner_email`, `api_hostname`, `inbox_hostname`, `api_origin`, and `inbox_origin`. API credentials never enter the repository.

On an already occupied server, the development stack can serve as captured-mail staging behind these gates. It publishes only loopback ports and does not take SMTP port 25. This is deliberately different from enabling production mail delivery. Do not claim this topology validates the separate production bootstrap command.
