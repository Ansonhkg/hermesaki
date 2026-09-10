# Recovery

## Complete bind-mount reinstall snapshots

`scripts/reinstall.py snapshot` now includes every absolute bind mount, including certificate stores outside `.runtime`. Compose configuration and the bind inventory are encrypted inside the snapshot. Existing version-one snapshots remain readable. Named volumes and missing bind sources are rejected before pausing services rather than silently omitted. Keep the encryption key separately, with private permissions.

Run `python3 scripts/verify_reinstall.py --help` for the complete backup and isolated restore rehearsal. Confirm the exact source Compose path and choose new archive and destination paths. It pauses the source briefly for a consistent snapshot, resumes it, restores into a new directory, and starts only mail, API and webmail on an internal-only network without published ports. It compares authenticated mailbox content hashes and domains, restarts the isolated copy, checks again, then removes the test containers and verifies the source is available. No worker or tunnel starts in the restored copy. Restored private data remains at the chosen destination for inspection.

This rehearsal proves restoration and container restart, not a host reboot or an independently completed setup wizard. Preserve separate evidence for those checks.
