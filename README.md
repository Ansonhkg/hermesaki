# Hermesaki

A reusable, self-hosted email product for people and agents.

Run the same mail server, browser inbox, API and MCP integration locally and in production. Simulate external delivery and failures locally, then turn sanitized production incidents into regression fixtures.

## Status

This repository is the implementation specification and the preserved starting point from a working deployment. It is **not yet a complete, one-command email product**.

The source deployment verified SMTP sending and receiving, Roundcube login, Cloudflare Access, and read-only MCP access. Those results do not establish that a fresh Hermesaki deployment works. The clean-install and operational acceptance tests remain to be implemented.

## Contents

- [Acceptance criteria](docs/acceptance.md): release gates and required evidence.
- [Architecture](docs/architecture.md): local and production boundaries.
- [Implementation milestones](docs/milestones.md): ordered work toward the first release.
- [Existing deployment evidence](docs/baseline.md): what was verified and what was not.
- `components.lock.json`: exact mail-server and webmail image versions and MCP source revision.
- `patches/`: two tested MCP compatibility fixes.
- `integrations/mcpcube/`: resolved dependency lock and Apache routes.
- `docker/roundcube/Dockerfile`: reproducible webmail/MCP image build recipe.

## Local repository checks

Requires Python 3.11+, Git, and the GitHub CLI (`gh`). Docker is needed for image builds.

```sh
make test             # validate this repository's foundation, not product acceptance
make prepare          # fetch pinned MCP source and apply the preserved fixes
make build-roundcube  # build the pinned Roundcube + MCP image locally
```

No CI or automatic deployment. Tests and deployment are operator-run commands. Future `make dev`, `make seed`, `make deploy`, `make backup`, and `make restore` targets are requirements, not implemented commands.

No live credentials, email bodies, private server addresses, or account identifiers belong in Git. Use fictional fixtures and deployment-specific secret files outside the repository. The repository is private; bundled upstream code retains its upstream license.
