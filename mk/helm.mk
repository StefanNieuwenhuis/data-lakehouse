# mk/helm.mk - owner: test-engineer (ADR-0006).
# Targets: helm-template, plus the chart checks called by `lint` and `test`.
#
# Stubs: #2 implements these (helm lint, helm template per values file,
# kubeconform -strict, requests/limits policy, fixture charts).

.PHONY: helm-template lint-charts test-charts

helm-template:
	@echo "==> helm-template: stub, implemented in #2"

lint-charts:
	@echo "==> lint-charts: stub, implemented in #2"

test-charts:
	@echo "==> test-charts: stub, implemented in #2"
