# Football Intelligence Platform — Agent Context

## Product scope
Build a focused football intelligence web MVP around Sportmonks data for five selected leagues.

Current product scope:
- Discover fixtures by competition and date;
- Open fixture detail pages;
- Inspect pre-match and historical match/team statistics relevant to a fixture;
- Inspect bookmaker odds available through the active Sportmonks subscription;
- Inspect Sportmonks predictions for supported markets and selections;
- Expose provider data through stable internal/product contracts.

Out of scope for the MVP:
- Live ingestion and live-delivery features;
- WebSockets;
- AI-generated insights;
- Custom ML prediction models;
- Mobile applications;
- Distributed microservices.

## Active Sportmonks subscription context
The MVP is being developed against the active Sportmonks Football Starter subscription captured on 23 August 2026.

Visible subscription characteristics:
- Football Starter plan;
- Five selected leagues;
- 2,000 API calls per entity per hour;
- Odds & Predictions add-on enabled;
- Monthly billing;
- Trial scheduled to end on 5 September 2026.

The five selected leagues and their Sportmonks league IDs are fixed for the MVP: Premier League (`8`), Bundesliga (`82`), Ligue 1 (`301`), Serie A (`384`), and La Liga (`564`). Treat these as the active subscription scope unless the project configuration is explicitly changed.

The Odds & Predictions add-on gives access to odds and prediction resources covered by the subscription. Prediction availability remains fixture-dependent: Sportmonks can mark fixtures as not predictable when there is insufficient model data. Product code must represent unavailable prediction states cleanly rather than fabricate values.

For the current MVP, prioritize pre-match statistics, pre-match odds, prediction probabilities, and related market/selection data. Live odds or live prediction capabilities are not part of the current product scope even if the provider subscription exposes them.

## Mandatory technology stack
### Frontend
- Next.js App Router
- React
- TypeScript
- Use shadcn/ui
- Tailwind CSS
- Bun as the required frontend runtime/tooling, package manager, dependency installer, lockfile manager, and script runner
- Keep frontend runtime packages in `dependencies` and development-only tooling/test/type packages in `devDependencies`
- Vitest as the frontend test runner
- React Testing Library for React component behavior tests
- React Doctor as a frontend development-quality diagnostic tool, installed in `devDependencies` and run against changed React/Next.js code before frontend work is considered complete
- Zustand only for justified cross-component client UI state

### Backend
- Python
- Django
- Django Ninja for the REST API
- Use uv as the required Python project and dependency manager for environments, dependency resolution, lockfiles, installation, and command execution
- Keep backend runtime packages in `[project].dependencies`; split development tooling into uv dependency groups named `lint`, `typecheck`, and `test`, with `dev` as the aggregate local-development group
- Use pytest + pytest-django as the backend testing stack
- Celery + Celery Beat for background and scheduled synchronization

### Data and infrastructure
- PostgreSQL as canonical operational and historical storage
- Redis for selective caching, locks, deduplication, and short-lived coordination
- Sportmonks as the external football-data provider
- Docker for application and service images
- Docker Compose as the local orchestration baseline
- GitHub Actions for CI/CD automation
- Commit `bun.lock` and `uv.lock`; Docker and CI must use reproducible/frozen dependency installation from those lockfiles where applicable
- Sentry and structured logging when observability is introduced


## Dependency classification
Production/runtime and development-only dependencies must be intentionally separated in both applications.

### Frontend dependency policy
Use `package.json` as follows:
- `dependencies`: packages required by the built/running Next.js application at runtime;
- `devDependencies`: formatters, linters, type tooling, test tooling, build-only developer tooling, and packages that are not required by the deployed application at runtime.

Typical development-only examples include Prettier, Prettier plugins, Vitest, React Testing Library tooling, React Doctor, and related test/type tooling when they are not runtime requirements. Do not place a package in `dependencies` merely because it is convenient during development, and do not move a true runtime package into `devDependencies` simply to reduce the production manifest.

Bun must preserve this distinction when adding packages. Use the appropriate Bun dependency mode and keep `bun.lock` synchronized with `package.json`.

### Backend dependency policy
Use `pyproject.toml` with uv as follows:
- `[project].dependencies`: packages required by the Django application and its production runtime;
- `lint`: linting/formatting tooling, currently Ruff;
- `typecheck`: static type-checking tooling, currently Pyright;
- `test`: testing tooling, currently pytest and pytest-django;
- `dev`: aggregate local-development group that includes `lint`, `typecheck`, and `test` via uv dependency-group inclusion.

Use the standard uv/PEP 735 group mechanism rather than optional extras for local engineering tooling. The intended shape is:

```toml
[dependency-groups]
lint = [
    "ruff",
]
typecheck = [
    "pyright",
]
test = [
    "pytest",
    "pytest-django",
]
dev = [
    { include-group = "lint" },
    { include-group = "typecheck" },
    { include-group = "test" },
]
```

Add future tools to the narrowest meaningful group. Introduce another named group only when a genuinely distinct concern appears (for example, `docs` if documentation tooling is later added). Do not create one group per package.

