"""CI-safe tests for tools/board.sh (issue #19).

A fake `gh` (gh_stub.py) is put first on PATH, so no test talks to GitHub.
Test names map to the acceptance criteria: add, re-add, move, every
missing-name failure message, and missing tools / token scope.
"""

import copy
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BOARD = REPO_ROOT / "tools" / "board.sh"
STUB = Path(__file__).with_name("gh_stub.py")
BASH = shutil.which("bash")
JQ = shutil.which("jq")

OWNER = "octo"
REPO = "octo/lake"

BASE_STATE = {
    "scopes": ["gist", "project", "repo"],
    "authenticated": True,
    "owner": OWNER,
    "number": 5,
    "project_id": "PVT_1",
    "fields": [
        {"id": "F_TITLE", "name": "Title", "type": "ProjectV2Field"},
        {
            "id": "F_STATUS",
            "name": "Status",
            "type": "ProjectV2SingleSelectField",
            "options": [
                {"id": "S_TODO", "name": "Todo"},
                {"id": "S_READY", "name": "Ready"},
                {"id": "S_PROG", "name": "In progress"},
                {"id": "S_REV", "name": "In review"},
                {"id": "S_BLOCK", "name": "Blocked"},
                {"id": "S_DONE", "name": "Done"},
            ],
        },
        {
            "id": "F_WAVE",
            "name": "Wave",
            "type": "ProjectV2SingleSelectField",
            "options": [
                {"id": f"W_{w}", "name": w}
                for w in ["1a", "1b", "2", "3", "4", "5", "1c", "6"]
            ],
        },
        {
            "id": "F_AGENT",
            "name": "Agent",
            "type": "ProjectV2SingleSelectField",
            "options": [
                {"id": "A_TE", "name": "test-engineer"},
                {"id": "A_PE", "name": "platform-engineer"},
            ],
        },
    ],
    "issues": {
        "19": f"https://github.com/{REPO}/issues/19",
        "20": f"https://github.com/{REPO}/issues/20",
        "42": f"https://github.com/{REPO}/pull/42",
    },
    "items": [],
}

# Fail, never skip, when a required tool is missing (issue #26): a CI image
# without jq must not turn this suite green by skipping it.
# test_missing_jq_fails_clearly still works: it hides jq through its own PATH.
_INSTALL_HINTS = {
    "bash": "install bash with your package manager",
    "jq": "run `make install-jq` (pinned jq into ~/.local/bin), or install jq with your package manager",
}
_MISSING = [name for name, path in (("bash", BASH), ("jq", JQ)) if path is None]
if _MISSING:
    pytest.fail(
        "tools/board.sh tests: required tool(s) not on PATH: "
        + ", ".join(_MISSING)
        + ". "
        + "; ".join(f"{n}: {_INSTALL_HINTS[n]}" for n in _MISSING),
        pytrace=False,
    )


