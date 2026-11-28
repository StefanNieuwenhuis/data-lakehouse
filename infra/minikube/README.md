# infra/minikube

Owner: platform-engineer. Decisions: [ADR-0006](../../docs/adr/0006-namespace-minikube-sizing-and-smoke-job.md)
and [ADR-0005](../../docs/adr/0005-secrets-catalog-auth-and-storage-credentials.md).

## Pinned versions

The pins live in [`versions.mk`](versions.mk); `make cluster-up` enforces them.

| Item | Version | Source |
|---|---|---|
| minikube | v1.39.0 | local tool; `cluster-up` fails on any other version |
| Kubernetes | v1.36.4 | `minikube config defaults kubernetes-version` (minikube v1.39.0) |
| Calico | v3.32.2 | embedded in minikube v1.39.0 (`--cni=calico`); `cluster-up` checks the calico-node image tag |
| Container runtime | containerd (2.3.4 in the kicbase image) | minikube v1.39.0 default, set explicitly |

Profile `dev`: docker driver, 8 CPUs, 24 GiB memory, 80 GiB disk.

## Targets (`mk/cluster.mk`)

- `make cluster-up` creates or starts profile `dev`, checks the pins, waits for the
  node and Calico, and applies `namespaces.yaml` and `quotas.yaml`. If `dev` is
  already running, minikube is not touched and the manifests report `unchanged`.
- `make cluster-down` stops `dev`. It never deletes it.
- `make verify-etcd-encryption` writes a probe Secret with a random dummy marker,
  reads its raw etcd entry with `etcdctl` in the etcd pod, asserts the
  `k8s:enc:secretbox:v1:` prefix and the absence of the marker, and deletes the
  probe. It prints only PASS or FAIL and the prefix.
- `make validate-cluster-manifests` runs `kubeconform -strict` on the manifests,
  with the kubeconform and schema pins from `mk/helm.mk`.

## etcd encryption at rest

`etcd-encryption.sh ensure` generates `~/.config/lakehouse/etcd/encryption-config.yaml`
(mode 0600, `secretbox` first, `identity` as read fallback, random 32-byte key) only
if it is missing. It never rotates the key. Losing it makes existing Secrets
unreadable; recovery is a fresh cluster.

Delivery: while `minikube start` runs, the file is staged in minikube's file-sync
tree, and minikube copies it to `/var/lib/minikube/certs/encryption-config.yaml`
on the node. That is kubeadm's certificates directory, which the kube-apiserver
static pod already mounts. The apiserver gets
`--extra-config=apiserver.encryption-provider-config=/var/lib/minikube/certs/encryption-config.yaml`.
The staged copy is removed when `minikube start` returns, also on failure.

Host-side locations holding the key (for the Read deny rules, #15):

- `~/.config/lakehouse/etcd/encryption-config.yaml` (source of truth);
- `~/.minikube/files/var/lib/minikube/certs/encryption-config.yaml` (or under
  `$MINIKUBE_HOME`), only while `make cluster-up` runs `minikube start`.

On the node, the file is in the `dev` container's `/var` volume (inside the
Docker Desktop VM). No copy is ever written to the repo.

## Namespaces and quotas

`lh-storage`, `lh-catalog` and `lh-ops`, each with a `ResourceQuota` named
`lh-quota` (numbers from ADR-0006) and no `LimitRange`, so a pod without
requests and limits is rejected.