Local development may use the aggregate `dev` group. CI should install only the focused group or groups required by each job when practical. Production images/installations must install only runtime dependencies and omit development groups. Keep `pyproject.toml` and `uv.lock` synchronized.

Dependency placement is based on runtime necessity, not package category or habit. A package used by application code in production belongs to runtime dependencies even if it is also useful during development.

## Environments
The project must be structured for three environments:
- `local`: active environment during MVP development;
- `preproduction`: future staging/preproduction environment;
- `production`: future production environment.

Only `local` needs to be operational initially, but code, settings, Docker, environment variables, and deployment assumptions must not block later preproduction/production separation.

Prefer shared application code with environment-specific configuration rather than copied settings. Never commit real secrets.

### One environment template, not three
A single committed `.env.example` documents every required variable. Per-environment templates are deliberately rejected: the variable names are identical in `local`, `preproduction`, and `production`, `DJANGO_SETTINGS_MODULE` selects the environment, and only values and strictness differ. Outside `local` the settings modules upgrade `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` to `require_env_str`/`require_env_str_list`, so a missing value raises `ImproperlyConfigured`. The settings modules are therefore the authoritative contract: they fail loudly, whereas an extra template can drift silently and invites a real credential being pasted into a committed file. Real preproduction and production secrets are injected by the deployment platform.

Compose has exactly one selection mechanism, and it must stay that way. `compose.yml` declares per service which variables it receives, using `${NAME?hint}` interpolation, and no service uses `env_file:`. Because interpolation is the only source, `docker compose --env-file <file>` moves every service at once and there is no second mechanism to forget. The local file is `.env.local`, so every command carries `--env-file .env.local`.

Two details are deliberate. Declaring variables per service keeps least privilege explicit and reviewable: `api`, `worker`, and `beat` receive the 16 variables Django needs, the 15 the settings modules read plus `DJANGO_SETTINGS_MODULE` that selects them, `postgres` receives only its 3 credentials, `redis` none, and `web` only `BACKEND_API_BASE_URL` and `SESSION_COOKIE_INSECURE`, neither of which is a credential, so the frontend container never holds `SPORTMONKS_API_TOKEN` or `POSTGRES_PASSWORD`. And the `?` form without a colon rejects an absent variable while accepting a legitimately empty one, which matters because `SPORTMONKS_API_TOKEN=` is a documented empty default. Do not reintroduce `env_file:`, and do not switch to `:?`.

## Language policy
English is mandatory for the engineering codebase:
- Directories and filenames;
- Python and TypeScript identifiers;
- API and domain names;
- Classes, methods, functions, variables, enums, and constants;
- Source documentation and docstrings/doc comments;
- Tests and fixture names;
- Database, model, and migration naming;
- Docker and Compose services and scripts;
- CI workflow, job, and step names;
- Developer-facing technical documentation and logs;
- Commit messages, branch names, issues, pull requests, and release notes.

User-facing product copy may later be localized; this does not change the engineering-language rule.

## Editorial style
Markdown bullet items that are sentences or instructions must begin with an uppercase letter. If an official technology or package name begins with lowercase text, rephrase the bullet so the sentence starts with an uppercase word rather than changing the official name.

## Architecture: pragmatic hexagonal and vertical slices
Use design patterns deliberately but avoid overengineering.

Core principles:
1. Business/domain concepts must not depend on Sportmonks payloads or Django Ninja schemas.
2. Django Ninja is an inbound HTTP adapter; Sportmonks is an outbound provider adapter.
3. PostgreSQL/Django ORM persistence should be accessed through repositories or query modules when the boundary is non-trivial or reusable.
4. Do not create generic repository frameworks, factories, interfaces, or architecture layers that only forward one method and provide no real boundary.
5. Prefer domain and feature modules over technical dumping grounds.
6. Keep the modular Django monolith until a real scaling, deployment, security, or runtime requirement justifies a service split.
7. Never call Sportmonks directly from browser code.

### Suggested backend feature structure

```text
backend/
  manage.py
  apps/
    <domain>/
      api/
        router.py
        schemas.py
      application/
        services.py
        queries.py
      domain/
        entities.py
        enums.py
        exceptions.py
      infrastructure/
        repositories.py
      models.py
      tasks.py
  tests/
    unit/
    integration/
    api/
```

Backend tests live in the dedicated top-level `tests/` directory at the same project level as `manage.py`. Do not colocate test modules inside functional application packages. Organize the test tree by test level and/or mirrored business domain when useful.

This is a guide, not a requirement to create empty folders. Create only layers that contain meaningful behavior.

### Suggested frontend feature structure

```text
src/
  app/
  features/
    fixtures/
      api/
        client.ts
        repository.ts
      domain/
        fixture-window.ts
      server/
        get-fixtures.ts
      components/
      hooks/
      mappers/
      schemas/
      types/
    statistics/
    predictions/
    odds/
  components/
    ui/
  lib/
  tests/
    unit/
    components/
    integration/
```

