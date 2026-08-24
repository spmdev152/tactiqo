---
name: github-issue
description: Turn product or engineering work into focused GitHub issues with scope, acceptance criteria, and technical implications.
---
# GitHub Issue
Write engineering issues in English. Define problem/value, in-scope and out-of-scope work, acceptance criteria, architecture/data/API implications, tests, and dependencies. Respect the current fixtures/statistics/odds/predictions MVP and avoid introducing unrelated infrastructure. When proposing implementation branches, use a valid Conventional Branch purpose prefix and concise lowercase description.

Title an issue with a short, descriptive noun phrase naming the work: `Sign-in rate limiting`, not `feat(auth): rate-limit the sign-in endpoint`. Conventional Commits governs commit messages only, so an issue title carries no `type(scope):` prefix and never reuses a commit subject. Start with an uppercase letter, stay under roughly sixty characters, and leave the scope, the acceptance criteria and the technical implications to the body.
