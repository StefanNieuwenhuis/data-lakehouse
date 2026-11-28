#!/usr/bin/env python3
"""PostToolUse hook for Edit and Write: run the fast linter for the edited file.

  charts/<chart>/**   -> helm lint charts/<chart>
  *.yaml / *.yml      -> yamllint
  *.py                -> ruff check
  *.sql               -> sqlfluff lint (picks up the nearest .sqlfluff config)

If the linter fails, the hook exits 2 so Claude sees the output and fixes the file.
If a linter isn't installed, the hook prints a one-line notice and doesn't fail.
"""
import json
import os
import shutil
import subprocess
import sys


def run(cmd, cwd):
    tool = cmd[0]
    if not shutil.which(tool):
        print(json.dumps({"systemMessage": f"lint hook: {tool} not installed, skipped {cmd[-1]}"}))
        sys.exit(0)
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        out = (proc.stdout + proc.stderr).strip()
        print(f"`{' '.join(cmd)}` failed. Fix these issues:\n{out[-4000:]}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


def main():
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path", "")
    if not path or not os.path.isfile(path):
        sys.exit(0)
    cwd = data.get("cwd") or os.getcwd()
    try:
        repo = subprocess.run(["git", "-C", os.path.dirname(path), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, timeout=5).stdout.strip() or cwd
    except Exception:
        repo = cwd
    rel = os.path.relpath(path, repo)
    parts = rel.split(os.sep)
    ext = os.path.splitext(path)[1].lower()

    # Helm charts: chart templates aren't valid YAML, so lint the whole chart instead.
    if len(parts) >= 3 and parts[0] == "charts":
        chart_dir = os.path.join(repo, parts[0], parts[1])
        if os.path.isfile(os.path.join(chart_dir, "Chart.yaml")):
            run(["helm", "lint", chart_dir], repo)
        sys.exit(0)

    if ext in {".yaml", ".yml"}:
        run(["yamllint", "-s", path], repo)
    elif ext == ".py":
        run(["ruff", "check", path], repo)
    elif ext == ".sql":
        run(["sqlfluff", "lint", path], os.path.dirname(path))
    sys.exit(0)


if __name__ == "__main__":
    main()