Every module inside a feature belongs to one of those role directories; none sits loose at the feature root. `domain/` holds what the feature *is about* independently of any adapter: wire and URL contracts, closed vocabularies, product copy chosen from such a vocabulary, and the small functions that build or resolve them. It is the frontend counterpart of the backend `domain/` layer above, and it is also the only part of a feature that every runtime may import, which is what earns it a directory of its own. Every module in `server/` is either marked `import "server-only"` or is a `"use server"` action boundary, so `domain/` is the only part of a feature that an ordinary client import or `src/proxy.ts` — which runs outside the React Server environment — may reach. Do not "fix" the action boundary by marking it `server-only`: `features/auth/server/actions.ts` exists to be imported by `features/auth/components/login-form.tsx`, and marking it would break the build. `features/auth/domain/session-cookie-name.ts` and `features/auth/domain/session-loss.ts` are the standing examples: the proxy, a Server Component, a Server Action, and a client component all import them.

Do not add a `constants.ts` or a `utils.ts` to a feature. Both group by the kind of thing a value is instead of by the concept it serves, which has three costs paid here rather than hypothesised. One concept gets torn in two, since a search parameter name and the function that resolves it would land in different files. Product copy has no home, being a constant that is neither a contract nor a utility. And, worst, the runtime boundary above becomes a matter of luck: a single module that anything may import is safe only while nobody adds a `server-only` dependency to it, and a bucket named for a kind gives no reason to refuse one. A file is named after the concept it owns, so a reader knows from the name whether their change belongs there. `src/lib/utils.ts` stays as the one exception, because `components.json` aliases `utils` to it and shadcn/ui generates imports against that path.

Frontend tests live under the dedicated first-level `src/tests/` directory. Do not colocate `*.test.ts`, `*.test.tsx`, `*.spec.ts`, or `*.spec.tsx` files beside functional source modules. Mirror feature/domain names inside `src/tests/` when that improves discoverability.

After changing React or Next.js application code, run React Doctor against the changed scope and review relevant findings before considering the frontend task complete. Treat findings as engineering signals rather than commands: fix issues that materially improve correctness, performance, accessibility, security, or maintainability, and do not introduce unnecessary abstractions solely to satisfy a diagnostic. Use the project-pinned version from `bun.lock`; do not run an unpinned `@latest` version in CI.

Server-side data access and API calls must be colocated with the business feature/domain that owns them. Prefer Next.js Server Components and server-only data modules over client-side fetching abstractions.

## Python documentation: numpydoc
Python documentation follows the **numpydoc** convention defined at:
`https://numpydoc.readthedocs.io/en/latest/format.html`

Use numpydoc-formatted docstrings in English for public classes, functions, methods, and non-obvious internal callables. Module-level docstrings are prohibited: see "No file-header comments" below. Documentation attached to a declaration remains mandatory even when that declaration is the first thing in the file.

Use triple double quotes and the standard numpydoc section model where applicable, including:
- Short summary;
- Extended summary when useful;
- `Parameters`;
- `Returns`;
- `Yields`;
- `Raises`;
- `See Also`;
- `Notes`;
- `Examples`.

### Documenting classes
A class documents its non-method attributes in an `Attributes` section, below `Parameters` when both are present. This covers annotated fields, dataclass fields, `Protocol` members, and enum members. For an enum the serialized value is the part worth stating, because that string is the wire contract: `OK : str` described as "serialized as ``"ok"``" tells a reader something the member name does not.

A private or protected attribute stays out, symmetrically with the private methods excluded below, and for the same reason: the section documents what a caller may use, and numpydoc does not list private members at all. `User._password` and `User._password_removed` are the standing examples. Both are instance state the credential-revocation seam depends on, neither is part of the class's surface, and the place that explains them is the method that writes each one. Where a declaration exists only because a stub omits it, the workaround comment above it carries the reason.

Every method a class defines is documented in a `Methods` section, placed after `Attributes`, as a signature with a one-line description indented beneath it:

```
Methods
-------
load(module_name, **environment_variables) -> ModuleType
    Import a settings module against the given environment and nothing else.
emit(record) -> None
    Re-emit a standard-library record through Loguru.
```

The signature carries the method name, its parameters as bare names without `self` and with a default where one exists, and the return type in annotation syntax. Parameters are not annotated there: the method's own `Parameters` section owns their types, and repeating them would duplicate it with less detail.

Two deliberate deviations from the specification. It calls the section unnecessary and reserves it for a class with a wide method surface, and its examples stop before the return type. The project overrides both: "add it once the class grows" is a threshold nobody can evaluate, and truncating a signature before its return is arbitrary when the parameters are already written in Python syntax rather than prose. That is also why this does not conflict with the prose-type rule above, which governs the type field of a `Parameters` or `Returns` entry, not a signature line.

Private methods stay out of the section, which the specification forbids listing, and keep their own numpydoc docstring. A class that defines no method, such as an enum or a Django Ninja `Schema`, carries no section. A method a class overrides only to extend is documented like any other, since a reader of the subclass needs to know it behaves differently: `set_unusable_password() -> None` appears in `User`'s `Methods` section for exactly that reason.

Do not mechanically add sections that provide no information. Three consequences of that rule are worth stating, because each one was violated once and fixed:

