"""Tests for the PostToolUse hook .claude/hooks/lint_file.py (issue #13).

The hook fails open on its own bugs (exit 1, a warning on stderr) and blocks on a
real lint error (exit 2). The linters are stubbed with small scripts on PATH, so
the tests are deterministic and need no real linter. Stdlib only, Python 3.9+.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hooktest import load_hook, run_entrypoint, run_hook, write_executable

HOOK = "lint_file.py"
PASS, INTERNAL_ERROR, LINT_ERROR = 0, 1, 2


class LintFileTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.work = self.root / "work"
        self.work.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def stub_linter(self, name, exit_code, output=""):
        write_executable(self.bin / name, f"echo '{output}'\nexit {exit_code}")

    def path_with_stubs(self):
        return str(self.bin) + os.pathsep + os.environ.get("PATH", "")

    def edited(self, name, content="key: value\n"):
        path = self.work / name
        path.write_text(content)
        return {
            "tool_name": "Write",
            "tool_input": {"file_path": str(path)},
            "cwd": str(self.work),
        }


class InternalErrorFailsOpenTest(LintFileTestCase):
    """AC: an internal error exits 1 (non-blocking) with a warning on stderr."""

    def assertFailsOpen(self, code, err):
        self.assertEqual(code, INTERNAL_ERROR, err)
        self.assertIn("lint_file.py", err)
        self.assertIn("warning", err)

    def test_injected_internal_error_exits_1_with_warning(self):
        module = load_hook(HOOK)
        with mock.patch.object(module, "run", side_effect=RuntimeError("injected")):
            code, _, err = run_entrypoint(module, self.edited("x.yaml"))
        self.assertFailsOpen(code, err)
        self.assertIn("RuntimeError: injected", err)

    def test_malformed_json_exits_1_with_warning(self):
        proc = run_hook(HOOK, "{not json")
        self.assertFailsOpen(proc.returncode, proc.stderr)

    def test_empty_stdin_exits_1_with_warning(self):
        proc = run_hook(HOOK, "")
        self.assertFailsOpen(proc.returncode, proc.stderr)


class RealLintErrorBlocksTest(LintFileTestCase):
    """AC: a real lint error still exits 2."""

    def test_yamllint_failure_exits_2(self):
        self.stub_linter("yamllint", 1, "x.yaml: stub lint error")
        proc = run_hook(HOOK, self.edited("x.yaml"), path=self.path_with_stubs())
        self.assertEqual(proc.returncode, LINT_ERROR, proc.stderr)
        self.assertIn("stub lint error", proc.stderr)
        self.assertIn("yamllint -s", proc.stderr)

    def test_ruff_failure_exits_2(self):
        self.stub_linter("ruff", 1, "x.py: stub ruff error")
        payload = self.edited("x.py", "x = 1\n")
        proc = run_hook(HOOK, payload, path=self.path_with_stubs())
        self.assertEqual(proc.returncode, LINT_ERROR, proc.stderr)
        self.assertIn("stub ruff error", proc.stderr)


class PassingCasesTest(LintFileTestCase):
    def test_clean_file_exits_0(self):
        self.stub_linter("yamllint", 0)
        proc = run_hook(HOOK, self.edited("x.yaml"), path=self.path_with_stubs())
        self.assertEqual(proc.returncode, PASS, proc.stderr)

    def test_missing_linter_exits_0_with_notice(self):
        # PATH holds only the empty stub dir: no linter and no git either.
        proc = run_hook(HOOK, self.edited("x.yaml"), path=str(self.bin))
        self.assertEqual(proc.returncode, PASS, proc.stderr)
        notice = json.loads(proc.stdout)["systemMessage"]
        self.assertIn("yamllint not installed", notice)

    def test_missing_file_exits_0(self):
        payload = {"tool_input": {"file_path": str(self.work / "gone.yaml")}}
        proc = run_hook(HOOK, payload)
        self.assertEqual(proc.returncode, PASS, proc.stderr)

    def test_unlinted_extension_exits_0(self):
        proc = run_hook(HOOK, self.edited("notes.txt"), path=self.path_with_stubs())
        self.assertEqual(proc.returncode, PASS, proc.stderr)


if __name__ == "__main__":
    unittest.main()
