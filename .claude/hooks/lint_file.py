#!/usr/bin/env python3
"""PostToolUse hook for Edit and Write: run the fast linter for the edited file.

  charts/<chart>/**   -> helm lint charts/<chart>
  *.yaml / *.yml      -> yamllint
  *.py                -> ruff check
  *.sql               -> sqlfluff lint (picks up the nearest .sqlfluff config)

If the linter fails, the hook exits 2 so Claude sees the output and fixes the file.
If a linter isn't installed, the hook prints a one-line notice and doesn't fail.

This hook fails open, loudly: an internal error (malformed input, a crash, a linter
timeout) prints a warning naming the hook on stderr and exits 1, which does not block.

Runtime: the system python3 (3.9 on macOS), standard library only.
"""

import json
import os
import shutil
import subprocess
import sys

HOOK = ".claude/hooks/lint_file.py (PostToolUse)"
LINT_TIMEOUT = 120


def warn(message):
    print(f"{HOOK}: warning: {message}", file=sys.stderr)


def run(cmd, cwd):
    """Run one linter. Return 0 if it passes or isn't installed, 2 if it fails."""
    tool = cmd[0]
    if not shutil.which(tool):
        notice = f"lint hook: {tool} not installed, skipped {cmd[-1]}"
        print(json.dumps({"systemMessage": notice}))
        return 0
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, timeout=LINT_TIMEOUT, check=False
    )
    if proc.returncode != 0:
        out = (proc.stdout + proc.stderr).strip()
        print(
            f"`{' '.join(cmd)}` failed. Fix these issues:\n{out[-4000:]}",
            file=sys.stderr,
        )
        return 2
    return 0


def repo_root(path, cwd):
    try:
        top = subprocess.run(
            ["git", "-C", os.path.dirname(path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        warn(f"git rev-parse failed ({exc}); using {cwd} as the repo root")
        return cwd
    return top or cwd


def read_input(stream):
    data = json.loads(stream.read())
    if not isinstance(data, dict):
        raise TypeError("the hook input is not a JSON object")
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        raise TypeError("`tool_input` is not a JSON object")
    return tool_input.get("file_path") or "", data.get("cwd") or os.getcwd()


def main():
    """Lint the edited file. Return the exit code: 0 to pass, 2 on lint errors."""
    path, cwd = read_input(sys.stdin)
    if not path or not os.path.isfile(path):
        return 0
    repo = repo_root(path, cwd)
    rel = os.path.relpath(path, repo)
    parts = rel.split(os.sep)
    ext = os.path.splitext(path)[1].lower()

    # Helm charts: chart templates aren't valid YAML, so lint the whole chart instead.
    if len(parts) >= 3 and parts[0] == "charts":
        chart_dir = os.path.join(repo, parts[0], parts[1])
        if os.path.isfile(os.path.join(chart_dir, "Chart.yaml")):
            return run(["helm", "lint", chart_dir], repo)
        return 0

    if ext in {".yaml", ".yml"}:
        return run(["yamllint", "-s", path], repo)
    if ext == ".py":
        return run(["ruff", "check", path], repo)
    if ext == ".sql":
        return run(["sqlfluff", "lint", path], os.path.dirname(path))
    return 0


def entrypoint():
    """Run main(). Internal errors exit 1 (non-blocking) with a warning on stderr."""
    try:
        code = main()
    except Exception as exc:
        warn(
            f"internal error, the file was not linted ({type(exc).__name__}: {exc}). "
            "Fix the hook, or run the linter by hand."
        )
        raise SystemExit(1) from exc
    sys.exit(code)


if __name__ == "__main__":
    entrypoint()