- Write types in the prose form the specification uses, `list of str` and `int or tuple of int`, not the annotation form `list[str]`. The specification anchors this in `Parameters` and defines `Returns`, `Yields`, `Receives`, `Other Parameters`, and `Attributes` as formatted like it, so the notation applies wherever a type appears rather than only to return values. `Raises` and `Warns` name exception classes, where the question does not arise.
- Name the element type inside a container. `list of CapturedRecord` and `dict of str to Any` document the shape; `list of tuple` and a bare `dict` throw the information away. Prefer the module's own type alias so the docstring and the annotation cannot drift apart.
- Omit `Returns` and `Yields` when the value is `None`. A context manager yielding nothing, and any callable annotated `-> None`, has no value to describe, so the section would only restate the annotation. Explain what entering or calling it does in the summary instead.
- Keep the `...` body in a `Protocol` method, after its docstring. It looks like dead code and is not: removing it makes Pyright fail with `Function with declared return type "dict[str, object]" must return value on all code paths`, because a docstring-only body implicitly returns `None`. This applies to any protocol method whose return annotation is not `None`.

Every Python docstring starts on the line after the opening `"""`, with nothing sharing that line. This applies to every docstring in the backend, not only to tests: classes, functions, methods, and one-line docstrings alike. A one-line docstring therefore occupies three lines. This deliberately departs from the numpydoc habit of putting the summary on the opening line, and Ruff is configured to match: `D200` and `D202` are ignored project-wide so the mandated shape is what the linter enforces rather than what it fights. TSDoc already opens with a bare `/**`, so the frontend satisfies the same shape by construction.

Example:

```python
def get_fixture_statistics(fixture_id: int) -> FixtureStatistics:
    """
    Return normalized statistics for a fixture.

    Parameters
    ----------
    fixture_id : int
        Internal fixture identifier.

    Returns
    -------
    FixtureStatistics
        Normalized statistics consumed by the application layer.
    """

    statistics = repository.get_by_fixture_id(fixture_id)

    return statistics
```

### Python and TypeScript blank-line separation
Blank-line separation is a single policy with two mandatory halves: multi-line statements are isolated from their neighbors, and a statement that binds a newly constructed object or value is followed by a blank line. Both halves are mandatory rather than preferences, and both apply to Python and TypeScript at module level, in class bodies, and in function bodies.

#### Isolate multi-line statements
- Any statement or expression that spans more than one physical line must be separated by a blank line from the statement above it and the statement below it;
- This applies to Python and TypeScript, at module level, in class bodies, and in function bodies;
- Leave one blank line between the closing docstring and executable code;
- When a function or method performs executable work before returning, leave a blank line above the `return` statement;
- Do not compress unrelated operations into dense blocks merely because a formatter permits it; consecutive operations against the same already-bound object are related and may stay adjacent.

The only exemptions are:
- The multi-line statement is the first statement of its block, so nothing precedes it;
- The multi-line statement is the last statement of its block, so nothing follows it;
- A blank line is syntactically impossible, or the formatter removes it.

Violation:

```python
SPORTMONKS_API_TOKEN = env_str("SPORTMONKS_API_TOKEN", default="")
SPORTMONKS_BASE_URL = env_str(
    "SPORTMONKS_BASE_URL", default="https://api.sportmonks.com/v3/football"
)
SPORTMONKS_LEAGUE_IDS = env_int_list("SPORTMONKS_LEAGUE_IDS", default=[8, 82, 301, 384, 564])
```

Required form:

```python
SPORTMONKS_API_TOKEN = env_str("SPORTMONKS_API_TOKEN", default="")

SPORTMONKS_BASE_URL = env_str(
    "SPORTMONKS_BASE_URL", default="https://api.sportmonks.com/v3/football"
)

SPORTMONKS_LEAGUE_IDS = env_int_list("SPORTMONKS_LEAGUE_IDS", default=[8, 82, 301, 384, 564])
```

#### Blank line after an instance binding
A statement that binds a newly constructed object or value must be followed by a blank line, unless the immediately following statement is also such a binding. Statements that merely operate on an already-bound object — method calls, attribute mutations, registrations — may sit on consecutive lines with no blank line between them, because they are executions against an object that already exists.

Violation:

