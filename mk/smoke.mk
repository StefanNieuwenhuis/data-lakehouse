# mk/smoke.mk - owner: test-engineer (ADR-0006).
# Targets: smoke-phase1 (later smoke-phaseN). Suites live in tests/smoke/.

.PHONY: smoke-phase1

# Stub: fails on purpose, so a gate can't pass before the smoke suite exists.
smoke-phase1:
	@echo "smoke-phase1: not implemented" >&2
	@exit 1
