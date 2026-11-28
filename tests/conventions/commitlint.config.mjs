// commitlint config for PR titles (ADR-0007, issue #26).
// Run through `make check-conventions`; the squash commit on main is the PR
// title, so the title is linted as a commit header.
//
// The allowed types and scopes are read from docs/conventions.yaml at runtime.
// They are never copied here. CONVENTIONS_FILE overrides the path (tests).
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const conventionsPath =
  process.env.CONVENTIONS_FILE ||
  fileURLToPath(new URL("../../docs/conventions.yaml", import.meta.url));
const conventions = parse(readFileSync(conventionsPath, "utf8"));

for (const key of ["types", "scopes"]) {
  if (!Array.isArray(conventions?.[key]) || conventions[key].length === 0) {
    throw new Error(`${conventionsPath}: \`${key}\` must be a non-empty list`);
  }
}

export default {
  // Parser preset for `type(scope)!: summary`, plus its default rules
  // (type-case, subject-full-stop, subject-case, header-max-length, ...).
  extends: ["@commitlint/config-conventional"],
  plugins: [
    {
      rules: {
        // The one ADR-0007 rule commitlint has no built-in for: the summary
        // starts with a lowercase letter ("add SeaweedFS chart" is fine,
        // "SeaweedFS chart" is not), right after a single space.
        "subject-lowercase-first": ({ subject }) => {
          if (!subject) return [true];
          const first = subject[0];
          const ok = !/\s/.test(first) && first === first.toLowerCase();
          return [ok, `subject must start with a lowercase letter, after one space (got ${JSON.stringify(first)})`];
        },
      },
    },
  ],
  rules: {
    "type-enum": [2, "always", conventions.types],
    "type-empty": [2, "never"],
    "type-case": [2, "always", "lower-case"],
    "scope-enum": [2, "always", conventions.scopes],
    "scope-empty": [2, "never"],
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    "subject-lowercase-first": [2, "always"],
    "header-trim": [2, "always"],
  },
};
