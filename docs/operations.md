# Backup, recovery and upgrades

```sh
make backup FILE=/safe/hermesaki.hmb KEY=/separate/hermesaki-backup.key
.venv/bin/python scripts/backup.py restore /safe/hermesaki.hmb \
  --key-file /separate/hermesaki-backup.key --destination /safe/restored
make restore-test
```

For production, pass `--compose compose.production.yaml` to the backup script. The backup stops the stack for a consistent snapshot, encrypts the entire `.runtime` tree with AES-256-GCM, then restarts it. Keep the backup key separately. It includes mail data, Roundcube database, product database, configuration and encryption material. Snapshot memory usage is bounded by rejecting source trees over 1 GiB; larger installations need a streaming encrypted volume backup before use.

Restore only writes a new empty directory and refuses to overwrite state. It rejects symlinks and unsafe archive paths. A wrong key or modified archive fails authentication. The local rehearsal starts a second Docker project from the restored data and reruns the integration checks before removing its temporary containers.

To recover a deployment, stop its stack, preserve its current state directory, place the restored `state` directory at `.runtime`, and start the same repository revision and component versions as the backup. Preserve `.env` too, or regenerate its single `HERMESAKI_MAIL_HOST` entry from your production config. Never restore a snapshot over running mail storage.

## Upgrade and rollback

Keep a clean repository checkout. Record the current commit and image IDs, take an encrypted backup, and retain the old images. Change pinned component versions on a branch, rebuild, run `make test` and `make restore-test`, and rehearse against a copy of the data before upgrading production. Preserve the MCPcube compatibility smoke test during Roundcube upgrades.

The current product database schema is version 1; an unknown schema prevents startup. There are no destructive automatic migrations. An actual version-changing upgrade is still a release gate. Do not claim that restarting the same images proves upgrade compatibility.

Rollback of code alone is allowed only when its data format remains compatible. Otherwise preserve a new snapshot of post-upgrade state first, then restore the old snapshot into a separate directory. Reconcile mail accepted after that snapshot before switching traffic. No command automatically discards newer data.

## Recovery controls

The operator view lists queued, submitted, uncertain and failed sends, attempts, webhook dead letters and audit metadata. Investigate uncertain sends in Stalwart before resolving them through the API. Resolution does not resend. Replay only dead-letter webhooks; consumers must deduplicate IDs.

Run exactly one worker. The file lock rejects a second worker, and a restart recovers interrupted webhook attempts. Incoming mail polling runs every 15 seconds. Plan retention and storage monitoring for your installation; automatic log/mail retention is not included.
