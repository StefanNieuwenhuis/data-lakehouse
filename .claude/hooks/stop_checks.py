#!/usr/bin/env python3
"""Stop / SubagentStop hook: run `make lint` and `make test` before Claude (or a subagent) finishes.

If either target fails, the hook exits 2, so Claude has to keep working and fix the failure.
To avoid an endless loop, a second consecutive block (stop_hook_active=true) lets it stop,
but shows a visible warning so it can't quietly claim the work is done.
The checks run in the session's cwd, so a git worktree gets checked rather than the main checkout.
"""
import json
import os
import subprocess
import sys


def main():
    data = json.load(sys.stdin)
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        root = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or cwd
    except Exception:
        root = cwd
    if not os.path.isfile(os.path.join(root, "Makefile")):
        sys.exit(0)

    failures = []
    for target in ("lint", "test"):
        proc = subprocess.run(["make", target], cwd=root, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            failures.append(f"## make {target} (exit {proc.returncode})\n{(proc.stdout + proc.stderr).strip()[-3000:]}")

    if not failures:
        sys.exit(0)

    report = "\n\n".join(failures)
    if data.get("stop_hook_active"):
        print(json.dumps({"systemMessage": "make lint/test are STILL FAILING. The work is not done:\n" + report}))
        sys.exit(0)
    print("You can't finish while checks are failing. Fix them, or explain why they can't pass:\n\n" + report,
          file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
