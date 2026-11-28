# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A local data lakehouse that runs on minikube. MinIO provides object storage, Apache Iceberg is the table format, and Lakekeeper is the Iceberg REST catalog. Trino is the query engine, dbt handles transformations, and Dagster does orchestration. Phase 5 adds Cube and LangGraph chatbots. Work is delivered in phases, and each phase ends with a smoke-test gate.

## Commands

The Makefile is the single entry point. The hooks, CI and slash commands all call it, so add new checks there rather than in those places.

- `make lint`: all linters. Run by CI, the Stop hook and `/implement`.
- `make test`: unit and data tests. Run by the Stop hook and `/implement`.
- `make smoke-phaseN`: smoke suite for phase N's gate, run against the live cluster. Lives in `tests/smoke/`.

The per-file linters, which the PostToolUse hook runs after every edit: `yamllint -s <file>`, `ruff check <file>`, `sqlfluff lint <file>` (run from the file's directory, so it picks up the nearest `.sqlfluff`), and `helm lint charts/<chart>`.

To render a chart the way CI does: `helm template ci charts/<chart> [-f charts/<chart>/values-<env>.yaml]`.

## Layout and ownership

Each directory has exactly one owning agent, defined in `.claude/agents/`. Stay inside the owner's area. If a change crosses areas, hand it off.

| Path | Owner |
|---|---|
| `infra/minikube/`, `charts/` | platform-engineer: cluster, Helm, networking, storage, catalog |
| `pipelines/dagster/`, `pipelines/dbt/` | data-engineer: ingestion, assets, dbt models. Read-only kubectl only. |
| `tests/smoke/`, Makefile `lint`/`test` targets | test-engineer |
| `docs/adr/`, `docs/architecture.md` | orchestrator: plans, ADRs and issues; never code |
| PR reviews | reviewer: read-only; posts a `Verdict:` and a 5-line summary |

## Workflow

`/plan <goal>` → `/implement <issue>` → `/review <pr>` → `/gate <phase>`. Use `/status` for an overview.

- Every piece of work starts from a GitHub issue with acceptance criteria and two labels: `agent:<owner>` and `phase:N`. Without acceptance criteria, go back to `/plan`.
- Implementation happens in a worktree at `../lakehouse-wt/<n>-<kebab-title>`, on a branch with the same name. Commits reference `#<n>`. The PR body contains `Closes #<n>`, the acceptance-criteria checklist and the verify output.
- Architectural choices need an ADR (`docs/adr/NNNN-short-title.md`). If no ADR covers a decision, ask; don't decide on your own.
- Never push to `main`, and never merge PRs. The user decides.

## Guardrails (`.claude/settings.json`, `.claude/hooks/`)

- **PreToolUse on Bash** blocks `kubectl delete ns`, any `helm uninstall` not targeting `-n dev`, pushes to `main`, and `rm -rf` outside the repo or worktree. If it blocks something you really need, ask the user to run it. Don't try to work around the hook.
- **PostToolUse on Edit and Write** lints the edited file. Fix what it reports before moving on.
- **Stop and SubagentStop** run `make lint` and `make test`. You can't finish with failing checks, so fix them or explain why they can't pass.
- CI (`.github/workflows/ci.yml`) runs the `lint` and `helm-template` checks. `main` is meant to be protected with both as required checks.

## Conventions

- Pin every chart and image version. Never use `latest`. Helm is v4.x, pinned in CI; keep it in sync with the local version.
- Secrets belong in Kubernetes secrets or gitignored env files, never in git.
- Everything must be reproducible from a clean cluster through `make` targets.
- dbt models are layered as sources → staging → marts. Every model has a description and unique/not_null tests on its keys. Ingestion is idempotent per partition.
- Never weaken or delete a check just to make a gate pass.