```python
app = Celery("tactiqo")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

Required form:

```python
app = Celery("tactiqo")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
```

Consecutive bindings are exempt and need no blank line between them, which is why runs of Django settings constants and other adjacent assignments stay valid:

```python
app = Celery("tactiqo")
scheduler = Scheduler()
```

Scope and interaction:
- Applies to Python and TypeScript, at module level, in class bodies, and in function bodies;
- In TypeScript the binding forms are `const`, `let`, and `var` declarations, including `new Foo()` and factory calls;
- Composes with the multi-line rule above: when the binding itself spans multiple physical lines, that rule already demands blank lines on both sides and this one adds nothing;
- Where the formatter forces a different layout, the formatter wins and the case is exempt.

### Inline documentation
Routine inline explanatory comments are not part of the project style. Prefer:
- Clearer naming;
- Extraction into a function, method, or class;
- A focused numpydoc docstring at the new abstraction boundary.

A comment is acceptable only for an external constraint, algorithmic invariant, compatibility workaround, or non-obvious reason that cannot be made clear through structure and naming. Comments must be English.

### No file-header comments
Project-authored Python and TypeScript files must not begin with a comment or docstring that is not attached to a declaration. Module-level docstrings and file-banner comments, single-line or multi-line, are prohibited at the top of a file. The first meaningful line of a file is code: an import or a declaration.

Clarifications:
- Documentation attached to a declaration stays mandatory where the numpydoc/TSDoc rules require it, including when that declaration is the first thing in the file. A `/** ... */` block immediately followed by `export type Foo` documents `Foo`; it is not a file header and must be kept;
- Functional interpreter/compiler directives are not prose comments and are exempt: a `#!` shebang on a genuinely executable script, and TypeScript triple-slash directives such as `/// <reference types="next" />`. No project file currently carries a shebang: `backend/manage.py` is always invoked as `uv run python manage.py`, so its shebang was removed and its executable bit cleared rather than keeping a header comment nothing relied on;
- Generated/vendored files are out of scope: `**/migrations/**`, `frontend/src/components/ui/**`, and `frontend/next-env.d.ts`;
- Empty `__init__.py` package markers are fine; a package docstring is not.

## Python formatting, linting, imports, and typing
- Ruff is the formatter and linter for project-authored Python code; exclude Django-generated `**/migrations/**`.
- Ruff owns import sorting using its isort-compatible rules; do not add standalone isort.
- Pyright is the static type checker for project-authored Python code; exclude Django-generated `**/migrations/**`.
- Do not add Black as a second formatter unless the project explicitly changes this standard.
- Formatting, linting, and type checks must run identically locally and in GitHub Actions.
- Avoid blanket ignores or `# type: ignore` without a narrow justification.
- When a suppression follows from a file's role rather than from one specific line, express it in Ruff `per-file-ignores` instead of an inline `# noqa`. The layered settings modules are the canonical case: `from config.settings.base import *` is the intended way to inherit shared configuration, so `F403` and `F405` are ignored for `config/settings/{local,preproduction,production,test}.py` in `pyproject.toml` and those files carry no inline suppression. Keep the pattern as narrow as the role it describes, never a directory-wide catch-all.
- Prefer removing the cause over suppressing the finding. Project-authored Python carries zero inline suppressions: every settings module, `config/settings/test.py` included, reads `SECRET_KEY` from `DJANGO_SECRET_KEY` and falls back to `django.core.management.utils.get_random_secret_key()`, so no hardcoded credential exists to silence. Reach for `per-file-ignores` only when the finding is a false positive for that file's role, never to hide a real smell.
- Never source a secret from a literal in project-authored code. Read it from the environment. Generate local values with `openssl rand -base64 48` into your own gitignored `.env.local`, and keep `.env.example` on documented placeholders.

### Deliberately unused parameters
Ruff's `ARG` rules are enabled, so an unused parameter is a CI failure rather than an editor preference that differs per developer. Mark one with an underscore prefix that keeps its meaning: `*_args`, `**_kwargs`, `_payload`. Never use a bare `_`, because two unused parameters in one signature are a duplicate-argument `SyntaxError` and a bare name throws away the documentation the signature carried.

Two situations forbid the rename outright, and both are proven here rather than theoretical:
- A parameter a caller passes by keyword. `SettingsModuleLoader._intercept_dotenv_load` replaces `load_dotenv`, which `config/settings/base.py` calls as `load_dotenv(dotenv_path=path, override=False)`, so renaming `override` raises `TypeError`.
- A parameter a framework introspects. A Django Ninja handler's `request` cannot be prefixed: Ninja builds a Pydantic model from the handler signature and Pydantic raises `NameError: Fields must not use names with leading underscores`.

Resolve those two cases in this order. First, consume the parameter where doing so buys real coverage: recording `override` turned a dead argument into a test that pins the invariant that a dotenv never overrides configuration already injected into the process. The Django Ninja handler took the same route: `read_health` logs the probing client at debug level, so its `request` is genuinely used and no `ARG001` exemption exists in `pyproject.toml`. Only when a parameter truly cannot be used, exempt the file's role in `per-file-ignores`. Never reach for an inline `# noqa`.

### Logging: Loguru behind the standard library
Loguru is the single sink for every backend process, but application code never imports it. Modules keep calling `logging.getLogger(__name__)`, and `config/logging.py` installs an `InterceptHandler` that forwards standard-library records to Loguru. Django is wired through `LOGGING_CONFIG = "config.logging.configure"`, which Django calls exactly once per process with the `LOGGING` dictionary.

That indirection is the point. Django, Celery, kombu, and every third-party package emit through the standard library, so intercepting is the only way to get one format for the whole stack, and the sink stays replaceable without touching a single call site. `config/celery.py` connects an empty receiver to Celery's `setup_logging` signal, because Celery otherwise installs its own configuration and the worker and beat containers would print a different format from the API.

`config.logging.build_logging` builds the per-environment dictionary, so no settings module mutates an imported one:
- `local`: human-readable, colourized, `DEBUG`, `diagnose` enabled;
- `preproduction` and `production`: serialized JSON, `diagnose` disabled, level clamped by `deployed_log_level` so an environment exporting `DJANGO_LOG_LEVEL=DEBUG` still cannot emit debug records.

