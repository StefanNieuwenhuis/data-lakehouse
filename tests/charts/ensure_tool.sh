#!/usr/bin/env bash
# ensure_tool.sh - print the path of a pinned binary tool (helm, kubeconform,
# kube-linter).
# Owner: test-engineer. Called by tests/charts/chart_check.sh; the versions,
# download URLs and SHA-256 digests are pinned in mk/helm.mk (ADR-0003).
#
# Usage: ensure_tool.sh <helm|kubeconform|kube-linter>
#
# Resolution order:
#   1. $TOOLS_DIR/<tool>, if it reports exactly the pinned version;
#   2. <tool> on PATH, if it reports exactly the pinned version;
#   3. otherwise download the pinned release into $TOOLS_DIR (repo-local,
#      gitignored), verify it against the pinned SHA-256 and re-check the version.
#      Set TOOLS_DOWNLOAD=0 to disable this step and fail instead.
#
# Any failure exits non-zero with an "ERROR:" line naming the tool, the version
# found and the version required. Progress goes to stderr; stdout is the path.
set -euo pipefail

tool="${1:?usage: ensure_tool.sh <helm|kubeconform|kube-linter>}"
: "${TOOLS_DIR:?TOOLS_DIR is not set (run through make)}"
: "${TOOLS_OS:?TOOLS_OS is not set (run through make)}"
: "${TOOLS_ARCH:?TOOLS_ARCH is not set (run through make)}"

die() { echo "ERROR: $*" >&2; exit 1; }

case "$tool" in
  helm)
    want="${HELM_VERSION:?HELM_VERSION is not set}"
    url="https://get.helm.sh/helm-${want}-${TOOLS_OS}-${TOOLS_ARCH}.tar.gz"
    member="${TOOLS_OS}-${TOOLS_ARCH}/helm"
    sha_var="HELM_SHA256_${TOOLS_OS}_${TOOLS_ARCH}"
    ;;
  kubeconform)
    want="${KUBECONFORM_VERSION:?KUBECONFORM_VERSION is not set}"
    url="https://github.com/yannh/kubeconform/releases/download/${want}/kubeconform-${TOOLS_OS}-${TOOLS_ARCH}.tar.gz"
    member="kubeconform"
    sha_var="KUBECONFORM_SHA256_${TOOLS_OS}_${TOOLS_ARCH}"
    ;;
  kube-linter)
    want="${KUBE_LINTER_VERSION:?KUBE_LINTER_VERSION is not set}"
    # Release assets are named kube-linter-<os> (amd64) and kube-linter-<os>_arm64.
    suffix="$TOOLS_OS"
    [ "$TOOLS_ARCH" = amd64 ] || suffix="${TOOLS_OS}_${TOOLS_ARCH}"
    url="https://github.com/stackrox/kube-linter/releases/download/${want}/kube-linter-${suffix}.tar.gz"
    member="kube-linter"
    sha_var="KUBE_LINTER_SHA256_${TOOLS_OS}_${TOOLS_ARCH}"
    ;;
  *) die "unknown tool '$tool' (expected helm, kubeconform or kube-linter)" ;;
esac

# Prints the version a binary reports, or nothing if it can't run.
version_of() {
  case "$tool" in
    helm) "$1" version --template '{{.Version}}' 2>/dev/null || true ;;
    kubeconform) "$1" -v 2>/dev/null | head -n1 || true ;;
    # kube-linter prints the version without the leading "v" of its tag.
    kube-linter) v="$("$1" version 2>/dev/null | head -n1 || true)"; [ -z "$v" ] || echo "v$v" ;;
  esac
}

local_bin="$TOOLS_DIR/$tool"
if [ -x "$local_bin" ] && [ "$(version_of "$local_bin")" = "$want" ]; then
  echo "$local_bin"; exit 0
fi

found="not installed"
if path_bin="$(command -v "$tool" 2>/dev/null)"; then
  have="$(version_of "$path_bin")"
  if [ "$have" = "$want" ]; then
    echo "$path_bin"; exit 0
  fi
  found="${have:-unknown version} at $path_bin"
fi

if [ "${TOOLS_DOWNLOAD:-1}" = "0" ]; then
  die "$tool $want is required, found: $found. Install $tool $want, or run without TOOLS_DOWNLOAD=0 to fetch the pinned release into $TOOLS_DIR."
fi

sha="${!sha_var:-}"
[ -n "$sha" ] || die "$tool $want is required, found: $found. No pinned SHA-256 for ${TOOLS_OS}/${TOOLS_ARCH} in mk/helm.mk ($sha_var); install $tool $want manually."

echo "==> $tool $want required, found: $found. Fetching the pinned release into $TOOLS_DIR" >&2
command -v curl >/dev/null 2>&1 || die "curl not found; it is needed to fetch $tool $want."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL --retry 3 -o "$tmp/archive.tar.gz" "$url" || die "download of $tool $want failed: $url"

if command -v sha256sum >/dev/null 2>&1; then
  got="$(sha256sum "$tmp/archive.tar.gz" | cut -d' ' -f1)"
else
  got="$(shasum -a 256 "$tmp/archive.tar.gz" | cut -d' ' -f1)"
fi
[ "$got" = "$sha" ] || die "$tool $want checksum mismatch for $url: expected $sha, got $got."

tar -xzf "$tmp/archive.tar.gz" -C "$tmp" "$member" || die "could not extract $member from $url"
mkdir -p "$TOOLS_DIR"
install -m 0755 "$tmp/$member" "$local_bin"

have="$(version_of "$local_bin")"
[ "$have" = "$want" ] || die "$tool fetched from $url reports '$have', expected $want."
echo "==> $tool $want installed at $local_bin (sha256 verified)" >&2
echo "$local_bin"
