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

## Reinstall on the same host

A second VPS is not required for replacing an existing Hermesaki installation.
Keep the existing service versions during restoration. Back up every domain,
mailbox, webmail database, API state, encryption key and Tunnel credential together.

`scripts/reinstall.py snapshot --source <compose.json> --archive <new.aesgcm>
--key-file <private-key-file>` pauses the existing containers for a consistent,
encrypted snapshot and resumes them afterwards. Copy the archive and its private
composition sidecar off-host; store the encryption key separately. The command
currently supports runtimes smaller than 1 GiB with bind mounts beneath the
source's `.runtime` directory. Configuration sidecars contain secrets and must
remain private. For a final cutover snapshot, `--stop-source` leaves services
stopped so messages cannot arrive between the snapshot and replacement.

`scripts/reinstall.py restore --source <original-compose.json> --archive
<snapshot.aesgcm> --key-file <private-key-file> --destination <new-directory>`
decrypts into a new directory, preserves file ownership and modes, and generates
`compose.json` with storage redirected to the restored directory. It refuses
existing destinations, unsafe archives and unsupported external bind mounts.
Restoration does not start services or overwrite the original data.

First rehearse in an internal Docker network with no public ports or outbound
network. Compare authenticated mailbox contents and all domains. For cutover,
stop the source, take the final snapshot and restore again into a separate empty
directory. Start the restored composition, verify it, and retire the old command
path so later maintenance cannot accidentally start the old snapshot. Keep the
original data and encrypted backups. If rollback becomes necessary after mail has
arrived, retain the latest restored runtime rather than discarding new messages.

This operator recovery path is separate from completing a fresh installation
through the setup forms or API. Passing it does not prove those setup journeys.
