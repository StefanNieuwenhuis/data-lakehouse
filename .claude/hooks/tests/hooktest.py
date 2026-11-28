"""Shared helpers for the hook tests (stdlib only, Python 3.9 compatible).

The tests run under pytest in `make test` (Python 3.12) and under
`/usr/bin/python3 -m unittest discover -s .claude/hooks/tests` (Python 3.9).
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

HOOKS_DIR = Path(__file__).resolve().parent.parent

# Variables a parent `make` exports. Strip them so a nested `make` run by a hook
# under test behaves the same inside and outside `make test`.
MAKE_ENV = ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKEOVERRIDES")


def hook_env(path=None):
    env = {k: v for k, v in os.environ.items() if k not in MAKE_ENV}
    env.pop("CLAUDE_PROJECT_DIR", None)
    if path is not None:
        env["PATH"] = path
    return env


def run_hook(hook, stdin, path=None):
    """Run a hook as Claude Code does: stdin JSON in, exit code and stderr out.

    `stdin` is a dict (sent as JSON) or a str (sent as is, to test bad input).
    """
    if not isinstance(stdin, str):
        stdin = json.dumps(stdin)
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / hook)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=120,
        env=hook_env(path),
        check=False,
    )


def load_hook(hook):
    """Import a hook file as a module, so a test can inject faults into it."""
    name = "hook_under_test_" + hook.replace(".py", "")
    spec = importlib.util.spec_from_file_location(name, HOOKS_DIR / hook)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_entrypoint(module, stdin):
    """Call module.entrypoint() in-process. Return (exit code, stdout, stderr)."""
    if not isinstance(stdin, str):
        stdin = json.dumps(stdin)
    out, err = io.StringIO(), io.StringIO()
    code = None
    fake_stdin = mock.patch.object(sys, "stdin", io.StringIO(stdin))
    # One `with`, no parentheses: parenthesized context managers need Python 3.10.
    with fake_stdin, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            module.entrypoint()
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write_executable(path, body):
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(0o755)
