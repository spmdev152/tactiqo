# Tactiqo

Tactiqo is a football intelligence web platform built on top of the Sportmonks Football API.

The MVP is focused on a small, well-modelled product surface:

- Discover fixtures by competition and date.
- Open fixture detail pages.
- Inspect pre-match and historical match/team statistics relevant to a fixture.
- Inspect bookmaker odds available through the active Sportmonks subscription.
- Inspect Sportmonks predictions for the supported markets and selections.

The MVP league scope matches the active Sportmonks subscription: Premier League (`8`), Bundesliga (`82`), Ligue 1 (`301`), Serie A (`384`), and La Liga (`564`).

Out of scope for the MVP: live ingestion, WebSockets, AI-generated insights, custom prediction models, mobile applications, and distributed microservices.

## Stack

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, shadcn/ui, with Bun as runtime, package manager, and script runner.
- Backend: Python, Django, Django Ninja for the REST API, Celery and Celery Beat for background work, with uv as the project and dependency manager.
- Data: PostgreSQL for canonical storage and Redis for caching, locks, and coordination.
- Provider: Sportmonks, accessed only from the backend and never from the browser.
- Tooling: Ruff and Pyright for Python, Prettier, ESLint, TypeScript, Vitest, React Testing Library, and React Doctor for the frontend.
- Infrastructure: Docker and Docker Compose locally, GitHub Actions for CI.

## Repository layout

```text
backend/     Django project, Django Ninja API, Celery application, Sportmonks integration, and tests
frontend/    Next.js application, features, and tests
compose.yml  Local orchestration for every runnable service
.env.example Environment variable reference for every environment
.github/     GitHub Actions quality gates
```

## Local setup

Prerequisites: Docker with Compose v2 or newer. Bun and uv are only required when running a tree outside of Docker.

```bash
cp .env.example .env.local
docker compose --env-file .env.local up
```

The first start builds both application images, provisions PostgreSQL and Redis, and waits for their health checks before starting the Django and Celery containers.

Apply database migrations once the stack is running:

```bash
docker compose --env-file .env.local exec api uv run python manage.py migrate
```

Accounts are identified by an e-mail address rather than a username, so `createsuperuser` prompts for an e-mail address and stores it lowercased:

```bash
docker compose --env-file .env.local exec api uv run python manage.py createsuperuser
```

A database provisioned before the `accounts` application existed cannot be migrated onto it. `AUTH_USER_MODEL` is a swapped dependency of `django.contrib.admin`, so an older volume already has `admin.0001_initial` applied against Django's built-in user and `migrate` refuses with `InconsistentMigrationHistory`. Discard the volume, which holds no product data yet:

```bash
docker compose --env-file .env.local down --volumes
docker compose --env-file .env.local up --detach
docker compose --env-file .env.local exec api uv run python manage.py migrate
```

Source directories are bind-mounted into the containers, so local edits hot-reload without shadowing installed dependencies. The backend virtual environment lives at `/opt/venv` inside the API image, outside the bind-mounted `/app`, and the web image keeps `node_modules` in a named volume so the container's Linux install never shadows the host one.

Both services reconcile their dependencies at container start, which is what makes a `bun add` or a `uv add` on the host visible inside the stack. The `web` command is `bun install --frozen-lockfile && bun run dev`, because Docker copies an image's content into a named volume only while that volume is empty: without the install, `frontend-node-modules` would keep whatever the first `up` put there and every package added afterwards would fail to resolve at build time. The API needs no equivalent, since `uv run` syncs `/opt/venv` against the bind-mounted `uv.lock` on its own. Both installs are frozen, so a `package.json` or `pyproject.toml` that has drifted from its lockfile fails loudly instead of resolving something the lockfile never pinned.

The `web` container runs as its image's `bun` user, uid and gid 1000, rather than as root. That is what keeps `frontend/.next` owned by the developer: Docker creates a named-volume mountpoint on the host as root, so `.next` deliberately has no volume and lives in the bind mount, written by an unprivileged container. Without this, the first `docker compose up` on a fresh clone would leave `frontend/.next` root-owned and every host `bun run` command would fail with `EACCES`. A host account whose uid is not 1000 needs `user: "${UID}:${GID}"` on the service.

### Services and ports

| Service    | Description             | Host port |
| ---------- | ----------------------- | --------- |
| `web`      | Next.js application     | 3000      |
| `api`      | Django and Django Ninja | 8000      |
| `worker`   | Celery worker           | —         |
| `beat`     | Celery Beat scheduler   | —         |
| `postgres` | PostgreSQL 18           | 5432      |
| `redis`    | Redis 8                 | 6379      |

