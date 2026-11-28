# 0007. Conventional Commits and Conventional Branch for titles, commits and branches

Date: 2026-11-28

## Status

Accepted (issue #25). Enforcement in CI and issue forms follow in #26.

## Context

- Issue titles, PR titles, commit messages and branch names have no shared format. Titles so far range from `make secrets: ...` to `Hooks: ...` to `Process docs: ...`, and branches are named after the worktree directory.
- PRs are squash-merged, so the squash commit on `main` is the only commit that stays. Its message is set from the PR title. A consistent PR title gives a readable `main` history.
- Several agents create issues, branches and PRs in parallel. A format they can follow without judgement, and that a check can verify, avoids drift between agents.
- #26 adds CI checks for these names. Those checks need one machine-readable list of the allowed types and scopes.

## Decision

### Titles and commits

- Issue titles, PR titles and squash commits follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
- The PR title is the issue title. The squash commit message is the PR title (a repo setting, changed by the user).
- Format: `type(scope): summary`.
  - The summary is in the imperative mood ("add", not "adds" or "added").
  - It starts with a lowercase letter. Proper nouns and code identifiers keep their own case (for example `SeaweedFS`, `make smoke-phase1`).
  - It has no trailing period.
- Breaking changes put `!` after the type or scope (`feat(catalog)!: ...`), or add a `BREAKING CHANGE:` footer to the commit body.
- The allowed types and scopes are listed in [`docs/conventions.yaml`](../conventions.yaml). That file is the only place these lists live. This ADR and `CLAUDE.md` link to it, and the #26 checks read it. Adding a type or scope is a change to that file in its own PR, reviewed like any other.
- Commits on a branch, before the squash, follow the same format.

### Branches

- Branch names follow [Conventional Branch](https://conventionalbranch.org/), checked against spec version **1.1.0** on 2026-11-28.
- The spec lists these prefixes: `feature/` (or `feat/`), `bugfix/` (or `fix/`), `hotfix/`, `release/` and `chore/`, plus the AI-agent prefixes `ai/`, `claude/`, `codex/`, `copilot/` and `cursor/`. The spec's trunk branches are `main`, `master` and `develop`, and they take no prefix. This repo's only trunk is `main`.
- This repo accepts only three of them: **`feat/`, `fix/` and `chore/`**.
- The prefix comes from the issue title's type, through `branch_prefixes` in [`docs/conventions.yaml`](../conventions.yaml): `feat` becomes `feat/`, `fix` becomes `fix/`, and every type the spec has no prefix for becomes `chore/`.
- Format: `<prefix>/<issue>-<slug>`, for example `feat/7-seaweedfs-chart`. Lowercase letters, digits and hyphens only after the prefix. No consecutive, leading or trailing hyphens. The spec also allows dots (`.`) in the description, for example for version numbers. This repo deliberately forbids them, as a restriction on top of the spec.
- The worktree directory stays `../lakehouse-wt/<issue>-<slug>`, without the prefix. The branch and the worktree share the `<issue>-<slug>` part.

### Prefixes deliberately not used

- **`feature/` and `bugfix/`.** These are the long forms of `feat/` and `fix/`. Allowing both forms gives two names for the same thing. The short forms match the Conventional Commits types one to one.
- **`hotfix/`.** There are no releases or production deployments to patch. Every fix goes through a normal `fix/` branch and PR.
- **`release/`.** There is no release process. `main` is the only long-lived branch.
- **`ai/`, `claude/`, `codex/`, `copilot/`, `cursor/`.** These name the tool that made the branch, not the kind of change. In this repo agents make almost every branch, so such a prefix carries no information, and it would replace the type-based prefix that reviewers and checks rely on. Which agent did the work is already recorded in the issue's `agent:<owner>` label and in the commit trailers.

## Consequences

- `main` history reads as a list of typed changes, and the type of a merged change can be found from its commit alone.
- Agents pick the branch prefix mechanically from the issue title. There's no separate judgement call.
- Branch names carry only three types (`feat`, `fix`, `chore`). The full type is in the issue and PR title, not in the branch name.
- Existing closed issues, merged PRs and old commits keep their old titles. Only open issues and PRs are renamed (#25).
- Until #26 lands, the format is followed by convention only. Nothing rejects a non-conforming title or branch.
- The scope list is short and tied to the current layers and tooling. New areas (for example Phase 3 pipelines) need a new scope added to `docs/conventions.yaml` first.
- A future Conventional Branch release may change its prefix list. This ADR stays pinned to 1.1.0 until it is amended.

## Alternatives considered

- **No convention, free-form titles.** Rejected: titles already vary widely, and a check can't validate a free-form title.
- **Conventional Commits for titles, free-form branch names.** Rejected: the branch name is the first thing an agent creates, and a typed prefix makes the kind of change visible in `git branch` and in the PR list.
- **All Conventional Branch prefixes, including `feature/`, `bugfix/`, `hotfix/` and `release/`.** Rejected for the reasons above: duplicate names, and no release or hotfix process.
- **A branch prefix per commit type (`docs/`, `ci/`, `test/` and so on).** Rejected: these aren't Conventional Branch prefixes, so tools and readers that know the spec wouldn't recognise them.
- **AI-agent prefixes such as `claude/`.** Rejected: they describe who made the branch, which the labels and commit trailers already record, and they would drop the type.
- **Keeping the lists in `CLAUDE.md` or in this ADR.** Rejected: the #26 checks need a machine-readable file, and two copies of a list drift apart.
