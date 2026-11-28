# 0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job

Date: 2026-11-28

## Status

Accepted, amended after the PR #14 review. The namespace-per-layer layout is decided (PR #14 merged). It replaces the earlier single `dev` namespace.

## Context

- The PreToolUse hook (`.claude/hooks/block_destructive.py`) only allows `helm uninstall` with `-n dev`. It has no rule for `minikube delete` yet.
- In the PR #14 review, the user asked for alternatives to a single namespace, such as a namespace per service. Separate namespaces give separate quotas, NetworkPolicies and Secret placement. The cost is cross-namespace DNS, Secret copies and more policies.
- NetworkPolicies are only enforced if the CNI supports them. minikube's default CNI with the docker driver doesn't enforce them, and changing the CNI later means deleting the cluster.
- The host is Apple Silicon (arm64) with 14 CPUs and 48 GiB of memory. Docker Desktop has 28 GB. Local tools: minikube v1.39.0, kubectl v1.36.0, Helm v4.3.1 (matches CI), Docker 29.7.2 (arm64).
- minikube's memory can't be raised without deleting the cluster. Trino (Phase 2), Dagster (Phase 4) and Cube plus chatbots (Phase 5) are memory-hungry, so the cluster must be sized for later phases now.
- Several agents work in parallel worktrees against one shared cluster. Concurrent `helm upgrade`, secret applies or smoke runs would interfere with each other.
- The Phase 1 gate runs a PyIceberg script. S3 endpoints and catalog URLs returned by Lakekeeper are in-cluster service names, which a client on the host can't resolve without extra tricks.

## Decision

### Namespaces per layer

One namespace per layer, all with the prefix `lh-`:

| Namespace | Contents | Created in |
|---|---|---|
| `lh-storage` | SeaweedFS, the CNPG Postgres `Cluster` | Phase 1 |
| `lh-catalog` | Lakekeeper, its migration Job, the bootstrap Job | Phase 1 |
| `lh-ops` | CNPG operator, smoke Jobs | Phase 1 |
| `lh-compute` | Trino, later Spark | Phase 2 |
| `lh-orchestration` | Dagster | Phase 4 |
| `lh-ai` | Cube, LangGraph, Langfuse | Phase 5 |

- Phase 1 creates only `lh-storage`, `lh-catalog` and `lh-ops`, idempotently through `make cluster-up`. The manifests live in `infra/minikube/`. Each later phase creates its own namespace.
- There is still one environment, the minikube profile `dev`. Each chart keeps `values-dev.yaml`.
- Cross-namespace addresses always use the full service DNS name (`<svc>.<ns>.svc.cluster.local`). That includes the S3 endpoint stored in the Lakekeeper warehouse profile, so it resolves from every namespace.
- Secrets exist only in the namespaces that consume them. The placement table is in ADR-0005.

### Resource quotas

Each `lh-` namespace has a `ResourceQuota`, sized as the component limits in this ADR plus headroom for a rolling-update surge, CNPG init Jobs, and short-lived check pods. No `LimitRange` defaults are set, so a pod without limits is rejected and doesn't silently get defaults.

| Namespace | Steady-state limits | Quota limits.cpu / limits.memory | Quota requests.cpu / requests.memory | Storage |
|---|---|---|---|---|
| `lh-storage` | SeaweedFS 1 / 2 GiB + Postgres 1 / 1 GiB | 3 / 4.5 GiB | 2 / 3 GiB | 8 PVCs, 40 GiB |
| `lh-catalog` | Lakekeeper 0.5 / 512 MiB, migration and bootstrap Jobs 0.25 / 256 MiB each | 2 / 2 GiB | 1 / 1 GiB | 0 PVCs |
| `lh-ops` | CNPG operator 0.5 / 512 MiB, smoke Job 1 / 1 GiB | 2.5 / 2.5 GiB | 1 / 1.5 GiB | 0 PVCs |

The quota numbers live in `infra/minikube/`, and an issue may tune them with the reason stated in its PR. Changing a component's budget needs an amendment to this ADR.

### CNI and NetworkPolicy

- `make cluster-up` starts minikube with **`--cni=calico`**. The Calico version comes with minikube v1.39.0 and is recorded in the cluster issue. Calico adds roughly 0.25 CPU and 0.5 GiB in `kube-system`, which fits within 8 CPU / 24 GiB.
- NetworkPolicies are added in a **separate issue at the end of Phase 1**. Each `lh-` namespace gets default-deny for ingress and egress, plus explicit allows (matrix in `docs/architecture.md`). They use core `networking.k8s.io/v1` NetworkPolicy only, with no Calico CRDs. The Phase 1 gate must pass with the policies on.
- Until then, traffic between namespaces is open.

### Hook rules