### Local URLs

- Web application: `http://localhost:3000`
- API health check: `http://localhost:8000/api/v1/health`
- API documentation: `http://localhost:8000/api/v1/docs`

## Environment variables

All variables are documented in `.env.example`. Copy the file to `.env.local` and keep real credentials out of version control. Every `docker compose` command takes `--env-file .env.local`, and that flag is the single thing that selects an environment.

`compose.yml` declares explicitly which variables each service receives, so the exposure is readable at a glance and verifiable: `api`, `worker`, and `beat` receive the 19 variables the Django settings actually read, `postgres` receives only its 3 credentials, `redis` receives none, and `web` receives only `BACKEND_API_BASE_URL` and `SESSION_COOKIE_INSECURE`. Neither of those is a credential, so the frontend container still never holds `SPORTMONKS_API_TOKEN` or `POSTGRES_PASSWORD`. Every variable is declared as `${NAME?...}`, so a forgotten `--env-file` fails immediately with `required variable ... is missing a value` instead of silently starting a stack full of blank configuration. The form without a colon is deliberate: it accepts a legitimately empty value such as `SPORTMONKS_API_TOKEN=` while still rejecting an absent one.

`SESSION_COOKIE_INSECURE` exists so that dropping the `Secure` attribute from the session cookie is a deliberate declaration rather than a side effect. Only the exact value `true` drops it, which is correct for local development over plain HTTP and wrong everywhere else. Deriving it from `NODE_ENV` instead would have tied a transport security control to a build mode, and `frontend/Dockerfile` pins `NODE_ENV=development`, so the first deployed image built from it would have shipped a cookie with no `Secure` attribute and nothing in the types, the tests, or the quality gates would have said so.

### Logging

Loguru is the single sink for every backend process, installed behind the standard library so Django, Celery, and third-party packages share one format. Application code calls `logging.getLogger(__name__)` and never imports Loguru.

`DJANGO_LOG_LEVEL` controls verbosity. Local development defaults to `DEBUG` with human-readable colourized output; `preproduction` and `production` emit one JSON object per record and clamp the level, so exporting `DJANGO_LOG_LEVEL=DEBUG` against a deployed environment still yields `INFO`. That clamp is deliberate: debug records can carry request payloads, and Loguru's `diagnose` option, enabled only locally, prints the variable values around a traceback.

`SPORTMONKS_API_TOKEN` is backend-only and never reaches the frontend container. Only `NEXT_PUBLIC_*` variables are exposed to browser code.

### Sign-in rate limiting

`POST /api/v1/auth/login` is the only throttled operation. `DJANGO_SIGN_IN_THROTTLE_RATE` configures it per environment and defaults to `5/m`: a visitor needs two or three attempts to recover from a typo, and the credential behind this endpoint is issued by an administrator and never rotated by its owner, so an unlimited guessing rate against it is the wrong shape. A rate that parses but permits no attempt, or spans no time, is refused at boot rather than silently bricking sign-in or silently disabling the throttle.

Exceeding the rate answers `429` with `{"detail": "Too many requests."}`, which is uniform on purpose: the throttle counts attempts without reading the submitted address, so it cannot become the account oracle the `401` body deliberately refuses to be. Attempts are counted before the operation runs, which means a successful sign-in spends budget too — the throttle cannot know the outcome, and a client signing in more than a handful of times per minute is not a shape this product has.

The scope is sign-in alone rather than the whole `NinjaAPI`, so a rejected password can never deny `/health` or a future read endpoint. The counter lives in the configured cache, so every API process shares one budget per client rather than each holding its own.

Two properties of the counter are deliberate. It is a **fixed window**, one cache key per window named after the window's ordinal, rather than the sliding window Django Ninja implements: the sliding version reads the attempt history, mutates it and writes it back, so concurrent attempts all act on the same pre-state and one Redis round trip is enough for a client opening several connections to exceed the rate several-fold. The price is that a client can spend two windows' worth of attempts across a boundary. Naming the window in the key is what keeps the counter from expiring while its own window is current, which is the state in which Django's non-atomic `incr` would recreate it with no lifetime and refuse that one client forever; should a counter end up in that state anyway, the next window uses a different key and the damage expires on its own. And a **cache failure allows the attempt** and logs a warning with its cause, because denying every sign-in while Redis is unreachable would turn a degraded dependency into a total authentication outage; `config/health.py` already treats the cache as degradable rather than fatal.

