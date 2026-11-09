# Phase 8 — Final Report (part 2: commit, merge, finalize)

The gates in `references/phase-8.md` are green; this chapter closes the run.

### Auto-commit and push at the end of a clean pass

The invoking command (`/architect-team`) sets `AUTO_COMMIT` and `AUTO_PUSH` flags from `$ARGUMENTS` (defaults: both `true`; opt-out via `--no-commit` / `--no-push`). At the end of Phase 8, after the final-statement line is emitted, do this:

If `AUTO_COMMIT = true`:

0. **Run the completion audit FIRST — it gates the commit.** From the repo root, run `$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check` (the detect-once form; the `python3 … || python …` polyglot double-executed the audit and double-printed the block). This is the same audit the `Stop` hook runs; running it here, before staging anything, converts "clean pass" from the orchestrator's self-assessment into a checked fact. If it exits non-zero, the run is NOT complete (an open SR, a test-failure SR with no diagnostic plan, an unsatisfied editability loop, an unresolved test-completeness debt, a failing master-review audit verdict, a failing **documentation-currency audit** verdict, or a **frontend-impacting slice with no genuine passing E2E verdict** (`_audit_frontend_e2e` — see the frontend-E2E loop-exit gate below) — the worklist the loop keeps closing until empty; there is NO iteration ceiling) — do NOT auto-commit. Resolve every reported violation and re-run the audit, OR pause to collect required owner input per the run-state rules below. Only an exit-0 audit may proceed to step 1. The auto-commit also requires the Phase 7 **master-review audit** AND the Phase 8 **documentation-currency audit** verdicts to be `overall: pass` — `pipeline-completion-audit.py` enforces both: if a `.architect-team/master-review/audit-*.json` or a `.architect-team/documentation-currency/audit-*.json` verdict exists, its latest `overall` must be `pass`, alongside the existing checks.
1. `git -C <repo-root> status --porcelain` — enumerate what changed during the run.
2. Identify the pipeline's working set: every file under `openspec/changes/<change-name>/`, every CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP touched, every file referenced in any review-gate evidence's `files_changed`, and any test files added. Do NOT use `git add -A` — explicitly enumerate.
3. `git -C <repo-root> add <enumerated-files>`.
4. Construct the commit message from the Phase 8 report data:

   ```
   <change-name>: <one-line summary from Final Report>

   - Requirements implemented: <REQ-001, REQ-002, ...> (N total)
   - Tests added: <unit-count> unit / <integration-count> integration / <e2e-count> e2e — all passing
   - Coverage map: fully green
   - Phases −1 → 8 complete; openspec archive landed at <archive-path>

   Dispatch-Mode: <teams|subagents>
   Co-Authored-By: Claude <noreply@anthropic.com>
   ```

   The `Dispatch-Mode:` trailer (v1.5.0) is derived from
   `.architect-team/intake-state.json`'s `dispatch_mode` field — the
   orchestrator recorded it at startup per v1.0.0's mode-detection contract.
   Values are `teams` (Agent Teams primitive) or `subagents` (the ephemeral
   subagent fallback). The trailer makes `git log --format=%(trailers)`
   queryable for archeological "which mode produced this commit?" questions
   without needing to grep JSON. Read the value once at commit-build time;
   it does NOT change mid-run.

