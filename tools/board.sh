#!/usr/bin/env bash
# tools/board.sh - add and move cards on the Lakehouse GitHub Project board.
#
# Agents change the board only through this script (issue #19). It looks up
# every project, field, option and item ID by name at runtime with
# `gh project view`, `gh project field-list` and `gh project item-list`; no ID
# is hard-coded. It never creates or edits fields or options: if a name is
# missing it exits non-zero, names what was missing and lists what exists.
#
# Usage:
#   tools/board.sh add  <issue|pr> --wave <W> --agent <A>
#   tools/board.sh move <issue|pr> "<Status>"
#   tools/board.sh show <issue|pr>
#
# `add` puts the issue or PR on the board (once; re-adding reuses the card)
# and sets Wave and Agent. It sets Status to Ready when the card is new, has
# no Status, or sits in Todo (where auto-add puts items). A card already
# moved further by hand keeps its Status.
#
# `move` sets Status to one of: Todo, Ready, In progress, In review, Done,
# Blocked (validated against the board's own options).
#
# Environment overrides (defaults are the Lakehouse board):
#   BOARD_OWNER    project owner login   (StefanNieuwenhuis)
#   BOARD_PROJECT  project number        (5)
#   BOARD_REPO     owner/repo of issues  (StefanNieuwenhuis/lakehouse)
#   BOARD_LIMIT    max items to list     (1000)
#
# Requires bash 3.2+, gh and jq, and a gh token with the `project` scope.

set -euo pipefail

OWNER="${BOARD_OWNER:-StefanNieuwenhuis}"
PROJECT="${BOARD_PROJECT:-5}"
REPO="${BOARD_REPO:-StefanNieuwenhuis/lakehouse}"
LIMIT="${BOARD_LIMIT:-1000}"

STATUSES=("Todo" "Ready" "In progress" "In review" "Done" "Blocked")

die() {
  echo "board.sh: ERROR: $*" >&2
  exit 1
}

usage() {
  cat >&2 <<'EOF'
Usage:
  tools/board.sh add  <issue|pr> --wave <W> --agent <A>
  tools/board.sh move <issue|pr> "<Status>"
  tools/board.sh show <issue|pr>
Status is one of: Todo, Ready, In progress, In review, Done, Blocked.
EOF
  exit 2
}

# --- preflight ---------------------------------------------------------------

check_tools() {
  local missing=() tool
  for tool in gh jq; do
    command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
  done
  if [ "${#missing[@]}" -gt 0 ]; then
    die "required tool(s) not found on PATH: ${missing[*]}. Install gh (https://cli.github.com) and jq."
  fi
}

check_scope() {
  local status
  if ! status="$(gh auth status 2>&1)"; then
    die "gh is not authenticated (gh auth status failed). Run: gh auth login --scopes project"
  fi
  if ! printf '%s\n' "$status" | grep -i 'token scopes' | grep -q "'project'"; then
    die "gh token lacks the 'project' scope. Run: gh auth refresh --scopes project"
  fi
}

# --- lookups -----------------------------------------------------------------

PROJECT_ID=""
FIELDS_JSON=""
GH_ERR=""  # temp file for gh's stderr, so errors can quote gh's reason

# gh_reason: prints " (gh: <last stderr line>)" after a failed gh call.
gh_reason() {
  local reason=""
  [ -n "$GH_ERR" ] && reason="$(tail -n 1 "$GH_ERR" 2>/dev/null || true)"
  [ -z "$reason" ] || printf ' (gh: %s)' "$reason"
}

load_project() {
  local view
  if ! view="$(gh project view "$PROJECT" --owner "$OWNER" --format json 2>"$GH_ERR")"; then
    die "project $PROJECT (owner $OWNER) not found, or not readable with this token$(gh_reason)"
  fi
  PROJECT_ID="$(printf '%s' "$view" | jq -r '.id // empty')"
  [ -n "$PROJECT_ID" ] || die "project $PROJECT (owner $OWNER) not found: no id in gh project view output"
  if ! FIELDS_JSON="$(gh project field-list "$PROJECT" --owner "$OWNER" --format json --limit 100 2>"$GH_ERR")"; then
    die "could not list fields of project $PROJECT (owner $OWNER)$(gh_reason)"
  fi
}

# field_id <Field name>: prints the ID of a single-select field.
field_id() {
  local name="$1" id have
  id="$(printf '%s' "$FIELDS_JSON" | jq -r --arg n "$name" \
    '[.fields[] | select(.name == $n and .type == "ProjectV2SingleSelectField")][0].id // empty')"
  if [ -z "$id" ]; then
    have="$(printf '%s' "$FIELDS_JSON" | jq -r \
      '[.fields[] | select(.type == "ProjectV2SingleSelectField") | .name] | sort | join(", ")')"
    die "single-select field \"$name\" not found on project $PROJECT; have: ${have:-none}"
  fi
  printf '%s\n' "$id"
}

# option_id <Field name> <Option name>: prints the ID of a field option.
option_id() {
  local field="$1" name="$2" id have
  field_id "$field" >/dev/null
  id="$(printf '%s' "$FIELDS_JSON" | jq -r --arg f "$field" --arg n "$name" \
    '[.fields[] | select(.name == $f) | .options[]? | select(.name == $n)][0].id // empty')"
  if [ -z "$id" ]; then
    have="$(printf '%s' "$FIELDS_JSON" | jq -r --arg f "$field" \
      '[.fields[] | select(.name == $f) | .options[]?.name] | sort | join(", ")')"
    die "$field option \"$name\" not found; have: ${have:-none}"
  fi
  printf '%s\n' "$id"
}

