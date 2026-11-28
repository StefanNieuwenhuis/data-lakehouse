# Architecture

This document describes the target architecture of the local lakehouse, its components, how they connect, and the delivery phases with their gates. The decisions behind it are in [`docs/adr/`](adr/).

Last updated: 2026-11-28 (Phase 1 planning).

## Overview

A local data lakehouse on a single-node minikube cluster (Apple Silicon, arm64). Data is stored as Apache Iceberg tables in an S3-compatible object store. A REST catalog (Lakekeeper) tracks the tables, a query engine (Trino) reads and writes them, dbt transforms them, and Dagster orchestrates the pipelines. Phase 5 adds a semantic layer (Cube) and LangGraph chatbots.

```
                    +----------------------- minikube, namespace dev ------------------------+
                    |                                                                        |
  make deploy  ---> |  [CNPG operator] --manages--> [Postgres cluster]                       |
                    |                                   ^  db+role per consumer              |
                    |                                   |  (lakekeeper; later dagster)       |
                    |                                   |                                    |
   Iceberg clients  |  [Lakekeeper REST catalog] -------+                                    |
   (smoke Job,      |        |  static S3 keys, remote signing                               |
    Trino, dbt,     |        v                                                               |
    Dagster)  ----> |  [SeaweedFS S3 gateway] -- filer -- master -- volume   bucket: lakehouse|
                    |                                                                        |
                    +------------------------------------------------------------------------+
```

## Components

| Component | Phase | What it does | Chart | ADR |
|---|---|---|---|---|
| S3 object store: SeaweedFS 4.55 | 1 | Stores Iceberg data and metadata files. S3 gateway with path-style access and static keys | `charts/seaweedfs` wrapping `seaweedfs/seaweedfs` 4.55.0 | 0002, 0003 |
| CloudNativePG operator 1.30.2 | 1 | Manages Postgres | `charts/cnpg-operator` wrapping `cnpg/cloudnative-pg` 0.29.2 | 0004 |
| Postgres 17 (CNPG Cluster, 1 instance) | 1 | Catalog metadata for Lakekeeper. Later the Dagster metadata DB. One database and role per consumer | `charts/postgres` (in-repo) | 0004 |
| Lakekeeper 0.15.1 | 1 | Iceberg REST catalog with warehouse `lakehouse`. Auth disabled in Phase 1. Signs S3 requests for clients | `charts/lakekeeper` wrapping `lakekeeper/lakekeeper` 0.15.0 (Postgres and OpenFGA subcharts disabled) | 0003, 0005 |
| Trino | 2 | SQL engine over Iceberg through Lakekeeper | TBD | TBD |
| Ingestion (dlt / PyIceberg) and dbt | 3 | Load raw data and transform sources, then staging, then marts | n/a | TBD |
| Dagster | 4 | Orchestrates ingestion and dbt assets | TBD | TBD |
| Cube and LangGraph chatbots | 5 | Semantic layer and natural-language access | TBD | TBD |
| Optional extras: Spark, Superset, monitoring | 6 | Optional | TBD | TBD |

All images are pinned by tag and digest, and all have linux/arm64 variants. The table of digests is in ADR-0003.

## How components connect (Phase 1)

- **Namespace:** everything runs in `dev` (ADR-0006). Services are ClusterIP only, with no ingress in Phase 1.
- **Lakekeeper and Postgres:** Lakekeeper connects to the CNPG read-write Service, using database `lakekeeper` and role `lakekeeper`. The password and Lakekeeper's encryption key come from Kubernetes Secrets created by `make secrets`.
- **Lakekeeper and the object store:** warehouse `lakehouse` has an S3 storage profile pointing at the SeaweedFS S3 Service (path-style, STS disabled) and a static key pair as its storage credential.
- **Clients and storage:** clients talk to the Lakekeeper REST API. For S3 access they use **remote signing** through Lakekeeper and hold no keys themselves. PyIceberg uses the fsspec FileIO for this (ADR-0005). The fallback, by ADR amendment only, is static client keys.
- **Secrets:** generated once into the gitignored `.env.dev` and applied as Kubernetes Secrets. They are never rotated automatically. Charts use `existingSecret` (ADR-0005).

## Cluster and resources

- minikube profile `dev` with the docker driver, **8 CPUs, 24 GiB memory, 80 GiB disk**, and a pinned Kubernetes v1.35.x or v1.36.x (ADR-0006). The throwaway profile `spike` (2 CPUs, 4 GiB) is used only by the object-store spike and is deleted before `dev` is created.
- Every pod and Job has requests and limits, enforced by `make lint`. Phase 1 limits:

| Component | CPU limit | Memory limit |
|---|---|---|
| Object store (all SeaweedFS pods together) | 1 | 2 GiB |
| Postgres instance | 1 | 1 GiB |
| Lakekeeper | 0.5 | 512 MiB |
| CNPG operator, bootstrap and smoke Jobs | small, set per issue | small, set per issue |

## Tooling and checks

- **Single entry point:** the Makefile. CI calls only `make lint`, `make test` and `make helm-template`.
- **Pinned toolchain** (ADR-0003):
  - Python 3.12 tools through `uv` with a committed `uv.lock`;
  - Helm v4.3.1, kubeconform and kube-linter pinned as Makefile variables;
  - the CRDs-catalog pinned to a commit SHA;
  - GitHub Actions pinned to commit SHAs.
