# mk/helm.mk - owner: test-engineer (ADR-0006).
# Targets: helm-template, plus the chart checks called by `lint` and `test`.
#
#   helm-template  every charts/* with each of its values*.yaml: helm dependency
#                  build, helm lint --strict, helm template, kubeconform -strict
#                  -summary. Run by CI's helm-template job.
#   lint-charts    every charts/* with each of its values*.yaml: helm dependency
#                  build, helm template, kube-linter (requests/limits policy in
#                  $(KUBE_LINTER_CONFIG)). Run by `make lint`.
#   test-charts    runs both checks on the fixture charts in tests/fixtures/charts/
#                  and asserts which pass and which fail, and why. Run by `make test`.
#   check-helm, check-kubeconform, check-kube-linter
#                  resolve one pinned tool each (see below).
#
# The work is done by helm, kubeconform and kube-linter themselves; the scripts
# in tests/charts/ only loop over charts and values files, check tool versions
# and assert fixture outcomes.
#
# Tool pinning (ADR-0003). The binary tools are pinned here and used the same
# way locally and in CI. tests/charts/ensure_tool.sh uses a tool from
# $(TOOLS_DIR) or PATH only if it reports exactly the pinned version. Otherwise
# it downloads the pinned release into $(TOOLS_DIR) (repo-local, gitignored) and
# checks it against the SHA-256 digests below. If that is not possible it fails
# with an ERROR line naming the tool, the version found and the version
# required. Run with TOOLS_DOWNLOAD=0 to never download and fail instead.

.PHONY: helm-template lint-charts test-charts check-helm check-kubeconform check-kube-linter

# --- Pins -------------------------------------------------------------------
# Keep HELM_VERSION in sync with azure/setup-helm in .github/workflows/ci.yml
# and with the local Helm (CLAUDE.md).
HELM_VERSION        := v4.3.1
KUBECONFORM_VERSION := v0.8.0
KUBE_LINTER_VERSION := v0.8.3
# Kubernetes version the rendered output is validated against. Keep in sync
# with the minikube pin (v1.35.x or v1.36.x, ADR-0006) once the cluster issue
# records it.
KUBERNETES_VERSION  := 1.36.0
# yannh/kubernetes-json-schema (kubeconform's default schemas), pinned to a
# commit instead of master. Verified 2026-11-28.
K8S_SCHEMAS_SHA     := e62c03bd5a52fd34ff6ac28d083e2a300e0ae7c1
# datreeio/CRDs-catalog, pinned to a commit. Verified 2026-11-28.
CRDS_CATALOG_SHA    := b50f3fbc45169a14b6d2d3f767b32fd96ef4a3fa
# kube-linter config holding the requests/limits policy.
KUBE_LINTER_CONFIG  := tests/charts/kube-linter.yaml

# SHA-256 of the release archives: get.helm.sh/*.sha256sum, kubeconform's
# CHECKSUMS file and the asset digests of the kube-linter GitHub release.
# Update them together with the versions.
HELM_SHA256_darwin_arm64        := 6b4e61c8cd27d99e5a801e63ff25dd5c70b36875c2cd659d3e9ce6b76fc23198
HELM_SHA256_darwin_amd64        := 34bec4eba761ba5c16d1965ee6b8f5b0abe5993974a802274e2a4f0418893d89
HELM_SHA256_linux_amd64         := 0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b
HELM_SHA256_linux_arm64         := 8cf8f66ecbc252ac8f7f06cca68aba88508ddfde3a6a34feb1678ad1694b4f88
KUBECONFORM_SHA256_darwin_arm64 := f84f4dfbebf4a6b0b230385fa065a39ea35e02608c2b50d025dcf64775a69d67
KUBECONFORM_SHA256_darwin_amd64 := 71dbc87ac9f24099a62b93570e65aa06312ba6ac8aea63b7f86e9d999edf5a92
KUBECONFORM_SHA256_linux_amd64  := 9bc2bffbf71f261128533edaf912153948b7ff238f9a531ae6d34466ec287883
KUBECONFORM_SHA256_linux_arm64  := 1f53fc8e81258197a35e8603054162a5af1de8c5af13746c71ab680d9534ed87
KUBE_LINTER_SHA256_darwin_arm64 := 6e3443a8ff8625a9fc31a38682c783988d7559018f7ff707a4f8c77c18c92f14
KUBE_LINTER_SHA256_darwin_amd64 := c62e8af3c9df2557c7a3922119ea1b35597794737d1ccad493f63a0d66e7b8fc
KUBE_LINTER_SHA256_linux_amd64  := 1a6d8419b11971372971fdbc22682b684ebfb7cf1c39591662d1b6ca736c41df
KUBE_LINTER_SHA256_linux_arm64  := 802e1b09eabd08f6f0a060a6b8ab2bf7bc7e6bf4f673bb2692303704c84b3e22

