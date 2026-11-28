// commitlint config for PR titles (ADR-0007, issue #26).
// Run through `make check-title` (part of `make check-conventions`). The
// squash commit on main is the PR title, so the title is linted as a commit
// header.
//
// The allowed types and scopes are read from docs/conventions.yaml at runtime.
// They are never copied here. CONVENTIONS_FILE overrides the path (fixture
// tests). Only built-in commitlint rules are used.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const conventionsPath =
  process.env.CONVENTIONS_FILE ||
  fileURLToPath(new URL("../../docs/conventions.yaml", import.meta.url));
const { types, scopes } = parse(readFileSync(conventionsPath, "utf8"));

export default {
  // Parser preset for `type(scope)!: summary`, plus its default rules. Its
  // subject-case rule (never sentence-, start-, pascal- or upper-case) is what
  // enforces "the summary starts lowercase": it rejects "Add x" and
  // "SeaweedFS chart" but accepts "add SeaweedFS chart".
  extends: ["@commitlint/config-conventional"],
  // commitlint skips merge, revert, fixup! and squash! messages by default.
  // A PR title becomes the squash commit, so none of them is exempt.
  defaultIgnores: false,
  // The preset's header pattern, except the summary must start right after
  // one space and not with a digit (ADR-0007: it starts with a lowercase
  // letter; subject-case covers uppercase). "feat(ci):  x" and "feat(ci): 2
  // charts" do not parse, so type-empty fails.
  parserPreset: {
    parserOpts: { headerPattern: /^(\w*)(?:\((.*)\))?!?: ([^\s\d].*)$/ },
  },
  helpUrl: "docs/adr/0007-conventional-commits-and-branches.md",
  rules: {
    "type-enum": [2, "always", types],
    "type-empty": [2, "never"],
    "type-case": [2, "always", "lower-case"],
    "scope-enum": [2, "always", scopes],
    "scope-empty": [2, "never"],
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    "header-trim": [2, "always"],
  },
};