Both deployed choices are security decisions rather than preferences. `diagnose` prints the variable values surrounding a traceback, and debug records can carry request payloads, so neither may reach a deployed environment. The clamp is enforced in code and covered by tests instead of trusting configuration.

### Ignore and environment files
`.gitignore`, `.dockerignore`, and `.prettierignore` are organized as comment-titled groups of related patterns, with the patterns inside each group sorted lexicographically. Group order carries meaning and is deliberately not alphabetized, so the environment block stays first and the editor noise stays last.

The same grouping applies to `.env.example` and every local `.env.*` file: a short comment titles each group and the variables inside it are sorted lexicographically. Dotenv ordering carries no meaning, since the files hold no variable expansion and no duplicate keys, so the sort is free. Verify a reorganization by comparing the parsed key-value pairs and by running `docker compose --env-file <file> config`, never by reading the diff.

Order is semantic in these files, so a reordering is a behavioural change until proven otherwise. A negation must stay after the pattern it re-includes: `!` sorts before `.`, so sorting `!.env.example` above `.env.*` would silently make the only tracked environment file ignored again. Exclusion-only lists are order-independent, which is why the `.dockerignore` files could be freely permuted. Prove a reordering with `git check-ignore` and `prettier --file-info`, never by reading the diff.

### TOML formatting: Taplo
Taplo is the formatting authority for every TOML file in the repository. It is pinned in the backend `lint` dependency group so `uv.lock` reproduces it, and configured by the root `.taplo.toml`. Because the config is repo-wide rather than backend-only, run it from the repository root:

```bash
uv run --project backend taplo fmt --check --diff
uv run --project backend taplo fmt
```

Taplo is the engine behind the Even Better TOML editor extension, so an editor formatting on save and the CI gate must produce identical output. Two configuration choices are deliberate: the indentation matches the `[*.{yml,yaml,toml}]` rule in `.editorconfig`, and `array_auto_collapse = false` keeps multi-line arrays such as `dependencies` and `dev` expanded instead of folding them onto one line. Do not add a second TOML formatter, and do not let the editor and `.taplo.toml` disagree.

## Django and Django Ninja conventions
- One versioned `NinjaAPI`, for example `/api/v1/`.
- Domain-specific `Router`s such as fixtures, statistics, predictions, odds, and competitions.
- Explicit request and response schemas.
- Thin router operations: validation -> application service/query -> response/error mapping.
- Never expose Django ORM models or Sportmonks response objects directly as the public API contract.
- Repositories own meaningful persistence behavior; query modules may own optimized read models where appropriate.
- Application services orchestrate domain operations, repositories, and provider adapters.
- Database constraints enforce invariants where practical.
- Prevent N+1 queries with intentional ORM loading and indexing.
- Celery jobs must be idempotent or safely retryable.
- OpenAPI is a maintained contract artifact and may support generated frontend types later.
- Django migrations are generated artifacts. Keep them committed and review their operations, dependencies, reversibility, and schema impact, but do not reformat/lint/type-check `**/migrations/**` as project-authored source.

## TypeScript documentation: TSDoc
TypeScript documentation follows the **TSDoc** standard defined at:
`https://tsdoc.org/`

Use TSDoc doc comments in English for exported/public APIs and non-obvious reusable abstractions where documentation provides meaningful value.

Use standard TSDoc constructs where applicable, including:
- Summary text;
- `@remarks`;
- `@param`;
- `@returns`;
- `@throws`;
- `@example`;
- `@see` and `{@link ...}`.

Do not add documentation that merely repeats names or TypeScript types.

### Documenting component props
A component, page, or layout that takes props declares a **named props interface** and documents each prop on its own member:

```typescript
/**
 * Props of {@link PlatformHealthCard}.
 */
export interface PlatformHealthCardProps {
  /** Normalized platform health, including the unreported state. */
  readonly health: PlatformHealth;
}
```

Never use an anonymous inline type such as `Readonly<{ children: React.ReactNode }>`: its members cannot carry a doc comment, so the props become undocumentable by construction.

