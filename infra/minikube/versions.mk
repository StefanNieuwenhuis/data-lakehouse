# infra/minikube/versions.mk - owner: platform-engineer (ADR-0006, issue #5).
# Pinned versions and sizing for minikube profile `dev`. Included by
# mk/cluster.mk. Change a value here, never inline in a recipe.

# minikube release this setup is written and verified against. cluster-up
# fails on any other version, because the Kubernetes and Calico pins below
# depend on it.
MINIKUBE_REQUIRED_VERSION := v1.39.0

# Exact Kubernetes patch: v1.36.x (within one minor of kubectl v1.36.0) and
# listed by `minikube config defaults kubernetes-version` for minikube v1.39.0.
# Verified 2026-11-28. Keep KUBERNETES_VERSION in mk/helm.mk in sync.
MINIKUBE_K8S_VERSION := v1.36.4

# Calico is installed by `minikube start --cni=calico`; its version is fixed by
# the minikube release (manifest embedded in minikube v1.39.0). cluster-up
# asserts that the running calico-node image has exactly this tag.
CALICO_VERSION := v3.32.2

# Profile and sizing (ADR-0006).
MINIKUBE_PROFILE   := dev
MINIKUBE_DRIVER    := docker
MINIKUBE_RUNTIME   := containerd
MINIKUBE_CPUS      := 8
MINIKUBE_MEMORY    := 24g
MINIKUBE_DISK_SIZE := 80g
MINIKUBE_CNI       := calico
