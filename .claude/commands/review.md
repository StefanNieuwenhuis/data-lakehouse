---
description: Run the reviewer agent on a PR and post its verdict
argument-hint: <pr-number>
---

PR: #$ARGUMENTS

Use the **reviewer** agent to review PR #$ARGUMENTS:

1. Have it load the PR (`gh pr view`, `gh pr diff` and `gh pr checks`) and the issue the PR closes.
2. Have it check the PR against every acceptance criterion in that issue and against CLAUDE.md.
3. Have it post its review on the PR with `gh pr review $ARGUMENTS --comment`, using its standard format: a `Verdict:` line, a 5-line summary, then the details.

When it finishes, show me the verdict and the 5-line summary exactly as the reviewer wrote them, followed by the PR URL. Don't merge, approve or change anything. The decision is mine.