#### Which client a request is attributed to

The browser never contacts the API, so `REMOTE_ADDR` is the Next.js server for every visitor and keying on it alone would collapse every sign-in on the platform into one bucket, where one attacker locks everybody out. The frontend therefore forwards the `X-Forwarded-For` chain of the incoming request verbatim on its login call, and the backend decides what to believe:

- `DJANGO_TRUSTED_PROXY_NETWORKS` names the addresses the API accepts a forwarding header **from**: its own peer, which is the Next.js tier plus any proxy terminating between the two. Addresses and CIDR networks are both accepted, a default route is refused because it would trust every peer, and when the peer is outside the list the header is ignored entirely and the request is attributed to the peer.
- `DJANGO_TRUSTED_PROXY_HOPS` states how many entries **our own infrastructure appended after the visitor's address**. Zero is right for an edge that appends only its peer, which is what nginx's `$proxy_add_x_forwarded_for` does; `1` is right for an edge that also appends itself, which Google Cloud's external Application Load Balancer documents doing, and for each additional proxy between the frontend and the API that appends. The identity is the entry that many places left of the end of the chain. Counting from the right is what makes an entry a visitor supplied unreachable, since every hop appends after them. It is bounded to 8, because a value deeper than any real chain attributes every visitor to the peer.
- A chain too short for the configured hops, or an entry that is not an address, with or without a port, falls back to the truthful peer rather than to a value the visitor may have chosen — one shared bucket is a worse throttle, but a client-chosen bucket is no throttle at all. No header text can reach a cache key either way.
- An IPv6 client is identified by its `/64` prefix. A delegated `/64` holds 2**64 addresses, so a per-address bucket would be free to escape. A visitor holding a wider delegation, a `/56` or a `/48`, still has one bucket per `/64` in it.

**Before this is deployed**, three requirements, and `preproduction` and `production` refuse to boot without the first two rather than trusting a default. The peer addresses must be named in `DJANGO_TRUSTED_PROXY_NETWORKS`, as narrowly as the deployment allows: never a pod, service or VPC CIDR, because every workload inside the range could then forge a chain, mint buckets and spend a chosen visitor's budget. The depth must be stated in `DJANGO_TRUSTED_PROXY_HOPS`, because both directions of a wrong value hurt — too low attributes visitors to a proxy, too high attributes them to whatever they sent, and neither is what you want. And the edge in front of the frontend must set `X-Forwarded-For` from the connecting address: Next.js fills that header in from the socket only when the request carries none, so a directly exposed frontend would pass a visitor-chosen value straight through. That last one cannot be enforced from here, only stated.

Locally the list ships empty, and that is the honest setting rather than a placeholder: nothing appends `X-Forwarded-For` in front of a local `next dev`, so trusting the header would let any browser or `curl` pick its own bucket. The cost is that every local sign-in shares one bucket, which for a single developer is invisible. Fill it in locally only to exercise the deployed behaviour, and expect a forgeable throttle while it is filled.

Every rejected attempt is logged at warning level with the identified client **and** the peer it arrived from, so a forwarded attribution is always visible next to the address the connection really came from. Two misconfigurations announce themselves the same way: a chain that arrives shorter than the configured depth, and a peer the server reports as something other than an address, both of which collapse visitors into the peer's single bucket.

### One file per environment

There is a single `.env.example` rather than one template per environment, because the variable names are identical in `local`, `preproduction`, and `production`. Only the values and their strictness differ, and `DJANGO_SETTINGS_MODULE` selects which settings module reads them:

| Variable                        | `local` and `test`                | `preproduction` and `production`              |
| ------------------------------- | --------------------------------- | --------------------------------------------- |
| `DJANGO_SECRET_KEY`             | Optional, safe fallback           | Mandatory, `ImproperlyConfigured` when absent |
| `DJANGO_ALLOWED_HOSTS`          | Optional, local default           | Mandatory, `ImproperlyConfigured` when absent |
| `DJANGO_TRUSTED_PROXY_NETWORKS` | Optional, empty by design         | Mandatory, `ImproperlyConfigured` when absent |
| `DJANGO_TRUSTED_PROXY_HOPS`     | Optional, `0` by default          | Mandatory, `ImproperlyConfigured` when absent |
| Every other variable            | Read in `config/settings/base.py` | Same name and meaning in all environments     |

The settings modules are the authoritative contract: they fail loudly on a missing value, whereas an extra template file can drift silently. Real preproduction and production secrets are injected by the deployment platform rather than read from a committed file.

