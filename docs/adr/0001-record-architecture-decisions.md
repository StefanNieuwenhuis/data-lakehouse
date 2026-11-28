# 0001. Record architecture decisions

Date: 2026-11-28

## Status

Accepted

## Context

The lakehouse is built in phases by several agents (platform-engineer, data-engineer, test-engineer), coordinated by the orchestrator and reviewed by the user. CLAUDE.md requires that every architectural choice is covered by an ADR, and that an agent stops and asks if no ADR covers a decision. That only works if ADRs have a fixed place, format and lifecycle.

## Decision

- ADRs live in `docs/adr/` and are named `NNNN-short-title.md`, numbered sequentially from `0001`. Numbers are never reused.
- Each ADR has these sections: Status, Context, Decision, Consequences, Alternatives considered.
- Status is one of `Proposed`, `Accepted`, `Accepted (conditional)`, `Superseded by NNNN` or `Deprecated`. A conditional acceptance states the condition and the issue that resolves it.
- Accepted ADRs are not rewritten. A changed decision gets a new ADR that supersedes the old one, or an amendment section with a date, if the change is small and stays within the original decision.
- The orchestrator owns `docs/adr/` and `docs/architecture.md` and writes ADRs during `/plan`. Implementing agents cite the relevant ADR in their PRs and raise a question instead of deciding on their own when no ADR applies.
- `docs/architecture.md` describes the current target state and links to the ADRs behind it.

## Consequences

- Decisions and their reasons can be traced, which matters when agents without shared memory pick up work.
- Planning takes slightly longer, because significant choices are written down before implementation.
- Reviewers can reject a PR that makes an architectural choice not covered by an ADR.

## Alternatives considered

- **Decisions only in issues and PR descriptions.** Rejected: they are scattered, hard to find, and an issue closes when its work is done.
- **A single, constantly edited design document.** Rejected: it loses the history of why something changed. `docs/architecture.md` covers the current state, and ADRs cover the reasoning.