4b. **Default-branch guard — decide the target branch BEFORE committing.** Run `git -C <repo-root> rev-parse --abbrev-ref HEAD`. If the current branch is `main` or `master` AND `--allow-push-to-default` was NOT passed: the pipeline does NOT commit unreviewed work straight onto a default branch. Create and check out a feature branch first — `git -C <repo-root> checkout -b architect-team/<change-name>` — so the commit (step 5) and push (steps 6-8) land there, and the final report tells the user the work is on `architect-team/<change-name>` awaiting their review + a PR. If the current branch is NOT a default branch, OR `--allow-push-to-default` was passed, commit on the current branch as-is.
5. Commit AS THE RECORDED PERSON (`common-pipeline-conventions` `## Git commit identity discipline (v3.67.0)`; the identity was resolved, and on first use asked, at the front door into `<main-worktree>/.architect-team/git-identity.json`): `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd <repo-root> git -- -C <repo-root> commit -m "<message>"` (the wrapper injects `-c user.name= -c user.email=` from the record and REFUSES when there is none), or the explicit pair `git -C <repo-root> -c user.name="<name>" -c user.email="<email>" commit -m "<message>"` read from `git_identity.py status --json`; never ambient git config alone, never a hardcoded author (`skills/common-pipeline-conventions/references/git-commit-identity.md`).
5b. **Immediately after the commit succeeds**, the orchestrator emits a `git_commit` notification (best-effort; see `## Notifications`), passing `--commit` with the new commit SHA. It invokes the notifier from the target project's root and proceeds immediately:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha> || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" git_commit --project <name> --commit <commit-sha>
   ```

   This `git_commit` invocation is best-effort and NEVER blocks, fails, or alters the commit or the subsequent push — a notifier failure does not affect git in any way.

If `AUTO_PUSH = true` (and the commit succeeded):

6. `git -C <repo-root> rev-parse --abbrev-ref HEAD` to get the branch the commit landed on (the current branch, or the `architect-team/<change-name>` branch created by step 4b).
7. `git -C <repo-root> push -u origin <that-branch>` — push it to its upstream (`-u` so a freshly-created feature branch gets its upstream set).
8. Capture the commit SHA and the push range (e.g., `abc1234..def5678`); add them to the final user-facing report. If the commit went to an `architect-team/<change-name>` feature branch (step 4b's default-branch guard), the report MUST tell the user the work is on that branch and recommend opening a PR — do NOT let unreviewed pipeline output sit silently on a default branch.

If `AUTO_COMMIT = false`: skip steps 1-8 entirely. Mention in the final report that changes were left uncommitted at the user's request.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-5 only. Mention in the final report that the commit was made locally but not pushed.

If the working tree had unstaged or staged user changes BEFORE the pipeline started: surface their presence in the final report and do NOT include them in the pipeline's commit. The pipeline commits ONLY what the pipeline produced.

### Safety rules for the auto-commit step (non-negotiable)

- NEVER force-push (`--force`).
- NEVER skip git hooks (`--no-verify`).
- NEVER amend the previous commit (`--amend`).
- If a pre-commit hook fails, surface the failure, fix the underlying issue (if it is the pipeline's responsibility), and create a NEW commit. Never bypass the hook.
- If `git push` fails (non-fast-forward, network, auth), surface the error clearly and stop. Do NOT escalate to force-push.
- If the repo has detached HEAD or no upstream configured for the current branch, skip the push, mention it in the report, and tell the user how to set the upstream (`git push -u origin <branch>`).
- Do NOT push to `main` if the change has not been peer-reviewed by a human reviewer AND the repo's branch-protection policy requires reviews — the orchestrator does NOT have judgment to override branch protection. If push is rejected by branch protection, surface the rejection and stop.

### Auto-merge to main (v3.7.0)

When `AUTO_MERGE_MAIN = true` (the default; `--no-auto-merge` opts out) AND the completion audit passed AND the commit landed on `architect-team/<change-name>`: after the push (step 8), probe clean-mergeability and, if clean, merge + prune via `merge_branch_to_main_and_prune` (the polyglot Python pattern; run from the MAIN checkout since the helper runs `git checkout main` there):

```bash
python3 -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '${WORKTREE_PATH}', push=<AUTO_PUSH>)))" || python -c "import sys,json; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import merge_branch_to_main_and_prune; print(json.dumps(merge_branch_to_main_and_prune('architect-team/<change-name>', '${WORKTREE_PATH}', push=<AUTO_PUSH>)))"
```

- `reason: "merged-and-pruned"` → report merged into `main`, pushed, branch deleted (local + remote), worktree removed. (Skip the End-of-run worktree finalize step below — the worktree is already gone.)
- `conflict: true` (`reason: "conflict"` / `"conflict-on-merge"`) → the merge changed nothing; fall back to today's behavior: the branch stays pushed, recommend a PR, and run the v3.6.0 finalize step below (persistence warning).
- `reason: "push-rejected"` (branch protection / non-fast-forward) → STOP, report the rejection, leave the branch + worktree recoverable. NEVER force.

When `AUTO_MERGE_MAIN = false`: skip this step; the branch stays pushed, recommend a PR, and the v3.6.0 finalize step below runs verbatim. Per `common-pipeline-conventions` `## Auto-merge-to-main discipline (v3.7.0)`.

### End-of-run worktree finalize (v3.6.0)

After the auto-commit / push output (and the v3.7.0 auto-merge step, when it did NOT already prune the worktree) and BEFORE the auto-compact prompt, finalize the run worktree (only when this run created one — `AUTO_WORKTREE` was true and `$WORKTREE_PATH` is set). Invoke `finalize_run_worktree` via the polyglot Python pattern per `common-pipeline-conventions` `## Cross-platform Python invocation`:

```bash
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import finalize_run_worktree; from pathlib import Path; r = finalize_run_worktree(Path('${WORKTREE_PATH}')); print(r.get('warning') or f\"Worktree finalized: {r.get('reason')}\")" || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts/setup'); from worktree_lifecycle import finalize_run_worktree; from pathlib import Path; r = finalize_run_worktree(Path('${WORKTREE_PATH}')); print(r.get('warning') or f\"Worktree finalized: {r.get('reason')}\")"
```

If the run branch is already merged into `origin/main`, finalize removes the worktree + branch. If not (the common state — branch just pushed, PR pending), it leaves the folder and returns a `warning`; print that `warning` verbatim to the user (it names the path + the manual cleanup command). Unmerged work is NEVER auto-deleted. Best-effort: skip silently if the run had no worktree.

### Mark the run complete (v3.30.0 — the LAST state action of the run)

After the auto-commit / push / auto-merge / worktree-finalize steps have all landed (and only then), mark the active-run lifecycle marker complete — from the workspace root (the directory whose `.architect-team/` holds this run's state):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete || python "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --mark-complete
```

This is what tells the run-continuity enforcement (the Stop-hook continuation guard + the PreToolUse sticky arm + the SessionStart resume directive — see `common-pipeline-conventions` `## Run continuity discipline`) that the run is genuinely DONE. Until this runs, a Stop is blocked as an arbitrary mid-run stop and every fresh/resumed session is directed back into the pipeline. Never run it early: "the audit will pass eventually" is not complete; committed-and-pushed is.

Throughout the run, keep the marker's observability fields current at each phase boundary (best-effort, one line): `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/run_continuity.py" --set phase="Phase 5" slug=<change-name>` — the resume directive and the block messages quote these fields to a resumed session.

### Run-complete notification (v3.34.0 — the run's final email)

**Delivery manifest — the bill of sale (v3.46.0).** Before emitting `run_complete`, produce the run's delivery manifest per the `delivery-manifest` skill. Assemble the manifest data (plain-speak problem statement; stakeholder-executable validation steps, EACH with an expected result; for a feature, the location + name + functionality of every new element; if the user provided a template/example document, match its vocabulary and layout), write it to `<workspace>/.architect-team/delivery/<run-id>-manifest.json`, gate on the engine's zero-error validation, and render the markdown:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<run-id>-manifest.json" --repo-root . || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json "<workspace>/.architect-team/delivery/<run-id>-manifest.json" --repo-root .
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<run-id>-manifest.json" --out "<workspace>/.architect-team/delivery/<run-id>-manifest.md" --email || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json "<workspace>/.architect-team/delivery/<run-id>-manifest.json" --out "<workspace>/.architect-team/delivery/<run-id>-manifest.md" --email
```

A blocking validation finding means the manifest is a draft — fix the data and re-validate before publishing (advisories are prose-quality pointers). The rendered manifest embeds into the final email via the `--plan-file` flag on the `run_complete` invocation below, and is presented to the user as the run's closing deliverable (copy-paste ready).


Immediately after the run is marked complete (and after Phase 8's own `phase_complete`), emit `run_complete` ONCE — the run's final notification, telling recipients the run finished end-to-end and what it shipped (best-effort, per `## Notifications`; a notifier failure never blocks the close-out):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <run-id> --elapsed "<elapsed since run start>" --commit <final-commit-sha> --details "<what shipped: features delivered, test totals, SRs resolved>" --progress "All phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<run-id>-manifest.md" || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" run_complete --project <name> --run-id <run-id> --elapsed "<elapsed since run start>" --commit <final-commit-sha> --details "<what shipped: features delivered, test totals, SRs resolved>" --progress "All phases complete — run closed" --plan-file "<workspace>/.architect-team/delivery/<run-id>-manifest.md"
```

Omit `--commit` when the run produced no commit (`--no-commit`).

### Auto-compact prompt (after the final report; default on)

The invoking command (`/architect-team`) sets `AUTO_COMPACT_PROMPT` from `$ARGUMENTS` (default `true`; opt-out via `--no-compact`). After the Phase 8 final report (and the auto-commit / push output if applicable), emit this block as the very last thing the user sees in this turn:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Pipeline complete. Context is now full of build state.        ║
║  Run /compact NOW to free space for the next architect-team    ║
║  invocation. Type exactly:                                     ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

**Why it is a prompt, not an auto-execution:** the orchestrator runs as a model + tools; `/compact` is a slash command processed by the Claude Code REPL itself, not a tool the model can invoke. This block puts the literal command on its own line so the user can copy-paste or one-keystroke-confirm. Pipeline cycles tend to fill context — running `/compact` immediately is the right hygiene before the next invocation.

If `AUTO_COMPACT_PROMPT = false`: skip the block entirely.

Then clean up the team.