Do not reach for `@param` to document props. The TSDoc specification defines `@param` as "followed by a parameter name, followed by a hyphen, followed by a description", and a destructured props object has no parameter name to reference. Dot syntax such as `@param props.health` is [RFC #19](https://github.com/microsoft/tsdoc/issues/19), an open proposal rather than part of the standard. The member comment is also the one an editor surfaces at the call site, on the JSX attribute, which is where a reader actually needs it.

Export the props interface only when another module consumes it. A reusable component exports its props; a route-level page or layout keeps them local, because nothing outside the route can pass them.
 Prefer self-explanatory code and extraction over routine inline comments. Never open a file with a banner comment: a TSDoc block is valid only when it documents the declaration that immediately follows it, and triple-slash directives such as `/// <reference types="next" />` are functional rather than prose.

Example:

```typescript
/**
 * Returns normalized predictions for a fixture.
 *
 * @param fixtureId - Internal fixture identifier.
 * @returns Normalized prediction markets available for the fixture.
 */
export async function getFixturePredictions(
  fixtureId: number,
): Promise<FixturePredictions> {
  const response = await apiClient.get(`/fixtures/${fixtureId}/predictions`);

  return mapFixturePredictions(response);
}
```

## Frontend conventions
- Prefer Server Components; use `use client` only when browser state or interactivity requires it.
- Use shadcn/ui provides editable primitives; product components live above those primitives.
- Tailwind CSS is the styling system unless a future architectural decision explicitly changes it.
- Prefer Next.js App Router, Server Components, native `fetch`, caching, and revalidation for remote data access.
- Client-side fetching libraries are not part of the baseline stack; add one only after a concrete requirement and explicit project decision.
- Zustand is reserved for justified cross-component client UI state and must not become a server-data cache.
- Components consume normalized product contracts, never raw Sportmonks payloads or provider `type_id` values.
- Accessibility, responsive design, and loading/error/empty/stale/unavailable states are definition-of-done items.

## Testing conventions
### Test documentation: GIVEN / WHEN / THEN
Every backend and frontend test is documented with exactly three lines, in this order and nothing else: a `GIVEN ...` line, a `WHEN ...` line, and a `THEN ...` line. No summary line, no blank line inside the block, no numpydoc sections, no TSDoc tags, no extra prose.

The three lines always begin on the line after the opening delimiter. A test is not a normal callable with a leading summary to state, so nothing shares the line with `"""`. This keeps the Python and TypeScript forms visually identical, since a TSDoc block already opens with a bare `/**`.

Python shape, with the mandatory blank line between the docstring and executable code:

```python
def test_health_reports_ok_when_every_dependency_is_reachable(api_get: ApiGet) -> None:
    """
    GIVEN a reachable database and cache
    WHEN the health endpoint is requested
    THEN every dependency is reported as ok
    """

    response = api_get(HEALTH_URL)
```

TypeScript shape, as a TSDoc block directly above the test:

```typescript
/**
 * GIVEN a successful health payload
 * WHEN it is normalized for the product
 * THEN the platform reports operational dependencies
 */
it("normalizes a successful health payload", () => {
```

This three-line form applies to test cases. Non-test callables that live in the test tree, such as fixtures, factories, helpers, and stubs, keep ordinary concise numpydoc/TSDoc documentation and remain subject to the file-header rule.

### Backend testing
- Use `pytest` as the Python test runner and `pytest-django` for Django integration.
- Keep all backend tests in the top-level `tests/` directory at the same project level as `manage.py`.
- Do not place test packages inside functional Django apps.
- Organize tests into meaningful groups such as `unit/`, `integration/`, and `api/`, and mirror business domains underneath those groups when useful.
- Tests must be deterministic and must not require live Sportmonks calls.
- Prefer factories/fixtures that express product-domain data rather than raw provider payloads except when explicitly testing the Sportmonks adapter.
- Document every test with the mandatory three-line `GIVEN`/`WHEN`/`THEN` docstring and nothing else; fixtures, factories, and helpers in `tests/` keep ordinary numpydoc.

### Frontend testing
- Use `Vitest` as the frontend test runner.
- Use React Testing Library for React component behavior tests.
- Keep frontend tests in the dedicated `src/tests/` directory.
- Do not colocate test/spec files beside functional source files.
- Organize tests into meaningful groups such as `unit/`, `components/`, and `integration/`, mirroring feature/domain names when useful.
- Prefer behavior-focused assertions over implementation-detail assertions.
- Document every test with the mandatory three-line `GIVEN`/`WHEN`/`THEN` TSDoc block and nothing else; helpers, factories, and stubs in `src/tests/` keep ordinary TSDoc.

### Frontend formatting
Prettier is the formatting authority for project-authored frontend code. Exclude `src/components/ui/**`, which contains shadcn/ui-generated primitives, from Prettier formatting/checks. Treat those primitives as generated/vendor-like source unless the project intentionally takes ownership of a component.

Required plugin intent:
- `prettier-plugin-tailwindcss`: canonical Tailwind class ordering;
- `@trivago/prettier-plugin-sort-imports`: deterministic import ordering unless the project explicitly approves a replacement.

Keep plugin configuration centralized and ensure local and CI behavior is identical.

## Data strategy
Persist canonical relational and historical data in PostgreSQL, including competitions, seasons, teams, fixtures, normalized statistics needed by product queries, useful odds snapshots where product requirements justify history, and prediction snapshots/market-selection values.

Use Redis selectively for endpoint/query/provider-response cache, distributed locks, request deduplication, and stampede prevention.

Do not introduce an analytics database until PostgreSQL is measurably insufficient.

## Sportmonks integration
Centralize authentication, HTTP client behavior, retries/backoff, timeouts, pagination, error mapping, metrics, caching, and normalization under an integration boundary such as `integrations/sportmonks/`.

Prefer enriched and batched requests and cached reference data. Track freshness and provider timestamps. The UI and public API must not understand Sportmonks-specific field semantics.

For predictions:
- Support only markets actually returned by the active subscription and fixture;
- Honor provider predictability/availability metadata;
- Model unavailable or insufficient-data states explicitly;
- Preserve snapshots when historical prediction evolution provides product value.

For odds:
- Normalize bookmaker, market, selection, price, probability where supplied, timestamps, and provider identifiers behind internal contracts;
- Do not assume every market or bookmaker exists for every fixture;
- Avoid persisting every odds movement until there is a concrete product requirement for that history.

## Docker and Docker Compose
Every runnable application process must have a clear container strategy.

Expected local orchestration, when each component exists:

```text
web       # Next.js
api       # Django + Django Ninja
worker    # Celery
beat      # Celery Beat
postgres
redis
```

Prefer a root `compose.yml` coordinating per-service Dockerfiles. Use health checks and dependency readiness where needed. Keep images environment-agnostic and inject environment-specific configuration at runtime.

## Git commit convention
Commit messages follow the Conventional Commits cheatsheet specified by the project:
`https://gist.github.com/qoomon/5dfcdf8eec66a051ecd85625518cfd13`

General format:

```text
<type>(<optional scope>): <description>

<optional body>

<optional footer>
```

Allowed commit types:
- `feat`;
- `fix`;
- `refactor`;
- `perf`;
- `style`;
- `test`;
- `docs`;
- `build`;
- `ops`;
- `chore`.

Rules:
- Use imperative present tense;
- Start the description with lowercase;
- Do not end the description with a period;
- Scope is optional and should be a meaningful project/domain scope, not an issue identifier;
- Use `!` before `:` for breaking changes when appropriate;
- Explain breaking changes in the footer using `BREAKING CHANGE:` when additional detail is needed;
- Use issue references in the footer when useful, for example `Closes #123`;
- The initial commit uses `chore: init`.

Examples:

```text
feat(predictions): add fixture probability endpoint
fix(sportmonks): handle unavailable prediction payloads
refactor(fixtures): extract repository query boundary
ops(ci): add pyright quality gate
```

### Issue and pull request titles
Conventional Commits governs commit messages only. An issue or pull request title is a short, descriptive noun phrase naming the work, with no `type(scope):` prefix and no imperative verb copied from a commit. Reusing a commit subject is the mistake to avoid: a reader scanning a list of issues wants the subject, not the change type, and the type is already carried by every commit in the branch and by the labels.

| Instead of | Write |
| --- | --- |
| `feat(auth): add email and password sign-in across both services` | `Email and password sign-in` |
| `feat(auth): rate-limit the sign-in endpoint` | `Sign-in rate limiting` |
| `ops(ci): gate compose validity, test documentation and test placement` | `CI gates for compose, test docs and test placement` |

Start with an uppercase letter, keep it under roughly sixty characters, and put the detail in the body where it belongs. The body still carries the scope, the acceptance criteria and the technical implications.

## Git branch convention
Branch names follow Conventional Branch 1.1.0:
`https://conventionalbranch.org/`

General format:

```text
<type>/<description>
```

Preferred purpose prefixes:
- `feature/` or `feat/`;
- `bugfix/` or `fix/`;
- `hotfix/`;
- `release/`;
- `chore/`.

Conventional Branch also defines AI-agent source prefixes such as `ai/`, `claude/`, `codex/`, `cursor/`, and `copilot/`. Use them only when the workflow intentionally identifies the branch by generating agent rather than by work purpose. For normal project work, prefer purpose prefixes.

Branch descriptions:
- Lowercase only;
- Use letters, digits, and hyphens; dots are allowed for release versions;
- No spaces or underscores;
- No leading, trailing, or consecutive hyphens/dots;
- Concise and descriptive;
- Include an issue/ticket identifier when useful, for example `feature/issue-123-add-predictions`.

Trunk branches such as `main`, `master`, and `develop` do not use a prefix.

Link an implementation branch to its issue in GitHub's development panel, not only by naming it after the issue. The name is a convention a reader has to trust; the link is a fact GitHub records on the issue. Create it with `gh issue develop`, from the issue's development panel, or with the GraphQL `createLinkedBranch` mutation, since the REST API has no equivalent, and verify it rather than assuming the call worked. Where it cannot be created, say so in the handover instead of letting the branch name imply it.

A closing keyword closes an issue only when its pull request merges into the default branch, `main`. Feature work merges into `develop`, so `Closes #123` closes nothing on merge and must not be presented as if it did: close the issue explicitly with a state reason once the work lands. An issue left open after its work has merged is an incomplete handover.

## CI expectations
GitHub Actions will enforce project quality gates.

Backend baseline:
- Ruff format check for project-authored code, excluding `**/migrations/**`;
- Ruff lint with import-order/isort-compatible rules for project-authored code, excluding `**/migrations/**`;
- Pyright excluding `**/migrations/**`;
- Use pytest/pytest-django;
- Migration consistency checks.

Frontend baseline:
- Prettier check for project-authored code, excluding `src/components/ui/**`;
- TypeScript type checking;
- Vitest;
- React Testing Library component tests where applicable;
- Next.js build.

Repository workflow baseline:
- Validate commit message convention;
- Validate branch naming convention;
- Never depend on live Sportmonks calls in CI.

Never merge with failing mandatory CI. Never commit `.env.local` or any other `.env.*` file, tokens, credentials, production data, or private keys. Only `.env.example` is tracked.
