# 0005. Secrets, Lakekeeper auth and storage credentials

Date: 2026-11-28

## Status

Accepted. Approved by the user on 2026-11-28 as "Accepted (conditional)", amended after the PR #14 review, and confirmed with client conditions by the object-store spike (issue #3) on 2026-11-28. See the amendment at the end: remote signing stays, every PyIceberg client runs with one worker until the lift rule there is met (upstream apache/iceberg-python#4414 fixed in a pinned release, plus 10 consecutive clean round trips at default workers), and deletes go through Lakekeeper.

The original condition was that the object-store spike (ADR-0002) confirms the write-access mechanism, remote signing through PyIceberg's `FsspecFileIO` against SeaweedFS. The secrets and auth decisions weren't affected by the condition.

## Context

Phase 1 needs credentials for Postgres roles, the S3 object store, and Lakekeeper's own encryption key. CLAUDE.md forbids secrets in git and requires reproducibility through `make`. Lakekeeper stores warehouse storage credentials in Postgres, encrypted with a key it is given at start-up. If that key or the Postgres password changes, Lakekeeper can no longer reach its database or decrypt its stored credentials. SeaweedFS doesn't offer a usable STS, so vended temporary credentials aren't available. Iceberg clients (PyIceberg now, Trino in Phase 2) need write access to table data in the bucket.

In the PR #14 review, the user asked for credentials to be encrypted, and not stored in plaintext in Secrets on the cluster. The upstream SeaweedFS, CNPG and Lakekeeper charts consume credentials through `existingSecret`, so Kubernetes Secrets can't be avoided entirely. They can be encrypted at rest, and kept away from agents.

## Decision

### Threat model

- **Protect against:** agents leaking credentials into transcripts (which leave the host), logs, issue or PR text, or commits. This includes accidents and prompt-injected instructions.
- **Assets:**
  - the S3 key pair;
  - the Postgres `lakekeeper` password;
  - the Lakekeeper Postgres encryption key;
  - the age private key (decrypts `.env.dev.sops`);
  - the etcd encryption key.
- **Disk at rest:** the host disk is covered by FileVault, and the cluster's etcd is covered by Kubernetes encryption at rest (ADR-0006). `.env.dev.sops` is encrypted with SOPS and age.
- **Out of scope:** a malicious local user or a compromised host; workloads inside the cluster (Phase 1 has no in-cluster auth, see below); attackers on the network (nothing is exposed outside minikube).

### Secret generation and storage

- Credentials live in **`.env.dev.sops`** in the repo root. It is a dotenv file encrypted with **SOPS and age**, and it stays **gitignored** (`.env.dev*`). The age private key is in `~/.config/sops/age/keys.txt` (mode 0600), outside the repo. `make secrets` generates it if it is missing. The age recipient is derived from that key file, so no `.sops.yaml` with a personal key goes into git.
- `make secrets` (owned by platform-engineer) is the **only path that decrypts**:
  1. if `.env.dev.sops` is missing, it generates random values in memory and writes them only in encrypted form;
  2. if the file exists, it decrypts **in memory**, adds any missing keys, and never changes or rotates existing values;
  3. it applies each value as a Kubernetes Secret **only in the namespaces that consume it** (table below), idempotently, by piping into `kubectl apply`. The apply step holds the cluster lock (ADR-0006).
