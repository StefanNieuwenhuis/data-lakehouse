---
description: Implement an issue in its own worktree with the owning agent, verify it, and open a PR
argument-hint: <issue-number>
---

Issue: #$ARGUMENTS

1. **Load the issue.** Run `gh issue view $ARGUMENTS --json number,title,body,labels`. If it has no acceptance criteria, stop and tell me to run `/plan` first.
2. **Pick the implementer.** Use the `agent:*` label: platform-engineer, data-engineer or test-engineer. If the issue has no such label, or more than one, ask me which to use.
3. **Create a worktree and branch.** The issue title has the form `type(scope): summary` ([ADR-0007](../../docs/adr/0007-conventional-commits-and-branches.md)). Look up the title's type in the type → branch-prefix map in `docs/conventions.yaml` to get `<prefix>`. If the title doesn't follow the format, or its type isn't in the list file, stop and ask me to fix the title. Make the slug from the summary: `<n>-<short-kebab-summary>`, lowercase and hyphen-separated, for example `7-seaweedfs-wrapper-chart`. The branch is `<prefix>/<slug>`, for example `feat/7-seaweedfs-wrapper-chart`. Create the worktree with `git worktree add ../lakehouse-wt/<slug> -b <prefix>/<slug> main`, then do all the work inside it.
4. **Delegate.** Start the implementer agent and give it the full issue text and the worktree path. Tell it to work only inside that worktree, to meet every acceptance criterion, and to write every commit message in the format `type(scope): summary` with types and scopes from `docs/conventions.yaml`, referencing the issue (`#<n>`).
5. **Verify.** In the worktree, run `make lint` and `make test`, plus `make smoke-phaseN` when the issue has a `phase:N` label and the cluster is running. If anything fails, send the failure back to the same agent to fix. If it still fails after two attempts, stop and report to me.
6. **Open the PR.** Push the branch and run `gh pr create`. The PR title is the issue title, unchanged; it becomes the squash commit on `main`. In the body, include the line `Closes #<n>`, a checklist of the acceptance criteria and how each one was met, and the output of the verify commands.
7. **Report.** Give me the PR URL and suggest running `/review <pr>`.

Never merge the PR, and never push to `main`.
