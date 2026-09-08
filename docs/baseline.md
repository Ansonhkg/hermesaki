# Existing deployment baseline

Observed on 2026-09-08, before this repository was created:

- Stalwart 0.16.19 accepted external SMTP and delivered outgoing mail to an external mailbox.
- An external reply was received in the Stalwart inbox.
- Roundcube was upgraded from 1.6.19 to 1.7.4 after backing up its configuration and database.
- Roundcube login worked after the upgrade.
- Cloudflare Access protected the browser inbox, MCP and OAuth routes; the web origin listened on loopback only.
- A dedicated Access service credential and a separate mailbox OAuth grant connected a client.
- MCP OAuth PKCE approval, token exchange, initialization, folder listing and message listing were tested.
- The persistent mailbox grant was mail.read. Temporary installation-test grants were revoked.

## Preserved fixes

1. MCPcube originally stored only the IMAP hostname, losing TLS and port. Reconnection tried plain port 143. The patch preserves storage_ssl and storage_port from the authenticated Roundcube session.
2. The plugin dependency autoloader is registered after the host autoloader so bundled dependency copies do not take precedence over Roundcube core classes.
3. The upstream Composer lock was refreshed against the actual PHP runtime. The resolved lock is included.
4. MCP and OAuth routes are inserted into the image's public_html/.htaccess source, which is copied at startup.

## Not yet proven

A fresh product install, full clean-server restore, unattended backups, automatic updates, systematic tenant isolation, write operations through MCP, signed webhooks, durable agent jobs, and the local failure simulator. Nothing in the existing manual deployment is evidence that these acceptance gates already pass.
