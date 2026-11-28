# 0005. Secrets, Lakekeeper auth and storage credentials

Date: 2026-11-28

## Status

Accepted (conditional), approved by the user on 2026-11-28. The condition is that the object-store spike (ADR-0002) confirms the write-access mechanism, remote signing through PyIceberg's `FsspecFileIO` against SeaweedFS. If the spike fails, the fallback below applies by amendment. The secrets and auth decisions aren't affected by the condition.

## Context

Phase 1 needs credentials for Postgres roles, the S3 object store, and Lakekeeper's own encryption key. CLAUDE.md forbids secrets in git and requires reproducibility through `make`. Lakekeeper stores warehouse storage credentials in Postgres, encrypted with a key it is given at start-up. If that key or the Postgres password changes, Lakekeeper can no longer reach its database or decrypt its stored credentials. SeaweedFS doesn't offer a usable STS, so vended temporary credentials aren't available. Iceberg clients (PyIceberg now, Trino in Phase 2) need write access to table data in the bucket.

## Decision

### Secret generation and storage

- `make secrets` (owned by platform-engineer):
  1. creates `.env.dev` in the repo root with random values, **only if the file doesn't exist**. If it exists, values are read and never regenerated or rotated. A missing individual key is added, but existing keys are never overwritten;
  2. applies the values as Kubernetes Secrets in namespace `dev`, idempotently (`kubectl apply` of generated manifests, never written to disk in the repo). The apply step holds the cluster lock (ADR-0006).
- `.env.dev` is gitignored. No credential appears in values files, manifests or Makefile lines. Charts reference Secrets through `existingSecret` (or the upstream chart's equivalent).
- Phase 1 secrets are: the S3 admin access and secret key (SeaweedFS S3 config), the Postgres `lakekeeper` role password, and the Lakekeeper Postgres encryption key.
- `make deploy` runs `make secrets` first, so `make cluster-up deploy` works on a clean checkout.
- Rotation is out of scope. Deleting `.env.dev` while the cluster has data is documented as destructive (Postgres and Lakekeeper would be locked out). The recovery is `minikube delete` and a fresh `make cluster-up deploy`.

### Lakekeeper auth

- Phase 1 runs Lakekeeper with **authentication and authorization disabled** (no OIDC, OpenFGA subchart disabled). The REST API is reachable only inside the cluster (ClusterIP).
- Lakekeeper's one-time server bootstrap (accepting the terms of use) and the creation of warehouse `lakehouse` are done by the idempotent `make bootstrap` step.
- OIDC (for example Keycloak) and OpenFGA authorization will come in a later phase under a new ADR.

### Storage credentials and client write access

- Lakekeeper's warehouse `lakehouse` uses an S3 storage profile pointing to the in-cluster SeaweedFS S3 endpoint, with path-style access, a fixed region string and **STS disabled**. Its storage credential is the **static S3 key pair** from `make secrets`.
- **Clients get write access through Lakekeeper remote signing.** The static key pair is held only by Lakekeeper. Iceberg clients load the table config from the REST catalog and send their S3 requests to Lakekeeper to be signed. They hold no S3 keys themselves.
- For PyIceberg this means the **fsspec FileIO** (`pyiceberg.io.fsspec.FsspecFileIO`), because PyIceberg's remote S3 signer is implemented for fsspec/s3fs. pyarrow is still used for in-memory data and Parquet encoding. The spike and the smoke test set this FileIO explicitly.
- **Fallback (only by amendment after a failed spike):** static client keys. The smoke Job (and later Trino) gets the S3 key pair from a Kubernetes Secret through environment variables and writes with PyArrowFileIO. Remote signing is then disabled in the storage profile.

## Consequences

- No secret is ever committed. A clean clone plus `make cluster-up deploy` gives a working stack with fresh random credentials.
- Credentials are stable across redeploys, because they are never rotated automatically. Losing `.env.dev` means recreating the cluster.
- With no auth, anything in the cluster can manage the catalog. That is acceptable for a local, single-user setup, and not exposed outside the cluster.
- Remote signing keeps S3 keys out of client configs, which matches how Trino (Phase 2) can consume Lakekeeper. The cost: PyIceberg is tied to the fsspec FileIO, and every S3 request needs a signing round-trip to Lakekeeper.
- Remote signing against SeaweedFS is a compatibility risk, which is why the spike checks it before Lakekeeper is integrated.

## Alternatives considered

- **STS or vended temporary credentials.** Rejected: SeaweedFS has no usable STS. This can be revisited with a different store.
- **Static keys in every client** (as the primary approach). Kept as the fallback. It is simpler, but spreads the admin key to every client, and it's a pattern that doesn't carry over to authenticated phases.
- **sealed-secrets, SOPS or External Secrets.** Rejected for Phase 1: extra components and key management for a local, single-user cluster.
- **Let CNPG or charts generate random passwords.** Rejected: values would change when the cluster is recreated, and Lakekeeper's encryption key must stay in sync with stored data. One source (`.env.dev`) is simpler.
- **OIDC from Phase 1.** Rejected: an identity provider adds a component and complexity before the core data path works.
