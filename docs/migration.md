# Adopt an existing mail installation

Migration is currently an operator procedure. The setup wizard does not yet automate this procedure or prove a complete clean production install.

Before cutover, inventory every domain using the mail database, the webmail database and plugin configuration, TLS hostnames, SMTP consumers, published ports, and Cloudflare routes. Preserve the existing mail and webmail versions for the first migration. Obtain authorization for the concrete plan.

1. Take an encrypted, consistent backup while all writers are paused. Always unpause them in a `finally` block. Keep the decryption key separately and verify decryption.
2. Restore an isolated copy with no outbound delivery. Test TLS mailbox login, folder and message identities, and real webmail login.
3. Stop source writers for the final copy. Use an ownership-preserving copy such as `cp -a`; Python `shutil.copytree` does not preserve ownership. Verify the mail and webmail runtime users can access their state. Keep the original containers and data.
4. Start the target with the same ports and TLS names. If temporary recovery administration is required to create a dedicated management identity, remove it and recreate the mail container before exposing the runtime.
5. Adopt the existing mailbox through `POST /v1/inboxes/import`. This validates the current credentials without resetting the password or provisioning a replacement mailbox.
6. Start the production API, worker, webmail and tunnel. The tunnel process must be able to read its private token file; preserve its runtime user or assign token ownership to the actual process UID with mode `0600`.
7. Verify mailbox contents, webmail, all domain consumers, API authorization, Cloudflare protection and external mail delivery. Record separately which checks passed and which remain unverified. Take a new encrypted backup.

If rollback is needed, stop target writers first. With unchanged database versions, copy the latest target mail and webmail data back with ownership preserved before restarting source containers. Retain both prior snapshots. Do not discard messages received after cutover. Validate service health and mailbox access after rollback.

A successful migration is not evidence of host-restart recovery, certificate renewal, a clean setup journey, or external inbox delivery. Test those separately before declaring the self-hosted product complete.
