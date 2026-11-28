# Architecture

This document describes the target architecture of the local lakehouse, its components, how they connect, and the delivery phases with their gates. The decisions behind it are in [`docs/adr/`](adr/).

Last updated: 2026-11-28 (Phase 1 planning, amended after the PR #14 review, after spike #3, and for the naming conventions in ADR-0007).

## Overview

A local data lakehouse on a single-node minikube cluster (profile `dev`, Apple Silicon, arm64, Calico CNI). Data is stored as Apache Iceberg tables in an S3-compatible object store. A REST catalog (Lakekeeper) tracks the tables, a query engine (Trino) reads and writes them, dbt transforms them, and Dagster orchestrates the pipelines. Phase 5 adds a semantic layer (Cube) and LangGraph chatbots. Workloads are split into one namespace per layer, all prefixed `lh-` (ADR-0006).

```
 minikube profile dev (Calico)

 +-- lh-ops ------------------+     +-- lh-catalog ---------------------+
 | CNPG operator              |     | Lakekeeper REST (auth none)       |
 | smoke Job (PyIceberg,      |---->|   :8181                           |
 |  no credentials)           |     | migration Job, bootstrap Job      |
 +----------------------------+     +-----------------------------------+
      |  manages (watch,                |  5432          |  S3 :8333
      |  status :8000)                  v                v
      |                         +-- lh-storage -----------------------+
      +------------------------>| CNPG Postgres 17 (db+role/consumer) |
                                | SeaweedFS (master, volume, filer,   |
   smoke Job S3 data traffic -->|   s3 gateway), bucket lakehouse     |
   (remote-signed by Lakekeeper)+-------------------------------------+

 Later: lh-compute (Trino, Spark), lh-orchestration (Dagster), lh-ai (Cube, LangGraph, Langfuse)
```

## Components

| Component | Phase | Namespace | What it does | Chart | ADR |
|---|---|---|---|---|---|
| S3 object store: SeaweedFS 4.55 | 1 | `lh-storage` | Stores Iceberg data and metadata files. S3 gateway with path-style access and static keys | `charts/seaweedfs` wrapping `seaweedfs/seaweedfs` 4.55.0 | 0002, 0003 |
| CloudNativePG operator 1.30.2 | 1 | `lh-ops` (watches `lh-storage`) | Manages Postgres | `charts/cnpg-operator` wrapping `cnpg/cloudnative-pg` 0.29.2 | 0004 |
| Postgres 17 (CNPG Cluster, 1 instance) | 1 | `lh-storage` | Catalog metadata for Lakekeeper. Later the Dagster metadata DB. One database and role per consumer | `charts/postgres` (in-repo) | 0004 |
| Lakekeeper 0.15.1 | 1 | `lh-catalog` | Iceberg REST catalog with warehouse `lakehouse`. Auth disabled in Phase 1. Signs S3 requests for clients | `charts/lakekeeper` wrapping `lakekeeper/lakekeeper` 0.15.0 (Postgres and OpenFGA subcharts disabled) | 0003, 0005 |
| Bootstrap Job | 1 | `lh-catalog` | Idempotently creates the bucket, runs the Lakekeeper server bootstrap, and creates the warehouse | in `charts/lakekeeper` or `infra/` | 0005, 0006 |
| Smoke Job | 1 | `lh-ops` | Phase 1 gate (PyIceberg) | `tests/smoke/` | 0006 |
| Trino | 2 | `lh-compute` | SQL engine over Iceberg through Lakekeeper | TBD | TBD |
| Ingestion (dlt / PyIceberg) and dbt | 3 | TBD | Load raw data and transform sources, then staging, then marts | n/a | TBD |
| Dagster | 4 | `lh-orchestration` | Orchestrates ingestion and dbt assets | TBD | TBD |
| Cube, LangGraph chatbots, Langfuse | 5 | `lh-ai` | Semantic layer, natural-language access, tracing | TBD | TBD |
| Optional extras: Spark, Superset, monitoring | 6 | `lh-compute` / TBD | Optional | TBD | TBD |

All images are pinned by tag and digest, and all have linux/arm64 variants. The table of digests is in ADR-0003.

## Namespaces

| Namespace | Phase created | Contents | Quota limits CPU / memory | Quota requests CPU / memory |
|---|---|---|---|---|
| `lh-storage` | 1 | SeaweedFS, CNPG Postgres | 3 / 4.5 GiB (8 PVCs, 40 GiB) | 2 / 3 GiB |
| `lh-catalog` | 1 | Lakekeeper, migration and bootstrap Jobs | 2 / 2 GiB | 1 / 1 GiB |
| `lh-ops` | 1 | CNPG operator, smoke Jobs | 2.5 / 2.5 GiB | 1 / 1.5 GiB |
| `lh-compute` | 2 | Trino, later Spark | set in Phase 2 | set in Phase 2 |
| `lh-orchestration` | 4 | Dagster | set in Phase 4 | set in Phase 4 |
| `lh-ai` | 5 | Cube, LangGraph, Langfuse | set in Phase 5 | set in Phase 5 |

Namespaces and quotas are created by `make cluster-up` from manifests in `infra/minikube/`. There are no `LimitRange` defaults, so a pod without limits is rejected.

## How components connect (Phase 1)

- **Addressing:** every cross-namespace address uses the full DNS name `<svc>.<ns>.svc.cluster.local`. That includes the S3 endpoint stored in the warehouse profile. Services are ClusterIP only, with no ingress.
- **Lakekeeper and Postgres:** Lakekeeper (`lh-catalog`) connects to the CNPG read-write Service in `lh-storage` on 5432, using database `lakekeeper` and role `lakekeeper`.
- **Lakekeeper and the object store:** warehouse `lakehouse` has an S3 storage profile pointing at the SeaweedFS S3 Service in `lh-storage` (path-style, STS disabled, remote signing enabled with `remote-signing-url-style: path`) and delete profile `hard`, with the static key pair as its storage credential. The bootstrap Job stores it, and Lakekeeper keeps it encrypted in Postgres.
- **Clients and storage:** clients talk to the Lakekeeper REST API. S3 requests are **remote-signed** by Lakekeeper, but the client still sends its S3 traffic **directly** to SeaweedFS. Clients hold no keys. PyIceberg uses the fsspec FileIO for this (ADR-0005). Two conditions from the spike #3 amendment to ADR-0005 apply to every PyIceberg client:
  - it runs with `PYICEBERG_MAX_WORKERS=1` until apache/iceberg-python#4414 is fixed in a released PyIceberg version that we pin, and 10 consecutive clean round trips pass at default workers (two `make smoke-phase1` runs; lifting it is a new ADR-0005 amendment);
  - it deletes tables and files through Lakekeeper (`purge_table`, warehouse delete profile `hard`), never through `FileIO.delete()`.
- **CNPG:** the operator (`lh-ops`) watches the `Cluster` in `lh-storage` and polls each instance's status endpoint. The API server calls the operator's admission webhook.

## Secrets

Details are in ADR-0005.

- **One source:** `.env.dev.sops`, a gitignored dotenv file encrypted with SOPS and age. The age key is in `~/.config/sops/age/`.
- **Single decryption path:** `make secrets` decrypts in memory and applies each value **only to the namespaces that consume it**. It never echoes values. `make secrets-verify` prints only sha256 digests.

| Secret | Namespaces |
|---|---|
| S3 key pair | `lh-storage` (SeaweedFS identity config), `lh-catalog` (bootstrap Job) |
| Postgres `lakekeeper` password | `lh-storage` (CNPG managed role), `lh-catalog` (Lakekeeper, migration Job) |
| Lakekeeper encryption key | `lh-catalog` only |
| none | `lh-ops` |

- **At rest:** etcd encrypts Secrets with secretbox. The key is in `~/.config/lakehouse/etcd/`, generated once by `make cluster-up` and never rotated. The host disk is covered by FileVault.
- **Agent-leak guards:**
  - `permissions.deny` rules in `.claude/settings.json` as a backstop;
  - the PreToolUse hook as the primary guard (it parses arguments);
  - gitleaks in CI (`make secrets-scan`).

  The residual risks are listed in ADR-0005.

## Network policy matrix (issue 17, end of Phase 1)

Each `lh-` namespace gets default-deny for ingress and egress. Allows use core `networking.k8s.io/v1` NetworkPolicy only. Ports marked "verify" are checked against upstream documentation when the issue is implemented.

| From | To | Port(s) | Why |
|---|---|---|---|
| all `lh-` namespaces | `kube-system` kube-dns | UDP/TCP 53 | DNS |
| `lh-ops` smoke Job | `lh-catalog` Lakekeeper | TCP 8181 (verify) | Iceberg REST and remote signing |
| `lh-ops` smoke Job | `lh-storage` SeaweedFS S3 | TCP 8333 (verify) | Signed S3 data traffic goes straight to the store |
| `lh-catalog` Lakekeeper and migration Job | `lh-storage` Postgres | TCP 5432 | Catalog database |
| `lh-catalog` Lakekeeper and bootstrap Job | `lh-storage` SeaweedFS S3 | TCP 8333 (verify) | Bucket creation, storage validation |
| `lh-catalog` bootstrap Job | `lh-catalog` Lakekeeper | TCP 8181 (verify) | Management API |
| `lh-ops` CNPG operator | `lh-storage` Postgres pods | TCP 8000 (status, verify), TCP 5432 | Instance manager status, management |
| Kubernetes API server | `lh-ops` CNPG operator webhook | TCP 9443 (verify) | Admission webhooks |
| `lh-ops` CNPG operator, `lh-storage` CNPG instances | Kubernetes API server | apiserver endpoint, TCP 8443 in minikube (verify) | Watch and status updates |
| within `lh-storage` | SeaweedFS components | master 9333/19333, volume 8080/18080, filer 8888/18888, s3 8333 (verify) | Internal SeaweedFS traffic |

Negative checks: for example, a non-operator pod in `lh-ops` can't reach Postgres on 5432, and `lh-ops` can't reach Postgres except from the operator. The Phase 1 gate must pass with the policies on.

## Cluster and resources

- minikube profile `dev`: docker driver, **8 CPUs, 24 GiB memory, 80 GiB disk**, `--cni=calico`, a pinned Kubernetes v1.35.x or v1.36.x, and etcd encryption (ADR-0006).
- The throwaway profile `spike` (2 CPUs, 4 GiB) is used only by the object-store spike, and is deleted before `dev` is created.
- Every pod and Job has requests and limits, enforced by `make lint` and by the namespace quotas. Phase 1 limits:

| Component | CPU limit | Memory limit |
|---|---|---|
| Object store (all SeaweedFS pods together) | 1 | 2 GiB |
| Postgres instance | 1 | 1 GiB |
| Lakekeeper | 0.5 | 512 MiB |
| CNPG operator | 0.5 | 512 MiB |
| Smoke Job | 1 | 1 GiB |
| Migration and bootstrap Jobs, check pods | 0.25 each | 256 MiB each |

Calico adds about 0.25 CPU and 0.5 GiB in `kube-system`.

## Tooling and checks

- **Single entry point:** the Makefile. CI calls only `make lint`, `make test`, `make helm-template` and `make secrets-scan`.
- **Pinned toolchain** (ADR-0003):
  - Python 3.12 tools through `uv` with a committed `uv.lock`;
  - Helm v4.3.1, kubeconform, kube-linter and gitleaks pinned as Makefile variables;
  - the CRDs-catalog pinned to a commit SHA;
  - GitHub Actions pinned to commit SHAs;
  - `sops` and `age` versions checked by `make secrets`.
- `make lint` runs yamllint, ruff, sqlfluff and a requests/limits policy check on the rendered charts.
- `make helm-template` runs, for every chart and values file, `helm dependency build`, `helm lint` and `helm template`, then validates the output with `kubeconform -strict` (CRD schemas included).
- `make test` runs pytest, including the hook tests and the lock tests. It passes when there are no tests. Fixture charts under `tests/` prove the chart checks.
- `make secrets-scan` runs gitleaks over the PR diff. `.gitleaks.toml` allowlists only test fixtures.

## Make targets

The top-level `Makefile` only includes one file per area (ADR-0006):

| File | Owner | Targets |
|---|---|---|
| `Makefile` | test-engineer | includes only |
| `mk/lint.mk` | test-engineer | `lint`, `test`, `secrets-scan` |
| `mk/helm.mk` | test-engineer | `helm-template`, plus the chart checks called by `lint` and `test` |
| `mk/smoke.mk` | test-engineer | `smoke-phase1` |
| `mk/cluster.mk` | platform-engineer | `cluster-up`, `cluster-down`, `verify-etcd-encryption` |
| `mk/deploy.mk` | platform-engineer | `secrets`, `secrets-verify`, `deploy`, `undeploy`, `bootstrap` |

**Cluster lock.** `scripts/cluster-lock.sh` (platform-engineer) is a host-wide file lock, shared by all worktrees. It is re-entrant within one make run, and a stale lock is taken over after a timeout (default 30 minutes). `secrets` (apply), `deploy`, `undeploy`, `bootstrap` and `smoke-phase1` all take it.

**Hook rules** (`.claude/hooks/block_destructive.py`, test-engineer):
- `helm uninstall` is allowed only with `-n lh-[a-z]+`;
- `minikube delete` is allowed only for profile `spike`;
- the secret-leak rules from ADR-0005 apply;
- every rule has unit tests in `.claude/hooks/tests/`, run by `make test`.

## Ownership and review of process files

- The orchestrator owns the process docs: `docs/adr/`, `docs/architecture.md`, `docs/conventions.yaml`, `CLAUDE.md`, `README.md` and `.claude/agents/`. They are not code. The orchestrator can own issues (`agent:orchestrator`). The main session commits, pushes and opens PRs for those issues.
- test-engineer owns `.claude/hooks/` and `.claude/settings.json`. platform-engineer owns `scripts/`.
- Any PR that touches `.claude/` or `CLAUDE.md` gets the label **`needs-human-read`**, and the user reviews it in full before it can merge.
- A hook or settings change always ships in **its own small PR** labelled `needs-human-read`, never in the same PR as the work that needs it. An agent never edits `.claude/settings.json` or `.claude/hooks/` in a PR that benefits from the change.

## Agent concurrency and Phase 1 waves

At most **three agents** work at the same time. A wave starts when the issues it depends on are merged.

| Wave | Issues (titles abbreviated) | Notes |
|---|---|---|
| 1a | 1 toolchain, lint and CI; 3 object-store spike; 4 process docs | No dependencies |
| 1b | 13 hook rules (namespaces, `minikube delete`), starts first; 2 helm-template and kubeconform; 25 naming conventions (ADR-0007) | All need 1. 25 needs 22 |
| 1c | 5 cluster (Calico, etcd encryption, namespaces, quotas); 15 secret-leak guards; 18 cluster lock and deploy skeleton (proposed split from 5) | 5 needs 1 and 13, and needs 3 finished with profile `spike` deleted. 15 needs 13. 18 needs 1 |
| 1d | 19 board tooling; 26 naming checks, Markdown lint, issue forms; 23 guardrail wording after 13 | 26 needs 25. 23 needs 13 |
| 2 | 6 secrets (SOPS); 8 CNPG operator; 16 gitleaks | 6 needs 5, 15 and 18 |
| 3 | 7 SeaweedFS chart; 9 Postgres cluster; 20 board process docs | 20 needs 19 |
| 4 | 10 Lakekeeper; 12 smoke gate (in development) | |
| 5 | 11 bootstrap, then 12's gate run and PR | |
| 6 | 17 NetworkPolicies | Needs 11 and 12. The gate runs again with policies on |

## Phases and gates

Each phase ends with a gate: `make smoke-phaseN` passes against a freshly deployed cluster.

| Phase | Scope | Gate |
|---|---|---|
| 1 | Platform: S3 object store (SeaweedFS), Postgres (CNPG), Lakekeeper, in `lh-storage`, `lh-catalog` and `lh-ops` with quotas and NetworkPolicies. Pinned charts, limits, arm64. Real lint, helm-template and secret-scan checks. Encrypted secrets and agent-leak guards. Cluster lifecycle, secrets, deploy and bootstrap targets | From `minikube delete`: `make cluster-up deploy smoke-phase1` passes, and a second `make smoke-phase1` also passes, with NetworkPolicies on. The smoke Job (PyIceberg, `PYICEBERG_MAX_WORKERS=1`) creates a namespace and table, writes deterministic rows, reads them back and compares them, then drops them through Lakekeeper. It runs this round trip 5 times in a row and fails on any 403, with no retries (ADR-0006, spike #3 amendment). `make lint`, `make helm-template` and `make secrets-scan` pass in CI |
| 2 | Trino in `lh-compute`, connected to Lakekeeper (Iceberg REST, remote signing) | `make smoke-phase2`: create, insert into and select from an Iceberg table through Trino. Exact gate defined at Phase 2 planning |
| 3 | Ingestion (dlt / PyIceberg, idempotent per partition) and dbt (sources, staging, marts, with tests) | `make smoke-phase3`. Defined at Phase 3 planning |
| 4 | Dagster in `lh-orchestration`, orchestrating ingestion and dbt assets | `make smoke-phase4`. Defined at Phase 4 planning |
| 5 | Cube, LangGraph chatbots and Langfuse in `lh-ai`, plus evals. Proposed new agent: `ai-engineer` | `make smoke-phase5`. Defined at Phase 5 planning |
| 6 | Optional extras: Spark, Superset, monitoring | Defined if and when planned |

## Open items

- ADR-0002 and ADR-0005 were confirmed by the object-store spike (#3) on 2026-11-28. ADR-0005 now carries client conditions for PyIceberg (one worker, deletes through Lakekeeper). The one-worker condition lifts only when [apache/iceberg-python#4414](https://github.com/apache/iceberg-python/issues/4414) (the gating issue) is fixed in a released PyIceberg version that we pin, and 10 consecutive clean round trips pass at default workers (two `make smoke-phase1` runs). The related [#3896](https://github.com/apache/iceberg-python/issues/3896) is closed by the merged PR #4405, which isn't in a release yet and isn't enough on its own. ADR-0006 was amended for the 5x smoke round trip.
- With Docker Desktop at 28 GB, the `spike` profile (4 GiB) and `dev` (24 GiB) can't run together. The spike run is finished and profile `spike` has been deleted (see the spike #3 result).
- Ports in the network policy matrix marked "verify" (CNPG webhook and status port, Lakekeeper and SeaweedFS ports, the minikube apiserver port) are confirmed in issue 17.
- Splitting the cluster lock out of issue 5 into a new issue 18 is proposed, pending approval.
- OpenBao with External Secrets Operator is deferred to the OIDC/auth phase.
