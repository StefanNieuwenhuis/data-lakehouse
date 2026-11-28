#!/usr/bin/env python3
"""PreToolUse hook for Bash: block destructive commands.

It blocks these commands (exit 2, with the reason sent back to Claude on stderr):
  - kubectl delete ns/namespace/namespaces
  - helm uninstall/delete/del/un, unless the target namespace is "dev"
  - git push to main (origin main, HEAD:main, refs/heads/main, --mirror, or a bare push while on main)
  - rm with both -r and -f on a path outside the repo, or on the repo root itself
"""
import json
import os
import re
import shlex
import subprocess
import sys

SEPARATORS = {"&&", "||", ";", "|", "&", "\n"}


def block(reason):
    print(f"Blocked by .claude/hooks/block_destructive.py: {reason}", file=sys.stderr)
    sys.exit(2)


def split_commands(command):
    """Split a shell line into simple commands, given as token lists."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:  # unbalanced quotes; fall back to plain whitespace splitting
        tokens = command.split()
    cmds, cur = [], []
    for tok in tokens:
        if tok in SEPARATORS or set(tok) <= set(";&|\n"):
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
        while c and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", c[0]) or c[0] in {"sudo", "env", "time", "command", "exec", "nohup"}):
            c = c[1:]
        if c:
            cleaned.append(c)
    return cleaned


def flag_value(args, *names):
    for i, a in enumerate(args):
        for n in names:
            if a == n and i + 1 < len(args):
                return args[i + 1]
            if a.startswith(n + "="):
                return a.split("=", 1)[1]
    return None


def check_kubectl(args):
    if "delete" not in args:
        return
    rest = args[args.index("delete") + 1:]
    for a in rest:
        kinds = a.split("/")[0].split(",")
        if any(k in {"ns", "namespace", "namespaces"} for k in kinds):
            block("`kubectl delete namespace` is not allowed. Ask the user to run it themselves if it's really intended.")


def check_helm(args):
    if not any(a in {"uninstall", "delete", "del", "un"} for a in args):
        return
    ns = flag_value(args, "-n", "--namespace")
    if ns != "dev":
        block(f"`helm uninstall` is only allowed in namespace `dev` (got: {ns or 'current/default namespace'}). Pass `-n dev` explicitly, or ask the user.")


def current_branch(cwd):
    try:
        return subprocess.run(["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def check_git(args, cwd):
    if "push" not in args:
        return
    rest = args[args.index("push") + 1:]
    if "--mirror" in rest or "--all" in rest:
        block("`git push --mirror/--all` is not allowed.")
    positional = [a for a in rest if not a.startswith("-")]
    refspecs = positional[1:]  # positional[0] is the remote
    for r in refspecs:
        dst = r.split(":")[-1].lstrip("+")
        if dst in {"main", "refs/heads/main", "master", "refs/heads/master"}:
            block("Pushing to main is not allowed. Push a feature branch and open a PR.")
    if not refspecs and current_branch(cwd) in {"main", "master"}:
        block("A bare `git push` while on main is not allowed. Push a feature branch and open a PR.")


def check_rm(args, cwd, repo):
    flags = "".join(a.lstrip("-") for a in args if a.startswith("-") and not a.startswith("--"))
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
            block(f"`rm -rf {t}` uses an unresolved variable or substitution. Use an explicit path inside the repo.")
        path = os.path.realpath(os.path.join(cwd, expanded))
        if path == repo_real:
            block("`rm -rf` on the repository root is not allowed.")
        if not path.startswith(repo_real + os.sep):
            block(f"`rm -rf {t}` resolves to {path}, which is outside the repo ({repo_real}).")


def main():
    data = json.load(sys.stdin)
    command = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    repo = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    # Treat git worktrees as part of the repo, so rm -rf inside a worktree is allowed.
    try:
        top = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if top:
            repo = top
    except Exception:
        pass

    for c in split_commands(command):
        prog = os.path.basename(c[0])
        args = c[1:]
        if prog == "kubectl":
            check_kubectl(args)
        elif prog == "helm":
            check_helm(args)
        elif prog == "git":
            check_git(args, cwd)
        elif prog == "rm":
            check_rm(args, cwd, repo)
    sys.exit(0)


if __name__ == "__main__":
    main()
