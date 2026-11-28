// branch-name-lint config for branch names (ADR-0007, issue #26).
// Run through `make check-branch` (part of `make check-conventions`).
//
// branch-name-lint reads the branch from $BRANCH, or from git when BRANCH is
// empty. Everything allowed is read from docs/conventions.yaml at runtime and
// never copied here. The title's type comes from $TITLE, parsed with the same
// Conventional Commits parser preset that commitlint uses. When it is a known
// type, only the prefix that branch_prefixes maps it to is accepted.
// CONVENTIONS_FILE overrides the path (fixture tests).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import createPreset from "conventional-changelog-conventionalcommits";
import { CommitParser } from "conventional-commits-parser";
import { parse } from "yaml";

const conventionsPath =
  process.env.CONVENTIONS_FILE ||
  fileURLToPath(new URL("../../docs/conventions.yaml", import.meta.url));
const { types, branch_prefixes: prefixMap } = parse(readFileSync(conventionsPath, "utf8"));

const title = process.env.TITLE || "";
const titleType = title ? new CommitParser(createPreset().parser).parse(title).type : null;
const expected = types.includes(titleType) ? prefixMap[titleType] : null;

// Prefixes without the trailing "/", which branch-name-lint uses as separator.
const allowed = expected ? [expected] : [...new Set(Object.values(prefixMap))];
const prefixes = allowed.map((p) => p.replace(/\/$/, ""));
const mapText = Object.entries(prefixMap)
  .map(([t, p]) => `${t} -> ${p}`)
  .join(", ");
const prefixRule = expected
  ? `title type "${titleType}" needs prefix "${expected}"`
  : `allowed prefixes: ${allowed.join(", ")}`;

export const branchNameLinter = {
  prefixes,
  suggestions: {},
  banned: [],
  disallowed: [],
  skip: [],
  separator: "/",
  // <prefix>/<issue>-<slug>: issue number without a leading zero, then
  // lowercase a-z0-9 words joined by single hyphens. ADR-0007 forbids dots.
  regex: "^[a-z]+/[1-9][0-9]*-[a-z0-9]+(-[a-z0-9]+)*$",
  branchNameEnvVariable: "BRANCH",
  msgseparatorRequired: `[branch-format] "%s" must be <prefix>/<issue>-<slug> (separator "%s"); ${prefixRule}.`,
  msgDoesNotMatchRegex:
    '[branch-slug] "%s" must be <prefix>/<issue>-<slug>: lowercase a-z0-9, ' +
    "an issue number, single hyphens, no dots, nothing leading or trailing " +
    `(pattern %s); ${prefixRule}.`,
  msgPrefixNotAllowed: `[branch-prefix] prefix "%s/" is not allowed: ${prefixRule}. Type -> prefix map: ${mapText}.`,
};
