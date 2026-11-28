---
description: One-screen overview of open issues, open PRs and their review verdicts
---

Give me a one-screen overview of where the project stands. This command is read-only.

1. Open issues: `gh issue list --state open --json number,title,labels,assignees`
2. Open PRs: `gh pr list --state open --json number,title,headRefName,isDraft,statusCheckRollup,closingIssuesReferences`
3. For each open PR, get the latest reviewer verdict: run `gh pr view <n> --json reviews,comments` and take the most recent `Verdict:` line. If there isn't one, show "not reviewed".

Present it like this:

```
ISSUES (open)
#  phase  owner              title                       PR
12 1      platform-engineer  Object store chart          #15
...

PRS (open)
#  issue  checks  verdict           title
15 #12    pass    REQUEST CHANGES   Add object store chart
...

NEXT
- <1-3 suggested next actions, e.g. "/review 16", "/implement 13", "/gate 1">
```

Keep it on one screen: no extra prose, and truncate long titles.
