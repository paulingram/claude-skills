# Phase M7 — Auto-merge to main

**Mock-retirement gate (v3.48.0 — CFP-6).** If M4 created any interface contract, run the gate BEFORE the merge — a run does not close on a surface still serving a provisional payload:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger "<workspace>/.architect-team/contracts/ledger.json" || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger "<workspace>/.architect-team/contracts/ledger.json"
```

Any blocking finding routes back to the backend agent to flip the surface to real data, verify end-to-end through the same live path, and transition the entry to `live` — including a finding that the gate could not READ an entry or the ledger's container, which fails closed for the same reason. Confirm retirement with `... drift --json <contract.json> --observed <payload.json> --retirement` (the provisional marker must be gone), then capture the gate output and close each contract's registered gate with `... satisfy-gate --gate-id cfp-retirement-<contract-id> --evidence <captured-output> --registry "<workspace>/.architect-team/declared-gates.json"`. A run with no contracts skips this: the command prints `no contracts recorded` and exits 0, so an absent ledger is a no-op.

### Deploy mandate final gate (v2.20.0)

If `intake_state.deploy_mandate.active == true`, invoke the 18th Layer 3 tool `verify-deploy-mandate-satisfied` BEFORE the auto-merge sequence — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Deploy-mandate row; it BLOCKS).

Any of the 4 severities blocks the auto-merge. The mini loop routes the failure back to Phase M8 cycle as `verdict: red` with the deploy-mandate gap as the explicit failure reason; the architect re-spawns to satisfy the missing binding criterion. See `common-pipeline-conventions/SKILL.md` `## Deploy mandate discipline (v2.20.0)` for the canonical home.

### Unilateral-override meta-gate (v3.0.0)

