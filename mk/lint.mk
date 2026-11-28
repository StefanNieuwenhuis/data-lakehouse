# mk/lint.mk - owner: test-engineer (ADR-0006).
# Targets: lint, test, test-fixtures, check-conventions (check-title,
# check-branch), node-deps, install-lychee, install-jq (secrets-scan arrives
# with #16).
#
# Every Python tool runs through `uv run --locked`, with the exact versions
# pinned in pyproject.toml and uv.lock (ADR-0003), so CI and local runs match.
# `--locked` fails if uv.lock is out of date with pyproject.toml instead of
# silently re-locking.

UV     ?= uv
UV_RUN := $(UV) run --locked

.PHONY: lint test check-uv lint-yaml lint-python lint-sql lint-shell test-python \
        lint-markdown lint-links lint-links-external check-lychee install-lychee \
        install-jq check-jq check-conventions node-deps lint-workflows \
        check-title check-branch check-link-file test-fixtures

check-uv:
	@command -v $(UV) >/dev/null 2>&1 || { \
	  echo "ERROR: uv not found. Install the version pinned in pyproject.toml ([tool.uv] required-version)." >&2; \
	  exit 1; }

## lint: every linter; fails on the first one that reports a problem.
lint: lint-yaml lint-python lint-sql lint-shell lint-markdown lint-links lint-workflows lint-charts
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

# Every tracked or new (not ignored) *.sh file. shellcheck comes from the
# shellcheck-py pin in pyproject.toml, so CI and local runs use one version.
lint-shell: check-uv
	@echo "==> shellcheck (all *.sh files)"
	@files="$$(git ls-files --cached --others --exclude-standard -- '*.sh')"; \
	if [ -z "$$files" ]; then echo "shellcheck: no shell scripts"; exit 0; fi; \
	echo "$$files" | xargs $(UV_RUN) shellcheck