- The hook allows `helm uninstall` only with a namespace matching **`^lh-[a-z]+$`** (`-n` or `--namespace`, including the `=` forms). The `dev` namespace no longer exists. The profile is still called `dev`.
- It blocks `minikube delete`, including `--all`, unless the command targets profile `spike` (`-p spike`, `-p=spike`, `--profile spike` or `--profile=spike`). Deleting profile `dev` is left to the user.
- It also carries the **secret-leak rules** from ADR-0005. It blocks:
  - `kubectl get`, `describe` or `edit` of secrets in any argument order, and `kubectl create secret`;
  - `kubectl get --raw` on secrets, and `kubectl get all` with `-o yaml|json|jsonpath|go-template|custom-columns`;
  - `kubectl exec ... -- env|printenv`;
  - `helm get values|all|manifest`;
  - commands that read `.env*` files, `~/.config/sops/` or `~/.config/lakehouse/`;
  - `sops` decrypt, exec and edit forms, and `age -d`.
- Matching `permissions.deny` entries in `.claude/settings.json` are a prefix-match backstop. The hook's argument parsing is the primary guard.
- Unit tests for every blocked and allowed form, including argument-order variants, live in `.claude/hooks/tests/` and run in `make test`.
- `.claude/hooks/` and `.claude/settings.json` are owned by **test-engineer**. A hook or settings change always ships in **its own small PR** labelled `needs-human-read`, never in the same PR as the work that needs it. An agent never edits `.claude/settings.json` or `.claude/hooks/` in a PR that benefits from the change.

### minikube

- Profile `dev`: driver **docker**, **8 CPUs, 24 GiB memory, 80 GiB disk**, CNI **calico**, created by `make cluster-up` (platform-engineer, `infra/minikube/`).
- The Kubernetes version is pinned to an exact patch release within one minor of kubectl v1.36 (that is v1.35.x or v1.36.x) and supported by minikube v1.39.0. The cluster issue picks and records the exact version.
- `make cluster-down` stops the cluster and does not delete it.
- **etcd encryption at rest:**
  - The kube-apiserver runs with an `EncryptionConfiguration` for `secrets`, with `secretbox` as the first provider and `identity` only as the read fallback. It is set with `--extra-config=apiserver.encryption-provider-config=<node path>`.
  - The source of truth is `~/.config/lakehouse/etcd/encryption-config.yaml` (mode 0600), outside the repo and never in git. `make cluster-up` generates it once, with a random 32-byte key, if it is missing, and **never rotates it**.
  - The file reaches the node through minikube's file sync or a mount, at a path the apiserver static pod already mounts. Any host-side copy (for example under `~/.minikube/files/`) is covered by the same Read deny rules as the source.
  - Losing the key makes existing Secrets unreadable. Recovery is `minikube delete` and a fresh `make cluster-up deploy`.
  - `make verify-etcd-encryption` (in `mk/cluster.mk`) writes a probe Secret with a dummy value. It reads the raw etcd entry, asserts the `k8s:enc:secretbox:v1:` prefix and the absence of the dummy plaintext, then deletes the probe. It prints only pass or fail and the prefix.
- **Spike profile:** the object-store spike uses a separate profile `spike` with `--memory 4g --cpus 2`. With Docker Desktop at 28 GB, `spike` (4 GiB) and `dev` (24 GiB) can't run together. So the spike must finish, and profile `spike` must be deleted, before `make cluster-up` creates `dev`. The alternative is for the user to raise Docker Desktop to 36 GB or more.
- Phase 1 limits: object store 1 CPU / 2 GiB in total, Postgres 1 CPU / 1 GiB, Lakekeeper 0.5 CPU / 512 MiB, CNPG operator 0.5 CPU / 512 MiB, smoke Job 1 CPU / 1 GiB, other Jobs 0.25 CPU / 256 MiB. Every pod and Job has requests and limits, enforced by `make lint` and by the quotas.

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
| `mk/lint.mk` | test-engineer | `lint`, `test`, `secrets-scan` |
| `mk/helm.mk` | test-engineer | `helm-template`, plus the chart checks called by `lint` and `test` |
| `mk/smoke.mk` | test-engineer | `smoke-phase1` (later `smoke-phaseN`) |
| `mk/cluster.mk` | platform-engineer | `cluster-up`, `cluster-down`, `verify-etcd-encryption` |
| `mk/deploy.mk` | platform-engineer | `secrets`, `secrets-verify`, `deploy`, `undeploy`, `bootstrap` |

- `deploy` runs `secrets`, installs all charts into their `lh-` namespaces in dependency order (CNPG operator, Postgres, SeaweedFS, Lakekeeper), waits for readiness, then runs `bootstrap`. `bootstrap` runs as an in-cluster Job in `lh-catalog`.
- `undeploy` runs `helm uninstall -n lh-<ns>` per release, in reverse order.

### Smoke test

