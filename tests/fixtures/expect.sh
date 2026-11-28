#!/usr/bin/env bash
# Fixture runner for `make test-fixtures` (issue #26).
#
#   expect.sh <title|branch|link> <pass|fail> <cases-file>
#
# Runs the real make target once per case and checks the tool's exit code:
#   title      make check-title    TITLE=<case> in the environment (commitlint)
#   title-arg  make check-title    TITLE=<case> on the make command line, to
#                                  prove make does not expand $(...) in it
#   branch  make check-branch      TITLE, BRANCH          (branch-name-lint)
#   link    make check-link-file   LINK_FILE=<case>       (lychee --offline)
#   lockfile make check-lockfile   LOCKFILE=<case>        (lockfile-lint)
#
# Case lines (blank lines and lines starting with # are skipped):
#   pass files:  <case>
#   fail files:  <expect> <case>   where <expect> must appear in the tool's
#                output, e.g. the commitlint rule [subject-full-stop], so a
#                case can't pass by failing for some other reason.
#   branch cases are "<type> <branch>"; the title is "<type>(ci): fixture".
# Inputs reach make only through the environment.
set -uo pipefail

kind=${1:?kind: title, title-arg, branch, link or lockfile}
want=${2:?want: pass or fail}
file=${3:?cases file}
[[ $want == pass || $want == fail ]] || { echo "expect.sh: want must be pass or fail" >&2; exit 2; }
[[ -f $file ]] || { echo "expect.sh: no such cases file: $file" >&2; exit 2; }
MAKE=${MAKE:-make}

n=0
bad=0
while IFS= read -r line || [[ -n $line ]]; do
  [[ -z $line || $line == \#* ]] && continue
  expect=""
  if [[ $want == fail ]]; then
    expect=${line%% *}
    line=${line#* }
  fi
  case $kind in
    title)  out=$(TITLE=$line "$MAKE" -s --no-print-directory check-title 2>&1) ;;
    title-arg) out=$("$MAKE" -s --no-print-directory check-title "TITLE=$line" 2>&1) ;;
    branch) out=$(TITLE="${line%% *}(ci): fixture" BRANCH=${line#* } \
                  "$MAKE" -s --no-print-directory check-branch 2>&1) ;;
    link)   out=$(LINK_FILE=$line "$MAKE" -s --no-print-directory check-link-file 2>&1) ;;
    lockfile) out=$(LOCKFILE=$PWD/$line "$MAKE" -s --no-print-directory check-lockfile 2>&1) ;;
    *) echo "expect.sh: unknown kind: $kind" >&2; exit 2 ;;
  esac
  rc=$?
  n=$((n + 1))
  if [[ $want == pass && $rc -eq 0 ]]; then
    echo "  ok   pass  $kind: $line"
  elif [[ $want == fail && $rc -ne 0 && $out == *"$expect"* ]]; then
    echo "  ok   fail  $kind: $line  ($expect)"
  else
    bad=$((bad + 1))
    echo "  FAIL $kind: $line: expected $want${expect:+ with $expect}, got exit $rc" >&2
    printf '%s\n' "$out" | sed 's/^/       | /' >&2
  fi
done < "$file"

if [[ $n -eq 0 ]]; then
  echo "expect.sh: $file has no cases" >&2
  exit 1
fi
echo "==> $file: $((n - bad))/$n as expected"
[[ $bad -eq 0 ]]
