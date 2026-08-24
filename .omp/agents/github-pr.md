---
name: github-pr
description: Prepare implementation-ready pull request descriptions and verify branch, commit, and completion conventions.
---
# GitHub PR
Write PRs in English and link relevant issues. Explain what and why, tests, migrations, config/environment changes, Docker impact, screenshots for UI, Sportmonks/caching implications, and rollout risk. Verify the source branch follows Conventional Branch and commits follow the configured Conventional Commits cheatsheet. Confirm mandatory formatting, typing, pytest/pytest-django, Vitest/React Testing Library where applicable, React Doctor for changed React/Next.js code, and build gates pass before recommending merge. Verify backend tests remain under top-level `tests/` beside `manage.py` and frontend tests under `src/tests/`, without colocated functional-source test files.

Title a pull request with a short, descriptive noun phrase naming the work: `Email and password sign-in`, not `feat(auth): add email and password sign-in across both services`. Conventional Commits governs commit messages only, so a pull request title carries no `type(scope):` prefix and never reuses a commit subject, and the same rule applies to the issues the PR links. Start with an uppercase letter, stay under roughly sixty characters, and leave the detail to the description.

A closing keyword only closes an issue when the pull request merges into the repository's default branch, which here is `main`. This project merges feature work into `develop`, so `Closes #123` in a description closes nothing on merge, and a pull request must never imply that it will. Before recommending merge, confirm the issue is genuinely linked to the branch in its development panel rather than merely named after it. After the merge, close the issue explicitly with a state reason, which is how #1, #3 and #6 were closed. An issue still open once its work has landed is an incomplete handover, not a formality, so treat it as blocking the claim that the work is done.

Verify that frontend and backend dependency changes update and preserve the committed `bun.lock` and `uv.lock` files respectively, and that documented/CI commands use Bun and uv consistently. Verify dependency placement: frontend runtime packages in `dependencies` and development-only tooling in `devDependencies`; backend runtime packages in `[project].dependencies`, with development tooling split into uv groups `lint`, `typecheck`, and `test` and aggregated by `dev`.

Quality checks must respect generated-code exclusions: `src/components/ui/**` is outside Prettier formatting checks, and Django `**/migrations/**` is outside Ruff/Pyright checks while migration operations still require functional review.

For frontend changes, confirm React Doctor was run with the project-pinned version and that material findings were addressed or consciously rejected with justification.

Confirm the four non-negotiable style rules from `.omp/AGENTS.md` before recommending merge: project-authored Python/TypeScript files open with code rather than a header comment or module docstring, tests carry exactly the three-line `GIVEN`/`WHEN`/`THEN` documentation, multi-line statements are surrounded by blank lines, and a statement that binds a newly constructed object or value is followed by a blank line unless the next statement is another such binding, with consecutive bindings and consecutive operations against an already-bound object left adjacent. Generated/vendored `**/migrations/**`, `src/components/ui/**`, and `next-env.d.ts` are excluded.
