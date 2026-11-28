# 0003. Chart sourcing, image pinning and tool pinning

Date: 2026-11-28

## Status

Accepted

## Context

CLAUDE.md requires every chart and image version to be pinned (never `latest`) and everything to be reproducible from a clean cluster through `make`. In 2025 Bitnami moved its free images to a frozen `bitnamilegacy` repository, so Bitnami charts and images are no longer a sustainable default. The host is arm64, so every image must have a linux/arm64 variant. CI runs `lint` and `helm-template`. At the moment CI installs linters without pinned versions, and the `helm-template` job has its own inline script instead of calling a `make` target.

## Decision

### Charts

- Every component gets an **in-repo wrapper chart** in `charts/<component>/`:
  - `Chart.yaml` declares exactly one pinned upstream chart as a dependency (exact version, no ranges) from its official repository;
  - `values.yaml` holds the shared defaults and `values-dev.yaml` the `dev` overrides;
  - `Chart.lock` is committed. Downloaded dependency archives (`charts/*/charts/*.tgz`) are gitignored and rebuilt with `helm dependency build`.
- No Bitnami charts or images, directly or as subcharts. Subcharts that pull Bitnami or Bitnami-derived images are disabled.
- Pinned upstream charts for Phase 1 (verified 2026-11-28 with `helm search repo`):

| Wrapper chart | Upstream chart | Chart version | App version | Repository |
|---|---|---|---|---|
| `charts/seaweedfs` | `seaweedfs/seaweedfs` | 4.55.0 | 4.55 | <https://seaweedfs.github.io/seaweedfs/helm> |
| `charts/cnpg-operator` | `cnpg/cloudnative-pg` | 0.29.2 | 1.30.2 | <https://cloudnative-pg.github.io/charts> |
| `charts/postgres` | none (in-repo templates for the CNPG `Cluster` and `Database` resources) | n/a | Postgres 17 (ADR-0004) | n/a |
| `charts/lakekeeper` | `lakekeeper/lakekeeper` | 0.15.0 | 0.15.1 | <https://lakekeeper.github.io/lakekeeper-charts> |

- In the Lakekeeper chart, the optional `postgresql` subchart (groundhog2k/postgres 1.6.9, default image `quay.io/lakekeeper/postgresql:15.4.0-debian-11-r45`, Bitnami-derived) is **disabled** in favour of CloudNativePG (ADR-0004). The optional `openfga` subchart (0.4.1) is **disabled**, since auth is `none` in Phase 1 (ADR-0005).

### Images

- Images are referenced by **tag and digest** (`repo:tag@sha256:<index digest>`) in the values files, so they stay multi-arch while being immutable. Floating tags such as `postgresql:17` are not allowed in values. Each one is replaced by an exact minor tag plus its digest.
- arm64 availability is checked with `docker buildx imagetools inspect IMAGE:TAG`, not with `docker manifest inspect`, which returns nothing for several registries. The index digest and the linux/arm64 digest are recorded below. When an image is bumped, this table gets an amendment.

Verified 2026-11-28, all multi-arch with linux/amd64 and linux/arm64:

| Image | Index digest | linux/arm64 digest |
|---|---|---|
| `quay.io/lakekeeper/catalog:v0.15.1` | `sha256:22dcb6044c106a962c242b70051bd226bd50c9134c763121d8713c37fe9a70ec` | `sha256:c76b758e0bd67d052c411f0d5194f1203beb24a8ce31466ca09f3be8ba58dee9` |
| `chrislusf/seaweedfs:4.55` | `sha256:7ca46aeae2f223b37e5d91593c17ab37738eec6df6ab69b48a0487f7643342b9` | `sha256:1d857dc0ff7f0829e5f0228c7dd8d6907b4d1e7b01b553eb5c05c17c9a9a7b49` |
| `ghcr.io/cloudnative-pg/cloudnative-pg:1.30.2` | `sha256:f96f6be3d81ec93819b443c665c575c609342fca840df90d4d87dae314a5b913` | `sha256:9be85561bd93beb1dfac8c1976562b4acb6585c9b58c0dfd5169fba8d6b85807` |
| `ghcr.io/cloudnative-pg/postgresql:17` (floating; reference only, must be replaced by an exact minor tag in the Postgres issue) | `sha256:70664ebcfa1100361b5bdc28bbf06fdbe08db2dc4ad7bd14de33c5e05fe8ea8e` | `sha256:6604fb7b7abbb76174bc2ac2d8115ba3d8af5ca9c33ce294d966a6a038afa009` |
| `ghcr.io/cloudnative-pg/postgresql:18` (floating; reference only, not used) | `sha256:899d3ed526b659d77935dde0e6bf2d69dbbf17d3d8c6486ca8cfd04bd3c18533` | `sha256:63079eb3fcef08657344d06c477c20d6c8737e0e315caf5576948a6a6e96fa73` |

### Tools

- All lint and test tools are pinned in the repo and used **identically by CI and locally**:
  - Python tools (yamllint, ruff, sqlfluff, pytest and later pyiceberg) are pinned in a `uv` project with a committed `uv.lock`, on Python 3.12;
  - binary tools (Helm, kubeconform, kube-linter) are pinned as version variables in the Makefile. CI installs them from those variables, and local runs check the installed version against them. Helm is **v4.3.1**, in sync with the local version;
  - CRD schemas for kubeconform come from the datreeio CRDs-catalog, **pinned to a commit SHA**. `-ignore-missing-schemas` is not used.
- CI calls `make` targets only (`make lint`, `make test`, `make helm-template`). It doesn't run linters through inline scripts. Make targets are split into `mk/*.mk` files per owner (ADR-0006).
- GitHub Actions are pinned to full commit SHAs, with the version in a trailing comment.
- `make helm-template` renders every chart with each of its values files and validates the output with `kubeconform -strict`. `make lint` includes a requests/limits policy check (pinned kube-linter or a small script) on the rendered output. Both are proven by fixture charts under `tests/`: a valid one must pass and a broken one must fail.
- chart-testing (`ct`) is not used in Phase 1.

## Consequences

- Upgrading a chart or image is an explicit, reviewable change: bump the version, update `Chart.lock` and the digest, amend the table here.
- Wrapper charts add a layer, but CI validates exactly what `make deploy` installs, and the `dev` overrides stay in the repo.
- Pinning by digest means a re-pushed tag can't silently change what runs.
- Running `uv`, kubeconform and kube-linter locally becomes a prerequisite. `make lint` fails with a clear message if a tool is missing or has the wrong version.

## Alternatives considered

- **Bitnami charts and images.** Rejected: the free catalog is frozen (`bitnamilegacy`) and Bitnami Secure Images need a subscription.
- **Install upstream charts directly with `--set` flags.** Rejected: overrides would live in Makefile lines, and CI couldn't render what is deployed.
- **Vendored (copied) upstream charts.** Rejected: hard to upgrade and diff. A dependency plus a committed lock gives the same reproducibility.
- **Tags without digests.** Rejected: tags can be re-pushed. Digests are cheap to record.
- **`kubeconform -ignore-missing-schemas`.** Rejected: CNPG `Cluster` and `Database` resources would go unvalidated.
- **chart-testing (`ct lint`).** Deferred: `helm lint`, `helm template` and kubeconform cover Phase 1.
