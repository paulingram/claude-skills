# Baseline SHA capture

The orchestrator captures a single immutable SHA reference at run start and includes it in every teammate's spawn brief. Teammates use it to diff their own work against the run's baseline WITHOUT touching shared git state — no `git stash`, no `git reset`, no race.

This sub-section documents the orchestrator-side mechanics. The forbidden-operations list and the failure-mode worked example live in `common-pipeline-conventions` `## Teammate git discipline` — read that first if you haven't.

### When the capture runs

At pipeline entry, BEFORE the first teammate is dispatched (so every teammate's spawn brief can carry the captured value):

- **architect-team-pipeline:** Phase −2 (Triage & Routing) prelude, alongside the dispatch-mode selection. The capture is one of the first orchestrator actions after the dispatch-mode banner prints.
- **bug-fix-pipeline:** Phase B−1 entry, before B0 (intake).
- **mini-architect-team-pipeline:** Phase M0 entry, before M1 (read prompt + brief).

The orchestrator runs `git rev-parse HEAD` once and records the SHA. Re-running the capture mid-run is forbidden — the baseline is the run-start anchor; if it slides, the teammates' diffs become meaningless.

### Capture command

```bash
BASELINE_SHA=$(git rev-parse HEAD)
```

The same command resolves in any worktree the run might be executing in (the v1.2.0 auto-worktree, the main checkout, or a `--no-worktree` invocation). `git rev-parse HEAD` returns the SHA of the current branch's tip; it is a read-only probe and safe to call from any state.

### Persisting the captured value

The orchestrator records the SHA in two places:

1. **`<workspace>/.architect-team/intake-state.json`** as the `baseline_sha` field — the same file that already holds the `dispatch_mode` decision (v1.0.0) and the run's other startup metadata.
2. **Every teammate's spawn brief** at `<workspace>/.architect-team/teammates/<teammate>.json` (the v0.9.13 teammate manifest schema). The brief gains a `baseline_sha` field carrying the same value verbatim.

The teammate manifest schema (from `## Teammate manifest` above) is extended to carry the `baseline_sha` — and, beside it, the `spec_fingerprint` recording the SPEC state the teammate was briefed against:

```json
{
  "schema_version": 1,
  "teammate": "backend-auth",
  "spawned_at": "<ISO 8601 UTC>",
  "task_ids": ["T-10", "T-11", "T-12"],
  "files_owned": ["src/auth/login.py", "tests/auth/test_login.py", "..."],
  "expected_review_evidence": ["T-10", "T-11", "T-12"],
  "baseline_sha": "0a21702abc...def",
  "spec_fingerprint": "3def77ec62e2...cda0"
}
```

The teammate reads `baseline_sha` from its manifest at spawn and uses it for all baseline-diff verification within its tasks.

**`spec_fingerprint` (additive).** The two fields are the same idea one axis apart: `baseline_sha` freezes the CODE the teammate started from; `spec_fingerprint` freezes the SPEC it was briefed against — a SHA-256 over the sorted (posix relative path, content) pairs of `openspec/changes/<active-slug>/`, computed by `hooks/spec_fingerprint.py` and written by the orchestrator at Phase 2 dispatch. The field is purely additive: a pre-upgrade manifest without it stays valid, and the `_audit_spec_currency` arm fails open when no manifest carries one. When the orchestrator amends an openspec artifact after dispatch, the fingerprint moves — and every teammate whose scope the amendment touches is owed a re-brief handoff plus an updated manifest fingerprint, per `common-pipeline-conventions` `## Spec currency discipline (mid-run) (v3.47.0)`. A teammate still working against a superseded fingerprint with no re-brief record is the failure that discipline exists to catch: two implementations built to two different readings of one line.

### How teammates use it

Teammates substitute baseline-SHA diffs for `git stash` everywhere they would have stashed:

```bash
# What have I changed in MY files since the run started?
git diff $BASELINE_SHA -- <my-files>

# What does the current head differ from baseline?
git diff $BASELINE_SHA..HEAD

# Which commits in this run touched my files?
git log $BASELINE_SHA..HEAD --oneline -- <my-files>

# Has another teammate's commit already landed in a file I depend on?
git log $BASELINE_SHA..HEAD --oneline -- <upstream-file>
```

Each of these is a read-only operation on the shared git state. Two teammates running `git diff $BASELINE_SHA` concurrently cannot corrupt each other; the operation is idempotent and side-effect-free, the exact opposite of `git stash`.

### What teammates MUST NOT do

For the canonical forbidden-operations list (the 6 forbidden destructive git operations and the rationale for each), see `common-pipeline-conventions` `## Teammate git discipline`. The headline rule: no `git stash` / `git stash pop`, no `git reset --hard`, no `git rebase`, no `git commit --amend`, no `git checkout <other-branch>` / `git checkout .`, no `git clean -f`. The `baseline_sha` value the spawn brief carries is the alternative the orchestrator provides so teammates have a real way to verify their work without touching shared mutable state.