- `make secrets` never writes plaintext to disk. It never echoes values: no `set -x`, recipes are silenced, and error messages name keys, not values.
- `make secrets-verify` prints, per Secret key, only a sha256 digest of the in-cluster value next to the digest of the decrypted file value, and whether they match. This proves idempotency without anyone reading a Secret.
- No credential appears in values files, manifests or Makefile lines. Charts reference Secrets through `existingSecret` (or the upstream chart's equivalent). Pods get credentials only through `secretKeyRef` or a mounted Secret, never through a literal `env[].value`.
- Phase 1 secrets are: the S3 admin access and secret key (SeaweedFS S3 config), the Postgres `lakekeeper` role password, and the Lakekeeper Postgres encryption key.

### Secret placement per namespace

There is one source (`.env.dev.sops`), and each value is applied only where it is consumed. A shared credential can't be avoided where both ends of a connection need it: the server verifies it and the client presents it.

| Secret | Namespaces | Consumers | Why |
|---|---|---|---|
| S3 access key and secret key | `lh-storage`, `lh-catalog` | SeaweedFS S3 identity config (verifies signatures); the bootstrap Job (creates the bucket and stores the key pair as the warehouse storage credential, encrypted in Postgres) | SeaweedFS must know the key pair to verify SigV4 signatures. Lakekeeper must hold it to sign |
| Postgres `lakekeeper` role password | `lh-storage`, `lh-catalog` | CNPG managed role (`passwordSecret`); Lakekeeper DB connection and migration Job | Server and client of the same connection |
| Lakekeeper Postgres encryption key | `lh-catalog` only | Lakekeeper | Only Lakekeeper encrypts and decrypts its stored credentials |
| (none) | `lh-ops` | CNPG operator, smoke Job | The operator needs no application credentials (superuser access disabled, ADR-0004). The smoke Job uses remote signing |

The Lakekeeper Deployment itself doesn't mount the S3 key pair. After bootstrap, Lakekeeper reads the storage credential from Postgres. No namespace other than those listed gets a key, and later phases extend this table through an amendment.
- `make deploy` runs `make secrets` first, so `make cluster-up deploy` works on a clean checkout.
- Rotation is out of scope. Losing `.env.dev.sops` or the age key while the cluster has data is documented as destructive (Postgres and Lakekeeper would be locked out). The recovery is `minikube delete` and a fresh `make cluster-up deploy`. The user backs up the age key.

### Agent-leak guards

1. **`.claude/settings.json` `permissions.deny`** (a backstop):
   - `Read(**/.env*)`;
   - `Read(~/.config/sops/**)`;
   - `Read(~/.config/lakehouse/**)` (the etcd encryption config, ADR-0006), plus any copy minikube needs on the host (for example `Read(~/.minikube/files/**)`);
   - `Bash(kubectl get secret*)`, `Bash(kubectl describe secret*)`, `Bash(sops -d*)`.
2. **The PreToolUse hook** (`.claude/hooks/block_destructive.py`) is the **primary guard**. Deny rules only prefix-match the command string, so `kubectl -n dev get secret x` or `cat .env.dev.sops` slip past them. The hook parses arguments, in any order and inside chained commands, and blocks:
   - `kubectl get`, `describe` or `edit` of secrets in any form: `secret`, `secrets`, `secret/x`, or a combined list such as `secret,configmap`, with or without `-n`. Also `kubectl get --raw` paths containing `/secrets`, `kubectl create secret`, and `kubectl get all` with `-o yaml|json|jsonpath|go-template|custom-columns`;
   - `kubectl exec ... -- env` or `printenv`, or reading `/proc/*/environ`;
   - `helm get values`, `helm get all` and `helm get manifest`. Agents debug with `helm template` from the repo instead;
   - any command that has `.env.dev*` (or another `.env*` file) as an argument or redirection, except `ls`, `test`/`[`, `stat` and `git check-ignore`. This covers cat, less, head, tail, grep, source, `.`, and cp or mv;
   - any command with an argument under `~/.config/sops/` or `~/.config/lakehouse/`, with the same exceptions;
   - `sops` except `--version` and `--help` (decrypt, `-d`, `exec-env`, `exec-file` and edit), and `age -d` / `--decrypt`.

   Because the deny rules also prefix-block `kubectl get secrets`, agents can't list Secret names directly either. They use `make secrets-verify` to check existence and consistency.
3. **`make secrets`** is the only decryption path, and it never prints values. The hook sees only `make secrets` and doesn't inspect what the recipe runs.
4. **CI runs gitleaks** (pinned version, Action pinned to a SHA) over PR diffs through `make secrets-scan`. `.gitleaks.toml` allowlists only test fixtures.

The settings and hook changes are test-engineer work and ship in their own small PR labelled `needs-human-read` (ADR-0006).

### Residual risks

| Risk | Status |
|---|---|
| `kubectl exec <pod> -- env` / `printenv` | **Blocked** by the hook. Indirect forms (`sh -c '...'`, other binaries) are best-effort only |
| `helm get values` (and `all`, `manifest`) | **Blocked** by the hook |
| Literal credential in a pod spec, visible through `kubectl get pod -o yaml` | Not blocked. Mitigated: charts use only `secretKeyRef`/`existingSecret`, review checks this, and gitleaks scans diffs |
| `kubectl port-forward` plus direct API calls (Postgres, S3, Lakekeeper) | Not blocked. Using a service doesn't reveal its credential by itself. Mitigated by review |
| Application logs (`kubectl logs`) printing credentials | Not blocked. Mitigated: our Jobs never log values, and a Phase 1 check (issue for the leak guards) scans the startup logs of every Phase 1 component for the decrypted secret values in-process and prints only pass/fail, never the values |
| Node access (`minikube ssh`, `docker exec` into the node) can read the etcd key and mounted Secrets | Not blocked in Phase 1, because cluster checks need it. Mitigated by wrapping the etcd check in a make target. Blocking direct node access is a candidate for a later hook PR |
| Agent-authored code run through `make` or scripts that prints secrets | Not blockable by the hook. Mitigated by PR review, `make secrets` being the only decryption path, and gitleaks |

### Lakekeeper auth

- Phase 1 runs Lakekeeper with **authentication and authorization disabled** (no OIDC, OpenFGA subchart disabled). The REST API is reachable only inside the cluster (ClusterIP).
- Lakekeeper's one-time server bootstrap (accepting the terms of use) and the creation of warehouse `lakehouse` are done by the idempotent `make bootstrap` step.
- OIDC (for example Keycloak) and OpenFGA authorization will come in a later phase under a new ADR. That phase also revisits secret delivery with OpenBao and External Secrets Operator.

### Storage credentials and client write access

- Lakekeeper's warehouse `lakehouse` uses an S3 storage profile pointing to the in-cluster SeaweedFS S3 endpoint, with path-style access, a fixed region string and **STS disabled**. Its storage credential is the **static S3 key pair** from `make secrets`, passed to the bootstrap Job by `secretKeyRef`.
- **Clients get write access through Lakekeeper remote signing.** The static key pair is held only by Lakekeeper. Iceberg clients load the table config from the REST catalog and send their S3 requests to Lakekeeper to be signed. They hold no S3 keys themselves.
- For PyIceberg this means the **fsspec FileIO** (`pyiceberg.io.fsspec.FsspecFileIO`), because PyIceberg's remote S3 signer is implemented for fsspec/s3fs. pyarrow is still used for in-memory data and Parquet encoding. The spike and the smoke test set this FileIO explicitly.
- **Fallback (only by amendment after a failed spike):** static client keys. The smoke Job (and later Trino) gets the S3 key pair through `secretKeyRef` and writes with PyArrowFileIO. Remote signing is then disabled in the storage profile.

## Consequences

- No secret is ever committed, and none is in plaintext on disk. On the host it is SOPS-encrypted and on FileVault; in the cluster, etcd is encrypted. A clean clone plus `make cluster-up deploy` gives a working stack with fresh random credentials.
- Credentials are stable across redeploys, because they are never rotated automatically. Losing `.env.dev.sops` or the age key means recreating the cluster.
- Agents can't read Secrets, `.env.dev*` or key files through normal commands. Debugging has to go through `make secrets-verify`, events and pod status. That is a small cost in convenience.
- The hook becomes security-relevant code, so it gets unit tests for every blocked and allowed form, and changes ship in their own PR with a full human read.
- The guards reduce accidental and casual leaks. They aren't a sandbox, as the residual risks list shows.
- New local prerequisites: `sops` and `age`, with pinned versions checked by `make secrets`.
- Two credentials exist in two namespaces each. This is inherent to server and client needing the same secret. Applying both from one source prevents drift.
- With no auth, anything in the cluster can manage the catalog. From issue 17 onwards, NetworkPolicies limit which namespaces can reach it. That is acceptable for a local, single-user setup, and not exposed outside the cluster.
- Remote signing keeps S3 keys out of client configs, which matches how Trino (Phase 2) can consume Lakekeeper. The cost: PyIceberg is tied to the fsspec FileIO, and every S3 request needs a signing round-trip to Lakekeeper.
- Remote signing against SeaweedFS is a compatibility risk, which is why the spike checks it before Lakekeeper is integrated.

## Alternatives considered

- **Sealed Secrets.** Rejected: it only encrypts for git, and its controller still writes ordinary, base64-encoded Secrets into the cluster. We never commit secrets anyway, so it adds a component without protecting anything we care about.
- **OpenBao with External Secrets Operator.** Deferred to the OIDC/auth phase. Checked on 2026-11-28: the openbao chart is 0.30.8 (app 2.7.3) and ESO is 2.15.0, both with arm64 images. ESO still materialises Kubernetes Secrets for `existingSecret` consumers, so it wouldn't remove the need for etcd encryption and agent guards in Phase 1.
- **SOPS only** (no etcd encryption). Rejected as partial: Secrets would sit unencrypted in etcd on the minikube disk.
- **etcd encryption only** (plain `.env.dev`). Rejected as partial: the host file would be plaintext, readable by any tool or agent.
- **KMS v2 provider for etcd.** Rejected for Phase 1: it needs a KMS plugin. A local secretbox key is enough given the threat model.
- **STS or vended temporary credentials.** Rejected: SeaweedFS has no usable STS. This can be revisited with a different store.
- **Static keys in every client** (as the primary approach). Kept as the fallback. It is simpler, but spreads the admin key to every client, and it's a pattern that doesn't carry over to authenticated phases.
- **Let CNPG or charts generate random passwords.** Rejected: values would change when the cluster is recreated, and Lakekeeper's encryption key must stay in sync with stored data. One source (`.env.dev.sops`) is simpler.
- **OIDC from Phase 1.** Rejected: an identity provider adds a component and complexity before the core data path works.

## Amendment (2026-11-28, spike #3): remote signing confirmed, with client conditions

Evidence: [spike #3 result](https://github.com/StefanNieuwenhuis/lakehouse/issues/3#issuecomment-7242767101), accepted by the user on 2026-11-28.

### What the spike confirmed

- Lakekeeper 0.15.1 remote signing works against SeaweedFS 4.55 with this warehouse storage profile: `sts-enabled: false`, `remote-signing-enabled: true`, `remote-signing-url-style: path`, `path-style-access: true`, `flavor: s3-compat`. The server accepts only `path` for the URL style, even though its OpenAPI docs say `path-style`.
- PyIceberg 0.12.0 with `FsspecFileIO` and no S3 keys on the client created a namespace and a table, appended, and read the rows back. The client pod had no S3 environment variables, no `~/.aws` and no credentials in its catalog or table config.
- **Remote signing stays the write-access mechanism.** The decision under "Storage credentials and client write access" is unchanged, with the two conditions below.

### Conditions for every PyIceberg client

These apply to every PyIceberg client in this project: the Phase 1 smoke Job now, and later ingestion code and Dagster assets.

1. **Run PyIceberg with one worker: `PYICEBERG_MAX_WORKERS=1`** in the pod environment (or `max-workers: 1` in `.pyiceberg.yaml`).
   - Why: in PyIceberg 0.12.0, `FsspecFileIO` removes and re-adds its remote-signer hook (`before-sign.s3`, `unregister` then `register_last`) on an s3fs client that fsspec's instance cache shares across threads. A request signed in that gap goes out unsigned, because the client is configured as `UNSIGNED`, and the store rejects it with 403. The spike saw this in 3 of 8 runs with default workers, and in 0 of 8 runs with one worker.
   - Upstream: [apache/iceberg-python#3896](https://github.com/apache/iceberg-python/issues/3896) (closed by the merged PR [#4405](https://github.com/apache/iceberg-python/pull/4405), "Register the S3 signer on a session instead of a shared client", 2026-11-18, not in 0.12.0), and the related open issue [apache/iceberg-python#4414](https://github.com/apache/iceberg-python/issues/4414) (signer swapped on a shared, cached `S3FileSystem`).
   - When to lift it: only when **both** of these hold:
     1. [apache/iceberg-python#4414](https://github.com/apache/iceberg-python/issues/4414) is fixed in a released PyIceberg version, and we pin that version. #4414 is the gating issue: the merged #4405 isn't enough on its own, because nothing confirms that it resolves #4414;
     2. 10 consecutive clean round trips pass at default workers (two `make smoke-phase1` runs, `PYICEBERG_MAX_WORKERS` unset), with the gate otherwise as defined in ADR-0006 and its amendment.

     Lifting the condition still needs a new amendment to this ADR, which records the pinned version and the 10 round trips. A PyIceberg bump on its own keeps the condition in force.
   - Cost: no parallel scans or writes in PyIceberg. That is negligible at local scale.
2. **Deletes go through Lakekeeper, not through `FileIO.delete()`.**
   - Why: s3fs deletes with S3 DeleteObjects (`POST ?delete`). Lakekeeper refuses to sign it (`400 DeleteWithoutBody`), because PyIceberg's signer doesn't send the request body.
   - Rule: table and file deletion uses Lakekeeper: `purge_table` with the warehouse delete profile `hard`. The smoke Job must clean up this way (#12). Client code doesn't call `FileIO.delete()` or s3fs `rm` on table locations.

### Other findings

- When remote signing is on, Lakekeeper returns `py-io-impl=pyiceberg.io.fsspec.FsspecFileIO` in the table config, and table config overrides client properties. So clients get `FsspecFileIO` even if they don't set it, and they can't switch to PyArrowFileIO while remote signing is on. The smoke test still sets the FileIO explicitly.
- Trino (Phase 2) isn't affected by these PyIceberg-specific conditions. Its remote signing is checked at its own gate.

### Static-key fallback

- The fallback was verified: a second warehouse with remote signing disabled, PyArrowFileIO, and the key pair through `secretKeyRef`, passed 5 of 5 runs with default workers.
- It stays the **documented fallback, used only by amendment** to this ADR. It isn't enabled because of the conditions above. Switching to it needs `remote-signing-enabled: false` on the warehouse (see "Other findings"), and extends the secret placement table with the client namespaces that would get the key pair.
