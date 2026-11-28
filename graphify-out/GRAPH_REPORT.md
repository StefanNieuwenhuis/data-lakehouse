# Graph Report - 2-helm-template-kubeconform  (2026-11-28)

## Corpus Check
- 56 files · ~23,110 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 23 file(s) not represented in the graph (top: (none) 17, .mk 5, .lock 1)
- WARNING: 23 of 79 files seen (29%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 455 nodes · 589 edges · 45 communities (28 shown, 17 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 33 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `45f9325d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- block_destructive.py
- branch_prefixes
- Decision
- Decision
- Architecture
- ci.yml
- test_board.py
- 0003. Chart sourcing, image pinning and tool pinning
- 0001. Record architecture decisions
- 0004. Postgres via CloudNativePG
- data-engineer.md
- containers
- platform-engineer.md
- reviewer.md
- test-engineer.md
- README.md
- Job {{ .Release.Name }}-nolimits
- lakehouse
- board.sh
- Job {{ .Release.Name }}-once
- customChecks
- broken-crd-unknown-field/templates/cnpg-cluster.yaml
- 0007. Conventional Commits and Conventional Branch for titles, commits and branches
- valid/templates/cnpg-cluster.yaml
- broken-crd-unknown-field/Chart.yaml
- broken-dev-values/Chart.yaml
- broken-missing-limits/Chart.yaml
- broken-missing-schema/Chart.yaml
- widget.yaml
- broken-schema/Chart.yaml
- valid/Chart.yaml
- ensure_tool.sh
- chart_check.sh
- test_fixture_charts.sh
- broken-crd-unknown-field/values.yaml
- broken-dev-values/values.yaml
- broken-missing-limits/values.yaml
- broken-schema/values.yaml
- valid/values.yaml

## God Nodes (most connected - your core abstractions)
1. `Board` - 15 edges
2. `assert_fails()` - 15 edges
3. `Architecture` - 14 edges
4. `die()` - 13 edges
5. `branch_prefixes` - 11 edges
6. `main()` - 10 edges
7. `Decision` - 10 edges
8. `cmd_add()` - 9 edges
9. `main()` - 8 edges
10. `cmd_show()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `test_unknown_project_fails()` --calls--> `json`  [EXTRACTED]
  tests/tools/test_board.py →   _Bridges community 6 → community 0_

## Import Cycles
- None detected.

## Communities (45 total, 17 thin omitted)

### Community 0 - "block_destructive.py"
Cohesion: 0.14
Nodes (19): block(), check_git(), check_helm(), check_kubectl(), check_rm(), current_branch(), flag_value(), main() (+11 more)

### Community 1 - "branch_prefixes"
Cohesion: 0.05
Nodes (34): Growing the team, Hard rules, Your job, Commands, Conventions, Guardrails (`.claude/settings.json`, `.claude/hooks/`), Layout and ownership, Naming (+26 more)

### Community 2 - "Decision"
Cohesion: 0.11
Nodes (18): 0005. Secrets, Lakekeeper auth and storage credentials, Agent-leak guards, Alternatives considered, Amendment (2026-11-28, spike #3): remote signing confirmed, with client conditions, Conditions for every PyIceberg client, Consequences, Context, Decision (+10 more)

### Community 3 - "Decision"
Cohesion: 0.12
Nodes (16): 0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job, Agent concurrency, Alternatives considered, Amendment (2026-11-28, spike #3): smoke round trip repeated 5 times, one worker, no retries, Cluster lock, CNI and NetworkPolicy, Consequences, Context (+8 more)

### Community 4 - "Architecture"
Cohesion: 0.13
Nodes (14): Agent concurrency and Phase 1 waves, Architecture, Cluster and resources, Components, How components connect (Phase 1), Make targets, Namespaces, Network policy matrix (issue 17, end of Phase 1) (+6 more)

### Community 5 - "ci.yml"
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

### Community 11 - "containers"
Cohesion: 0.08
Nodes (26): apiVersion, command, image, name, resources, command, image, name (+18 more)

### Community 12 - "platform-engineer.md"
Cohesion: 0.50
Nodes (3): How you work, Not yours, You own

### Community 17 - "Job {{ .Release.Name }}-nolimits"
Cohesion: 0.09
Nodes (23): command, image, name, resources, apiVersion, kind, metadata, spec (+15 more)

### Community 22 - "board.sh"
Cohesion: 0.30
Nodes (17): check_scope(), check_tools(), cmd_add(), cmd_move(), cmd_show(), content_url(), describe(), die() (+9 more)

### Community 25 - "Job {{ .Release.Name }}-once"
Cohesion: 0.09
Nodes (23): command, image, name, resources, apiVersion, kind, metadata, spec (+15 more)

### Community 26 - "customChecks"
Cohesion: 0.14
Nodes (13): checks, doNotAutoAddDefaults, customChecks, description, name, params, remediation, template (+5 more)

### Community 27 - "broken-crd-unknown-field/templates/cnpg-cluster.yaml"
Cohesion: 0.20
Nodes (9): apiVersion, kind, metadata, name, spec, instances, storage, unknownField (+1 more)

### Community 28 - "0007. Conventional Commits and Conventional Branch for titles, commits and branches"
Cohesion: 0.22
Nodes (9): 0007. Conventional Commits and Conventional Branch for titles, commits and branches, Alternatives considered, Branches, Consequences, Context, Decision, Prefixes deliberately not used, Status (+1 more)

### Community 29 - "valid/templates/cnpg-cluster.yaml"
Cohesion: 0.22
Nodes (8): apiVersion, kind, metadata, name, spec, instances, storage, size

### Community 30 - "broken-crd-unknown-field/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 31 - "broken-dev-values/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 32 - "broken-missing-limits/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 33 - "broken-missing-schema/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 34 - "widget.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, kind, metadata, name, spec, size

### Community 35 - "broken-schema/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 36 - "valid/Chart.yaml"
Cohesion: 0.29
Nodes (6): apiVersion, appVersion, description, name, type, version

### Community 37 - "ensure_tool.sh"
Cohesion: 0.83
Nodes (3): die(), ensure_tool.sh script, version_of()

## Knowledge Gaps
- **1 isolated node(s):** `lakehouse`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 249 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `0005. Secrets, Lakekeeper auth and storage credentials` connect `Decision` to `branch_prefixes`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **What connects `lakehouse` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `block_destructive.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14453781512605043 - nodes in this community are weakly interconnected._
- **Why does `0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job` connect `Decision` to `branch_prefixes`?**
  _High betweenness centrality (0.011) - this node is a cross-community bridge._
- **Should `branch_prefixes` be split into smaller, more focused modules?**
  _Cohesion score 0.048726467331118496 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._