### Running locally against another environment

One flag does it. Add the environment's file next to `.env.local` and point `--env-file` at it:

```bash
docker compose --env-file .env.preproduction up
```

Nothing else changes. There is a single mechanism, so the flag moves every service at once: the backend settings module, the PostgreSQL credentials, and the frontend API URL all come from the file you named. Every `.env.*` file other than the tracked `.env.example` is gitignored.

One caveat makes this rarely what you want. The non-local settings modules set `SECURE_SSL_REDIRECT = True`, so a plain HTTP request to a locally running preproduction container answers `301` to `https://localhost:<port>/...` and nothing is reachable without TLS termination in front. Verifying that the preproduction and production settings modules resolve correctly belongs in `tests/unit/test_environment_settings.py`, which asserts their real contract, rather than in a booted stack.

If you only want local development against remote data, do not change the settings module. Stay on `config.settings.local` and point `POSTGRES_*` and `REDIS_URL` at the remote services in your `.env.local`.

## Session lifecycle

A session is a row in `accounts.AuthSession` holding the SHA-256 digest of an opaque bearer token, never the token, and it authenticates for 14 days. `resolve_session` re-reads the row on every request, so revocation, expiry, and a deactivated account all take effect immediately.

Replacing the credential of an account ends the sessions issued under the previous one. The revocation hangs on the write rather than on a caller, so the admin, `changepassword` and a bare `set_password` followed by a save all reach it through one `post_save` receiver, and so does the admin's own "Password-based authentication: Disabled" submit, which destroys the credential instead of rotating it. `User.save` wraps the write in a transaction and the receiver runs inside it, so the new credential and the revocation commit together or not at all. The receiver distinguishes a new credential from a re-encoded one — Django clears the raw password before saving a hash it upgraded to the preferred hasher, so signing in against an outdated hasher does not sign anybody out — and it ignores a save that left the password column alone. Revocation only ever stamps a row that carries no instant yet, so the first revocation of a session is permanent.

Two paths write the password column without going through a model save, and both are outside any signal by construction: a queryset `update(password=...)` and a raw SQL update. They are asymmetric in a way that misleads, so it is worth stating: Django's own session-auth hash covers the admin session, which dies either way, while a bearer token does not, so a bulk credential rotation must call `revoke_sessions` on the affected accounts itself.

Nothing else deletes a row, so a Beat entry does. `accounts-purge-expired-sessions` runs `accounts.purge_expired_sessions` hourly at minute 15 and deletes every session whose expiry has passed. It is one conditional delete, which is what makes it idempotent and safe to run beside itself: a row another run already removed simply stops matching, and a test pins the statement count so the property cannot quietly become a row-by-row collection. The entry expires after 3000 seconds, so a run queued while the workers were down cannot fire once its slot has passed; the next hour does the same work anyway. `expires_at` carries an index for that query and for nothing else. Two loose ends land here rather than needing machinery of their own: a sign-out whose revocation call never reached the API still cleared the cookie, and a second sign-in orphans the row of the first.

A revoked session is kept until its own expiry rather than deleted with the rest. It costs nothing and it keeps a record of the revocation for as long as the token it invalidated could still have been presented.

The row is not the trail. An issuance is logged where sessions are issued, naming the session and the account but never the token, and the sign-in endpoint adds the client it came from and the peer it arrived from, mirroring the line a rejected attempt already writes; the layer that issues a session knows nothing about HTTP, which is why the attribution is a second record rather than a longer one. The admin revocation action logs the count, the accounts locked out and the operator who did it, by identifier rather than by address. Those records outlive the rows the purge deletes, which is what makes an incident reconstructable after 14 days.

## Fixture ingestion

Fixture scheduling is close to static: a day's fixture list changes when a match is postponed, not by the minute. So neither the browser nor the API talks to Sportmonks on a date change. `fixtures-synchronize` runs `fixtures.synchronize_fixtures` every six hours at minute 5, refreshing a rolling window from two days back to fourteen days ahead, and `GET /api/v1/fixtures` then serves entirely from PostgreSQL.

`integrations/sportmonks/` is the only code that knows the provider exists. It owns authentication, timeouts, bounded retries, pagination and error mapping, and it normalizes a window into `ProviderFixture` dataclasses. Nothing past it sees a Sportmonks field name, and the public schemas expose the internal primary key rather than the provider identifier.

