# Design: teammate-git-discipline

## Reference

Full ACs + WHY + WHAT in `proposal.md`. This file holds the architectural anchors.

## The discipline

### Forbidden teammate operations (the canonical list)

| Operation | Why forbidden |
|---|---|
| `git stash` / `git stash pop` | Stash stack is process-shared; concurrent stash + pop interleaves catastrophically (this is the immediate cause of the heirship-app-v2 failure) |
| `git reset --hard <ref>` | Destroys shared working-tree state |
| `git reset --soft <ref>` (to anything outside teammate's scope) | Same — alters shared state |
| `git rebase` | Rewrites shared history |
| `git commit --amend` | Alters the last shared commit |
| `git checkout <other-branch>` / `git checkout .` | Steps outside teammate's owned scope |
| `git clean -f` / `git clean -fd` | Deletes shared untracked state |

A teammate that runs ANY of these is touching state shared with other teammates — even with v1.2.0's per-RUN worktree, the teammates WITHIN a run share that worktree.

### The right pattern

Instead of `git stash` for baseline verification, the orchestrator captures the SHA once:

```bash
BASELINE_SHA=$(git rev-parse HEAD)
```

Each teammate's spawn brief carries `$BASELINE_SHA`. Teammates diff against it:

```bash
git diff $BASELINE_SHA -- <my-files>     # what have I changed?
git diff $BASELINE_SHA..HEAD             # what does the current head differ from baseline?
```

No stash, no reset, no race. The baseline is a SHA reference, not mutable state.

## The 4 enforcement points

Same layered pattern as v1.4.0 scope-discipline:

1. **`common-pipeline-conventions/SKILL.md`** — canonical home of the discipline. The 6 forbidden ops, the right pattern, the worked example, the rationale.
2. **3 pipeline SKILL.md bodies** — each has a one-line anti-pattern entry pointing at the canonical section. Catches the discipline at the pipeline level.
3. **All 27 agent role-definitions** — each gets a `## Forbidden git operations` section. Catches the discipline at the teammate level (every agent body reminds the agent of the rule).
4. **`team-spawning-and-review-gates/SKILL.md`** — documents the orchestrator's baseline-SHA capture pattern. Provides the right alternative.

The 27-agent uniform update mirrors the v1.0.0 `## Operating context` pattern + the v1.4.0 scope-discipline cross-references. Same shape, different content.

## Reuse Decision Log

### RD-1: Extend `common-pipeline-conventions/SKILL.md`

**Decision:** Extend.
**Anchor:** The skill is the canonical home for cross-cutting disciplines (v1.0.0 / v1.4.0 / v1.5.0 precedents).

### RD-2: Extend 3 pipeline SKILL.md bodies

**Decision:** Extend — one-line anti-pattern entry pointing at canonical section.

### RD-3: Extend all 27 `agents/*.md` files with `## Forbidden git operations`

**Decision:** Edit in place — same uniform 5-line block pattern v1.0.0 used for `## Operating context`.
**Reuse opportunity (avoided to keep the discipline visible at every agent's level):** could have done a single shared section + 27 one-line references (as v1.4.0 did for `## Operating context`). For git-discipline, inlining the 5-line block in every agent is more defensive — the rule is right there in the agent's own file, not behind a cross-reference. Worth the duplication for safety.

### RD-4: Extend `team-spawning-and-review-gates/SKILL.md`

**Decision:** Extend with a `## Baseline SHA capture` sub-section.
**Anchor:** The skill is the canonical home for teammate-spawn discipline. The baseline-SHA pattern is a spawn-time orchestrator action.

### RD-5: NEW `tests/test_teammate_git_discipline.py`

**Decision:** New file.

### RD-6: NO worktree-per-teammate dispatch in v1.6.0

**Decision:** Deeper architectural fix; deserves a separate change in v1.7+.
**Reason:** v1.6.0 ships the discipline layer; v1.7+ can ship the structural layer (each teammate spawned into its own worktree) once the discipline is in place. The two are independent.

## Migration / backwards compatibility

- **v1.5.0 → v1.6.0:** Purely additive documentation + structural tests. Existing flows continue to work; well-behaved teammates that don't run destructive git ops see no change.
- **No flag.** The discipline applies to every future run.
- **No behavior change for the runtime.** v1.6.0 is documentation + tests; no executable code changes. The discipline lives in the agent bodies + skill bodies that future Claude sessions read.

## Trade-offs accepted

- **Documentation-only discipline.** Same trade-off as v1.4.0 — no runtime detector. The agent has to actually read + apply. Mitigated by structural tests asserting the discipline is documented in the right places.
- **Inlining the `## Forbidden git operations` section in all 27 agents** (rather than cross-referencing a single shared section) — accepts ~5 × 27 = 135 lines of duplication for the safety benefit. The rule is right in front of every agent.
- **The 6-op list isn't exhaustive.** Future destructive ops could surface (e.g., `git restore --source=`). The list is the most common ones; can grow.

## Version

v1.6.0 — minor bump (additive discipline, no breaking change).
