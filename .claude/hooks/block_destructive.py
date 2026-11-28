#!/usr/bin/env python3
"""PreToolUse hook for Bash: block destructive commands.

It blocks these commands (exit 2, with the reason sent back to Claude on stderr):
  - kubectl delete ns/namespace/namespaces
  - helm uninstall/delete/del/un, unless every namespace flag (-n, -n=, --namespace,
    --namespace=) fully matches ^lh-[a-z]+$ (ADR-0006); a missing namespace is blocked
  - minikube delete, unless the profile (-p, -p=, --profile, --profile=) is `spike`;
    --all and --purge are always blocked, because they reach beyond one profile
  - git push to main (origin main, HEAD:main, refs/heads/main, --mirror, or a bare push
    while on main)
  - rm with both -r and -f on a path outside the repo, or on the repo root itself

The rules apply to every simple command in a chained line (&&, ||, ;, |, &, newline,
parentheses), after stripping leading VAR=value assignments and wrappers such as
env and sudo.

This hook fails closed: any internal error, malformed or empty input included, prints
a short message on stderr and exits 2, so the command is blocked.

Runtime: the system python3 (3.9 on macOS), standard library only.
"""

import json
import os
import re
import shlex
import subprocess
import sys

HOOK = ".claude/hooks/block_destructive.py"
PUNCTUATION = ";&|\n()"
WRAPPERS = {"sudo", "env", "time", "command", "exec", "nohup"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HELM_UNINSTALL = {"uninstall", "delete", "del", "un"}
HELM_NAMESPACE = re.compile(r"lh-[a-z]+")
MINIKUBE_DELETABLE_PROFILES = {"spike"}


class Blocked(Exception):
    """Raised by a check when a command must be blocked."""


def block(reason):
    raise Blocked(reason)


def warn(message):
    print(f"{HOOK}: warning: {message}", file=sys.stderr)


def tokenize(command):
    """Split a shell line into tokens, keeping separators as their own tokens."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError as exc:
        # Unbalanced quotes, for example an apostrophe in an unquoted heredoc body.
        # Fall back to splitting on separators and whitespace, so a chained command
        # is still checked part by part.
        warn(f"could not parse the command as shell ({exc}); using a plain split")
        return re.findall(r"[;&|\n()]+|[^\s;&|()]+", command)


def split_commands(command):
    """Split a shell line into simple commands, given as token lists."""
    cmds, cur = [], []
    for tok in tokenize(command):
        if set(tok) <= set(PUNCTUATION):
            if cur:
                cmds.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        cmds.append(cur)
    # Strip leading env assignments and wrappers like sudo/env/time/command.
    cleaned = []
    for c in cmds:
        while c and (ENV_ASSIGNMENT.match(c[0]) or c[0] in WRAPPERS):
            c = c[1:]
        if c:
            cleaned.append(c)
    return cleaned


def flag_values(args, *names):
    """Return every value given for the flags in names, as `-x v` or `-x=v`.

    A flag with no value after it yields an empty string.
    """
    values = []
    for i, a in enumerate(args):
        for n in names:
            if a == n:
                values.append(args[i + 1] if i + 1 < len(args) else "")
            elif a.startswith(n + "="):
                values.append(a.split("=", 1)[1])
    return values


def check_kubectl(args):
    if "delete" not in args:
        return
    rest = args[args.index("delete") + 1 :]
    for a in rest:
        kinds = a.split("/")[0].split(",")
        if any(k in {"ns", "namespace", "namespaces"} for k in kinds):
            block(
                "`kubectl delete namespace` is not allowed. "
                "Ask the user to run it themselves if it's really intended."
            )


def check_helm(args):
    if not any(a in HELM_UNINSTALL for a in args):
        return
    namespaces = flag_values(args, "-n", "--namespace")
    bad = [ns for ns in namespaces if not HELM_NAMESPACE.fullmatch(ns)]
    if not namespaces or bad:
        got = ", ".join(repr(ns) for ns in bad) if bad else "no namespace flag"
        block(
            "`helm uninstall` is only allowed in an `lh-<layer>` namespace "
            f"(must fully match ^lh-[a-z]+$; got: {got}). "
            "Pass it explicitly, for example `-n lh-storage`, or ask the user."
        )


def check_minikube(args):
    if "delete" not in args:
        return
    if any(a == "--all" or a.startswith("--all=") for a in args):
        block(
            "`minikube delete --all` is not allowed: it deletes every profile, "
            "including `dev`. Ask the user to run it themselves."
        )
    if any(a == "--purge" or a.startswith("--purge=") for a in args):
        block(
            "`minikube delete --purge` is not allowed: it removes ~/.minikube, "
            "which every profile uses. Ask the user to run it themselves."
        )
    profiles = flag_values(args, "-p", "--profile")
    if not profiles or any(p not in MINIKUBE_DELETABLE_PROFILES for p in profiles):
        got = ", ".join(repr(p) for p in profiles) if profiles else "no profile flag"
        block(
            "`minikube delete` is only allowed for profile `spike` "
            f"(`-p spike`; got: {got}). The `dev` cluster must not be deleted. "
            "Ask the user to run it themselves if it's really intended."
        )


def current_branch(cwd):
    # Errors propagate on purpose: entrypoint() turns them into a block (fail closed).
    return subprocess.run(
        ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    ).stdout.strip()


def check_git(args, cwd):
    if "push" not in args:
        return
    rest = args[args.index("push") + 1 :]
    if "--mirror" in rest or "--all" in rest:
        block("`git push --mirror/--all` is not allowed.")
    positional = [a for a in rest if not a.startswith("-")]
    refspecs = positional[1:]  # positional[0] is the remote
    for r in refspecs:
        dst = r.split(":")[-1].lstrip("+")
        if dst in {"main", "refs/heads/main", "master", "refs/heads/master"}:
            block(
                "Pushing to main is not allowed. Push a feature branch and open a PR."
            )
    if not refspecs and current_branch(cwd) in {"main", "master"}:
        block(
            "A bare `git push` while on main is not allowed. "
            "Push a feature branch and open a PR."
        )


def check_rm(args, cwd, repo):
    flags = "".join(
        a.lstrip("-") for a in args if a.startswith("-") and not a.startswith("--")
    )
    long_flags = {a for a in args if a.startswith("--")}
    recursive = "r" in flags or "R" in flags or "--recursive" in long_flags
    force = "f" in flags or "--force" in long_flags
    if not (recursive and force):
        return
    targets = [a for a in args if not a.startswith("-")]
    if not targets:
        return
    repo_real = os.path.realpath(repo)
    for t in targets:
        expanded = os.path.expanduser(os.path.expandvars(t))
        if "$" in expanded or "`" in expanded:
            block(
                f"`rm -rf {t}` uses an unresolved variable or substitution. "
                "Use an explicit path inside the repo."
            )
        path = os.path.realpath(os.path.join(cwd, expanded))
        if path == repo_real:
            block("`rm -rf` on the repository root is not allowed.")
        if not path.startswith(repo_real + os.sep):
            block(
                f"`rm -rf {t}` resolves to {path}, "
                f"which is outside the repo ({repo_real})."
            )


def repo_root(cwd):
    """Return the git top level of cwd, so rm -rf inside a worktree is allowed.

    On error, fall back to CLAUDE_PROJECT_DIR or cwd. That is the stricter bound,
    so the fallback can only block more, never less.
    """
    fallback = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    try:
        top = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        warn(f"git rev-parse failed ({exc}); using {fallback} as the repo root")
        return fallback
    return top or fallback


def read_command(stream):
    raw = stream.read()
    if not raw.strip():
        raise ValueError("empty input on stdin")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise TypeError("the hook input is not a JSON object")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        raise TypeError("the hook input has no `tool_input` object")
    command = tool_input.get("command")
    if not isinstance(command, str):
        raise TypeError("`tool_input.command` is missing or not a string")
    cwd = data.get("cwd") or os.getcwd()
    return command, cwd


def main():
    command, cwd = read_command(sys.stdin)
    repo = None
    for c in split_commands(command):
        prog = os.path.basename(c[0])
        args = c[1:]
        if prog == "kubectl":
            check_kubectl(args)
        elif prog == "helm":
            check_helm(args)
        elif prog == "minikube":
            check_minikube(args)
        elif prog == "git":
            check_git(args, cwd)
        elif prog == "rm":
            if repo is None:
                repo = repo_root(cwd)
            check_rm(args, cwd, repo)


def entrypoint():
    """Run main(); exit 0 to allow, 2 to block. Any error blocks (fail closed)."""
    try:
        main()
    except Blocked as exc:
        print(f"Blocked by {HOOK}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:
        print(
            f"Blocked by {HOOK}: the guard failed ({type(exc).__name__}: {exc}), "
            "so it blocks by default. Ask the user if the command is safe.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc
    sys.exit(0)


if __name__ == "__main__":
    entrypoint()
