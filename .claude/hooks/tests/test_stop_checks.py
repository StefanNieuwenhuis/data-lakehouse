"""Tests for the Stop/SubagentStop hook .claude/hooks/stop_checks.py (issue #13).

The hook fails open on its own bugs (exit 1, a warning on stderr) and blocks when
`make lint` or `make test` really fails (exit 2). The real-failure tests run the
hook against a throwaway project whose Makefile passes or fails on purpose.
Stdlib only, Python 3.9+.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hooktest import load_hook, run_entrypoint, run_hook

HOOK = "stop_checks.py"
PASS, INTERNAL_ERROR, CHECKS_FAILED = 0, 1, 2


def makefile(lint_ok=True, test_ok=True):
    def recipe(name, ok):
        cmd = "@echo ok" if ok else f"@echo '{name} is broken'; exit 3"
        return f"{name}:\n\t{cmd}\n"

    return ".PHONY: lint test\n" + recipe("lint", lint_ok) + recipe("test", test_ok)


class StopChecksTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, **extra):
        data = {"hook_event_name": "Stop", "cwd": str(self.project)}
        data.update(extra)
        return data

    def with_makefile(self, **kwargs):
        (self.project / "Makefile").write_text(makefile(**kwargs))


class InternalErrorFailsOpenTest(StopChecksTestCase):
    """AC: a crashing stop_checks.py exits 1, not 2, with a warning on stderr."""

    def assertFailsOpen(self, code, err):
        self.assertEqual(code, INTERNAL_ERROR, err)
        self.assertIn("stop_checks.py", err)
        self.assertIn("warning", err)

    def test_injected_internal_error_exits_1_with_warning(self):
        self.with_makefile(lint_ok=False)
        module = load_hook(HOOK)
        with mock.patch.object(
            module, "run_target", side_effect=RuntimeError("injected")
        ):
            code, _, err = run_entrypoint(module, self.payload())
        self.assertFailsOpen(code, err)
        self.assertIn("RuntimeError: injected", err)

    def test_malformed_json_exits_1_with_warning(self):
        proc = run_hook(HOOK, "{not json")
        self.assertFailsOpen(proc.returncode, proc.stderr)

    def test_empty_stdin_exits_1_with_warning(self):
        proc = run_hook(HOOK, "")
        self.assertFailsOpen(proc.returncode, proc.stderr)

    def test_make_not_installed_exits_1_with_warning(self):
        self.with_makefile()
        empty_bin = self.project / "empty-bin"
        empty_bin.mkdir()
        proc = run_hook(HOOK, self.payload(), path=str(empty_bin))
        self.assertFailsOpen(proc.returncode, proc.stderr)


class RealFailureBlocksTest(StopChecksTestCase):
    """AC: a real `make lint` or `make test` failure still exits 2."""

    def test_make_lint_failure_exits_2(self):
        self.with_makefile(lint_ok=False)
        proc = run_hook(HOOK, self.payload())
        self.assertEqual(proc.returncode, CHECKS_FAILED, proc.stderr)
        self.assertIn("## make lint (exit", proc.stderr)
        self.assertIn("lint is broken", proc.stderr)

    def test_make_test_failure_exits_2(self):
        self.with_makefile(test_ok=False)
        proc = run_hook(HOOK, self.payload())
        self.assertEqual(proc.returncode, CHECKS_FAILED, proc.stderr)
        self.assertIn("## make test (exit", proc.stderr)
        self.assertNotIn("## make lint", proc.stderr)

    def test_subagent_stop_failure_exits_2(self):
        self.with_makefile(lint_ok=False, test_ok=False)
        proc = run_hook(HOOK, self.payload(hook_event_name="SubagentStop"))
        self.assertEqual(proc.returncode, CHECKS_FAILED, proc.stderr)
        self.assertIn("## make lint", proc.stderr)
        self.assertIn("## make test", proc.stderr)


class PassingCasesTest(StopChecksTestCase):
    def test_green_checks_exit_0(self):
        self.with_makefile()
        proc = run_hook(HOOK, self.payload())
        self.assertEqual(proc.returncode, PASS, proc.stderr)

    def test_second_block_lets_claude_stop_with_a_visible_warning(self):
        self.with_makefile(lint_ok=False)
        proc = run_hook(HOOK, self.payload(stop_hook_active=True))
        self.assertEqual(proc.returncode, PASS, proc.stderr)
        self.assertIn("STILL FAILING", json.loads(proc.stdout)["systemMessage"])

    def test_no_makefile_exits_0(self):
        proc = run_hook(HOOK, self.payload())
        self.assertEqual(proc.returncode, PASS, proc.stderr)


if __name__ == "__main__":
    unittest.main()