- `make lint` runs yamllint, ruff, sqlfluff and a requests/limits policy check on the rendered charts.
- `make helm-template` runs, for every chart and values file, `helm dependency build`, `helm lint` and `helm template`, then validates the output with `kubeconform -strict` (CRD schemas included).
- `make test` runs pytest on unit and data tests. It passes when there are no tests. Fixture charts under `tests/` prove the chart checks: a valid fixture must pass and a broken one must fail.

## Make targets

The top-level `Makefile` only includes one file per area (ADR-0006):

| File | Owner | Targets |
|---|---|---|
| `Makefile` | test-engineer | includes only |
| `mk/lint.mk` | test-engineer | `lint`, `test` |
| `mk/helm.mk` | test-engineer | `helm-template`, plus the chart checks called by `lint` and `test` |
| `mk/smoke.mk` | test-engineer | `smoke-phase1` |
| `mk/cluster.mk` | platform-engineer | `cluster-up`, `cluster-down` |
| `mk/deploy.mk` | platform-engineer | `secrets`, `deploy`, `undeploy`, `bootstrap` |

**Cluster lock.** `scripts/cluster-lock.sh` (platform-engineer) is a host-wide file lock, shared by all worktrees. It is re-entrant within one make run, and a stale lock is taken over after a timeout (default 30 minutes). `secrets` (apply), `deploy`, `undeploy`, `bootstrap` and `smoke-phase1` all take it.

**Hook rules.** `.claude/hooks/block_destructive.py` allows `helm uninstall` only with `-n dev`, and `minikube delete` only for profile `spike`. Both rules have unit tests in `.claude/hooks/tests/`, run by `make test`.

## Ownership and review of process files

- The orchestrator owns the process docs: `docs/adr/`, `docs/architecture.md`, `CLAUDE.md`, `README.md` and `.claude/agents/`. They are not code. The orchestrator can own issues (`agent:orchestrator`). The main session commits, pushes and opens PRs for those issues.
- test-engineer owns `.claude/hooks/`. platform-engineer owns `scripts/`.
- Any PR that touches `.claude/` or `CLAUDE.md` gets the label **`needs-human-read`**, and the user reviews it in full before it can merge.
- A hook change always ships in **its own small PR** labelled `needs-human-read`, never in the same PR as the work that needs it.

## Agent concurrency and Phase 1 waves

At most **three agents** work at the same time. A wave starts when the issues it depends on are merged.

| Wave | Issues (titles abbreviated) | Notes |
|---|---|---|
| 1a | 1 toolchain, lint and CI; 3 object-store spike; 4 process-doc rewording | 1, 3 and 4 have no dependencies |
| 1b | 2 helm-template and kubeconform; 13 hook rules (`minikube delete` guard) | Both need 1 |
| 1c | 5 cluster lifecycle and cluster lock | Needs 1 and 13, and needs 3 finished with profile `spike` deleted |
| 2 | 6 secrets; 8 CNPG operator | |
| 3 | 7 SeaweedFS chart; 9 Postgres cluster | |
| 4 | 10 Lakekeeper; 12 smoke gate (developed in parallel) | |
| 5 | 11 bootstrap, then 12's gate run and PR | |

## Phases and gates

Each phase ends with a gate: `make smoke-phaseN` passes against a freshly deployed cluster.

| Phase | Scope | Gate |
|---|---|---|
| 1 | Platform: S3 object store (SeaweedFS), Postgres (CNPG), Lakekeeper. Pinned charts, limits, arm64. Real lint and helm-template checks. Cluster lifecycle, secrets, deploy and bootstrap targets | From `minikube delete`: `make cluster-up deploy smoke-phase1` passes, and a second `make smoke-phase1` also passes. The smoke Job (PyIceberg) creates a namespace and table, writes deterministic rows, reads them back and compares them, then drops them. `make lint` and `make helm-template` pass in CI |
| 2 | Trino connected to Lakekeeper (Iceberg REST, remote signing) | `make smoke-phase2`: create, insert into and select from an Iceberg table through Trino. Exact gate defined at Phase 2 planning |
| 3 | Ingestion (dlt / PyIceberg, idempotent per partition) and dbt (sources, staging, marts, with tests) | `make smoke-phase3`. Defined at Phase 3 planning |
| 4 | Dagster orchestrating ingestion and dbt assets | `make smoke-phase4`. Defined at Phase 4 planning |
| 5 | Cube semantic layer and LangGraph chatbots, plus evals. Proposed new agent: `ai-engineer` | `make smoke-phase5`. Defined at Phase 5 planning |
| 6 | Optional extras: Spark, Superset, monitoring | Defined if and when planned |

## Open items

- CLAUDE.md, README and the agent prompts still name MinIO and contain the old ownership. They are reworded to "S3 object store", with the ownership above, through a Phase 1 PR labelled `needs-human-read`. That issue first widens the orchestrator's own prompt to allow these edits.
- ADR-0002 and ADR-0005 are conditional on the object-store spike (S3 compatibility and remote signing via `FsspecFileIO` with SeaweedFS).
- With Docker Desktop at 28 GB, the `spike` profile (4 GiB) and `dev` (24 GiB) can't run together. The spike must finish first, unless the user raises Docker Desktop to 36 GB or more.