# --- Paths and environment for tests/charts/*.sh ------------------------------
TOOLS_DIR         ?= $(CURDIR)/.tools/bin
KUBECONFORM_CACHE ?= $(CURDIR)/.tools/kubeconform-cache
TOOLS_OS          := $(shell uname -s | tr '[:upper:]' '[:lower:]')
TOOLS_ARCH        := $(patsubst aarch64,arm64,$(patsubst x86_64,amd64,$(shell uname -m)))

ENSURE_TOOL  := tests/charts/ensure_tool.sh
CHART_CHECK  := tests/charts/chart_check.sh
CHART_DIRS   := $(patsubst %/Chart.yaml,%,$(wildcard charts/*/Chart.yaml))
FIXTURES_DIR := tests/fixtures/charts

export HELM_VERSION KUBECONFORM_VERSION KUBE_LINTER_VERSION KUBERNETES_VERSION
export K8S_SCHEMAS_SHA CRDS_CATALOG_SHA KUBE_LINTER_CONFIG
export HELM_SHA256_darwin_arm64 HELM_SHA256_darwin_amd64 HELM_SHA256_linux_amd64 HELM_SHA256_linux_arm64
export KUBECONFORM_SHA256_darwin_arm64 KUBECONFORM_SHA256_darwin_amd64
export KUBECONFORM_SHA256_linux_amd64 KUBECONFORM_SHA256_linux_arm64
export KUBE_LINTER_SHA256_darwin_arm64 KUBE_LINTER_SHA256_darwin_amd64
export KUBE_LINTER_SHA256_linux_amd64 KUBE_LINTER_SHA256_linux_arm64
export TOOLS_DIR TOOLS_OS TOOLS_ARCH KUBECONFORM_CACHE

# --- Targets ----------------------------------------------------------------
check-helm:
	@p="$$($(ENSURE_TOOL) helm)" && echo "==> helm $(HELM_VERSION): $$p"

check-kubeconform:
	@p="$$($(ENSURE_TOOL) kubeconform)" && echo "==> kubeconform $(KUBECONFORM_VERSION): $$p"

check-kube-linter:
	@p="$$($(ENSURE_TOOL) kube-linter)" && echo "==> kube-linter $(KUBE_LINTER_VERSION): $$p"

## helm-template: lint, render and kubeconform-validate every chart and values file.
helm-template: check-helm check-kubeconform
	@$(CHART_CHECK) template $(CHART_DIRS)

## lint-charts: kube-linter requests/limits policy on every chart's rendered output.
lint-charts: check-helm check-kube-linter
	@$(CHART_CHECK) policy $(CHART_DIRS)

## test-charts: the checks above must pass the valid fixture and fail each broken one.
test-charts: check-helm check-kubeconform check-kube-linter
	@FIXTURES_DIR="$(FIXTURES_DIR)" CHART_CHECK="$(CHART_CHECK)" tests/charts/test_fixture_charts.sh