The token travels in the `Authorization` header, although the provider also accepts it as a query parameter. `httpx` logs the full request URL at info level and every standard-library record reaches the Loguru sink, so a token in the query string would be written verbatim into the serialized logs of every deployed environment. The pagination cursor gets the same treatment from the other direction: the provider advertises the next page as an absolute URL, and because the credential is a header on the connection it would travel to whatever host that URL named. Only the cursor token is lifted out of it and re-merged onto the URL the client built itself, so a response body can contribute a scalar and never a destination.

Two provider calls make one window. The fixture payload carries a competition badge but no country flag, so the competitions are read once per window with their country included; the fixtures themselves come from `/fixtures/between` filtered to the five subscribed leagues. Those competitions are stored in full rather than only as the ones a fixture mentioned, so a league keeps being listed through its winter break. At `per_page=50` — the documented maximum, above which the provider silently falls back to 25 — a seventeen-day window is four requests, against a budget of 2000 per entity per hour.

The task is guarded by `cache.add`, which is one atomic Redis command that both tests and sets; a read followed by a write leaves a window in which two runs both believe they hold the lock. A run that finds the lock taken returns without writing, because the run holding it is fetching the same window. The lease carries a per-run token and is released only when that token is still the one stored, so a run that outlived its lease cannot free a successor's; the check is not itself atomic, and what makes an overlap harmless rather than merely unlikely is that the write is idempotent. The upsert is keyed on the provider identifier, so re-ingesting a window is a no-op and a postponed fixture moves its row instead of duplicating it, and it collapses a repeated identifier before the statement reaches PostgreSQL, since `ON CONFLICT DO UPDATE` refuses to touch the same row twice in one statement. Within the range it just read, the run also deletes the fixtures the provider no longer places there, which is what stops a match postponed past the window from being listed for months on a day it will not be played. That deletion is only sound because a truncated read raises instead of returning a prefix.

Beat populates an empty database within six hours. To fill it immediately:

```bash
docker compose --env-file .env.local exec worker uv run celery -A config call fixtures.synchronize_fixtures
```

Kick-off times are stored and rendered in UTC, and the view leaves them unlabelled: the zone is carried only by the machine-readable `dateTime` each row emits. The visitor's timezone is not knowable during a server render, and every alternative either flashes the wrong time after hydration or mismatches outright; resolving it properly needs a stored preference and a product decision. The visible marker the view once carried was dropped when the rows were narrowed, because it cost a column in every row to repeat a fact that never varies.

## Pre-match statistics

Every completed match contributes two rows to `match_statistic`, one per team, holding the twenty-two provider metrics the product renders. `statistics-synchronize` runs `statistics.synchronize_statistics` every six hours at minute 20, after the fixture run at minute 5 whose parents it depends on, over a trailing window of five days. That window is deliberately backwards-only and its own constant rather than the fixture pair: a statistic exists only for a match already played, and five days is a full matchweek plus the midweek round either side of it, so a run missed overnight still catches every result it would have written.

The result is not stored. Goals, and therefore the win, draw and loss shares, come from `Fixture.home_goals` and `Fixture.away_goals`, which are already synchronized and already guarded as a pair. The provider omits its own goals statistic when a side failed to score, so a table sourcing goals from the statistics would read every goalless performance as missing data rather than as nought. That omission is the general rule and not a defect: measured over the fifty fixtures of April 2026, thirty-five of the forty-six published types appear on every side of every match while `redcards` appears on 20 percent of sides and `penalties` on 18, because a count is left out at nought instead of being sent. The boundary therefore reads an absent optional count as nought and drops a record that lacks a type the provider always publishes.

Completion rates are stored as their two halves rather than as the percentages the provider also publishes, because the accuracy over six matches is the completed passes of those six over their attempts, and the mean of six per-match percentages is a different and wrong number. Possession is the one percentage stored as published: it is already normalized to a single match, and its two sides sum to a hundred, which is also why no opposing figure is published for it.

A run walks its range in chunks of thirty days and reads each chunk twice, once for the fixtures and once for their statistics. The chunk bound is not a preference: the client refuses a read it cannot finish in forty pages of fifty fixtures, so an unchunked backfill over two seasons would be truncated, and a truncated window is indistinguishable from a complete one. Five leagues produce on the order of two hundred fixtures a month, so a month-wide chunk stays an order of magnitude inside that ceiling.

The trailing window keeps the table current but establishes no depth, and every range the panel offers reads backwards inside one season. `days_back` is the same task's only argument, so an operator fills that depth with the same code path beat runs, under the same lease and the same idempotent upsert:

```bash
docker compose --env-file .env.local exec worker uv run celery -A config call statistics.synchronize_statistics --args='[400]'
```

Four hundred days reaches the start of the previous season, which is as far back as the subscription serves. Two seasons of depth is not there so that a window can span both: it is there so that opening a fixture played last season reads that season's earlier matches, which is what makes a backward-looking study possible at all. That is roughly 3,800 fixtures over about twenty-eight chunks, against a budget of 2000 calls per entity per hour, so the backfill fits inside a single hour. Re-running it is free: the upsert is keyed on the fixture and the team, and reconciliation is by stamp identity over exactly the fixtures the run resolved, so a match the provider stops publishing statistics for loses its rows while nothing else is touched.

`GET /api/v1/fixtures/{id}/form` folds those rows into all six range-and-scope combinations per team in one read, so the panel's filters are a re-render rather than a request. Three statements answer the whole payload however much history the two clubs have.

Every range is confined to the season of the fixture being read, and that is a product decision rather than an implementation detail. A window that reached into an earlier season would make one figure mean two different things, and last season's matches are not evidence about this one: a pre-match read is about form in the campaign being played. Last 3, Last 6 and Season are therefore prefixes of the same season-bound list, so they coincide while a season is younger than three matches, which is the ordinary state through August and September. Reading a fixture from an earlier season works the same way and is the reason the depth exists: the window starts at that fixture's kick-off, excludes the fixture itself, and reaches back only through its own season, so what the panel shows is what a reader would have known before the match was played.

The scope resolves per team: under Home / away the home side is measured on its home matches and the away side on its away matches, since any other reading would compare one team's home record against the other's whole record. Every sample states how many matches it found, so a short one is visible rather than implied.

## Quality gates

The same commands run locally and in GitHub Actions. Each backend job installs only the dependency groups it needs, and CI sets `UV_NO_SYNC=1` so that `uv run` uses the environment as synced instead of silently re-adding the aggregate `dev` group.

Backend, from `backend/`:

```bash
uv sync --frozen --no-default-groups --group lint
uv run ruff format --check .
uv run ruff check .
```

TOML formatting is checked from the repository root, because `.taplo.toml` governs every TOML file in the project and not only the backend ones:

```bash
uv run --project backend taplo fmt --check --diff
uv run --project backend taplo fmt
```

Taplo is the TOML formatting authority. It is the same engine the Even Better TOML editor extension uses, so formatting on save and the CI gate agree. Its 2-space indentation matches the `[*.{yml,yaml,toml}]` rule in `.editorconfig`, and `array_auto_collapse = false` keeps multi-line arrays such as `dependencies` and `dev` expanded.

```bash
uv sync --frozen --no-default-groups --group typecheck --group test
uv run pyright

uv sync --frozen --no-default-groups --group test
uv run pytest

uv sync --frozen --no-default-groups
uv run python manage.py makemigrations --check --dry-run
```

The type-check job also installs the `test` group because Pyright analyses `tests/` and needs to resolve pytest imports. For day-to-day local work, `uv sync --frozen --group dev` installs the aggregate development group instead.

Frontend, from `frontend/`:

```bash
bun install --frozen-lockfile
bun run format:check
bun run lint
bun run typecheck
bun run test
bun run build
bun run doctor
```

`backend/uv.lock` and `frontend/bun.lock` are committed, and every install in CI and Docker is frozen against them.

## Conventions

### Commit messages

Commit messages follow the project's [Conventional Commits cheatsheet](https://gist.github.com/qoomon/5dfcdf8eec66a051ecd85625518cfd13):

```text
<type>(<optional scope>): <description>
```

- Allowed types are `feat`, `fix`, `refactor`, `perf`, `style`, `test`, `docs`, `build`, `ops`, and `chore`.
- Descriptions use the imperative present tense, start with a lowercase letter, and have no trailing period.
- Add `!` before the colon for breaking changes and explain them in a `BREAKING CHANGE:` footer.

### Branch names

Branch names follow [Conventional Branch 1.1.0](https://conventionalbranch.org/):

```text
<type>/<description>
```

- Prefer purpose prefixes such as `feature/`, `fix/`, `hotfix/`, `release/`, and `chore/`.
- Descriptions are lowercase and use letters, digits, and hyphens; dots are reserved for release versions.
- Trunk branches `main`, `master`, and `develop` carry no prefix.

The `Repository conventions` workflow enforces both rules on every push and pull request.

### Language

English is mandatory for code, filenames, identifiers, tests, documentation, logs, commits, branches, issues, and pull requests.