# content_url <number>: prints the URL of issue or PR <number> in $REPO.
content_url() {
  local number="$1" url
  case "$number" in
    '' | *[!0-9]*) die "\"$number\" is not an issue or PR number" ;;
  esac
  if ! url="$(gh api "repos/$REPO/issues/$number" 2>"$GH_ERR" | jq -r '.html_url // empty')" || [ -z "$url" ]; then
    die "issue or PR #$number not found in $REPO$(gh_reason)"
  fi
  printf '%s\n' "$url"
}

# item_json <url>: prints the board item for <url> as JSON, or nothing.
item_json() {
  local url="$1" items
  if ! items="$(gh project item-list "$PROJECT" --owner "$OWNER" --format json --limit "$LIMIT" 2>"$GH_ERR")"; then
    die "could not list items of project $PROJECT (owner $OWNER)$(gh_reason)"
  fi
  printf '%s' "$items" | jq -c --arg u "$url" '[.items[] | select(.content.url == $u)][0] // empty'
}

set_option() {
  local item="$1" field="$2" option="$3" fid oid
  fid="$(field_id "$field")"
  oid="$(option_id "$field" "$option")"
  gh project item-edit --id "$item" --project-id "$PROJECT_ID" \
    --field-id "$fid" --single-select-option-id "$oid" >/dev/null 2>"$GH_ERR" ||
    die "could not set $field to \"$option\" on item $item$(gh_reason)"
}

validate_status() {
  local want="$1" s
  for s in "${STATUSES[@]}"; do
    [ "$s" = "$want" ] && return 0
  done
  die "Status \"$want\" is not allowed; use one of: Todo, Ready, In progress, In review, Done, Blocked"
}

describe() {
  # describe <number> <item json>
  printf '%s' "$2" | jq -r --arg n "$1" \
    '"#\($n)  Status: \(.status // "-")  Wave: \(.wave // "-")  Agent: \(.agent // "-")"'
}

# --- commands ----------------------------------------------------------------

cmd_add() {
  local number="" wave="" agent=""
  [ "$#" -ge 1 ] || usage
  number="$1"
  shift
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --wave) [ "$#" -ge 2 ] || usage; wave="$2"; shift 2 ;;
      --agent) [ "$#" -ge 2 ] || usage; agent="$2"; shift 2 ;;
      *) usage ;;
    esac
  done
  [ -n "$wave" ] && [ -n "$agent" ] || usage

  check_scope
  load_project
  # Validate every name before changing anything.
  option_id Wave "$wave" >/dev/null
  option_id Agent "$agent" >/dev/null
  option_id Status Ready >/dev/null
  local url item id status
  url="$(content_url "$number")"
  item="$(item_json "$url")"

  if [ -n "$item" ]; then
    id="$(printf '%s' "$item" | jq -r '.id')"
    status="$(printf '%s' "$item" | jq -r '.status // ""')"
    echo "#$number is already on project $PROJECT; updating its card"
  else
    id="$(gh project item-add "$PROJECT" --owner "$OWNER" --url "$url" --format json 2>"$GH_ERR" | jq -r '.id // empty')" ||
      die "could not add #$number to project $PROJECT$(gh_reason)"
    [ -n "$id" ] || die "could not add #$number to project $PROJECT: no item id returned"
    status=""
    echo "added #$number to project $PROJECT"
  fi

  set_option "$id" Wave "$wave"
  set_option "$id" Agent "$agent"
  case "$status" in
    "" | Todo)
      set_option "$id" Status Ready
      echo "#$number Status: ${status:-none} -> Ready"
      ;;
    Ready)
      echo "#$number Status: already Ready"
      ;;
    *)
      echo "#$number Status: kept \"$status\" (moved by hand; use 'move' to change it)"
      ;;
  esac
  echo "#$number Wave: $wave  Agent: $agent"
}

cmd_move() {
  [ "$#" -eq 2 ] || usage
  local number="$1" want="$2" url item id status
  validate_status "$want"
  check_scope
  load_project
  option_id Status "$want" >/dev/null
  url="$(content_url "$number")"
  item="$(item_json "$url")"
  [ -n "$item" ] || die "#$number is not on project $PROJECT; add it first: tools/board.sh add $number --wave <W> --agent <A>"
  id="$(printf '%s' "$item" | jq -r '.id')"
  status="$(printf '%s' "$item" | jq -r '.status // ""')"
  set_option "$id" Status "$want"
  echo "#$number Status: ${status:-none} -> $want"
}

cmd_show() {
  [ "$#" -eq 1 ] || usage
  local number="$1" url item
  check_scope
  load_project
  url="$(content_url "$number")"
  item="$(item_json "$url")"
  [ -n "$item" ] || die "#$number is not on project $PROJECT"
  describe "$number" "$item"
}

main() {
  [ "$#" -ge 1 ] || usage
  local cmd="$1"
  shift
  case "$cmd" in
    add | move | show) ;;
    -h | --help | help) usage ;;
    *) echo "board.sh: unknown command \"$cmd\"" >&2; usage ;;
  esac
  check_tools
  GH_ERR="$(mktemp "${TMPDIR:-/tmp}/board.XXXXXX")"
  trap 'rm -f "$GH_ERR"' EXIT
  "cmd_$cmd" "$@"
}

main "$@"
