# Graph Report - lakehouse  (2026-11-28)

## Corpus Check
- 25 files · ~15,900 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 22 file(s) not represented in the graph (top: (none) 16, .mk 5, .lock 1)
- WARNING: 22 of 47 files seen (47%) have no supported extractor and are missing from this graph entirely. It may look complete while representing only part of the codebase.

## Summary
- 169 nodes · 193 edges · 22 communities (13 shown, 9 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `66abeb6d`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- block_destructive.py
- CLAUDE.md
- Decision
- Decision
- Architecture
- steps
- ci.yml
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

## God Nodes (most connected - your core abstractions)
1. `Architecture` - 14 edges
2. `main()` - 10 edges
3. `Decision` - 10 edges
4. `Decision` - 8 edges
5. `0002. Object store: SeaweedFS instead of MinIO` - 7 edges
6. `0005. Secrets, Lakekeeper auth and storage credentials` - 7 edges
7. `0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job` - 7 edges
8. `block()` - 6 edges
9. `run()` - 6 edges
10. `main()` - 6 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (22 total, 9 thin omitted)

### Community 0 - "block_destructive.py"
Cohesion: 0.19
Nodes (12): block(), check_git(), check_helm(), check_kubectl(), check_rm(), current_branch(), flag_value(), main() (+4 more)

### Community 1 - "CLAUDE.md"
Cohesion: 0.12
Nodes (13): Commands, Conventions, Guardrails (`.claude/settings.json`, `.claude/hooks/`), Layout and ownership, Project, Workflow, 0002. Object store: SeaweedFS instead of MinIO, Alternatives considered (+5 more)

### Community 2 - "Decision"
Cohesion: 0.11
Nodes (18): 0005. Secrets, Lakekeeper auth and storage credentials, Agent-leak guards, Alternatives considered, Amendment (2026-11-28, spike #3): remote signing confirmed, with client conditions, Conditions for every PyIceberg client, Consequences, Context, Decision (+10 more)

### Community 3 - "Decision"
Cohesion: 0.12
Nodes (16): 0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job, Agent concurrency, Alternatives considered, Amendment (2026-11-28, spike #3): smoke round trip repeated 5 times, one worker, no retries, Cluster lock, CNI and NetworkPolicy, Consequences, Context (+8 more)

### Community 4 - "Architecture"
Cohesion: 0.13
Nodes (14): Agent concurrency and Phase 1 waves, Architecture, Cluster and resources, Components, How components connect (Phase 1), Make targets, Namespaces, Network policy matrix (issue 17, end of Phase 1) (+6 more)

### Community 5 - "steps"
Cohesion: 0.17
Nodes (15): name, runs-on, steps, jobs, helm-template, lint, name, runs-on (+7 more)

### Community 6 - "ci.yml"
Cohesion: 0.18
Nodes (10): concurrency, cancel-in-progress, group, name, on, pull_request, push, permissions (+2 more)

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

## Knowledge Gaps
- **1 isolated node(s):** `lakehouse`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 112 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `0005. Secrets, Lakekeeper auth and storage credentials` connect `Decision` to `CLAUDE.md`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **What connects `lakehouse` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLAUDE.md` be split into smaller, more focused modules?**
  _Cohesion score 0.11764705882352941 - nodes in this community are weakly interconnected._
- **Why does `0006. Namespaces per layer, minikube sizing, cluster lock and in-cluster smoke Job` connect `Decision` to `CLAUDE.md`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `Decision` be split into smaller, more focused modules?**
  _Cohesion score 0.125 - nodes in this community are weakly interconnected._
- **Should `Architecture` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._