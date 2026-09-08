# Implementation milestones

1. **Capture the foundation (this commit).** Acceptance criteria, architecture, exact known-working component versions, MCP compatibility patches and reproducible webmail image recipe. This is not product acceptance.
2. **Local mail environment.** Compose stack, configuration generator, idempotent bootstrap, seed fixtures and local outbound capture. Pass A01-A04 and A12.
3. **Local agent interface.** Mailbox-scoped API/MCP, connection workflow and real protocol tests. Pass A05-A08 and A11.
4. **Repeatable operations.** Deployment preflight, DNS change plan, Cloudflare integration, backups, restore and upgrade/rollback. Pass A09-A10 and A13-A15. Release 0.1 only after all A criteria pass.
5. **Agent workflows.** Persistent event queue, signed webhooks, idempotency and operator history. Pass B01-B04 and B07-B08.
6. **Scenario runner and regression capture.** Deterministic failure injection and sanitized production fixtures. Pass B05-B06. Release 0.2 only after all B criteria pass.

Each milestone includes local test evidence. Do not add CI. Do not modify the existing live mailbox while building the local product. Deploy to an isolated staging instance first.
