---
description: Run a phase's smoke tests against the live cluster and report pass or fail
argument-hint: <phase-number>
---

Phase: $ARGUMENTS

1. **Pre-flight.** Check that the cluster is up with `minikube status` and `kubectl get pods -A`. If the cluster is down or pods are not ready, report that and stop. Don't try to fix the cluster.
2. **Run the gate.** Run `make smoke-phase$ARGUMENTS`. If that target doesn't exist, say so and stop.
3. **Report** in this format:

```
Gate phase $ARGUMENTS: PASS | FAIL
Ran: <timestamp>, <git short sha>
Checks: <passed>/<total>
Failures:
- <check name>: <one-line reason>
```

On failure, add the relevant log excerpt for each failing check, and suggest which agent should own the fix: platform-engineer for infrastructure, data-engineer for data, or test-engineer if the test itself is wrong.

Report only. Don't change code, tests or the cluster.
