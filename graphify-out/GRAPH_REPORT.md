# Graph Report - 26-enforce-conventions-markdown-lint  (2026-11-28)

## Corpus Check
- 46 files · ~24,418 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 23 file(s) not represented in the graph (top: (none) 17, .mk 5, .lock 1)
- WARNING: 23 of 69 files seen (33%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 452 nodes · 694 edges · 33 communities (22 shown, 11 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 33 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `45f9325d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- block_destructive.py
- test_check_conventions.py
- Decision
- Decision
- Architecture
- ci.yml
- test_board.py
- 0003. Chart sourcing, image pinning and tool pinning
- 0001. Record architecture decisions
- 0004. Postgres via CloudNativePG
- data-engineer.md
- branch_prefixes
- platform-engineer.md
- reviewer.md
- test-engineer.md
- README.md
- subprocess
- lakehouse
- board.sh
- steps
- steps
- package.json
- attributes
- attributes
- attributes
- valid-target.md
- broken-internal-link.md

## God Nodes (most connected - your core abstractions)
1. `run_check()` - 27 edges
2. `assert_fails()` - 20 edges
3. `Board` - 15 edges
4. `assert_fails()` - 15 edges
5. `Architecture` - 14 edges
6. `die()` - 13 edges
7. `branch_prefixes` - 11 edges
8. `main()` - 10 edges
9. `Decision` - 10 edges
10. `cmd_add()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `current_branch()` --calls--> `subprocess`  [EXTRACTED]
  .claude/hooks/block_destructive.py →   _Bridges community 0 → community 17_
- `load_conventions()` --calls--> `yaml`  [EXTRACTED]
  tests/conventions/check_conventions.py →   _Bridges community 17 → community 1_
- `test_unknown_project_fails()` --calls--> `json`  [EXTRACTED]
  tests/tools/test_board.py →   _Bridges community 6 → community 0_

## Import Cycles
- None detected.

## Communities (33 total, 11 thin omitted)

### Community 0 - "block_destructive.py"
Cohesion: 0.14
Nodes (19): block(), check_git(), check_helm(), check_kubectl(), check_rm(), current_branch(), flag_value(), main() (+11 more)

### Community 1 - "test_check_conventions.py"
Cohesion: 0.14
Nodes (32): assert_fails(), make_check(), run_check(), test_branch_double_hyphen_fails(), test_branch_fix_type_on_chore_prefix_fails(), test_branch_malformed_slug_fails(), test_branch_prefix_not_matching_type_fails_and_shows_map(), test_branch_trailing_hyphen_fails() (+24 more)

### Community 2 - "Decision"
Cohesion: 0.11
Nodes (18): 0005. Secrets, Lakekeeper auth and storage credentials, Agent-leak guards, Alternatives considered, Amendment (2026-11-28, spike #3): remote signing confirmed, with client conditions, Conditions for every PyIceberg client, Consequences, Context, Decision (+10 more)

### Community 3 - "Decision"
Cohesion: 0.06
Nodes (30): Commands, Conventions, Guardrails (`.claude/settings.json`, `.claude/hooks/`), Layout and ownership, Naming, Project, Workflow, 0002. Object store: SeaweedFS instead of MinIO (+22 more)

### Community 4 - "Architecture"
Cohesion: 0.13
Nodes (14): Agent concurrency and Phase 1 waves, Architecture, Cluster and resources, Components, How components connect (Phase 1), Make targets, Namespaces, Network policy matrix (issue 17, end of Phase 1) (+6 more)

### Community 5 - "ci.yml"
Cohesion: 0.09
Nodes (29): concurrency, cancel-in-progress, group, name, runs-on, steps, jobs, helm-template (+21 more)

### Community 6 - "test_board.py"
Cohesion: 0.12
Nodes (31): assert_fails(), board(), Board, test_add_moves_auto_added_todo_card_to_ready(), test_add_new_issue_sets_wave_agent_and_status_ready(), test_add_pull_request(), test_gh_failure_reason_is_shown(), test_ids_come_from_runtime_lookups() (+23 more)

### Community 7 - "0003. Chart sourcing, image pinning and tool pinning"
Cohesion: 0.20
Nodes (9): 0003. Chart sourcing, image pinning and tool pinning, Alternatives considered, Charts, Consequences, Context, Decision, Images, Status (+1 more)

### Community 8 - "0001. Record architecture decisions"
Cohesion: 0.29
Nodes (6): 0001. Record architecture decisions, Alternatives considered, Consequences, Context, Decision, Status

### Community 9 - "0004. Postgres via CloudNativePG"
Cohesion: 0.29
Nodes (6): 0004. Postgres via CloudNativePG, Alternatives considered, Consequences, Context, Decision, Status

### Community 10 - "data-engineer.md"
Cohesion: 0.50
Nodes (3): How you work, No cluster admin, You own

### Community 11 - "branch_prefixes"
Cohesion: 0.06
Nodes (29): Growing the team, Hard rules, Your job, 0007. Conventional Commits and Conventional Branch for titles, commits and branches, Alternatives considered, Branches, Consequences, Context (+21 more)

### Community 12 - "platform-engineer.md"
Cohesion: 0.50
Nodes (3): How you work, Not yours, You own

### Community 17 - "subprocess"
Cohesion: 0.14
Nodes (14): check_branch(), ConfigError, current_branch(), lint_title(), load_conventions(), main(), title_type(), lint_links() (+6 more)

### Community 22 - "board.sh"
Cohesion: 0.30
Nodes (17): check_scope(), check_tools(), cmd_add(), cmd_move(), cmd_show(), content_url(), describe(), die() (+9 more)

### Community 23 - "steps"
Cohesion: 0.08
Nodes (23): concurrency, cancel-in-progress, group, name, runs-on, steps, BRANCH, TITLE (+15 more)

### Community 24 - "steps"
Cohesion: 0.10
Nodes (19): GITHUB_TOKEN, jobs, links-external, name, runs-on, steps, name, on (+11 more)

### Community 25 - "package.json"
Cohesion: 0.14
Nodes (13): ADR-0007, @commitlint/cli, @commitlint/config-conventional, yaml, conventions, description, devDependencies, @commitlint/cli@21.2.4 (+5 more)

### Community 26 - "attributes"
Cohesion: 0.13
Nodes (14): description, label, options, render, value, body, attributes, id (+6 more)

### Community 27 - "attributes"
Cohesion: 0.13
Nodes (14): description, label, options, render, value, body, attributes, id (+6 more)

### Community 28 - "attributes"
Cohesion: 0.13
Nodes (14): description, label, options, render, value, body, attributes, id (+6 more)

### Community 29 - "valid-target.md"
Cohesion: 0.29
Nodes (4): Broken anchor, Valid internal link, Existing heading, Link target

## Knowledge Gaps
- **2 isolated node(s):** `lakehouse`, `ADR-0007`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 222 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `0005. Secrets, Lakekeeper auth and storage credentials` connect `Decision` to `Decision`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `lakehouse`, `ADR-0007` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `block_destructive.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14393939393939395 - nodes in this community are weakly interconnected._
- **Should `test_check_conventions.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14126984126984127 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.058823529411764705 - nodes in this community are weakly interconnected._
- **Should `Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._