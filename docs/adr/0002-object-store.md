# 0002. Object store: SeaweedFS instead of MinIO

Date: 2026-11-28

## Status

Accepted (conditional), approved by the user on 2026-11-28. The condition is that the Phase 1 object-store spike shows SeaweedFS's S3 gateway works with Lakekeeper and PyIceberg, as described under Decision. If the spike fails, it proposes an amendment, and Garage becomes the next candidate.

## Context

The lakehouse needs an S3-compatible object store on minikube (arm64 host, Apple Silicon) for Iceberg data and metadata files. The original plan named MinIO. The decision rule agreed in planning: use MinIO only if a maintained, official, arm64 image and Helm chart can be pulled and pinned; otherwise use SeaweedFS.

Verified on 2026-11-28 (`helm search repo`, `docker buildx imagetools inspect`):

- **MinIO.** The newest community chart, `minio/minio` from `charts.min.io`, is 5.4.0 with app `RELEASE.2024-12-18T13-15-44Z`, about two years old. `quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z` returns `401 Unauthorized`. `minio/minio` on Docker Hub returns "pull access denied, repository does not exist". So no maintained community image is available.
- **SeaweedFS.** The chart `seaweedfs/seaweedfs` 4.55.0 (app 4.55) is at `https://seaweedfs.github.io/seaweedfs/helm`. The image `chrislusf/seaweedfs:4.55` is multi-arch (linux/amd64 and linux/arm64). Digests are recorded in ADR-0003.

## Decision

- Use **SeaweedFS 4.55** (chart `seaweedfs/seaweedfs` 4.55.0) as the S3 object store, wrapped in an in-repo chart, `charts/seaweedfs/` (ADR-0003). It runs in namespace `lh-storage` (ADR-0006). Its S3 Service is addressed by its full DNS name, `<svc>.lh-storage.svc.cluster.local`.
- Only the S3 gateway is exposed to other components, through an in-cluster Service. Clients use **path-style** addressing and an explicit endpoint. Virtual-host-style addressing is not used.
- Access uses static S3 keys (ADR-0005). STS is not used.
- The resource limit budget for the object store, summed over all its pods (master, volume, filer, s3), is **1 CPU and 2 GiB memory**. Every pod has requests and limits.
- Documentation and agent prompts refer to "the S3 object store", not to a product, so a later swap doesn't require rewording.
- **Spike acceptance condition.** Before Lakekeeper is wired up, a spike shows against a live SeaweedFS in a throwaway minikube profile `spike` (`--memory 4g --cpus 2`, deleted before `dev` is created; ADR-0006) that:
  1. a bucket can be created idempotently, and objects can be put, got, listed and deleted with static keys, with path-style addressing and SigV4;
  2. the write-access mechanism chosen in ADR-0005 (Lakekeeper remote signing) works against SeaweedFS, or the spike documents exactly why not;
  3. PyIceberg (with the FileIO required by ADR-0005) can write and read Parquet data files through that mechanism. If Lakekeeper isn't deployed yet, this is checked with a plain S3 round-trip plus a signed-request check, and fully confirmed at the Phase 1 gate;
  4. multipart upload works, since pyarrow and fsspec use it for larger files.

  The spike ends with either a short "confirmed" amendment to this ADR, or a proposed superseding ADR.

## Consequences

- There are no MinIO-specific features (MinIO Console, `mc admin`). Bucket and key management uses SeaweedFS tools (`weed shell`, the S3 config file) or plain S3 API calls.
- SeaweedFS has more moving parts than a single MinIO pod (master, volume, filer, s3 gateway), so the 1 CPU / 2 GiB budget has to be split carefully. Single replicas and an embedded filer store (leveldb) are enough for local use.
- The S3 compatibility of SeaweedFS is good but not complete. Gaps surface in the spike or at the gate and are handled by amending this ADR.
- CLAUDE.md, README and the agent prompts still say "MinIO". They are reworded to "S3 object store" in a Phase 1 PR, not by hand.

## Alternatives considered

- **MinIO, community edition.** Rejected: no maintained, pullable official image (see Context). The chart is about two years stale.
- **Frozen MinIO tag from a mirror or `bitnamilegacy`.** Rejected: no security fixes, and not an official source. It breaks the "maintained and pinned" rule.
- **Garage.** A light, S3-compatible store with arm64 images. Kept as the **fallback** if the SeaweedFS spike fails. It has no IAM or STS and only limited S3 API coverage, and it has less ecosystem testing with Iceberg tooling.
- **Ceph RGW (Rook).** Rejected: too heavy for a single-node minikube with the memory budget in ADR-0006.
- **MinIO AIStor (commercial).** Rejected: license and cost are out of scope for a local learning lakehouse.
