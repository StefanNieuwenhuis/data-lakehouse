#!/usr/bin/env python3
"""Stop / SubagentStop hook: run `make lint` and `make test` before Claude finishes.

If either target fails, the hook exits 2, so Claude (or the subagent) has to keep
working and fix the failure. To avoid an endless loop, a second consecutive block
(stop_hook_active=true) lets it stop, but shows a visible warning so it can't quietly
claim the work is done. The checks run in the session's cwd, so a git worktree gets
checked rather than the main checkout.

This hook fails open, loudly: an internal error (malformed input, a crash, `make`
missing) prints a warning naming the hook on stderr and exits 1, which does not
block. A real `make lint` or `make test` failure, a timeout included, still exits 2.

Runtime: the system python3 (3.9 on macOS), standard library only.
"""

import json
import os
import subprocess
import sys

HOOK = ".claude/hooks/stop_checks.py (Stop/SubagentStop)"
TARGETS = ("lint", "test")
MAKE_TIMEOUT = 600


def warn(message):
    print(f"{HOOK}: warning: {message}", file=sys.stderr)


def project_root(cwd):
    try:
        top = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        warn(f"git rev-parse failed ({exc}); using {cwd} as the project root")
        return cwd
    return top or cwd


def run_target(target, root):
    """Run `make <target>`. Return None if it passes, else a failure report."""
    try:
        proc = subprocess.run(
            ["make", target],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=MAKE_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return f"## make {target} (timed out after {exc.timeout}s)"
    if proc.returncode == 0:
        return None
    out = (proc.stdout + proc.stderr).strip()[-3000:]
    return f"## make {target} (exit {proc.returncode})\n{out}"


def read_input(stream):
    data = json.loads(stream.read())
    if not isinstance(data, dict):
        raise TypeError("the hook input is not a JSON object")
    return data


def main():
    """Run the checks. Return the exit code: 0 to let Claude stop, 2 to block."""
    data = read_input(sys.stdin)
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    root = project_root(cwd)
    if not os.path.isfile(os.path.join(root, "Makefile")):
        return 0

    failures = [f for f in (run_target(t, root) for t in TARGETS) if f]
    if not failures:
        return 0

    report = "\n\n".join(failures)
    if data.get("stop_hook_active"):
        message = "make lint/test are STILL FAILING. The work is not done:\n" + report
        print(json.dumps({"systemMessage": message}))
        return 0
    print(
        "You can't finish while checks are failing. "
        "Fix them, or explain why they can't pass:\n\n" + report,
        file=sys.stderr,
    )
    return 2


def entrypoint():
    """Run main(). Internal errors exit 1 (non-blocking) with a warning on stderr."""
    try:
        code = main()
    except Exception as exc:
        warn(
            f"internal error, make lint/test did not run ({type(exc).__name__}: "
            f"{exc}). The work is NOT verified; run `make lint` and `make test`."
        )
        raise SystemExit(1) from exc
    sys.exit(code)


if __name__ == "__main__":
    entrypoint()
