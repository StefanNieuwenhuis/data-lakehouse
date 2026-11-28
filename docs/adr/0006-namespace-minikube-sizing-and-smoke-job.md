# 0006. Single namespace, minikube sizing, cluster lock and in-cluster smoke Job

Date: 2026-11-28

## Status

Accepted

## Context

- The PreToolUse hook (`.claude/hooks/block_destructive.py`) only allows `helm uninstall` in namespace `dev`. A namespace per component would make routine teardown impossible for agents. The hook has no rule for `minikube delete` yet.
- The host is Apple Silicon (arm64) with 14 CPUs and 48 GiB of memory. Docker Desktop has 28 GB. Local tools: minikube v1.39.0, kubectl v1.36.0, Helm v4.3.1 (matches CI), Docker 29.7.2 (arm64).
- minikube's memory can't be raised without deleting the cluster. Trino (Phase 2), Dagster (Phase 4) and Cube plus chatbots (Phase 5) are memory-hungry, so the cluster must be sized for later phases now.
- Several agents work in parallel worktrees against one shared cluster. Concurrent `helm upgrade`, secret applies or smoke runs would interfere with each other.
- The Phase 1 gate runs a PyIceberg script. S3 endpoints and catalog URLs returned by Lakekeeper are in-cluster service names, which a client on the host can't resolve without extra tricks.

## Decision

### Namespace and environments

- All Phase 1 workloads (object store, CNPG operator, Postgres cluster, Lakekeeper, bootstrap and smoke Jobs) run in **one namespace, `dev`**. That is the only environment, and each chart has `values-dev.yaml`.
- The hook keeps allowing `helm uninstall` only with `-n dev`. It also blocks `minikube delete` (including `--all`) unless the command targets profile `spike` (`-p spike`, `-p=spike`, `--profile spike` or `--profile=spike`). Unit tests for both rules live in `.claude/hooks/tests/` and run in `make test`. Deleting the `dev` profile is left to the user.
- `.claude/hooks/` is owned by **test-engineer**. A hook change always ships in **its own small PR** labelled `needs-human-read`, never in the same PR as the work that needs it.

### minikube

- Profile `dev`: driver **docker**, **8 CPUs, 24 GiB memory, 80 GiB disk**, created by `make cluster-up` (platform-engineer, `infra/minikube/`).
- The Kubernetes version is pinned to an exact patch release within one minor of kubectl v1.36 (that is v1.35.x or v1.36.x) and supported by minikube v1.39.0. The cluster issue picks and records the exact version.
- `make cluster-down` stops the cluster and does not delete it.
- **Spike profile:** the object-store spike uses a separate profile `spike` with `--memory 4g --cpus 2`. With Docker Desktop at 28 GB, `spike` (4 GiB) and `dev` (24 GiB) can't run together. So the spike must finish, and profile `spike` must be deleted, before `make cluster-up` creates `dev`. The alternative is for the user to raise Docker Desktop to 36 GB or more.
- Phase 1 limits: object store 1 CPU / 2 GiB in total, Postgres 1 CPU / 1 GiB, Lakekeeper 0.5 CPU / 512 MiB, plus small limits for the CNPG operator and the Jobs. Every pod and Job has requests and limits, enforced by `make lint`.

### Cluster lock

- `scripts/cluster-lock.sh` (`scripts/` is owned by platform-engineer) provides `acquire <target>` and `release`. It works across worktrees because it locks a fixed host path outside any checkout (for example `${XDG_CACHE_HOME:-$HOME/.cache}/lakehouse/cluster.lock`), created atomically (`mkdir`).
- The lock records holder, target, worktree, PID and start time. A lock older than a configurable stale timeout (default 30 minutes), or held by a dead PID, may be taken over, with a warning. `acquire` waits with a timeout and fails with a message that names the current holder.
- It is **re-entrant within one make invocation**: the holder exports a marker, so nested targets (for example `deploy` calling `secrets` and `bootstrap`) don't deadlock. Release happens on exit, including on failure (trap).
- Every target that changes or exercises cluster state takes the lock: `secrets` (the apply step), `deploy`, `undeploy`, `bootstrap` and `smoke-phase1`. Read-only targets (`lint`, `test`, `helm-template`) don't.

### Makefile structure and target ownership

