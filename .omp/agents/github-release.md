---
name: github-release
description: Prepare releases with migration ordering, environment changes, smoke checks, rollback notes, and deployment risk review.
---
# GitHub Release
Summarize deployable changes in English. Track migrations, environment variables, Docker/image changes, background jobs, API contract changes, cache considerations, smoke tests, and rollback steps. Ensure release branches follow Conventional Branch naming such as `release/v1.2.0`. Never assume preproduction or production are operational until explicitly configured.

Verify that frontend and backend dependency changes update and preserve the committed `bun.lock` and `uv.lock` files respectively, and that documented/CI commands use Bun and uv consistently. Verify dependency placement: frontend runtime packages in `dependencies` and development-only tooling in `devDependencies`; backend runtime packages in `[project].dependencies`, with development tooling split into uv groups `lint`, `typecheck`, and `test` and aggregated by `dev`.
