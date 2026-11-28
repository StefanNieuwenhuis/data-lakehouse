---
description: Plan a goal with the orchestrator, update the architecture doc and ADRs, and create issues
argument-hint: <goal>
---

Goal: $ARGUMENTS

Use the **orchestrator** agent to plan this goal with me. This is the planning step, so take the time to get it right before any code is written.

1. **Interview.** Have the orchestrator read CLAUDE.md, `docs/architecture.md` and the existing ADRs in `docs/adr/`, and list the open issues (`gh issue list`). Then ask me the questions it needs answered: scope, constraints, which phase this belongs to, what "done" looks like, and anything that is ambiguous. Relay the questions to me and wait for my answers. Don't guess.
2. **Decide.** For each significant decision, the orchestrator writes or updates an ADR in `docs/adr/`. It also updates `docs/architecture.md` so it reflects the new target state.
3. **Propose issues.** Show me the proposed issues before creating any of them: title, owner agent, acceptance criteria, and out of scope. Wait for my approval or edits.
4. **Create.** After I approve, create the issues with `gh issue create`. Label each one with its owner (`agent:platform-engineer`, `agent:data-engineer` or `agent:test-engineer`) and its phase (`phase:N`), creating the labels if they don't exist.
5. **Report.** End with a short list of the created issue numbers, the order to work on them in, and any ADRs or docs that changed.

Don't write or edit any code during this command.
