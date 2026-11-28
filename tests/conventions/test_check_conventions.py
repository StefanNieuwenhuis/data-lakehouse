"""Fixture tests for `make check-conventions` (issue #26, ADR-0007).

The checker runs as a subprocess with TITLE and BRANCH in its environment,
exactly as `make check-conventions` and the CI `conventions` job run it.
The title is linted by commitlint, so title failures carry commitlint's rule
names ([type-enum], [scope-enum], ...); branch failures carry the wrapper's
([branch-prefix], ...). Test names map to the acceptance criteria: valid
titles and branches, each invalid form, errors that name the rule and list
what is allowed, lists read only from the conventions file, and no shell
injection through TITLE.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER = REPO_ROOT / "tests" / "conventions" / "check_conventions.py"
CONVENTIONS = REPO_ROOT / "docs" / "conventions.yaml"
CONV = yaml.safe_load(CONVENTIONS.read_text())


def run_check(title, branch, conventions=None):
    env = {k: v for k, v in os.environ.items() if k not in ("TITLE", "BRANCH")}
    env["TITLE"] = title
    env["BRANCH"] = branch
    cmd = [sys.executable, str(CHECKER)]
    if conventions is not None:
        cmd += ["--conventions", str(conventions)]
    proc = subprocess.run(
        cmd, env=env, capture_output=True, text=True, check=False, timeout=60
    )
    print(
        f"TITLE={title!r} BRANCH={branch!r} rc={proc.returncode}\n{proc.stdout}{proc.stderr}"
    )
    return proc


def assert_fails(proc, rule):
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert f"[{rule}]" in proc.stderr


# --- valid -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "branch"),
    [
        (
            "feat(storage): add SeaweedFS wrapper chart deployed by make deploy",
            "feat/7-seaweedfs-chart",
        ),
        (
            "fix(hooks): fail closed when the guard cannot parse a command",
            "fix/13-hook-fail-closed",
        ),
        (
            "docs(adr): record the Trino catalog decision",
            "chore/25-conventional-commits-and-branches",
        ),
        (
            "ci(ci): enforce conventions, lint Markdown, add issue forms",
            "chore/26-enforce-conventions-markdown-lint",
        ),
        ("feat(catalog)!: drop the legacy warehouse", "feat/40-drop-legacy-warehouse"),
        ("chore(deps): bump ruff to 0.17.6", "chore/41-bump-ruff-0-17-6"),
        ("refactor(tools): split board.sh lookups", "chore/42-split-board-lookups"),
    ],
)
def test_valid_title_and_branch_pass(title, branch):
    proc = run_check(title, branch)
    assert proc.returncode == 0, proc.stderr
    assert "check-conventions: passed" in proc.stdout


def test_every_type_maps_to_its_listed_prefix():
    for ctype, prefix in CONV["branch_prefixes"].items():
        proc = run_check(f"{ctype}(ci): do the thing", f"{prefix}26-do-the-thing")
        assert proc.returncode == 0, (ctype, proc.stderr)


# --- invalid titles (commitlint) ---------------------------------------------


def test_title_wrong_type_fails_and_lists_types():
    proc = run_check("feature(storage): add a chart", "feat/7-chart")
    assert_fails(proc, "type-enum")
    assert "type must be one of [" + ", ".join(CONV["types"]) + "]" in proc.stderr


def test_title_unknown_scope_fails_and_lists_scopes():
    proc = run_check("feat(lakehouse): add a chart", "feat/7-chart")
    assert_fails(proc, "scope-enum")
    assert "scope must be one of [" + ", ".join(CONV["scopes"]) + "]" in proc.stderr


def test_title_missing_scope_fails():
    assert_fails(run_check("feat: add a chart", "feat/7-chart"), "scope-empty")


def test_title_uppercase_summary_fails():
    assert_fails(
        run_check("feat(storage): Add a chart", "feat/7-chart"),
        "subject-lowercase-first",
    )


def test_title_summary_starting_with_proper_noun_fails():
    # ADR-0007: proper nouns keep their case, but the summary starts lowercase.
    assert_fails(
        run_check("feat(storage): SeaweedFS wrapper chart", "feat/7-chart"),
        "subject-lowercase-first",
    )


def test_title_uppercase_type_fails():
    assert_fails(run_check("Feat(storage): add a chart", "feat/7-chart"), "type-case")


def test_title_trailing_period_fails():
    assert_fails(
        run_check("feat(storage): add a chart.", "feat/7-chart"), "subject-full-stop"
    )


def test_title_breaking_bang_after_scope_passes():
    assert (
        run_check(
            "fix(hooks)!: block every helm uninstall", "fix/13-block-helm"
        ).returncode
        == 0
    )


@pytest.mark.parametrize(
    "title", ["feat!(storage): add a chart", "feat(storage) !: add a chart"]
)
def test_title_bang_in_wrong_place_fails(title):
    assert_fails(run_check(title, "feat/7-chart"), "type-empty")


@pytest.mark.parametrize(
    ("title", "rule"),
    [
        ("feat(storage):add a chart", "type-empty"),  # no space after the colon
        ("feat(storage)  add a chart", "type-empty"),  # no colon
        ("add a chart", "type-empty"),  # no type at all
        (" feat(storage): add a chart", "header-trim"),  # leading whitespace
        ("feat(storage): add a chart ", "header-trim"),  # trailing whitespace
        ("feat(storage):  add a chart", "subject-lowercase-first"),  # two spaces
        ("feat(storage): ", "subject-empty"),  # empty summary
    ],
)
def test_title_malformed_fails(title, rule):
    assert_fails(run_check(title, "feat/7-chart"), rule)


# --- invalid branches --------------------------------------------------------


def test_branch_unknown_prefix_fails_and_lists_prefixes():
    proc = run_check("feat(storage): add a chart", "feature/7-chart")
    assert_fails(proc, "branch-prefix")
    allowed = sorted(set(CONV["branch_prefixes"].values()))
    assert "Allowed prefixes: " + ", ".join(allowed) in proc.stderr


@pytest.mark.parametrize("prefix", ["docs/", "ci/", "test/", "build/"])
def test_branch_type_name_as_prefix_fails(prefix):
    # Only the mapped prefixes (feat/, fix/, chore/) exist as branch prefixes.
    assert_fails(run_check("chore(ci): tidy", f"{prefix}9-tidy"), "branch-prefix")


def test_branch_prefix_not_matching_type_fails_and_shows_map():
    proc = run_check("ci(ci): enforce conventions", "feat/26-enforce-conventions")
    assert_fails(proc, "branch-prefix-type")
    assert "'ci' needs prefix 'chore/'" in proc.stderr
    assert "ci -> chore/" in proc.stderr


def test_branch_fix_type_on_chore_prefix_fails():
    assert_fails(
        run_check("fix(hooks): fail closed", "chore/13-fail-closed"),
        "branch-prefix-type",
    )


def test_branch_uppercase_fails():
    assert_fails(
        run_check("feat(storage): add a chart", "feat/7-SeaweedFS-chart"),
        "branch-lowercase",
    )


def test_branch_double_hyphen_fails():
    assert_fails(
        run_check("feat(storage): add a chart", "feat/7-seaweedfs--chart"),
        "branch-slug",
    )


def test_branch_trailing_hyphen_fails():
    assert_fails(
        run_check("feat(storage): add a chart", "feat/7-seaweedfs-chart-"),
        "branch-slug",
    )


@pytest.mark.parametrize(
    "branch",
    [
        "feat/-7-chart",  # leading hyphen
        "feat/chart",  # no issue number
        "feat/7",  # no slug
        "feat/07-chart",  # leading zero in the issue number
        "feat/7-v1.2-chart",  # dot: ADR-0007 forbids dots
        "feat/7_chart",  # underscore
        "feat/7-chart/extra",  # nested path
        "feat/",  # nothing after the prefix
    ],
)
def test_branch_malformed_slug_fails(branch):
    assert_fails(run_check("feat(storage): add a chart", branch), "branch-slug")


def test_branch_without_prefix_fails():
    assert_fails(run_check("feat(storage): add a chart", "7-chart"), "branch-format")


def test_title_and_branch_errors_are_all_reported():
    proc = run_check("feature(nope): Add it.", "feature/7--x")
    for rule in (
        "type-enum",
        "scope-enum",
        "subject-lowercase-first",
        "subject-full-stop",
        "branch-prefix",
        "branch-slug",
    ):
        assert f"[{rule}]" in proc.stderr, rule
    assert proc.returncode == 1


# --- lists come only from docs/conventions.yaml ------------------------------


def test_lists_are_read_from_the_conventions_file(tmp_path):
    conv = {
        "types": ["spike"],
        "scopes": ["lab"],
        "branch_prefixes": {"spike": "spike/"},
    }
    path = tmp_path / "conventions.yaml"
    path.write_text(yaml.safe_dump(conv))
    assert (
        run_check("spike(lab): try a thing", "spike/3-try-a-thing", path).returncode
        == 0
    )
    proc = run_check("feat(storage): add a chart", "feat/7-chart", path)
    assert_fails(proc, "type-enum")
    assert "type must be one of [spike]" in proc.stderr
    assert "scope must be one of [lab]" in proc.stderr
    assert "Allowed prefixes: spike/." in proc.stderr


def test_conventions_file_with_unmapped_type_is_a_config_error(tmp_path):
    path = tmp_path / "conventions.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "types": ["feat", "fix"],
                "scopes": ["ci"],
                "branch_prefixes": {"feat": "feat/"},
            }
        )
    )
    proc = run_check("feat(ci): x", "feat/1-x", path)
    assert proc.returncode == 2
    assert "missing: ['fix']" in proc.stderr


def test_no_title_is_a_usage_error():
    proc = run_check("", "feat/7-chart")
    assert proc.returncode == 2
    assert "TITLE is not set" in proc.stderr


# --- through make, as CI calls it --------------------------------------------

MAKE = shutil.which("make")


def make_check(env_extra):
    env = {
        k: v for k, v in os.environ.items() if k not in ("TITLE", "BRANCH", "MAKEFLAGS")
    }
    env.update(env_extra)
    proc = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(REPO_ROOT), "check-conventions"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    print(f"{env_extra} rc={proc.returncode}\n{proc.stdout}{proc.stderr}")
    return proc


def test_make_check_conventions_passes_valid_env():
    proc = make_check({"TITLE": "feat(storage): add a chart", "BRANCH": "feat/7-chart"})
    assert proc.returncode == 0, proc.stderr
    assert "check-conventions: passed" in proc.stdout


def test_make_check_conventions_fails_invalid_env():
    proc = make_check({"TITLE": "Feature: Add a chart.", "BRANCH": "feature/7-chart"})
    assert proc.returncode != 0
    assert "check-conventions: FAILED" in proc.stderr


def test_make_check_conventions_defaults_branch_to_git_branch():
    # The worktree branch is not known here, so only check that the branch
    # line shows what git reports.
    git_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    proc = make_check({"TITLE": "feat(storage): add a chart"})
    assert f"branch: {git_branch}" in proc.stdout


def test_title_cannot_inject_shell(tmp_path):
    marker = tmp_path / "pwned"
    hostile = f'feat(ci): x"; touch {marker}; echo "$(touch {marker})`touch {marker}`'
    proc = make_check({"TITLE": hostile, "BRANCH": f"feat/1-x$(touch {marker})"})
    assert not marker.exists(), "TITLE or BRANCH was executed by the shell"
    assert proc.returncode != 0
