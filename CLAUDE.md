# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A local data lakehouse that runs on minikube (profile `dev`). An S3 object store ([SeaweedFS](docs/adr/0002-object-store.md)) holds the data, Apache Iceberg is the table format, and Lakekeeper is the Iceberg REST catalog, backed by Postgres (CNPG). Trino is the query engine, dbt handles transformations, and Dagster does orchestration. Work is delivered in phases, and each phase ends with a smoke-test gate (`docs/architecture.md`):

1. Platform: S3 object store, Postgres, Lakekeeper. 2. Trino. 3. Ingestion and dbt. 4. Dagster. 5. Cube, LangGraph chatbots, Langfuse. 6. Optional extras (Spark, Superset, monitoring).

## Commands

The Makefile is the single entry point. The hooks, CI and slash commands all call it, so add new checks there rather than in those places.

- `make lint`: all linters. Run by CI, the Stop hook and `/implement`.
- `make test`: unit and data tests. Run by the Stop hook and `/implement`.
- `make smoke-phaseN`: smoke suite for phase N's gate, run against the live cluster. Lives in `tests/smoke/`.

The per-file linters, which the PostToolUse hook runs after every edit: `yamllint -s <file>`, `ruff check <file>`, `sqlfluff lint <file>` (run from the file's directory, so it picks up the nearest `.sqlfluff`), and `helm lint charts/<chart>`.

To render a chart the way CI does: `helm template ci charts/<chart> [-f charts/<chart>/values-<env>.yaml]`.

## Layout and ownership

Each listed path has exactly one owning agent, defined in `.claude/agents/`. Unlisted paths are owned by Stefan. Stay inside the owner's area. If a change crosses areas, hand it off.

| Path | Owner |
|---|---|
| `infra/minikube/`, `charts/`, `mk/cluster.mk`, `mk/deploy.mk`, `scripts/` | platform-engineer: cluster, Helm, networking, storage, catalog, cluster lock |
| `pipelines/dagster/`, `pipelines/dbt/` | data-engineer: ingestion, assets, dbt models. Read-only kubectl only. |
| `tests/smoke/`, `Makefile`, `mk/lint.mk`, `mk/helm.mk`, `mk/smoke.mk`, `.github/workflows/ci.yml`, `.claude/hooks/`, `.claude/settings.json`, `pyproject.toml`, `uv.lock` | test-engineer |
| `docs/adr/`, `docs/architecture.md`, `CLAUDE.md`, `README.md`, `.claude/agents/` (except `orchestrator.md` and `reviewer.md`, which only Stefan changes) | orchestrator: plans, ADRs, issues and process docs; never code, no git writes |
| PR reviews | reviewer: read-only; posts a `Verdict:` and a 5-line summary |

Namespaces: one per layer, all prefixed `lh-` (`lh-storage`, `lh-catalog`, `lh-ops`, later `lh-compute`, `lh-orchestration`, `lh-ai`; [ADR-0006](docs/adr/0006-namespace-minikube-sizing-and-smoke-job.md)). Cross-namespace addresses always use the full DNS name `<svc>.<ns>.svc.cluster.local`. `dev` is only the minikube profile name, not a namespace.

## Workflow

`/plan <goal>` → `/implement <issue>` → `/review <pr>` → `/gate <phase>`. Use `/status` for an overview.

- Every piece of work starts from a GitHub issue with acceptance criteria and two labels: `agent:<owner>` (`platform-engineer`, `data-engineer`, `test-engineer` or `orchestrator`) and `phase:N`. Without acceptance criteria, go back to `/plan`.
- Implementation happens in a worktree at `../lakehouse-wt/<n>-<kebab-title>`, on a branch with the same name. Commits reference `#<n>`. The PR body contains `Closes #<n>`, the acceptance-criteria checklist and the verify output. For `agent:orchestrator` issues, the orchestrator edits and the main session commits, pushes and opens the PR.
- At most three agents work at the same time.
- Architectural choices need an ADR (`docs/adr/NNNN-short-title.md`). If no ADR covers a decision, ask; don't decide on your own.
- Any PR touching `.claude/` or `CLAUDE.md` gets the label `needs-human-read`, and the user reads it in full.
- Changes to `.claude/settings.json` or `.claude/hooks/` always ship alone, in their own small PR labelled `needs-human-read`. An agent never makes them in a PR that benefits from the change.
- Never push to `main`, and never merge PRs. The user decides.

## Guardrails (`.claude/settings.json`, `.claude/hooks/`)

- **PreToolUse on Bash** blocks `kubectl delete ns`, pushes to `main`, `rm -rf` outside the repo or worktree, and every `helm uninstall` not run with `-n dev`. The `-n dev` exception predates ADR-0006; there is no `dev` namespace, so in practice the hook blocks every `helm uninstall` today. If it blocks something you really need, ask the user to run it. Don't try to work around the hook.
- **Planned, not yet enforced (#13):** the hook will allow `helm uninstall` only in `lh-*` namespaces (`-n lh-[a-z]+`), and `minikube delete` only for profile `spike`. Nothing blocks `minikube delete` today, so don't run it for any other profile.
- **Secret-leak guards, planned, not yet enforced (#13, #15):** agents never read or print Secrets, `.env*` files or key files (`~/.config/sops/`, `~/.config/lakehouse/`). `make secrets` is the only decryption path; use `make secrets-verify` (digests only) to check them. The hook will be the primary guard, `permissions.deny` a backstop, and CI runs gitleaks (`make secrets-scan`). Follow the rule now, even though nothing enforces it yet. Residual risks: [ADR-0005](docs/adr/0005-secrets-catalog-auth-and-storage-credentials.md).
- **Cluster lock, planned, not yet enforced (#18):** `secrets`, `deploy`, `undeploy`, `bootstrap` and `smoke-phase*` take `scripts/cluster-lock.sh`, a host-wide lock shared by all worktrees.
- **PostToolUse on Edit and Write** lints the edited file. Fix what it reports before moving on.
- **Stop and SubagentStop** run `make lint` and `make test`. You can't finish with failing checks, so fix them or explain why they can't pass.
- CI (`.github/workflows/ci.yml`) runs the `lint` and `helm-template` checks. `main` is meant to be protected with both as required checks.

## Conventions

- Pin every chart and image version. Never use `latest`. Helm is v4.x, pinned in CI; keep it in sync with the local version.
- Secrets: one source, `.env.dev.sops` (SOPS + age encrypted, gitignored). etcd encrypts Secrets at rest. Each Secret is placed only in the namespaces that consume it. Pods get credentials through `secretKeyRef` (or a mounted Secret via `existingSecret`), never as literal values in values files, manifests or the Makefile.
- Everything must be reproducible from a clean cluster through `make` targets.
- dbt models are layered as sources → staging → marts. Every model has a description and unique/not_null tests on its keys. Ingestion is idempotent per partition.
- Never weaken or delete a check just to make a gate pass.
