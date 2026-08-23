---
name: data-platform
description: Design PostgreSQL persistence, Redis usage, indexes, statistics, odds/prediction snapshots, caching, retention, and data-access boundaries.
---
# Data Platform
Treat PostgreSQL as canonical storage and Redis as selective cache, lock, and deduplication infrastructure. Model fixtures, statistics, predictions, and only the odds history the product actually needs. Use repositories and query modules when they add a meaningful boundary; avoid generic repository frameworks. Preserve provider timestamps and freshness metadata where useful. Optimize with evidence, not speculation.
