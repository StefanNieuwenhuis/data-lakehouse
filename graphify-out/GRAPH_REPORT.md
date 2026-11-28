# Graph Report - lakehouse  (2026-11-28)

## Corpus Check
- 28 files · ~19,105 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: (none) 16, .mk 5, .lock 1)
- WARNING: 22 of 50 files seen (44%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 244 nodes · 385 edges · 25 communities (14 shown, 11 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 33 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0a2c2793`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- block_destructive.py
- CLAUDE.md
- Decision
- Decision
- Architecture
- steps
- test_board.py
- 0003. Chart sourcing, image pinning and tool pinning
- 0001. Record architecture decisions
- 0004. Postgres via CloudNativePG
- data-engineer.md
- orchestrator.md
- platform-engineer.md
- reviewer.md
- test-engineer.md
- README.md
- lakehouse
- board.sh

## God Nodes (most connected - your core abstractions)
1. `Board` - 15 edges
2. `assert_fails()` - 15 edges
3. `Architecture` - 14 edges
4. `die()` - 13 edges
5. `main()` - 10 edges
6. `Decision` - 10 edges
7. `cmd_add()` - 9 edges
8. `main()` - 8 edges
9. `cmd_show()` - 8 edges
10. `Decision` - 8 edges

## Surprising Connections (you probably didn't know these)
- `test_unknown_project_fails()` --calls--> `json`  [EXTRACTED]
  tests/tools/test_board.py →   _Bridges community 6 → community 0_

## Import Cycles
- None detected.

## Communities (25 total, 11 thin omitted)

### Community 0 - "block_destructive.py"
Cohesion: 0.14
Nodes (19): block(), check_git(), check_helm(), check_kubectl(), check_rm(), current_branch(), flag_value(), main() (+11 more)

### Community 1 - "CLAUDE.md"
Cohesion: 0.29
Nodes (6): Commands, Conventions, Guardrails (`.claude/settings.json`, `.claude/hooks/`), Layout and ownership, Project, Workflow

### Community 2 - "Decision"
Cohesion: 0.07
Nodes (25): 0002. Object store: SeaweedFS instead of MinIO, Alternatives considered, Amendment (2026-11-28, spike #3): confirmed, Consequences, Context, Decision, Status, 0005. Secrets, Lakekeeper auth and storage credentials (+17 more)

### Community 3 - "Decision"
Cohesion: 0.12
Nodes (16): 0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job, Agent concurrency, Alternatives considered, Amendment (2026-11-28, spike #3): smoke round trip repeated 5 times, one worker, no retries, Cluster lock, CNI and NetworkPolicy, Consequences, Context (+8 more)

### Community 4 - "Architecture"
Cohesion: 0.13
Nodes (14): Agent concurrency and Phase 1 waves, Architecture, Cluster and resources, Components, How components connect (Phase 1), Make targets, Namespaces, Network policy matrix (issue 17, end of Phase 1) (+6 more)

### Community 5 - "steps"
Cohesion: 0.09
Nodes (25): concurrency, cancel-in-progress, group, name, runs-on, steps, jobs, helm-template (+17 more)

### Community 6 - "test_board.py"
Cohesion: 0.11
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

### Community 11 - "orchestrator.md"
Cohesion: 0.50
Nodes (3): Growing the team, Hard rules, Your job

### Community 12 - "platform-engineer.md"
Cohesion: 0.50
Nodes (3): How you work, Not yours, You own

### Community 22 - "board.sh"
Cohesion: 0.30
Nodes (17): check_scope(), check_tools(), cmd_add(), cmd_move(), cmd_show(), content_url(), describe(), die() (+9 more)

## Knowledge Gaps
- **1 isolated node(s):** `lakehouse`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 122 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job` connect `Decision` to `Decision`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `lakehouse` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `block_destructive.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14453781512605043 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.07142857142857142 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
- **Should `steps` be split into smaller, more focused modules?**
  _Cohesion score 0.08923076923076922 - nodes in this community are weakly interconnected._