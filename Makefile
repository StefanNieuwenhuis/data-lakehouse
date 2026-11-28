# Lakehouse Makefile: the single entry point for hooks, CI and slash commands.
# Owner: test-engineer. This file only includes the per-area files below; put
# targets in the file of the area that owns them (ADR-0006).
#
#   File            Owner              Targets
#   mk/lint.mk      test-engineer      lint, test, secrets-scan
#   mk/helm.mk      test-engineer      helm-template, lint-charts, test-charts
#   mk/smoke.mk     test-engineer      smoke-phase1 (later smoke-phaseN)
#   mk/cluster.mk   platform-engineer  cluster-up, cluster-down, verify-etcd-encryption
#   mk/deploy.mk    platform-engineer  secrets, secrets-verify, deploy, undeploy, bootstrap

include mk/lint.mk
include mk/helm.mk
include mk/cluster.mk
include mk/deploy.mk
include mk/smoke.mk
