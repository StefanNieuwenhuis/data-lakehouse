#!/usr/bin/env bash
# chart_check.sh - render Helm charts and validate the output.
# Owner: test-engineer. Called by mk/helm.mk; pins come from there (ADR-0003).
#
# Usage: chart_check.sh <template|policy> [chart-dir ...]
#
#   template  for every chart and each of its values*.yaml files:
#             helm dependency build, helm lint --strict, helm template, then
#             kubeconform -strict -summary on the rendered output. Kubernetes
#             schemas and CRD schemas (datreeio CRDs-catalog) both come from
#             commit-pinned URLs; a resource without a schema is an error.
#   policy    for every chart and each of its values*.yaml files:
#             helm dependency build, helm template, then kube-linter with
#             $KUBE_LINTER_CONFIG (the requests/limits policy) on the output.
#
# A chart without values*.yaml files is rendered once with its defaults.
# With no chart dirs the script passes and says so. Exits non-zero if any
# chart fails; every chart is still checked so the output lists all failures.
set -euo pipefail

mode="${1:?usage: chart_check.sh <template|policy> [chart-dir ...]}"
shift
case "$mode" in
  template | policy) ;;
  *) echo "ERROR: unknown mode '$mode' (expected template or policy)" >&2; exit 2 ;;
esac

if [ "$#" -eq 0 ]; then
  echo "==> $mode: no charts found, nothing to check"
  exit 0
fi

here="$(cd "$(dirname "$0")" && pwd)"
helm="$("$here/ensure_tool.sh" helm)"
: "${KUBERNETES_VERSION:?}"
if [ "$mode" = template ]; then
  kubeconform="$("$here/ensure_tool.sh" kubeconform)"
  : "${K8S_SCHEMAS_SHA:?}" "${CRDS_CATALOG_SHA:?}" "${KUBECONFORM_CACHE:?}"
  mkdir -p "$KUBECONFORM_CACHE"
  # Same layout as kubeconform's built-in default, but pinned to a commit
  # instead of the moving master branch.
  k8s_schemas="https://raw.githubusercontent.com/yannh/kubernetes-json-schema/${K8S_SCHEMAS_SHA}/{{.NormalizedKubernetesVersion}}-standalone{{.StrictSuffix}}/{{.ResourceKind}}{{.KindSuffix}}.json"
  crd_schemas="https://raw.githubusercontent.com/datreeio/CRDs-catalog/${CRDS_CATALOG_SHA}/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json"
else
  kube_linter="$("$here/ensure_tool.sh" kube-linter)"
  : "${KUBE_LINTER_CONFIG:?KUBE_LINTER_CONFIG is not set (run through make)}"
fi

out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT

failed=()

# check_one <chart-dir> <values-file or empty>; returns non-zero on failure.
check_one() {
  local chart="$1" values="$2" label rendered
  local -a vargs=()
  if [ -n "$values" ]; then
    vargs=(-f "$values")
    label="$chart with $(basename "$values")"
  else
    label="$chart with chart defaults"
  fi
  rendered="$out/$(echo "$label" | tr -c 'A-Za-z0-9._-' '_').yaml"

  if [ "$mode" = template ]; then
    echo "--> helm lint --strict: $label"
    "$helm" lint --strict --kube-version "$KUBERNETES_VERSION" "$chart" ${vargs[@]+"${vargs[@]}"} || return 1
  fi
  echo "--> helm template: $label"
  "$helm" template ci "$chart" --kube-version "$KUBERNETES_VERSION" ${vargs[@]+"${vargs[@]}"} >"$rendered" || return 1

  if [ "$mode" = template ]; then
    echo "--> kubeconform -strict (Kubernetes $KUBERNETES_VERSION): $label"
    "$kubeconform" -strict -summary \
      -kubernetes-version "$KUBERNETES_VERSION" \
      -schema-location "$k8s_schemas" \
      -schema-location "$crd_schemas" \
      -cache "$KUBECONFORM_CACHE" \
      "$rendered" || return 1
  else
    echo "--> kube-linter requests/limits policy: $label"
    "$kube_linter" lint --config "$KUBE_LINTER_CONFIG" "$rendered" || return 1
  fi
}

for chart in "$@"; do
  chart="${chart%/}"
  echo "==> $mode: $chart"
  if [ ! -f "$chart/Chart.yaml" ]; then
    echo "ERROR: $chart has no Chart.yaml" >&2
    failed+=("$chart")
    continue
  fi
  if ! "$helm" dependency build "$chart"; then
    echo "ERROR: helm dependency build failed for $chart" >&2
    failed+=("$chart")
    continue
  fi
  shopt -s nullglob
  values_files=("$chart"/values*.yaml)
  shopt -u nullglob
  [ "${#values_files[@]}" -gt 0 ] || values_files=("")
  for values in "${values_files[@]}"; do
    if ! check_one "$chart" "$values"; then
      echo "ERROR: $mode check failed: $chart ${values:+with $(basename "$values")}" >&2
      failed+=("$chart${values:+ ($(basename "$values"))}")
    fi
  done
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "==> $mode: FAILED for ${#failed[@]} chart/values combination(s):" >&2
  printf '    %s\n' "${failed[@]}" >&2
  exit 1
fi
echo "==> $mode: all $# chart(s) passed"