After the deploy-mandate gate, run the `verify-no-unilateral-override` Layer 3 tool as a meta-confession check across all text artifacts the mini run produced (architect's M3 self-confirm verdict, mini-qa M5 verdict notes, M6 final summary) — per `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` (the Unilateral-override row; it BLOCKS). Single severity `unilateral-override-with-virtue-framed-confession` blocks the auto-merge; routes to Phase M8 cycle as red. See `common-pipeline-conventions/SKILL.md` `## Unilateral-override discipline (v3.0.0) — META` for the canonical home.

### Declared-gates ship check (v3.47.0)

After the override meta-gate and BEFORE the auto-merge sequence, walk `<workspace>/.architect-team/declared-gates.json`: every entry must carry `satisfied_at` and an `evidence_path` that exists and is non-empty. An unsatisfied entry blocks the merge and routes to the Phase M8 cycle as `verdict: red` with the unsatisfied gate as the explicit failure reason — the mini pipeline is the one that lands on `main` directly, so a gate the run declared and skipped would ship unreviewed. Absent registry is fail-open. Canonical rule: `common-pipeline-conventions` `## Declared-gates discipline (v3.47.0)`.

On `verdict: green` from M6, the orchestrator performs the auto-merge sequence. **This is the only point in any architect-team pipeline that pushes to `main` directly.**

### The full suite once, before the merge (v4.0.0)

`python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 8 --json` returns every test with reason `full-suite-phase` -- no selector flag narrows it and `tests.full_suite_at` in `.architect-team-deploy.json` can only ADD phases. Run every layer plus the dev Playwright project enumerated from `<e2e-dir>/suite-manifest.json` (when one exists), record the results as evidence, then commit and merge. M4 and M5 ran the selected sets; this single full run is the safety net for everything the test index did not know (`skills/common-pipeline-conventions/references/test-selection.md`).

### Doc-currency single-pass

Per `documentation-currency`, run a single-pass doc update (no producer/checker split) covering: `README.md`, `CHANGELOG.md`, `CODEBASE_MAP.md`, `INTEGRATION_MAP.md`, `CLAUDE.md`, per-codebase `ROUTE_MAP.md` / `DESIGN_MAP.md` if they exist and are touched. The mini variant runs this in-line rather than spawning a separate `doc-updater` agent — the architect handles it. The pass ends with a homepage rebuild (v4.0.0, best-effort, never blocking — the page is part of the documentation inventory, `project-homepage` `## Rebuild moments`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "<workspace>" --json 2>&1 || echo "(homepage rebuild skipped; continuing.)"
```

### OpenSpec archive (uniform parity)

Before staging, run `openspec archive <slug>` to merge the change's spec deltas into the canonical `openspec/specs/` — uniform parity with the architect-team Phase 7 + bug-fix Phase B7 archive steps (per `common-pipeline-conventions/SKILL.md` `## Uniform plugin usage (v3.9.0)`). The archive runs only after the M6 `verdict: green` gate and the v2.20.0 / v3.0.0 meta-gates above pass — it is part of `superpowers:verification-before-completion`, not a shortcut around it. The resulting archive changes are staged into the same commit below; the `git merge --ff-only` auto-merge sequence is UNCHANGED.

### Commit sequence

1. Stage all M4 + M5 + doc-currency + openspec-archive changes.
2. Commit with trailers:
   ```
   Mini-Run: <slug>
   Dispatch-Mode: <teams|subagents>
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```
   Identity (v3.67.0): the commit is authored as the checkout's RECORDED person — `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- commit ...` (or the explicit `-c user.name="<name>" -c user.email="<email>"` pair from `.architect-team/git-identity.json`) per `common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)`. Never a hardcoded author, never ambient git config alone; the front door asked on first use, and the PreToolUse gate refuses a commit that lacks or contradicts the record.

   The `Dispatch-Mode:` trailer (v1.5.0) is derived from
   `.architect-team/intake-state.json`'s `dispatch_mode` field — recorded
   at M0 startup per v1.0.0's mode-detection contract. Values are `teams`
   (Agent Teams primitive) or `subagents` (the ephemeral subagent fallback).
   Sits alongside the existing `Mini-Run:` trailer so
   `/architect-team:mini-review-sweep` can filter sweep candidates by both
   dimensions when needed. Read the value once at M7 commit-build time; it
   does NOT change mid-run.
2b. **Immediately after the commit succeeds**, the orchestrator emits a `git_commit` notification (best-effort, per `## Notifications`), with `--commit <SHA>`. This is the highest-signal mini-run event — the commit will shortly land on `main` via the auto-merge sequence below. Invoke from the target project's root and proceed immediately:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha>
   ```

   This `git_commit` invocation is best-effort and NEVER blocks, fails, or alters the commit, the subsequent push, or the merge — a notifier failure does not affect git in any way.
3. Push the working branch: `git push -u origin mini/<slug>`.

### Merge sequence

1. `git fetch origin`
2. If `main` is unchanged since branch creation: fast-forward `main` to the branch tip:
   ```bash
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
3. If `main` has advanced: rebase the branch on `main` then fast-forward:
   ```bash
   git rebase origin/main && git push --force-with-lease origin mini/<slug>
   git checkout main && git merge --ff-only mini/<slug> && git push origin main
   ```
4. If rebase produces conflicts: **halt**. Write `.architect-team/mini/<slug>/merge-conflict.json` with the conflict files and surface to the user. **Never** auto-resolve. **Never** use `--no-verify`. **Never** use `--force` (only `--force-with-lease`).
5. On success: delete the working branch locally and remotely (`git push origin --delete mini/<slug>; git branch -d mini/<slug>`).

### Cleanup the run worktree (v1.3.0)

After the merge succeeds and the branch is deleted (step 5 above), remove the
run worktree itself. The mini pipeline just merged its own branch to main;
the worktree's purpose is fulfilled. This is the "in-run cleanup" trigger
documented in `common-pipeline-conventions` `## Auto-worktree lifecycle`
`### Auto-cleanup (v1.3.0)` — the other trigger (the start-of-run sweep at
the slash commands) handles every OTHER prior-run merged worktree.

Invoke `cleanup_run_worktree` against the current worktree path, with
`remove_branch=False` because step 5 already deleted the branch (a second
`git branch -d` would be a no-op-with-error). Polyglot pattern:

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_run_worktree; from pathlib import Path; cleanup_run_worktree(Path.cwd(), remove_branch=False)" || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import cleanup_run_worktree; from pathlib import Path; cleanup_run_worktree(Path.cwd(), remove_branch=False)"
```

`cleanup_run_worktree` is idempotent — if the worktree has already been
removed by some other path, the call is a no-op. The `git worktree remove`
runs from the main repo's toplevel (not from inside the worktree being
removed), so it doesn't break the orchestrator's cwd mid-call; the helper
handles that by resolving `_git_show_toplevel()` to the MAIN repo.

This in-run cleanup is best-effort just like the start-of-run sweep: a
failure surfaces a one-line note and the `/compact` prompt below still
fires.

**Alignment with `finalize_run_worktree` (v3.6.0).** The end-of-run merge
check `finalize_run_worktree` is the shared end-of-run disposition the full +
bug-fix pipelines call at Phase 8 / B8 (remove-if-merged, warn-if-not). The
mini pipeline's M7 already implements that same intent for its own worktree —
it merges to main, then removes the worktree above — so it keeps this explicit
auto-merge-then-clean behavior rather than re-deriving disposition. (Mini runs
on `mini/<slug>` branches, not `architect-team/<slug>`, so `finalize` — which
only acts on `architect-team/*` branches — would be a no-op here anyway; the
M7 step is the mini equivalent.) On the rare unmerged path (the merge in step
4 failed), M7 leaves the worktree on disk and surfaces a warning naming the
path + the manual cleanup command, exactly as `finalize` would.

**Alignment with the auto-merge-to-main discipline (v3.7.0).** Mini's M7 IS the
auto-merge-to-main behavior the v3.7.0 discipline makes the default for the full
+ bug-fix pipelines — M7 already merges the run branch to `main`, pushes, deletes
the branch (local + remote), and removes the worktree (the merge sequence + the
worktree cleanup above). `AUTO_MERGE_MAIN = true` is the mini default; the
`--no-auto-merge` flag is an alias of `--no-merge` (both set `AUTO_MERGE_MAIN =
false` and skip the merge sequence, leaving the branch + worktree for a manual
PR). Conflicts halt (step 4) and are never forced; a rejected `git push origin
main` (branch protection) halts the same way — `main` is never force-pushed.
Because mini runs on `mini/<slug>` branches (not `architect-team/<slug>`), it
keeps its own fast-forward-based merge sequence rather than routing through
`merge_branch_to_main_and_prune` (which acts only on `architect-team/*`
branches); the net effect — clean-merge → push → delete-branch → remove-worktree,
conflict/branch-protection → halt-never-force — is identical. Per
`common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.

### Mark the run complete (v3.30.0)

After the merge sequence lands (or, under `--no-merge` / `--no-push`, after the last step that DID run), and BEFORE the compact prompt, run `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete || python "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete` from the workspace root — the LAST state action of the mini run. Until then the run-continuity enforcement treats the mini run as in-flight (Stops blocked; resumed sessions directed back into this skill). Keep `--set phase="Phase M<N>" slug=<slug>` current at phase boundaries. On the M6-red hand-off to the full `/architect-team` pipeline, do NOT mark complete — the full pipeline's Skill invocation refreshes the same marker and the run continues under it. Per `common-pipeline-conventions` `## Run continuity discipline (v3.30.0)`.

### Run-complete notification (v3.34.0 — the run's final email)

**Delivery manifest — the bill of sale (v3.46.0).** Before emitting `run_complete`, produce the run's delivery manifest per the `delivery-manifest` skill. Assemble the manifest data (plain-speak problem statement; stakeholder-executable validation steps, EACH with an expected result; for a feature, the location + name + functionality of every new element; if the user provided a template/example document, match its vocabulary and layout), write it to `<workspace>/.architect-team/delivery/<slug>-manifest.json`, gate on the engine's zero-error validation, and render the markdown:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<slug>-manifest.json" --repo-root . || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<slug>-manifest.json" --repo-root .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<slug>-manifest.json" --out "<workspace>/.architect-team/delivery/<slug>-manifest.md" --email || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<slug>-manifest.json" --out "<workspace>/.architect-team/delivery/<slug>-manifest.md" --email
```

A blocking validation finding means the manifest is a draft — fix the data and re-validate before publishing (advisories are prose-quality pointers). The rendered manifest embeds into the final email via the `--plan-file` flag on the `run_complete` invocation below, and is presented to the user as the run's closing deliverable (copy-paste ready).


Immediately after the run is marked complete (and after M7's own `phase_complete`), emit `run_complete` ONCE — the mini run's final notification: the change is merged to `main`, what it shipped, and the QA outcome (best-effort, per `## Notifications`; a notifier failure never blocks the close-out). Omit `--commit` under `--no-commit`; on the M8 escalation hand-off to the full pipeline do NOT emit it (the full pipeline's own `run_complete` closes the run):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <slug> --elapsed "<elapsed since run start>" --commit <merged-commit-sha> --details "<what shipped: ACs delivered, QA verdict green (cycle N), merged to main>" --progress "All M-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<slug>-manifest.md" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <slug> --elapsed "<elapsed since run start>" --commit <merged-commit-sha> --details "<what shipped: ACs delivered, QA verdict green (cycle N), merged to main>" --progress "All M-phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<slug>-manifest.md"
```

### Compact prompt

After successful merge, emit the standard `/compact` prompt (matches `architect-team-pipeline` Phase 8 behavior). Suppressed by `--no-compact`.

### Flags affecting M7

- `--no-merge` (alias `--no-auto-merge`, `AUTO_MERGE_MAIN = false`) — skip the merge sequence entirely. The commit and push still happen on the working branch; the user merges manually. Falls back to existing `/architect-team` semantics. Natural-language equivalents: *"keep the branch"* / *"PR only"* / *"don't merge to main"* / *"no auto-merge"*.
- `--squash-merge` — replace the fast-forward with `git merge --squash mini/<slug>` + a single `Mini-Run:`-tagged commit. The architect/dev/QA commit chain is collapsed into one commit. Trade-off: easier `main` history; the sweep loses sub-commit granularity.
- `--no-commit` — skip the commit step (and therefore push + merge). Used when running the mini pipeline as a dry-run.
- `--no-push` — commit but do not push or merge.
- `--no-compact` — suppress the `/compact` prompt.