# --- GitHub workflows and issue forms ----------------------------------------
# actionlint (pinned through actionlint-py) checks the workflows, and runs the
# pinned shellcheck on their `run:` scripts. check-jsonschema validates the
# issue forms against the GitHub schemas it vendors (no network).
ISSUE_FORMS := $(filter-out .github/ISSUE_TEMPLATE/config.yml,$(wildcard .github/ISSUE_TEMPLATE/*.yml))
lint-workflows: check-uv
	@echo "==> actionlint (.github/workflows)"
	@$(UV_RUN) actionlint
	@echo "==> check-jsonschema (issue forms and issue template config)"
	@$(UV_RUN) check-jsonschema --builtin-schema vendor.github-issue-forms $(ISSUE_FORMS)
	@$(UV_RUN) check-jsonschema --builtin-schema vendor.github-issue-config .github/ISSUE_TEMPLATE/config.yml

# --- Markdown and links ------------------------------------------------------
# Markdown files: tracked or new (not ignored). graphify-out/ is left out:
# GRAPH_REPORT.md is generated and rewritten whole by `graphify update`, so a
# hand fix there would not survive the next rebuild.
MD_FILES = git ls-files --cached --others --exclude-standard -- '*.md' \
             | grep -v -e '^graphify-out/'
# The link check also skips tests/fixtures/: those files hold broken links on
# purpose, for the tests that prove lychee rejects them.
LINK_FILES = $(MD_FILES) | grep -v -e '^tests/fixtures/'

# pymarkdownlnt reads its config from [tool.pymarkdown] in pyproject.toml.
lint-markdown: check-uv
	@echo "==> pymarkdown scan (config: [tool.pymarkdown] in pyproject.toml)"
	@$(MD_FILES) | xargs $(UV_RUN) pymarkdown scan

# Internal links and anchors only: --offline skips every network URL, so this
# is deterministic and safe for the required `lint` job. External links are
# checked weekly by .github/workflows/links-external.yml.
lint-links: check-lychee
	@echo "==> lychee --offline (internal links and anchors in Markdown)"
	@$(LINK_FILES) | xargs $(LYCHEE) $(LYCHEE_FLAGS) --offline

# Network check of external links. Not part of `lint`: run by the scheduled
# links-external workflow, or by hand.
lint-links-external: check-lychee
	@echo "==> lychee (external links in Markdown)"
	@$(LINK_FILES) | xargs $(LYCHEE) $(LYCHEE_FLAGS) --max-retries 3 --timeout 30

# --- Pinned binaries: lychee, jq ---------------------------------------------
# Not Python, so not in uv.lock. Installed by exact version from the upstream
# GitHub release and verified against the sha256 pinned here (copied from the
# release's own checksum assets). CI runs `make install-lychee` and
# `make install-jq`; locally, run the same target or install the same version.
# The download goes to a fresh mktemp directory; only the named files in it are
# removed afterwards.
INSTALL_DIR ?= $(HOME)/.local/bin
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
PLATFORM := $(UNAME_S)-$(UNAME_M)

LYCHEE         ?= lychee
LYCHEE_VERSION := 0.24.2
LYCHEE_FLAGS   := --no-progress --include-fragments
LYCHEE_TARGET_Linux-x86_64  := x86_64-unknown-linux-gnu
LYCHEE_TARGET_Linux-aarch64 := aarch64-unknown-linux-gnu
LYCHEE_TARGET_Darwin-x86_64 := x86_64-apple-darwin
LYCHEE_TARGET_Darwin-arm64  := aarch64-apple-darwin
LYCHEE_SHA256_x86_64-unknown-linux-gnu  := 1f4e0ef7f6554a6ed33dd7ac144fb2e1bbed98598e7af973042fc5cd43951c9a
LYCHEE_SHA256_aarch64-unknown-linux-gnu := 91a7bd65685da41b90ccb9bc867a3d649a7818042dae04ff405e55a25bddee4c
LYCHEE_SHA256_x86_64-apple-darwin       := 887503a9cff667d322b8d0892b40bf49976eb9507af8483220a3706cdad55978
LYCHEE_SHA256_aarch64-apple-darwin      := c9d3740ea2d891854d37116c9fba840f37b6e7c89d330e7db84ac333631c4977
LYCHEE_TARGET := $(LYCHEE_TARGET_$(PLATFORM))
LYCHEE_SHA256 := $(LYCHEE_SHA256_$(LYCHEE_TARGET))
LYCHEE_URL    := https://github.com/lycheeverse/lychee/releases/download/lychee-v$(LYCHEE_VERSION)/lychee-$(LYCHEE_TARGET).tar.gz

JQ         ?= jq
JQ_VERSION := 1.8.2
JQ_ASSET_Linux-x86_64  := jq-linux-amd64
JQ_ASSET_Linux-aarch64 := jq-linux-arm64
JQ_ASSET_Darwin-x86_64 := jq-macos-amd64
JQ_ASSET_Darwin-arm64  := jq-macos-arm64
JQ_SHA256_jq-linux-amd64 := b1c22172dd303f3be49e935aa56aa48a8b7a46e0bc838b4997d3bb451495870f
JQ_SHA256_jq-linux-arm64 := 8b85c817833814ddca00a144c33705546355afccf0cf39b188f3cdb48b852309
JQ_SHA256_jq-macos-amd64 := e94b266e3c26690550006abe63152b782280f4e14374accdf04cbde844f00bc0
JQ_SHA256_jq-macos-arm64 := 2d75340ba57a4b4b4c8708a21c2dc8e958a48aaa8bba13b27f77f6e4c0eca07e
JQ_ASSET  := $(JQ_ASSET_$(PLATFORM))
JQ_SHA256 := $(JQ_SHA256_$(JQ_ASSET))
JQ_URL    := https://github.com/jqlang/jq/releases/download/jq-$(JQ_VERSION)/$(JQ_ASSET)

# Reads "<sha256>  <file>" lines on stdin and fails on any mismatch.
SHA256_CHECK = if command -v sha256sum >/dev/null 2>&1; then sha256sum -c -; else shasum -a 256 -c -; fi

LYCHEE_HINT = Install lychee $(LYCHEE_VERSION) with 'make install-lychee' (puts it in $(INSTALL_DIR), \
which must be on PATH), or point LYCHEE= at a lychee $(LYCHEE_VERSION) binary.

check-lychee:
	@command -v $(LYCHEE) >/dev/null 2>&1 || { \
	  echo "ERROR: lychee not found on PATH. $(LYCHEE_HINT)" >&2; exit 1; }
	@v="$$($(LYCHEE) --version 2>/dev/null)"; \
	if [ "$$v" != "lychee $(LYCHEE_VERSION)" ]; then \
	  echo "ERROR: wrong lychee version: '$$v' (need lychee $(LYCHEE_VERSION)). $(LYCHEE_HINT)" >&2; exit 1; fi

install-lychee:
	@set -eu; \
	if [ -z "$(LYCHEE_SHA256)" ]; then \
	  echo "ERROR: no pinned lychee $(LYCHEE_VERSION) build for $(PLATFORM)" >&2; exit 1; fi; \
	tmp="$$(mktemp -d)"; \
	echo "==> download $(LYCHEE_URL)"; \
	curl -fsSL --proto '=https' --retry 3 -o "$$tmp/lychee.tar.gz" "$(LYCHEE_URL)"; \
	(cd "$$tmp" && echo "$(LYCHEE_SHA256)  lychee.tar.gz" | { $(SHA256_CHECK); }); \
	tar -xzf "$$tmp/lychee.tar.gz" -C "$$tmp" "lychee-$(LYCHEE_TARGET)/lychee"; \
	mkdir -p "$(INSTALL_DIR)"; \
	install -m 0755 "$$tmp/lychee-$(LYCHEE_TARGET)/lychee" "$(INSTALL_DIR)/lychee"; \
	rm -f "$$tmp/lychee.tar.gz" "$$tmp/lychee-$(LYCHEE_TARGET)/lychee"; \
	rmdir "$$tmp/lychee-$(LYCHEE_TARGET)" "$$tmp"; \
	echo "==> installed $$("$(INSTALL_DIR)/lychee" --version) to $(INSTALL_DIR)"

install-jq:
	@set -eu; \
	if [ -z "$(JQ_SHA256)" ]; then \
	  echo "ERROR: no pinned jq $(JQ_VERSION) build for $(PLATFORM)" >&2; exit 1; fi; \
	tmp="$$(mktemp -d)"; \
	echo "==> download $(JQ_URL)"; \
	curl -fsSL --proto '=https' --retry 3 -o "$$tmp/jq" "$(JQ_URL)"; \
	(cd "$$tmp" && echo "$(JQ_SHA256)  jq" | { $(SHA256_CHECK); }); \
	mkdir -p "$(INSTALL_DIR)"; \
	install -m 0755 "$$tmp/jq" "$(INSTALL_DIR)/jq"; \
	rm -f "$$tmp/jq"; \
	rmdir "$$tmp"; \
	echo "==> installed $$("$(INSTALL_DIR)/jq" --version) to $(INSTALL_DIR)"

# CI runs this after install-jq, to prove the jq on PATH is the pinned one and
# not the runner image's. Locally any jq on PATH works for `make test`.
check-jq:
	@v="$$($(JQ) --version 2>/dev/null)"; \
	if [ "$$v" != "jq-$(JQ_VERSION)" ]; then \
	  echo "ERROR: jq on PATH is '$$v' (need jq-$(JQ_VERSION)). Run 'make install-jq'." >&2; exit 1; fi; \
	echo "==> $$v at $$(command -v $(JQ))"

# --- Naming conventions (ADR-0007) -------------------------------------------
# Validates a PR title and a branch name against docs/conventions.yaml, with
# two pinned OSS tools and no custom checker:
#   check-title   commitlint        ($(CONVENTIONS_DIR)/commitlint.config.mjs)
#   check-branch  branch-name-lint  ($(CONVENTIONS_DIR)/branch-name-lint.config.js)
# Both configs read the lists from docs/conventions.yaml at runtime.
#   make check-conventions TITLE='feat(storage): add x' [BRANCH=feat/7-x]
# BRANCH defaults to the current git branch. TITLE and BRANCH reach the tools
# only through the environment ("$$TITLE" in the recipe is a quoted shell
# variable, never make text), so a hostile title can't inject shell. CI passes
# them through `env:`.
#
# The npm packages are pinned in $(CONVENTIONS_DIR)/package.json and
# package-lock.json (npm verifies each package's integrity hash). Node and npm
# come from the nodejs-wheel pin in the uv dev group.
CONVENTIONS_DIR := tests/conventions
NODE_STAMP      := $(CONVENTIONS_DIR)/node_modules/.package-lock.json
NODE_BIN        := node_modules/.bin

node-deps: $(NODE_STAMP)
$(NODE_STAMP): $(CONVENTIONS_DIR)/package.json $(CONVENTIONS_DIR)/package-lock.json
	@$(MAKE) --no-print-directory check-uv
	@echo "==> npm ci ($(CONVENTIONS_DIR)/package-lock.json)"
	@cd $(CONVENTIONS_DIR) && $(UV_RUN) npm ci --ignore-scripts --no-audit --no-fund --loglevel=error
	@touch $@

# Make expands a recursive variable when it exports it, so a command-line
# TITLE='$(shell ...)' would run. $(value ...) takes the raw text, and := keeps
# it unexpanded; override applies it to command-line values too.
override TITLE  := $(value TITLE)
override BRANCH := $(value BRANCH)
export TITLE BRANCH

check-title: node-deps
	@if [ -z "$$TITLE" ]; then \
	  echo "ERROR: TITLE is not set. Usage: make check-conventions TITLE='type(scope): summary' [BRANCH=...]" >&2; exit 2; fi
	@echo "==> commitlint: $$TITLE"
	@cd $(CONVENTIONS_DIR) && printf '%s' "$$TITLE" \
	  | $(UV_RUN) $(NODE_BIN)/commitlint --config commitlint.config.mjs --color=false

check-branch: node-deps
	@echo "==> branch-name-lint: $${BRANCH:-$$(git rev-parse --abbrev-ref HEAD) (current git branch)}"
	@cd $(CONVENTIONS_DIR) && $(UV_RUN) $(NODE_BIN)/branch-name-lint branch-name-lint.config.js

# Runs both checks, so one run reports every problem, and fails if either fails.
check-conventions: node-deps
	@rc=0; \
	$(MAKE) --no-print-directory check-title || rc=1; \
	$(MAKE) --no-print-directory check-branch || rc=1; \
	if [ $$rc -ne 0 ]; then \
	  echo "check-conventions: FAILED (rules: docs/adr/0007-conventional-commits-and-branches.md)" >&2; exit 1; fi; \
	echo "==> check-conventions: passed"

## test: unit and data tests, plus chart tests.
test: test-python test-fixtures test-charts
	@echo "==> test: all checks passed"

# tests/ includes tests/tools/ (the tools/board.sh tests, which stub gh on PATH).
# pytest exits 5 when it collects no tests. That is a pass here: the suite is
# allowed to be empty until the first tests land. Any other non-zero code fails.
test-python: check-uv
	@echo "==> pytest (testpaths: tests, .claude/hooks/tests)"
	@$(UV_RUN) pytest; rc=$$?; \
	if [ $$rc -eq 5 ]; then echo "pytest: no tests collected, treating as pass"; exit 0; fi; \
	exit $$rc

# One lychee --offline run on one file, with the same flags as lint-links.
# The file comes through the environment (LINK_FILE), like TITLE and BRANCH.
check-link-file: check-lychee
	@if [ -z "$$LINK_FILE" ]; then echo "ERROR: LINK_FILE is not set" >&2; exit 2; fi
	@$(LYCHEE) $(LYCHEE_FLAGS) --offline "$$LINK_FILE"

# Fixture data files run through the real tools; each case must pass or fail
# as listed (tests/fixtures/expect.sh). Covers every title, branch and link
# case of #26, plus an alternative list file to prove the configs read the
# lists from the file they are given.
FIXTURES := tests/fixtures/conventions
EXPECT   := tests/fixtures/expect.sh
ALT_CONV := CONVENTIONS_FILE=$(CURDIR)/$(FIXTURES)/alt/conventions.yaml
test-fixtures: node-deps check-lychee
	@echo "==> fixtures: titles (commitlint)"
	@$(EXPECT) title pass $(FIXTURES)/titles-valid.txt
	@$(EXPECT) title fail $(FIXTURES)/titles-invalid.txt
	@$(EXPECT) title-arg pass $(FIXTURES)/titles-make-args.txt
	@echo "==> fixtures: branches (branch-name-lint)"
	@$(EXPECT) branch pass $(FIXTURES)/branches-valid.txt
	@$(EXPECT) branch fail $(FIXTURES)/branches-invalid.txt
	@echo "==> fixtures: lists come only from the given list file"
	@$(ALT_CONV) $(EXPECT) title pass $(FIXTURES)/alt/titles-valid.txt
	@$(ALT_CONV) $(EXPECT) title fail $(FIXTURES)/alt/titles-invalid.txt
	@$(ALT_CONV) $(EXPECT) branch pass $(FIXTURES)/alt/branches-valid.txt
	@$(ALT_CONV) $(EXPECT) branch fail $(FIXTURES)/alt/branches-invalid.txt
	@echo "==> fixtures: internal links (lychee --offline)"
	@$(EXPECT) link pass $(FIXTURES)/links-valid.txt
	@$(EXPECT) link fail $(FIXTURES)/links-invalid.txt