class Board:
    """Runs board.sh against a fake gh with its own state file."""

    def __init__(self, tmp_path, state):
        self.tmp = tmp_path
        self.state_file = tmp_path / "state.json"
        self.log_file = tmp_path / "gh.log"
        self.state_file.write_text(json.dumps(state))
        self.log_file.write_text("")
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(f"#!{sys.executable}\n" + STUB.read_text())
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)

    def run(self, *args, path=None):
        env = {
            "PATH": path
            if path is not None
            else f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.tmp),
            "GH_STUB_STATE": str(self.state_file),
            "GH_STUB_LOG": str(self.log_file),
            "BOARD_OWNER": OWNER,
            "BOARD_PROJECT": "5",
            "BOARD_REPO": REPO,
        }
        proc = subprocess.run(
            [BASH, str(BOARD), *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        print(f"$ board.sh {' '.join(args)}\n{proc.stdout}{proc.stderr}")
        return proc

    @property
    def state(self):
        return json.loads(self.state_file.read_text())

    def calls(self):
        return [json.loads(line) for line in self.log_file.read_text().splitlines()]

    def mutating_calls(self):
        return [
            c
            for c in self.calls()
            if c[:2] in (["project", "item-add"], ["project", "item-edit"])
        ]

    def item(self, number):
        items = [i for i in self.state["items"] if i["number"] == number]
        assert len(items) == 1, f"expected one card for #{number}, got {items}"
        return items[0]


@pytest.fixture
def board(tmp_path):
    return Board(tmp_path, copy.deepcopy(BASE_STATE))


def with_items(tmp_path, *items):
    state = copy.deepcopy(BASE_STATE)
    state["items"] = list(items)
    return Board(tmp_path, state)


# --- add ---------------------------------------------------------------------


def test_add_new_issue_sets_wave_agent_and_status_ready(board):
    proc = board.run("add", "19", "--wave", "1c", "--agent", "test-engineer")
    assert proc.returncode == 0, proc.stderr
    assert board.item(19)["values"] == {
        "Wave": "1c",
        "Agent": "test-engineer",
        "Status": "Ready",
    }


def test_add_pull_request(board):
    proc = board.run("add", "42", "--wave", "2", "--agent", "platform-engineer")
    assert proc.returncode == 0, proc.stderr
    assert board.item(42)["values"]["Status"] == "Ready"


def test_add_moves_auto_added_todo_card_to_ready(tmp_path):
    b = with_items(
        tmp_path,
        {
            "id": "PVTI_x",
            "url": f"https://github.com/{REPO}/issues/19",
            "number": 19,
            "values": {"Status": "Todo"},
        },
    )
    proc = b.run("add", "19", "--wave", "1a", "--agent", "test-engineer")
    assert proc.returncode == 0, proc.stderr
    assert b.item(19)["values"]["Status"] == "Ready"
    assert not [c for c in b.calls() if c[:2] == ["project", "item-add"]]


def test_readd_updates_fields_without_duplicate_card(board):
    assert (
        board.run("add", "19", "--wave", "1a", "--agent", "test-engineer").returncode
        == 0
    )
    proc = board.run("add", "19", "--wave", "2", "--agent", "platform-engineer")
    assert proc.returncode == 0, proc.stderr
    assert "already on project 5" in proc.stdout
    assert "Status: already Ready" in proc.stdout
    card = board.item(19)  # asserts exactly one card
    assert card["values"] == {
        "Wave": "2",
        "Agent": "platform-engineer",
        "Status": "Ready",
    }
    assert len([c for c in board.calls() if c[:2] == ["project", "item-add"]]) == 1


def test_readd_keeps_status_moved_by_hand(tmp_path):
    b = with_items(
        tmp_path,
        {
            "id": "PVTI_x",
            "url": f"https://github.com/{REPO}/issues/19",
            "number": 19,
            "values": {"Status": "In progress"},
        },
    )
    proc = b.run("add", "19", "--wave", "1a", "--agent", "test-engineer")
    assert proc.returncode == 0, proc.stderr
    assert b.item(19)["values"] == {
        "Status": "In progress",
        "Wave": "1a",
        "Agent": "test-engineer",
    }
    assert 'kept "In progress"' in proc.stdout


# --- move --------------------------------------------------------------------


@pytest.mark.parametrize(
    "status", ["Todo", "Ready", "In progress", "In review", "Done", "Blocked"]
)
def test_move_sets_each_allowed_status(board, status):
    assert (
        board.run("add", "19", "--wave", "1a", "--agent", "test-engineer").returncode
        == 0
    )
    proc = board.run("move", "19", status)
    assert proc.returncode == 0, proc.stderr
    assert board.item(19)["values"]["Status"] == status
    assert f"-> {status}" in proc.stdout


def test_move_pull_request(board):
    assert (
        board.run("add", "42", "--wave", "2", "--agent", "test-engineer").returncode
        == 0
    )
    assert board.run("move", "42", "In review").returncode == 0
    assert board.item(42)["values"]["Status"] == "In review"


def test_show_prints_card_fields(board):
    assert (
        board.run("add", "19", "--wave", "1b", "--agent", "test-engineer").returncode
        == 0
    )
    proc = board.run("show", "19")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "#19  Status: Ready  Wave: 1b  Agent: test-engineer"


def test_ids_come_from_runtime_lookups(board):
    """No hard-coded IDs: every edit uses IDs that only the stub's field-list knows."""
    assert (
        board.run("add", "19", "--wave", "1a", "--agent", "test-engineer").returncode
        == 0
    )
    edits = [c for c in board.calls() if c[:2] == ["project", "item-edit"]]
    assert {c[c.index("--field-id") + 1] for c in edits} == {
        "F_WAVE",
        "F_AGENT",
        "F_STATUS",
    }
    assert all(c[c.index("--project-id") + 1] == "PVT_1" for c in edits)
    called = {tuple(c[:2]) for c in board.calls()}
    assert ("project", "field-list") in called
    assert ("project", "item-list") in called


# --- missing names -----------------------------------------------------------


def assert_fails(proc, board, message):
    assert proc.returncode != 0
    assert message in proc.stderr, proc.stderr
    assert board.mutating_calls() == [], "nothing may change on failure"


def test_unknown_wave_option_fails_and_lists_options(board):
    proc = board.run("add", "19", "--wave", "1d", "--agent", "test-engineer")
    assert_fails(
        proc, board, 'Wave option "1d" not found; have: 1a, 1b, 1c, 2, 3, 4, 5, 6'
    )


def test_unknown_agent_option_fails_and_lists_options(board):
    proc = board.run("add", "19", "--wave", "1a", "--agent", "ai-engineer")
    assert_fails(
        proc,
        board,
        'Agent option "ai-engineer" not found; have: platform-engineer, test-engineer',
    )


def test_unknown_status_name_fails_and_lists_allowed(board):
    proc = board.run("move", "19", "Doing")
    assert_fails(
        proc,
        board,
        'Status "Doing" is not allowed; use one of: Todo, Ready, In progress, In review, Done, Blocked',
    )


def test_status_option_missing_on_board_fails(tmp_path):
    state = copy.deepcopy(BASE_STATE)
    status = next(f for f in state["fields"] if f["name"] == "Status")
    status["options"] = [o for o in status["options"] if o["name"] != "Blocked"]
    b = Board(tmp_path, state)
    proc = b.run("move", "19", "Blocked")
    assert_fails(
        proc,
        b,
        'Status option "Blocked" not found; have: Done, In progress, In review, Ready, Todo',
    )


def test_ready_option_missing_makes_add_fail(tmp_path):
    state = copy.deepcopy(BASE_STATE)
    status = next(f for f in state["fields"] if f["name"] == "Status")
    status["options"] = [o for o in status["options"] if o["name"] != "Ready"]
    b = Board(tmp_path, state)
    proc = b.run("add", "19", "--wave", "1a", "--agent", "test-engineer")
    assert_fails(
        proc,
        b,
        'Status option "Ready" not found; have: Blocked, Done, In progress, In review, Todo',
    )


@pytest.mark.parametrize("missing", ["Wave", "Agent", "Status"])
def test_missing_field_fails_and_lists_fields(tmp_path, missing):
    state = copy.deepcopy(BASE_STATE)
    state["fields"] = [f for f in state["fields"] if f["name"] != missing]
    b = Board(tmp_path, state)
    have = ", ".join(sorted({"Status", "Wave", "Agent"} - {missing}))
    proc = b.run("add", "19", "--wave", "1a", "--agent", "test-engineer")
    assert_fails(
        proc, b, f'single-select field "{missing}" not found on project 5; have: {have}'
    )


def test_unknown_project_fails(board):
    state = board.state
    state["number"] = 6  # the stub now only knows project 6
    board.state_file.write_text(json.dumps(state))
    proc = board.run("move", "19", "Ready")
    assert_fails(proc, board, f"project 5 (owner {OWNER}) not found")


def test_unknown_issue_fails_on_add(board):
    proc = board.run("add", "999", "--wave", "1a", "--agent", "test-engineer")
    assert_fails(proc, board, f"issue or PR #999 not found in {REPO}")


def test_unknown_issue_fails_on_move(board):
    proc = board.run("move", "999", "Ready")
    assert_fails(proc, board, f"issue or PR #999 not found in {REPO}")


def test_issue_not_on_board_fails_on_move(board):
    proc = board.run("move", "20", "Ready")
    assert_fails(proc, board, "#20 is not on project 5; add it first")


def test_non_numeric_issue_fails(board):
    proc = board.run("move", "abc", "Ready")
    assert_fails(proc, board, '"abc" is not an issue or PR number')


def test_never_creates_fields_or_options(board):
    board.run("add", "19", "--wave", "1d", "--agent", "test-engineer")
    board.run("add", "19", "--wave", "1a", "--agent", "test-engineer")
    board.run("move", "19", "Done")
    allowed = {
        ("auth", "status"),
        ("api",),
        ("project", "view"),
        ("project", "field-list"),
        ("project", "item-list"),
        ("project", "item-add"),
        ("project", "item-edit"),
    }
    for call in board.calls():
        key = ("api",) if call[0] == "api" else tuple(call[:2])
        assert key in allowed, call
        if key == ("project", "item-edit"):
            assert "--single-select-option-id" in call


# --- tools and scope ---------------------------------------------------------


def test_missing_gh_fails_clearly(board, tmp_path):
    jq_dir = tmp_path / "jqonly"
    jq_dir.mkdir()
    (jq_dir / "jq").symlink_to(JQ)
    proc = board.run("show", "19", path=str(jq_dir))
    assert proc.returncode != 0
    assert "required tool(s) not found on PATH: gh" in proc.stderr


def test_missing_jq_fails_clearly(board):
    proc = board.run("show", "19", path=str(board.bin))  # stub gh only, no jq
    assert proc.returncode != 0
    assert "required tool(s) not found on PATH: jq" in proc.stderr


def test_missing_project_scope_fails_clearly(tmp_path):
    state = copy.deepcopy(BASE_STATE)
    state["scopes"] = ["gist", "repo"]
    b = Board(tmp_path, state)
    proc = b.run("move", "19", "Ready")
    assert_fails(proc, b, "gh token lacks the 'project' scope")


def test_unauthenticated_gh_fails_clearly(tmp_path):
    state = copy.deepcopy(BASE_STATE)
    state["authenticated"] = False
    b = Board(tmp_path, state)
    proc = b.run("move", "19", "Ready")
    assert_fails(proc, b, "gh is not authenticated")


def test_usage_error_exits_non_zero(board):
    assert board.run().returncode != 0
    assert board.run("add", "19", "--wave", "1a").returncode != 0
    assert board.run("frobnicate").returncode != 0


def test_gh_failure_reason_is_shown(tmp_path):
    state = copy.deepcopy(BASE_STATE)
    state["fail"] = {"project field-list": "GraphQL: API rate limit exceeded"}
    b = Board(tmp_path, state)
    proc = b.run("move", "19", "Ready")
    assert_fails(
        proc,
        b,
        "could not list fields of project 5 (owner octo) "
        "(gh: GraphQL: API rate limit exceeded)",
    )
