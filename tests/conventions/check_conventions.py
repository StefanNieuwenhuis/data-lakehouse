"""Check a PR title and a branch name against docs/conventions.yaml (ADR-0007).

Run through `make check-conventions`. Inputs come from the environment only:
TITLE (required) and BRANCH (defaults to the current git branch).

- The title is linted by commitlint (pinned in tests/conventions/package.json),
  with tests/conventions/commitlint.config.mjs, which reads the allowed types
  and scopes from the conventions file at runtime.
- The branch is checked here. This is the gap no maintained tool covers: the
  prefix must be the one the conventions file maps the title's type to, and
  each failed rule is named with the allowed values. Nothing is copied from
  the conventions file into this script.

Branch: <prefix>/<issue>-<slug>

Exit 0 when both pass, 1 when a rule fails, 2 on a usage or config error.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DEFAULT_CONVENTIONS = REPO_ROOT / "docs" / "conventions.yaml"
COMMITLINT = HERE / "node_modules" / "@commitlint" / "cli" / "cli.js"
COMMITLINT_CONFIG = HERE / "commitlint.config.mjs"

# Title type, only to look up the branch prefix; commitlint checks the title.
TITLE_TYPE_RE = re.compile(r"^(?P<type>[a-z]+)(?:\(|!|:)")
BRANCH_RE = re.compile(r"^(?P<prefix>[^/]+/)(?P<rest>.*)$")
# <issue>-<slug>: issue number without a leading zero, then lowercase a-z0-9
# words joined by single hyphens, none leading or trailing. ADR-0007 forbids
# dots, as a restriction on top of Conventional Branch.
BRANCH_REST_RE = re.compile(
    r"^(?P<issue>[1-9][0-9]*)-(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)


class ConfigError(Exception):
    pass


def load_conventions(path):
    try:
        data = yaml.safe_load(Path(path).read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    types = data.get("types") if isinstance(data, dict) else None
    prefixes = data.get("branch_prefixes") if isinstance(data, dict) else None
    if not (isinstance(types, list) and types):
        raise ConfigError(f"{path}: `types` must be a non-empty list")
    if not isinstance(prefixes, dict):
        raise ConfigError(
            f"{path}: `branch_prefixes` must be a mapping of type -> prefix"
        )
    missing = [t for t in types if t not in prefixes]
    extra = [t for t in prefixes if t not in types]
    if missing or extra:
        raise ConfigError(
            f"{path}: `branch_prefixes` must have exactly one entry per type "
            f"(missing: {missing or 'none'}, unknown: {extra or 'none'})"
        )
    bad = [p for p in prefixes.values() if not (isinstance(p, str) and p.endswith("/"))]
    if bad:
        raise ConfigError(f"{path}: every branch prefix must end in '/': {bad}")
    return {"types": types, "branch_prefixes": prefixes}


def lint_title(title, conventions_path):
    """Run commitlint on the title. Returns True when it passes."""
    node = shutil.which("node")
    if node is None or not COMMITLINT.is_file():
        raise ConfigError(
            "commitlint is not installed. Run `make node-deps` (Node comes from the uv dev group)."
        )
    env = dict(os.environ, CONVENTIONS_FILE=str(conventions_path))
    proc = subprocess.run(
        [node, str(COMMITLINT), "--config", str(COMMITLINT_CONFIG), "--color=false"],
        input=title,
        env=env,
        cwd=HERE,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    out = (proc.stdout + proc.stderr).strip()
    if proc.returncode != 0:
        print(out, file=sys.stderr)
    return proc.returncode == 0


def title_type(title, conv):
    m = TITLE_TYPE_RE.match(title)
    return m["type"] if m and m["type"] in conv["types"] else None


def check_branch(branch, conv, ctype):
    prefixes = conv["branch_prefixes"]
    allowed = sorted(set(prefixes.values()))
    if branch != branch.lower():
        return [
            f"[branch-lowercase] {branch!r} has uppercase letters; branches are all lowercase."
        ]
    m = BRANCH_RE.match(branch)
    if not m:
        return [
            f"[branch-format] {branch!r} does not match <prefix>/<issue>-<slug>. Allowed prefixes: {', '.join(allowed)}."
        ]
    errors = []
    prefix, rest = m["prefix"], m["rest"]
    if prefix not in allowed:
        errors.append(
            f"[branch-prefix] unknown prefix {prefix!r}. Allowed prefixes: {', '.join(allowed)}."
        )
    elif ctype is not None and prefixes[ctype] != prefix:
        mapping = ", ".join(f"{t} -> {p}" for t, p in prefixes.items())
        errors.append(
            f"[branch-prefix-type] title type {ctype!r} needs prefix {prefixes[ctype]!r}, "
            f"branch has {prefix!r}. Type -> prefix map: {mapping}."
        )
    if not BRANCH_REST_RE.match(rest):
        errors.append(
            f"[branch-slug] {rest!r} after the prefix must be <issue>-<slug>: an issue "
            "number, then lowercase a-z0-9 words joined by single hyphens, with no "
            "dots and no leading, trailing or double hyphens."
        )
    return errors


def current_branch():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(
            f"BRANCH not set and the current git branch can't be read: {exc}"
        ) from exc
    return out.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--conventions",
        default=str(DEFAULT_CONVENTIONS),
        help="path to the conventions YAML (default: docs/conventions.yaml)",
    )
    args = parser.parse_args(argv)
    title = os.environ.get("TITLE", "")
    branch = os.environ.get("BRANCH", "")
    try:
        conv = load_conventions(args.conventions)
        if not title:
            raise ConfigError(
                "TITLE is not set. Usage: make check-conventions TITLE='type(scope): summary' [BRANCH=...]"
            )
        if not branch:
            branch = current_branch()
        print(f"title:  {title}")
        title_ok = lint_title(title, Path(args.conventions).resolve())
    except ConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print("  ok (commitlint)" if title_ok else "  FAIL (commitlint, see above)")

    print(f"branch: {branch}")
    branch_errors = check_branch(branch, conv, title_type(title, conv))
    for e in branch_errors:
        print(f"  FAIL {e}", file=sys.stderr)
    if not branch_errors:
        print("  ok")

    if not title_ok or branch_errors:
        print(
            "check-conventions: FAILED (rules: docs/adr/0007-conventional-commits-and-branches.md)",
            file=sys.stderr,
        )
        return 1
    print("check-conventions: passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
