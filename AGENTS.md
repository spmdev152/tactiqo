# Football Intelligence Platform

Project-wide agent instructions live in `.omp/AGENTS.md`, with sticky non-negotiable rules in `.omp/RULES.md`.

Core project decisions:
- Next.js App Router + React + TypeScript + shadcn/ui + Tailwind CSS, managed with Bun; keep runtime packages in `dependencies` and development-only tooling in `devDependencies`.
- Django + Django Ninja for the backend REST API, with uv for Python project and dependency management; keep runtime packages in `[project].dependencies` and split development tooling into `lint`, `typecheck`, and `test` uv groups, aggregated by `dev`.
- PostgreSQL, Redis, Celery, Docker, Docker Compose, and GitHub Actions.
- Commit `bun.lock` and `uv.lock`; local, Docker, and CI workflows must use those lockfiles reproducibly.
- Current MVP: fixtures, football statistics, bookmaker odds, and Sportmonks predictions for the five subscribed leagues.
- Python documentation follows numpydoc and TypeScript documentation follows TSDoc, and every doc block must be attached to a declaration. Every Python docstring starts on the line after the opening `"""`, so a one-line docstring occupies three lines; TSDoc already opens with a bare `/**`. File-header comments and module-level docstrings are prohibited: the first meaningful line of a project-authored file is an import or a declaration. A `#!` shebang on a genuinely executable script and TypeScript triple-slash directives are exempt, and no project file carries a shebang today, and generated/vendored `**/migrations/**`, `frontend/src/components/ui/**`, and `frontend/next-env.d.ts` are out of scope.
- Classes document non-method attributes in an `Attributes` section, enum members included with their serialized value; and every public method it defines in a `Methods` section as a full signature including the return type, which is stricter than numpydoc deliberately, since a growth threshold is not evaluable and a truncated signature is arbitrary; private methods and private or protected attributes are excluded, and the method that writes such an attribute documents it instead.
- Numpydoc sections must carry information: name the element type inside a container rather than the bare container, omit `Returns` and `Yields` whose value is `None`, and keep the `...` body in a `Protocol` method because Pyright requires it after a docstring-only body.
- Test documentation is exactly three lines, in order: a `GIVEN ...` line, a `WHEN ...` line, and a `THEN ...` line, all beginning on the line after the opening delimiter, with no summary, no blank line inside, and no numpydoc sections or TSDoc tags. Fixtures, factories, helpers, and stubs in the test tree keep ordinary concise documentation.
- Components, pages, and layouts declare a named props interface and document each prop on its own member; `@param` is not used for props, because TSDoc requires a parameter name and a destructured object has none. Props interfaces are exported only when another module consumes them.
- Blank-line separation is mandatory: any Python or TypeScript statement or expression spanning more than one line is separated by a blank line from the statement above and below it, except as the first or last statement of its block or where a blank line is impossible or the formatter removes it.
- A statement that binds a newly constructed object or value is followed by a blank line, unless the immediately following statement is another such binding; consecutive bindings stay valid when adjacent, and statements that only operate on an already-bound object, such as method calls, attribute mutations, and registrations, may also stay adjacent. This covers Python and TypeScript `const`, `let`, and `var` declarations including `new Foo()` and factory calls, and the formatter wins where it forces a different layout.
- Loguru is the single backend log sink, installed behind the standard library through `LOGGING_CONFIG` and an intercept handler; application code keeps using `logging.getLogger(__name__)` and never imports Loguru. Local logs are human-readable at `DEBUG`; `preproduction` and `production` emit serialized JSON with the level clamped so debug records can never leak.
- Ruff + Pyright govern project-authored Python quality, excluding Django `**/migrations/**`; pytest + pytest-django are the backend testing stack. Prettier governs project-authored frontend formatting, excluding shadcn/ui-generated `src/components/ui/**`; Vitest + React Testing Library are the frontend testing stack, and React Doctor is a development-only diagnostic run against changed React/Next.js code.
- Use pragmatic hexagonal/vertical-slice architecture and repositories only where they provide meaningful boundaries.
- Next.js native server-side data fetching is the default frontend data-access approach.
- Backend tests live in top-level `tests/` beside `manage.py`; frontend tests live in `src/tests/`. Tests are not colocated with functional source modules.
- Engineering artifacts and Git metadata are written in English.
- Commits follow the project's Conventional Commits cheatsheet.
- Branches follow Conventional Branch 1.1.0.

Read `.omp/AGENTS.md` and `.omp/RULES.md` before implementing or reviewing work.
