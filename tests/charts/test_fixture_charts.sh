#!/usr/bin/env bash
# test_fixture_charts.sh - prove the chart checks catch what they claim to (#2).
# Owner: test-engineer. Run by `make test-charts` (through `make test`), which
# sets FIXTURES_DIR, CHART_CHECK and the tool pins.
#
# Each case runs one chart_check.sh mode on one fixture chart and asserts the
# exit status and, for failures, the reason, so a fixture can't "fail" for an
# unrelated cause (a typo, a download error) and still count as caught.
# Exits non-zero if any case does not behave as expected.
set -uo pipefail

: "${FIXTURES_DIR:?FIXTURES_DIR is not set (run through make)}"
: "${CHART_CHECK:?CHART_CHECK is not set (run through make)}"

log="$(mktemp)"
trap 'rm -f "$log"' EXIT
passed=0
failed=0

# expect <case-name> <template|policy> <fixture> <pass|fail> [expected-output ...]
expect() {
  local name="$1" mode="$2" fixture="$3" want="$4" got rc needle ok=1
  shift 4
  "$CHART_CHECK" "$mode" "$FIXTURES_DIR/$fixture" >"$log" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then got=pass; else got=fail; fi
  if [ "$got" != "$want" ]; then
    echo "FAIL $name: expected $mode on $fixture to $want, but it did $got (exit $rc)"
    ok=0
  fi
  for needle in "$@"; do
    if ! grep -qF -- "$needle" "$log"; then
      echo "FAIL $name: output of $mode on $fixture lacks: $needle"
      ok=0
    fi
  done
  if [ "$ok" -eq 1 ]; then
    echo "ok   $name"
    passed=$((passed + 1))
  else
    echo "---- output of $CHART_CHECK $mode $FIXTURES_DIR/$fixture:"
    sed 's/^/     /' "$log"
    failed=$((failed + 1))
  fi
}

echo "==> test-charts: fixture charts in $FIXTURES_DIR"

# AC: a valid fixture passes (every values file, built-in and CRD-backed kinds).
expect valid_fixture_passes_helm_template template valid pass \
  "with values.yaml" "with values-dev.yaml" "Valid: 4, Invalid: 0, Errors: 0, Skipped: 0"
expect valid_fixture_passes_lint_charts_policy policy valid pass \
  "No lint errors found!"

# AC: a schema error fails kubeconform.
expect schema_error_fails_helm_template template broken-schema fail \
  "Deployment ci-web is invalid" "at '/spec/replicas': got string"

# AC: missing limits fail the lint-charts policy. The fixture is schema-valid,
# so it is the policy, not kubeconform, that catches it.
# It also covers a Job container and a CronJob init container.
expect missing_limits_is_schema_valid template broken-missing-limits pass \
  "Valid: 3, Invalid: 0"
expect missing_limits_fails_lint_charts_policy policy broken-missing-limits fail \
  'ci-nolimits batch/v1, Kind=Job) container "run" has cpu limit 0' \
  'ci-nolimits batch/v1, Kind=Job) container "run" has memory limit 0' \
  'ci-nightly batch/v1, Kind=CronJob) container "prepare" has memory limit 0' \
  "found 3 lint errors"

# AC: an unknown field on a CRD-backed resource fails kubeconform, using the
# schema from the pinned datreeio CRDs-catalog.
expect crd_unknown_field_fails_helm_template template broken-crd-unknown-field fail \
  "datreeio/CRDs-catalog/${CRDS_CATALOG_SHA:-}/postgresql.cnpg.io/cluster_v1.json" \
  "additional properties 'unknownField' not allowed"

# AC: every values*.yaml is checked, not only values.yaml.
expect dev_values_schema_error_fails_helm_template template broken-dev-values fail \
  "template check failed: $FIXTURES_DIR/broken-dev-values with values-dev.yaml" \
  "FAILED for 1 chart/values combination(s)"

# AC: missing schemas are errors, never skipped, so a kind without a schema fails.
expect missing_schema_fails_helm_template template broken-missing-schema fail \
  "could not find schema for Widget"

echo "==> test-charts: $passed passed, $failed failed"
[ "$failed" -eq 0 ]
