#!/usr/bin/env bash
# infra/minikube/cluster-up.sh - owner: platform-engineer (ADR-0006, #5).
#
# Creates or starts minikube profile $PROFILE with the pinned versions and
# sizing from infra/minikube/versions.mk (passed in by mk/cluster.mk), then
# applies the Phase 1 namespaces and quotas. Idempotent: if the profile is
# already running, minikube is not touched, and kubectl apply reports the
# manifests as unchanged.
set -euo pipefail

: "${PROFILE:?}" "${DRIVER:?}" "${RUNTIME:?}" "${CPUS:?}" "${MEMORY:?}" "${DISK_SIZE:?}"
: "${CNI:?}" "${K8S_VERSION:?}" "${CALICO_VERSION:?}" "${REQUIRED_MINIKUBE_VERSION:?}"

here="$(cd "$(dirname "$0")" && pwd)"
enc="$here/etcd-encryption.sh"
kc=(kubectl --context "$PROFILE")

log() { echo "==> $*"; }
die() {
  echo "ERROR: $*" >&2
  exit 1
}

# 1. Tool pin.
mk_version="$(minikube version --short 2>/dev/null || true)"
[ "$mk_version" = "$REQUIRED_MINIKUBE_VERSION" ] ||
  die "minikube $REQUIRED_MINIKUBE_VERSION required, found '${mk_version:-none}'"

# 2. etcd encryption config (generated once, never rotated).
"$enc" ensure
node_path="$("$enc" node-path)"

# 3. Create or start the profile, unless it already runs.
status="$(minikube status -p "$PROFILE" --format '{{.Host}}/{{.Kubelet}}/{{.APIServer}}' 2>/dev/null || true)"
# A missing profile prints a hint instead of a state.
case "$status" in */*/*) ;; *) status="" ;; esac
if [ "$status" = "Running/Running/Running" ]; then
  log "minikube profile $PROFILE already running: nothing to start"
else
  log "minikube profile $PROFILE state '${status:-absent}': starting"
  "$enc" stage
  trap '"$enc" unstage' EXIT
  minikube start -p "$PROFILE" \
    --driver="$DRIVER" \
    --container-runtime="$RUNTIME" \
    --kubernetes-version="$K8S_VERSION" \
    --cpus="$CPUS" \
    --memory="$MEMORY" \
    --disk-size="$DISK_SIZE" \
    --cni="$CNI" \
    --extra-config="apiserver.encryption-provider-config=$node_path"
  "$enc" unstage
  trap - EXIT
fi

# 4. The running cluster must match the pins; a mismatch needs a new cluster,
# which is the user's call (minikube delete is not run here).
server_version="$("${kc[@]}" version -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["serverVersion"]["gitVersion"])')"
[ "$server_version" = "$K8S_VERSION" ] ||
  die "profile $PROFILE runs Kubernetes $server_version, pinned $K8S_VERSION; recreate the cluster"

apiserver_cmd="$("${kc[@]}" -n kube-system get pod -l component=kube-apiserver -o jsonpath='{.items[0].spec.containers[0].command}')"
case "$apiserver_cmd" in
  *"--encryption-provider-config=$node_path"*) log "kube-apiserver: encryption-provider-config=$node_path" ;;
  *) die "kube-apiserver runs without --encryption-provider-config=$node_path" ;;
esac

# 5. Node and Calico readiness, and the Calico pin.
"${kc[@]}" wait --for=condition=Ready node --all --timeout=300s
"${kc[@]}" -n kube-system rollout status daemonset/calico-node --timeout=300s
"${kc[@]}" -n kube-system rollout status deployment/calico-kube-controllers --timeout=300s
calico_image="$("${kc[@]}" -n kube-system get daemonset calico-node -o jsonpath='{.spec.template.spec.containers[0].image}')"
case "$calico_image" in
  *":$CALICO_VERSION" | *":$CALICO_VERSION@"*) log "calico-node image $calico_image (pinned $CALICO_VERSION)" ;;
  *) die "calico-node image is $calico_image, pinned $CALICO_VERSION" ;;
esac

# 6. Namespaces and quotas (ADR-0006), no LimitRange.
"${kc[@]}" apply -f "$here/namespaces.yaml"
"${kc[@]}" apply -f "$here/quotas.yaml"
for ns in lh-storage lh-catalog lh-ops; do
  n="$("${kc[@]}" -n "$ns" get limitrange -o name | wc -l | tr -d ' ')"
  [ "$n" = "0" ] || die "namespace $ns has a LimitRange; ADR-0006 forbids defaults"
done
log "cluster-up: profile $PROFILE ready (Kubernetes $K8S_VERSION, Calico $CALICO_VERSION)"
