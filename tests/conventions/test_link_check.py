"""Fixture tests for `make lint-links` (lychee --offline, issue #26).

Each test runs the real `lint-links` target on one fixture file under
tests/fixtures/markdown/, so it uses the same lychee flags as `make lint`.
lychee must be installed at the pinned version (`make install-lychee`); a
missing or wrong lychee fails these tests instead of skipping them.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path("tests") / "fixtures" / "markdown"
MAKE = shutil.which("make")


def lint_links(fixture):
    path = FIXTURES / fixture
    assert (REPO_ROOT / path).is_file(), path
    env = {k: v for k, v in os.environ.items() if k != "MAKEFLAGS"}
    proc = subprocess.run(
        [
            MAKE,
            "--no-print-directory",
            "-C",
            str(REPO_ROOT),
            "lint-links",
            f"LINK_FILES=echo {path}",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    print(
        f"make lint-links on {path}: rc={proc.returncode}\n{proc.stdout}{proc.stderr}"
    )
    return proc


@pytest.fixture(scope="module", autouse=True)
def lychee_installed():
    env = {k: v for k, v in os.environ.items() if k != "MAKEFLAGS"}
    proc = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(REPO_ROOT), "check-lychee"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(
            f"lychee is required for the link-check tests:\n{proc.stderr}",
            pytrace=False,
        )


def test_valid_internal_link_and_anchor_pass():
    proc = lint_links("valid-internal-link.md")
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_broken_internal_link_is_rejected():
    proc = lint_links("broken-internal-link.md")
    assert proc.returncode != 0
    assert "does-not-exist.md" in proc.stdout + proc.stderr


def test_broken_anchor_is_rejected():
    proc = lint_links("broken-anchor.md")
    assert proc.returncode != 0
    assert "no-such-heading" in proc.stdout + proc.stderr


def test_lint_links_skips_the_broken_fixtures(tmp_path):
    # The default file list must leave tests/fixtures/ out, or `make lint`
    # would fail on the files that are broken on purpose.
    env = {k: v for k, v in os.environ.items() if k != "MAKEFLAGS"}
    proc = subprocess.run(
        [MAKE, "--no-print-directory", "-C", str(REPO_ROOT), "-n", "lint-links"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "grep -v -e '^tests/fixtures/'" in proc.stdout
