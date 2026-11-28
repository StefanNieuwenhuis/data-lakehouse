"""Fake `gh` for the tools/board.sh tests (issue #19).

The tests install this file as `gh` on PATH. It implements only the gh
subcommands board.sh calls, backed by a JSON state file named in
$GH_STUB_STATE, and appends each call (one JSON argv list per line) to
$GH_STUB_LOG so tests can assert what was, and was not, changed.

State layout:
    {
      "scopes": ["project", "repo"],      # gh auth status token scopes
      "authenticated": true,
      "owner": "o", "number": 5, "project_id": "PVT_1",
      "fields": [{"id", "name", "type", "options": [{"id", "name"}]}],
      "issues": {"19": "https://github.com/o/r/issues/19"},
      "items": [{"id", "url", "number", "values": {"Status": "Todo"}}]
    }
"""

import json
import os
import sys


def load():
    with open(os.environ["GH_STUB_STATE"]) as fh:
        return json.load(fh)


def save(state):
    with open(os.environ["GH_STUB_STATE"], "w") as fh:
        json.dump(state, fh)


def flag(args, name):
    i = args.index(name)
    return args[i + 1]


def fail(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def check_project(state, args):
    if str(args[2]) != str(state["number"]) or flag(args, "--owner") != state["owner"]:
        fail("Could not resolve to a ProjectV2 with the number " + str(args[2]))


def item_view(state, item):
    out = {"id": item["id"], "content": {"url": item["url"], "number": item["number"]}}
    for field, value in item["values"].items():
        out[field.lower()] = value
    return out


def main():
    args = sys.argv[1:]
    with open(os.environ["GH_STUB_LOG"], "a") as fh:
        fh.write(json.dumps(args) + "\n")
    state = load()

    # "fail": {"project field-list": "GraphQL: API rate limit exceeded"} makes
    # that subcommand fail with the given stderr message.
    message = state.get("fail", {}).get(" ".join(args[:2]))
    if message:
        fail(message)

    if args[:2] == ["auth", "status"]:
        if not state.get("authenticated", True):
            fail("You are not logged into any GitHub hosts.")
        scopes = ", ".join(f"'{s}'" for s in state["scopes"])
        print("github.com\n  - Token scopes: " + scopes)
        return

    if args[:1] == ["api"]:
        number = args[1].rsplit("/", 1)[-1]
        url = state["issues"].get(number)
        if url is None:
            fail("gh: Not Found (HTTP 404)")
        print(json.dumps({"number": int(number), "html_url": url}))
        return

    if args[:2] == ["project", "view"]:
        check_project(state, args)
        print(json.dumps({"id": state["project_id"], "number": state["number"]}))
        return

    if args[:2] == ["project", "field-list"]:
        check_project(state, args)
        print(
            json.dumps({"fields": state["fields"], "totalCount": len(state["fields"])})
        )
        return

    if args[:2] == ["project", "item-list"]:
        check_project(state, args)
        items = [item_view(state, i) for i in state["items"]]
        print(json.dumps({"items": items, "totalCount": len(items)}))
        return

    if args[:2] == ["project", "item-add"]:
        check_project(state, args)
        url = flag(args, "--url")
        for item in state["items"]:
            if item["url"] == url:
                break
        else:
            item = {
                "id": f"PVTI_{len(state['items']) + 1}",
                "url": url,
                "number": int(url.rsplit("/", 1)[-1]),
                "values": {},
            }
            state["items"].append(item)
            save(state)
        print(json.dumps({"id": item["id"]}))
        return

    if args[:2] == ["project", "item-edit"]:
        if flag(args, "--project-id") != state["project_id"]:
            fail("project id mismatch")
        item = next((i for i in state["items"] if i["id"] == flag(args, "--id")), None)
        field = next(
            (f for f in state["fields"] if f["id"] == flag(args, "--field-id")), None
        )
        if item is None or field is None:
            fail("unknown item or field id")
        oid = flag(args, "--single-select-option-id")
        option = next((o for o in field["options"] if o["id"] == oid), None)
        if option is None:
            fail("unknown option id")
        item["values"][field["name"]] = option["name"]
        save(state)
        print(json.dumps({"id": item["id"]}))
        return

    fail("gh stub: unsupported call: " + " ".join(args), code=99)


if __name__ == "__main__":
    main()