- `make smoke-phase1` runs the PyIceberg gate script as a **Kubernetes Job in `lh-ops`**. It reaches Lakekeeper (`lh-catalog`) and the S3 endpoint (`lh-storage`) by full service DNS names. There are no port-forwards, and the Job holds no credentials (remote signing, ADR-0005).
- The Job image is built from `tests/smoke/` with `minikube image build`. It uses a Python 3.12 base image pinned by digest, and `uv sync --frozen` against the committed `uv.lock` (pinned `pyiceberg[pyarrow]` plus the fsspec/s3fs extras needed by ADR-0005). It is tagged with a content hash and uses `imagePullPolicy: Never`. Nothing is installed at Job run time.
- The script creates a uniquely named namespace and table, writes deterministic rows, reads them back and compares them, then drops the table and namespace. It exits non-zero on any failed step and prints a clear message for each step. The row-comparison logic also has a CI-safe unit test in `make test`.
- The Make target deletes any previous run's Job and waits for the Job to **complete or fail**. It always prints the Job's logs, and exits non-zero if the Job fails, not only on timeout.
- **Phase 1 done:** from `minikube delete`, `make cluster-up deploy smoke-phase1` passes, a second `make smoke-phase1` also passes, and both runs pass with the NetworkPolicies on.

### Agent concurrency

- At most **three agents** work at the same time. Phase 1 waves:

| Wave | Issues |
|---|---|
| 1a | 1, 3, 4 |
| 1b | 2, 13, 16 |
| 1c | 5, 15, 18 |
| 2 | 6, 8 |
| 3 | 7, 9 |
| 4 | 10, with 12 in development |
| 5 | 11, then 12's gate run |
| 6 | 17 |

Issue numbers are planning numbers. `docs/architecture.md` maps them to titles. Issue 18 (cluster lock and deploy skeleton, split from 5) is proposed, pending the user's approval.

## Consequences

- Each layer has its own quota and, at the end of Phase 1, its own default-deny network boundary. A runaway Job in one layer can't starve another.
- Teardown and redeploy go through `helm uninstall -n lh-<ns>` per release, which the hook allows. Agents can delete only the throwaway `spike` profile. `kube-system` and other namespaces can't be uninstalled by agents.
- Some credentials exist in two namespaces (the S3 keys and the Postgres `lakekeeper` password, see ADR-0005). `make secrets` applies them from one source, so they can't drift.
- Every cross-layer connection needs a full DNS name and, from issue 17, an explicit allow rule. This adds configuration, but it also documents the data flows.
- CNPG runs in `lh-ops` and manages a `Cluster` in `lh-storage`, so the operator needs a cross-namespace watch (ADR-0004).
- Calico costs about 0.25 CPU and 0.5 GiB. It is chosen now because switching CNI later means recreating the cluster.
- 24 GiB is reserved for minikube on a 48 GiB host. This is decided up front, so there's no cluster recreation in Phase 2. The spike and `dev` are serialised.
- The cluster lock serialises deploys and smoke runs from parallel worktrees. A crashed holder blocks others for at most the stale timeout.
- Each area has its own Makefile include, so parallel PRs from different owners don't conflict in one Makefile.
- The smoke test exercises the same cross-namespace network paths and catalog-returned endpoints that clients in `lh-compute` (Trino) will use.

## Alternatives considered

- **A single `dev` namespace** (the previous decision). Rejected after the PR #14 review: no per-layer quotas or network boundaries, and every Secret visible to every workload in the namespace.
- **One namespace per service** (SeaweedFS, Postgres, CNPG, Lakekeeper and so on each separate). Rejected: more Secret copies, quotas and policies, for little extra isolation at this scale. Layers already separate the trust boundaries that matter.
- **CNPG operator in its conventional `cnpg-system` namespace.** Rejected: an extra namespace outside the `lh-` prefix, which the hook couldn't uninstall from. `lh-ops` holds operational components.
- **Keeping minikube's default CNI.** Rejected: NetworkPolicies wouldn't be enforced, and switching later requires deleting the cluster.
- **Cilium instead of Calico.** Rejected: heavier on a single node. Calico is a supported `minikube --cni` option and enforces core NetworkPolicy.
- **Smaller minikube (6 CPUs / 12 GiB).** Rejected: too small for Trino and later phases, and memory can't be raised without deleting the cluster.
- **Running `spike` and `dev` side by side.** Rejected unless the user raises Docker Desktop memory to 36 GB or more.
- **vfkit or qemu drivers.** Rejected: Docker is already installed and is the best-trodden minikube path on macOS arm64.
- **No lock, relying on agents coordinating.** Rejected: agents share no memory, and concurrent Helm releases fail in confusing ways.
- **An in-cluster lock (a Lease or ConfigMap).** Rejected for Phase 1: it needs a running cluster and kubectl in every lock call. A host file lock is simpler, and all agents run on the same host.
- **A single monolithic Makefile.** Rejected: it creates merge conflicts between owners working in parallel.
- **`kubectl port-forward` with a host-side Python script.** Rejected: flaky, and endpoints returned by the catalog are in-cluster names, so the host would need different configuration than real clients.
- **Job image that runs `pip install` at start-up.** Rejected: not reproducible, and it needs network access during the gate.
