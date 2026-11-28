#!/usr/bin/env bash
# infra/minikube/verify-etcd-encryption.sh - owner: platform-engineer (ADR-0006, #5).
#
# Writes a probe Secret holding a random dummy marker (never a real
# credential), reads its raw etcd entry with etcdctl inside the etcd static
# pod on the node, and asserts:
#   - the value starts with k8s:enc:secretbox:v1:
#   - the dummy plaintext does not appear in it.
# Then deletes the probe. Prints only PASS or FAIL and the prefix; the raw
# entry is kept in a 0600 temp file that is removed on exit, never printed.
set -euo pipefail

: "${PROFILE:?}"
kc=(kubectl --context "$PROFILE")
PREFIX="k8s:enc:secretbox:v1:"
ns="default"
name="lh-etcd-probe-$(date +%s)-$$"
marker="lh-dummy-probe-$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n')"
raw="$(mktemp)"
chmod 600 "$raw"

cleanup() {
  rm -f "$raw"
  "${kc[@]}" -n "$ns" delete secret "$name" --ignore-not-found >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  echo "verify-etcd-encryption: FAIL ($*)"
  exit 1
}

"${kc[@]}" -n "$ns" create secret generic "$name" --from-literal=probe="$marker" >/dev/null ||
  fail "could not create probe Secret"

etcd_pod="$("${kc[@]}" -n kube-system get pod -l component=etcd -o jsonpath='{.items[0].metadata.name}')"
[ -n "$etcd_pod" ] || fail "no etcd pod found"

certs=/var/lib/minikube/certs/etcd
"${kc[@]}" -n kube-system exec "$etcd_pod" -- etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert="$certs/ca.crt" \
  --cert="$certs/healthcheck-client.crt" \
  --key="$certs/healthcheck-client.key" \
  get "/registry/secrets/$ns/$name" --print-value-only >"$raw" 2>/dev/null ||
  fail "etcdctl get failed"

[ -s "$raw" ] || fail "empty etcd entry"
got="$(LC_ALL=C head -c "${#PREFIX}" "$raw")"
[ "$got" = "$PREFIX" ] || fail "entry does not start with $PREFIX"
if LC_ALL=C grep -aqF "$marker" "$raw"; then
  fail "dummy plaintext found in etcd entry"
fi
echo "verify-etcd-encryption: PASS (prefix $PREFIX)"
