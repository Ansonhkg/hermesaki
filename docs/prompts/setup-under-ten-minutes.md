# Reduce configured setup time below ten minutes

Status: proposed work; no application changes are included in this PR.

Baseline: [published measurement](../../landing/setup-baseline.html), 12 September 2026. The current result is 58m 16s for installation and full verification, not a demonstrated sub-ten-minute setup.

## Copyable implementation-planning prompt

Improve Hermesaki setup so configuration takes less than 10 minutes once the required details, credentials, access and action approvals are available. This is a target to verify, not an existing performance claim.

First read the repository instructions, setup guide and the published 12 September 2026 baseline. The assisted rehearsal took 58m 16s for installation and full verification, or 1h 9m 34s including teardown and cleanup. Provider configuration, approvals and browser recovery occupied 17m 59s. Service provisioning occupied 3m 09s. DNS-related delays overlapped useful work; do not subtract the approximately 30-minute fail-to-pass window to invent an active setup time.

Inspect the current implementation and propose the smallest practical fixes. Check prerequisites and provider permissions once, reuse supplied details, publish DNS as early as dependencies allow, run independent work concurrently, keep browser ownership stable, and use tested MCP client configuration. Preserve existing resources and authorization protections. Do not bypass approvals, disable TLS verification, loosen permissions, send unauthorized email, or tear down a live installation for a benchmark.

Represent configured, DNS pending, and fully verified as distinct states. When observed DNS/cache information supports it, show an approximate retry interval and its basis: “Setup configured. DNS is still propagating. Try verification again in approximately X minutes. Your agent can resume without reinstalling.” If the interval cannot be estimated, say so. Preserve progress and idempotency; after the suggested window, diagnose a persistent failure instead of repeatedly reinstalling or calling every error propagation. Keep native MCP send/read/reply, recipient receipt, SPF/DKIM/DMARC, TLS and access checks mandatory before fully verified status.

Instrument setup start, configuration ready, each explicit DNS-blocked interval, owner requests and responses, native MCP readiness, full verification, cleanup and evidence collection. Use UTC wall-clock timestamps and monotonic durations. Label overlaps, agent/tool failures, supervisor assistance, prerequisites, cache state, source revision and benchmark environment. Report human hands-on time only if actually measured. Keep teardown, preparation, DNS waits and extended audit time separate; retain the full elapsed total as well. Do not obtain a sub-10-minute result by omitting required work or blindly subtracting overlapping waits.

Start with a prompt-only or documentation-only PR describing the inspected causes, proposed changes, acceptance checks and measurement plan; do not implement application changes in that PR. Link the baseline and distinguish observed facts from hypotheses. A later implementation PR should include focused local tests for resumability, DNS-pending UX, permission failures and timing accounting, followed by an explicitly authorized measured rehearsal. Preserve private evidence locally and publish only sanitized results. Do not change repository visibility or add CI/automatic deployment.
