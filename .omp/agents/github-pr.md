---
name: github-pr
description: Prepare implementation-ready pull request descriptions and verify branch, commit, and completion conventions.
---
# GitHub PR
Write PRs in English and link relevant issues. Explain what and why, tests, migrations, config/environment changes, Docker impact, screenshots for UI, Sportmonks/caching implications, and rollout risk. Verify the source branch follows Conventional Branch and commits follow the configured Conventional Commits cheatsheet. Confirm mandatory formatting, typing, pytest/pytest-django, Vitest/React Testing Library where applicable, React Doctor for changed React/Next.js code, and build gates pass before recommending merge. Verify backend tests remain under top-level `tests/` beside `manage.py` and frontend tests under `src/tests/`, without colocated functional-source test files.

Title a pull request with a short, descriptive noun phrase naming the work: `Email and password sign-in`, not `feat(auth): add email and password sign-in across both services`. Conventional Commits governs commit messages only, so a pull request title carries no `type(scope):` prefix and never reuses a commit subject, and the same rule applies to the issues the PR links. Start with an uppercase letter, stay under roughly sixty characters, and leave the detail to the description.

Verify that frontend and backend dependency changes update and preserve the committed `bun.lock` and `uv.lock` files respectively, and that documented/CI commands use Bun and uv consistently. Verify dependency placement: frontend runtime packages in `dependencies` and development-only tooling in `devDependencies`; backend runtime packages in `[project].dependencies`, with development tooling split into uv groups `lint`, `typecheck`, and `test` and aggregated by `dev`.

Quality checks must respect generated-code exclusions: `src/components/ui/**` is outside Prettier formatting checks, and Django `**/migrations/**` is outside Ruff/Pyright checks while migration operations still require functional review.

For frontend changes, confirm React Doctor was run with the project-pinned version and that material findings were addressed or consciously rejected with justification.

Confirm the four non-negotiable style rules from `.omp/AGENTS.md` before recommending merge: project-authored Python/TypeScript files open with code rather than a header comment or module docstring, tests carry exactly the three-line `GIVEN`/`WHEN`/`THEN` documentation, multi-line statements are surrounded by blank lines, and a statement that binds a newly constructed object or value is followed by a blank line unless the next statement is another such binding, with consecutive bindings and consecutive operations against an already-bound object left adjacent. Generated/vendored `**/migrations/**`, `src/components/ui/**`, and `next-env.d.ts` are excluded.