The top-level `Makefile` is thin and includes one file per area, each with one owner:

| File | Owner | Targets |
|---|---|---|
| `Makefile` | test-engineer | includes only |
| `mk/lint.mk` | test-engineer | `lint`, `test` |
| `mk/helm.mk` | test-engineer | `helm-template`, plus the chart checks called by `lint` and `test` |
| `mk/smoke.mk` | test-engineer | `smoke-phase1` (later `smoke-phaseN`) |
| `mk/cluster.mk` | platform-engineer | `cluster-up`, `cluster-down` |
| `mk/deploy.mk` | platform-engineer | `secrets`, `deploy`, `undeploy`, `bootstrap` |

`deploy` runs `secrets`, installs all charts in `dev` in dependency order, waits for readiness, then runs `bootstrap`. `bootstrap` runs as an in-cluster Job.

### Smoke test

- `make smoke-phase1` runs the PyIceberg gate script as a **Kubernetes Job in `dev`**. It reaches Lakekeeper and the S3 endpoint by service DNS. There are no port-forwards.
- The Job image is built from `tests/smoke/` with `minikube image build`. It uses a Python 3.12 base image pinned by digest, and `uv sync --frozen` against the committed `uv.lock` (pinned `pyiceberg[pyarrow]` plus the fsspec/s3fs extras needed by ADR-0005). It is tagged with a content hash and uses `imagePullPolicy: Never`. Nothing is installed at Job run time.
- The script creates a uniquely named namespace and table, writes deterministic rows, reads them back and compares them, then drops the table and namespace. It exits non-zero on any failed step and prints a clear message for each step. The row-comparison logic also has a CI-safe unit test in `make test`.
- The Make target deletes any previous run's Job and waits for the Job to **complete or fail**. It always prints the Job's logs, and exits non-zero if the Job fails, not only on timeout.
- **Phase 1 done:** from `minikube delete`, `make cluster-up deploy smoke-phase1` passes, and running `make smoke-phase1` a second time also passes.

### Agent concurrency

- At most **three agents** work at the same time. Phase 1 waves:

| Wave | Issues |
|---|---|
| 1a | 1, 3, 4 |
| 1b | 2, 13 |
| 1c | 5 |
| 2 | 6, 8 |
| 3 | 7, 9 |
| 4 | 10, with 12 in development |
| 5 | 11, then 12's gate run |

Issue numbers are planning numbers. `docs/architecture.md` maps them to titles.

## Consequences

- Teardown and redeploy of the whole stack is a single `helm uninstall -n dev` per release, which the hook allows. Agents can delete only the throwaway `spike` profile.
- There is no isolation between components inside the namespace. That is acceptable locally.
- 24 GiB is reserved for minikube on a 48 GiB host. This is decided up front, so there's no cluster recreation in Phase 2. The spike and `dev` are serialised.
- The cluster lock serialises deploys and smoke runs from parallel worktrees. A crashed holder blocks others for at most the stale timeout.
- Each area has its own Makefile include, so parallel PRs from different owners don't conflict in one Makefile.
- The smoke test exercises the same network paths and catalog-returned endpoints that in-cluster clients like Trino will use.

## Alternatives considered

- **A namespace per component.** Rejected: the hook would block `helm uninstall` outside `dev`.
- **Smaller minikube (6 CPUs / 12 GiB).** Rejected: too small for Trino and later phases, and memory can't be raised without deleting the cluster.
- **Running `spike` and `dev` side by side.** Rejected unless the user raises Docker Desktop memory to 36 GB or more.
- **vfkit or qemu drivers.** Rejected: Docker is already installed and is the best-trodden minikube path on macOS arm64.
- **No lock, relying on agents coordinating.** Rejected: agents share no memory, and concurrent Helm releases fail in confusing ways.
- **An in-cluster lock (a Lease or ConfigMap).** Rejected for Phase 1: it needs a running cluster and kubectl in every lock call. A host file lock is simpler, and all agents run on the same host.
- **A single monolithic Makefile.** Rejected: it creates merge conflicts between owners working in parallel.
- **`kubectl port-forward` with a host-side Python script.** Rejected: flaky, and endpoints returned by the catalog are in-cluster names, so the host would need different configuration than real clients.
- **Job image that runs `pip install` at start-up.** Rejected: not reproducible, and it needs network access during the gate.
