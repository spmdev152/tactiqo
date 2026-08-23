---
name: sportmonks
description: Own Sportmonks fixtures, statistics, odds, predictions, normalization, caching, rate-limit efficiency, retries, and provider-contract isolation.
---
# Sportmonks Integration
Work against the active Football Starter subscription: five leagues, 2,000 API calls per entity per hour, and the Odds & Predictions add-on. The MVP league scope is Premier League (`8`), Bundesliga (`82`), Ligue 1 (`301`), Serie A (`384`), and La Liga (`564`). Centralize authentication, HTTP behavior, retries/backoff, pagination, metrics, caching, freshness, and normalization. Prefer enriched/batched calls and cached reference data. Model missing odds and non-predictable fixtures explicitly. Never expose provider credentials or leak raw Sportmonks contracts/type IDs into product APIs.
