---
name: github-issue
description: Turn product or engineering work into focused GitHub issues with scope, acceptance criteria, and technical implications.
---
# GitHub Issue
Write engineering issues in English. Define problem/value, in-scope and out-of-scope work, acceptance criteria, architecture/data/API implications, tests, and dependencies. Respect the current fixtures/statistics/odds/predictions MVP and avoid introducing unrelated infrastructure. When proposing implementation branches, use a valid Conventional Branch purpose prefix and concise lowercase description.

Title an issue with a short, descriptive noun phrase naming the work: `Sign-in rate limiting`, not `feat(auth): rate-limit the sign-in endpoint`. Conventional Commits governs commit messages only, so an issue title carries no `type(scope):` prefix and never reuses a commit subject. Start with an uppercase letter, stay under roughly sixty characters, and leave the scope, the acceptance criteria and the technical implications to the body.

Link the implementation branch to the issue in GitHub's development panel; naming it after the issue is not the same thing. `feature/issue-6-session-expiry-warning` is a convention a reader has to trust, while a linked branch is a fact GitHub records, shows on the issue, and uses to offer the closing behaviour. Create it with `gh issue develop <number> --base develop --name <branch>`, from the issue's own development panel, or with the GraphQL `createLinkedBranch` mutation. The REST API has no equivalent, so a tool that only speaks REST cannot do it, and neither can a plain `git push`.

Verify the link exists rather than assuming the call created it, and when it genuinely cannot be created — no `gh`, no GraphQL access — say so plainly in the handover instead of leaving a reader to infer from the branch name that the issue is linked. Issue #6 shipped with a conventionally named but unlinked branch, so nothing closed when its pull request merged and the gap surfaced only after the fact.
