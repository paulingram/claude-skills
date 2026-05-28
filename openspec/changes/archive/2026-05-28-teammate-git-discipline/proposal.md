# Proposal: teammate-git-discipline (v1.6.0)

## Why

Real-world failure surfaced by the user in a separate session: four teammates were dispatched in parallel against the same working tree. Each ran `git stash` to verify their work against baseline, then popped back. `git stash` is not atomic across processes; the concurrent stash + reset operations interleaved and clobbered each other. Net result: 3 of 4 teammates' work was lost; only 1 file survived. The reflog showed 10+ consecutive `reset: moving to HEAD` entries — the smoking gun.

This is the same anti-pattern shape as v1.4.0 scope-discipline: **a missing plugin-level rule lets teammates do something they shouldn't**. The plugin currently doesn't forbid teammates from running destructive git operations, so teammates do. The right discipline:

- Teammates work on their owned file scope ONLY
- Teammates NEVER manipulate shared git state (no stash, reset --hard, rebase, amend, checkout other branches, clean -f)
- The orchestrator captures the baseline SHA once at run start; teammates diff against `<baseline>..` — no stash needed

## What changes

1. **`skills/common-pipeline-conventions/SKILL.md` gains a `## Teammate git discipline` section** — names the 6 forbidden destructive operations, documents the right pattern (orchestrator baseline-SHA capture; teammates diff against the SHA), and includes the failure-mode worked example (the heirship-app-v2 reflog evidence from this session) showing why the rule exists.

2. **Three pipeline bodies** (`architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline`) each gain a one-line anti-pattern entry referring to the canonical section.

3. **All 27 agents/*.md files** get a `## Forbidden git operations` section in their body (uniform 5-line block, similar to the v1.0.0 Operating context pattern). Naming the 6 forbidden ops + cross-referencing the canonical section.

4. **`skills/team-spawning-and-review-gates/SKILL.md` gains a `## Baseline SHA capture` sub-section** documenting the orchestrator's baseline-capture pattern: at run start, capture `git rev-parse HEAD` as `$BASELINE_SHA`; pass it to every teammate's spawn brief; teammates use it for `git diff <baseline>..` verification.

5. **New `tests/test_teammate_git_discipline.py`** — grep audits asserting:
   - The 6 forbidden ops appear in the canonical section
   - All 27 agents have the forbidden-git-operations section
   - No agent body documents running `git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git clean -f`, `git checkout <other-branch>` as ITS own action
   - The 3 pipeline bodies reference the canonical section
   - `team-spawning-and-review-gates` documents the baseline-SHA capture pattern

6. **Version bump to v1.6.0** in plugin.json + marketplace.json + CHANGELOG + CLAUDE.md + README + maps.

## QA Guidance

### Acceptance Criteria

- [AC-1] `skills/common-pipeline-conventions/SKILL.md` has a `## Teammate git discipline` section naming the 6 forbidden operations, the right pattern (orchestrator baseline-SHA capture), the worked example from the heirship-app-v2 reflog evidence, and the rationale.
- [AC-2] Each of the 3 pipeline SKILL.md bodies has an anti-pattern entry referring to `common-pipeline-conventions` `## Teammate git discipline`.
- [AC-3] Every `agents/*.md` file (27 total) carries a `## Forbidden git operations` section listing the 6 forbidden ops + cross-reference to the canonical section.
- [AC-4] `skills/team-spawning-and-review-gates/SKILL.md` documents the baseline-SHA capture pattern in a dedicated sub-section.
- [AC-5] `tests/test_teammate_git_discipline.py` exists with ≥ 8 tests (likely more via parametrize over 27 agents + 6 forbidden ops).
- [AC-6] All existing tests pass (1765 baseline) + new tests. Target: ~1775+ / 1 skipped.
- [AC-7] Version `1.6.0` consistent across plugin.json, marketplace.json, CHANGELOG, README, CLAUDE.md.

### Unit Test Targets

- `tests/test_teammate_git_discipline.py`: grep audit on `common-pipeline-conventions/SKILL.md` for `## Teammate git discipline` section + the 6 verbs
- Each of the 27 agents has the section
- No agent body documents running the forbidden ops
- The 3 pipeline bodies reference the canonical section
- `team-spawning-and-review-gates` documents the baseline-SHA pattern

### Integration Test Targets

- N/A — documentation + structural-test change; the plugin's pytest suite IS the integration test.

### Playwright Flows

- N/A.

### Out of Scope

- **Worktree-per-teammate dispatch** — each teammate spawned into its own worktree. Deeper architectural fix; deserves its own change. Tracked separately for v1.7+. The v1.6.0 discipline change reduces the failure rate substantially without it.
- **A runtime hook that detects destructive git ops by teammates** — automated detection is harder than documented discipline. Future v1.x.
- **Retroactively flagging prior runs** — discipline is forward-looking only.

## The 6 forbidden operations (v1.6.0 list)

| Operation | Why forbidden |
|---|---|
| **`git stash` / `git stash pop`** | Stash stack is process-shared; concurrent stash + pop interleaves catastrophically (the heirship-app-v2 failure mode) |
| **`git reset --hard <ref>`** | Destroys working tree state shared with other teammates |
| **`git reset --soft <ref>`** to anything outside teammate's scope | Same — alters shared state |
| **`git rebase`** | Rewrites shared history |
| **`git commit --amend`** | Alters the last shared commit |
| **`git checkout <other-branch>` or `git checkout .`** | Steps outside teammate's owned scope |
| **`git clean -f` / `git clean -fd`** | Deletes shared untracked state |

(Some sources may count this as 6 or 7 depending on whether stash/pop is one rule or two — proposal text uses "6" as the headline count; the table can show 7 individual operations.)

## Impact

- **Modified:** `skills/common-pipeline-conventions/SKILL.md` (new section), 3 pipeline SKILL.md bodies (anti-pattern entries), 27 `agents/*.md` files (new `## Forbidden git operations` section), `skills/team-spawning-and-review-gates/SKILL.md` (new sub-section), CHANGELOG, CLAUDE.md, README, CODEBASE_MAP, INTEGRATION_MAP, plugin.json, marketplace.json.
- **New:** `tests/test_teammate_git_discipline.py`, 1 openspec change folder.
- **Test count:** 1765 → ~1775+.
- **Version:** v1.5.0 → **v1.6.0**.
- **Backwards-compatible:** purely additive discipline; no behavior change for runs whose teammates didn't run destructive git ops (which should be all properly-behaved runs).
