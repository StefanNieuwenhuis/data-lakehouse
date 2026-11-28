# 0004. Postgres via CloudNativePG

Date: 2026-11-28

## Status

Accepted

## Context

Lakekeeper needs a Postgres database for catalog metadata. Dagster (Phase 4) and possibly other components will need one later. The Lakekeeper chart's bundled Postgres subchart uses a Bitnami-derived image (ADR-0003). Images must be arm64, pinned and maintained. The cluster is a single-node minikube with limited memory (ADR-0006).

## Decision

- Run Postgres with the **CloudNativePG** operator, chart `cnpg/cloudnative-pg` **0.29.2** (operator **1.30.2**), wrapped in `charts/cnpg-operator/`. The operator runs in namespace `dev` (ADR-0006). Its CRDs are cluster-scoped, which is inherent to CRDs.
- Run **one** CNPG `Cluster`, defined in the in-repo chart `charts/postgres/`, with **one instance** (no replicas) in Phase 1.
- **One database and one role per consumer.** Phase 1 has `lakekeeper`. Later consumers, such as Dagster, get their own database and role in the same cluster, declared as CNPG `Database` resources or managed roles.
- Postgres major version **17**. Release 17 is mature and widely supported by tooling and Lakekeeper's tested setups. Release 18 is newer than we need, and nothing in the stack calls for it. The image is `ghcr.io/cloudnative-pg/postgresql` with an **exact minor tag and digest**, chosen and recorded (as an amendment to ADR-0003) in the Postgres issue. The floating `17` tag isn't used.
- Resource limits for the Postgres instance: **1 CPU and 1 GiB memory**. The operator pod also has requests and limits.
- Role passwords come from Kubernetes Secrets created by `make secrets` (ADR-0005) and are referenced by the `Cluster` and the Lakekeeper chart. CNPG doesn't generate them, so they survive a redeploy.
- PVC storage uses minikube's default `standard` StorageClass.
- **Fallback:** if CNPG turns out not to work on this setup, use a small in-repo StatefulSet around the official `postgres` image (pinned by digest). That needs an amendment to this ADR.

## Consequences

- One extra component (the operator) has to run, with its own resource budget.
- Databases and roles are declarative, and adding Dagster later is a small change.
- kubeconform needs CNPG CRD schemas, from the pinned CRDs-catalog (ADR-0003).
- Operator CRDs survive `helm uninstall -n dev`. Clean teardown of CRDs is `minikube delete`, which is acceptable locally.
- There is no high availability or backup in Phase 1. Data is disposable and recreated from `make` targets.

## Alternatives considered

- **Lakekeeper's bundled `postgresql` subchart.** Rejected: Bitnami-derived image, and it ties Postgres to Lakekeeper's lifecycle.
- **Bitnami PostgreSQL chart.** Rejected: Bitnami catalog changes (ADR-0003).
- **Plain StatefulSet on the official `postgres` image.** This is the fallback. It is simpler, but roles, databases and passwords would be handled by hand-written init scripts.
- **One Postgres per consumer.** Rejected: wastes memory on a single node, and per-database isolation is enough locally.
- **Postgres 18.** Not chosen now. It can be revisited with a superseding ADR.
