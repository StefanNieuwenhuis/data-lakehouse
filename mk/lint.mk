# mk/lint.mk - owner: test-engineer (ADR-0006).
# Targets: lint, test (secrets-scan arrives with #16).
#
# Every Python tool runs through `uv run --locked`, with the exact versions
# pinned in pyproject.toml and uv.lock (ADR-0003), so CI and local runs match.
# `--locked` fails if uv.lock is out of date with pyproject.toml instead of
# silently re-locking.

UV     ?= uv
UV_RUN := $(UV) run --locked

.PHONY: lint test check-uv lint-yaml lint-python lint-sql test-python

check-uv:
	@command -v $(UV) >/dev/null 2>&1 || { \
	  echo "ERROR: uv not found. Install the version pinned in pyproject.toml ([tool.uv] required-version)." >&2; \
	  exit 1; }

## lint: every linter; fails on the first one that reports a problem.
lint: lint-yaml lint-python lint-sql lint-charts
	@echo "==> lint: all checks passed"

lint-yaml: check-uv
	@echo "==> yamllint (strict, repo .yamllint)"
	@$(UV_RUN) yamllint -s .

lint-python: check-uv
	@echo "==> ruff check"
	@$(UV_RUN) ruff check .
	@echo "==> ruff format --check"
	@$(UV_RUN) ruff format --check .

lint-sql: check-uv
	@echo "==> sqlfluff lint (root .sqlfluff, dialect trino)"
	@$(UV_RUN) sqlfluff lint .

## test: unit and data tests, plus chart tests.
test: test-python test-charts
	@echo "==> test: all checks passed"

# pytest exits 5 when it collects no tests. That is a pass here: the suite is
# allowed to be empty until the first tests land. Any other non-zero code fails.
test-python: check-uv
	@echo "==> pytest (testpaths: tests, .claude/hooks/tests)"
	@$(UV_RUN) pytest; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "pytest: no tests collected, treating as pass"; exit 0; fi; \
	exit $$rc
