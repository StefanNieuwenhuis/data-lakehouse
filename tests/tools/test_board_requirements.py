"""The board tests fail, not skip, when bash or jq is missing (issue #26).

Runs pytest on test_board.py in a subprocess whose PATH has bash but no jq.
The run must fail and name jq and how to install it, so a CI image without
jq can't turn the suite green by skipping it.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

BOARD_TESTS = Path(__file__).with_name("test_board.py")


def test_board_tests_fail_when_jq_is_missing(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    bash = shutil.which("bash")
    assert bash, "bash is required to run this test"
    (bin_dir / "bash").symlink_to(bash)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PATH"] = str(bin_dir)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(BOARD_TESTS),
        ],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=tmp_path,
    )
    out = proc.stdout + proc.stderr
    print(out)
    assert proc.returncode not in (0, 5), (
        "board tests passed or were skipped without jq"
    )
    assert "skipped" not in out
    assert "required tool(s) not on PATH: jq" in out
    assert "make install-jq" in out
