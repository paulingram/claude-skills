# Teammate git discipline

Teammates work on their owned file scope. They MUST NOT manipulate shared git state. Even with the v1.2.0 per-run worktree (each `/architect-team` invocation gets its own working tree), the teammates WITHIN a single run share that worktree — the index, the working tree, the stash stack, the reflog, the branch HEAD are all one shared piece of state. A teammate that runs a destructive git command against that shared state is touching the work of every other teammate dispatched into the same run.

The discipline is documented at four enforcement points (same layered shape as v1.4.0 scope-discipline): this canonical section, three pipeline anti-pattern entries, all 27 agent role-definitions, and the `team-spawning-and-review-gates` `## Baseline SHA capture` sub-section that documents the right alternative.

### The forbidden operations (v1.6.0 list)

| Operation | Why forbidden |
|---|---|
| `git stash` / `git stash pop` | The stash stack is process-shared. Concurrent stash + pop interleaves catastrophically — two teammates stashing within milliseconds of each other corrupt the stack, and the pop walks the wrong index. This is the immediate cause of the v1.6.0 worked example below. |
| `git reset --hard <ref>` | Destroys the shared working tree state — every other teammate's in-flight edits to other files are silently reverted. |
| `git reset --soft <ref>` (to anything outside teammate's scope) | Same shape — alters the shared index. A soft reset that walks the HEAD back past another teammate's commit destroys the audit trail of who-changed-what. |
| `git rebase` | Rewrites shared history. Other teammates' commits get re-parented; the `BASELINE_SHA` reference the orchestrator captured at run start no longer resolves cleanly. |
| `git commit --amend` | Alters the last shared commit. If another teammate has already pulled / read from that SHA, the amend invalidates their view. |
| `git checkout <other-branch>` / `git checkout .` | Steps outside the teammate's owned scope — `checkout .` blasts the working tree (every untracked / modified file); `checkout <other-branch>` leaves the working tree in a different branch's state and every other teammate's writes land on the wrong branch. |
| `git clean -f` / `git clean -fd` | Deletes shared untracked state — including the `.architect-team/` per-run state directory if invoked from the repo root, which destroys every other teammate's review-evidence files, expectation files, RCA artifacts, and SR files in one stroke. |

A teammate that runs ANY of these is touching state shared with other teammates within the same run.

### Worked example — the v1.6.0 failure mode

In the `heirship-app-v2` project four teammates ran in parallel against one working tree, each `git stash`-ing to verify against baseline then `git stash pop`-ing to restore. `git stash` is not atomic across processes; the concurrent stash + pop interleaved catastrophically and the end-of-run reflog showed 10+ consecutive `reset: moving to HEAD` entries — each a stash-pop walking the index back to HEAD, clobbering whatever another teammate had just written. Three of four teammates' work was lost (only the last writer in the race survived). **The reflog signature `reset: moving to HEAD` repeated more than 3-4 times in one run is the diagnostic marker for this failure mode.**

### The right pattern — baseline-SHA capture

Instead of `git stash` for baseline verification, the orchestrator captures the SHA once at run start:

```bash
BASELINE_SHA=$(git rev-parse HEAD)
```

The orchestrator records `BASELINE_SHA` in `<workspace>/.architect-team/intake-state.json` as the `baseline_sha` field and includes it in every teammate's spawn brief (per the v0.9.13 teammate manifest schema). Each teammate diffs against the SHA instead of stashing:

```bash
git diff $BASELINE_SHA -- <my-files>            # what have I changed since the run started?
git diff $BASELINE_SHA..HEAD                    # what does the current head differ from baseline?
git log $BASELINE_SHA..HEAD --oneline -- <my-files>   # which commits in this run touched my files?
```

No stash, no reset, no race. The baseline is a SHA reference — immutable state — not a stash entry that mutates across processes. Two teammates running `git diff $BASELINE_SHA` concurrently cannot interfere with each other; the operation is read-only on the shared state.

See `team-spawning-and-review-gates` `## Baseline SHA capture` for the orchestrator-side mechanics (when the capture runs, what field name carries it through the spawn brief, how teammates receive it).

### Why the discipline ships alongside, not instead of, the per-run worktree

The v1.2.0 per-run worktree isolates each `/architect-team` INVOCATION, but the teammates WITHIN one run still share that single worktree — the failure mode above happened entirely inside one run's worktree. A future v1.x may add worktree-per-teammate dispatch as the structural fix; v1.6.0 ships the discipline first.
