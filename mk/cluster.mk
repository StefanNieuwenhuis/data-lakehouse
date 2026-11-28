# mk/cluster.mk - owner: platform-engineer (ADR-0006).
# Targets: cluster-up, cluster-down, verify-etcd-encryption,
# validate-cluster-manifests.
#
#   cluster-up                  create or start minikube profile `dev` (pins and
#                               sizing in infra/minikube/versions.mk), with Calico
#                               and etcd encryption at rest, then apply the Phase 1
#                               namespaces and ResourceQuotas. A second run is a
#                               no-op.
#   cluster-down                stop profile `dev`; never deletes it.
#   verify-etcd-encryption      probe Secret with a dummy value; asserts the raw
#                               etcd entry is secretbox-encrypted. Prints only
#                               PASS/FAIL and the prefix.
#   validate-cluster-manifests  kubeconform -strict on the namespace and quota
#                               manifests, with the kubeconform and schema pins
#                               from mk/helm.mk.
#
# Recipes are silenced and never use `set -x`, so no key material is echoed.

include infra/minikube/versions.mk

MINIKUBE_DIR      := infra/minikube
CLUSTER_MANIFESTS := $(MINIKUBE_DIR)/namespaces.yaml $(MINIKUBE_DIR)/quotas.yaml

.PHONY: cluster-up cluster-down verify-etcd-encryption validate-cluster-manifests

## cluster-up: create or start profile dev, with namespaces and quotas.
cluster-up:
	@PROFILE="$(MINIKUBE_PROFILE)" DRIVER="$(MINIKUBE_DRIVER)" RUNTIME="$(MINIKUBE_RUNTIME)" \
	  CPUS="$(MINIKUBE_CPUS)" MEMORY="$(MINIKUBE_MEMORY)" DISK_SIZE="$(MINIKUBE_DISK_SIZE)" \
	  CNI="$(MINIKUBE_CNI)" K8S_VERSION="$(MINIKUBE_K8S_VERSION)" CALICO_VERSION="$(CALICO_VERSION)" \
	  REQUIRED_MINIKUBE_VERSION="$(MINIKUBE_REQUIRED_VERSION)" \
	  $(MINIKUBE_DIR)/cluster-up.sh

## cluster-down: stop profile dev without deleting it.
cluster-down:
	@status="$$(minikube status -p $(MINIKUBE_PROFILE) --format '{{.Host}}' 2>/dev/null | head -n 1 || true)"; \
	if [ "$$status" = "Running" ]; then \
	  minikube stop -p $(MINIKUBE_PROFILE); \
	else \
	  echo "==> minikube profile $(MINIKUBE_PROFILE) not running ($${status:-absent}): nothing to stop"; \
	fi

## verify-etcd-encryption: assert Secrets are secretbox-encrypted in etcd.
verify-etcd-encryption:
	@PROFILE="$(MINIKUBE_PROFILE)" $(MINIKUBE_DIR)/verify-etcd-encryption.sh

## validate-cluster-manifests: kubeconform -strict on the namespace and quota manifests.
validate-cluster-manifests: check-kubeconform
	@mkdir -p "$(KUBECONFORM_CACHE)"
	@kubeconform="$$($(ENSURE_TOOL) kubeconform)" && \
	"$$kubeconform" -strict -summary \
	  -kubernetes-version "$(patsubst v%,%,$(MINIKUBE_K8S_VERSION))" \
	  -cache "$(KUBECONFORM_CACHE)" \
	  -schema-location "https://raw.githubusercontent.com/yannh/kubernetes-json-schema/$(K8S_SCHEMAS_SHA)/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json" \
	  $(CLUSTER_MANIFESTS)
