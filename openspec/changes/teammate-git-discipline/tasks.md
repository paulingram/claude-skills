# Tasks: teammate-git-discipline

Single implementer slice.

## Files owned

- Modify: `skills/common-pipeline-conventions/SKILL.md` (new `## Teammate git discipline` section)
- Modify: `skills/architect-team-pipeline/SKILL.md` (anti-pattern entry)
- Modify: `skills/bug-fix-pipeline/SKILL.md` (same)
- Modify: `skills/mini-architect-team-pipeline/SKILL.md` (same)
- Modify: all 27 `agents/*.md` files (new `## Forbidden git operations` section)
- Modify: `skills/team-spawning-and-review-gates/SKILL.md` (new `## Baseline SHA capture` sub-section)
- Create: `tests/test_teammate_git_discipline.py` (≥ 8 tests)
- Modify: `.claude-plugin/plugin.json` (1.6.0)
- Modify: `.claude-plugin/marketplace.json` (1.6.0)
- Modify: `CHANGELOG.md`, `CLAUDE.md`, `README.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`

## Tasks

- [TASK-1] Author `## Teammate git discipline` section in `skills/common-pipeline-conventions/SKILL.md`. Cover:
  - Anti-pattern: teammates running destructive git operations on shared working tree
  - The 6 forbidden operations table (verbatim from `design.md`)
  - Worked example: heirship-app-v2 reflog evidence (10× `reset: moving to HEAD` after concurrent stash by 4 teammates; mock-purge + TAMatters + TAExecution work clobbered, TAReview survived only because it was the last in)
  - The right pattern: orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at run start; teammates use `git diff $BASELINE_SHA -- <my-files>` instead of stash
  - Cross-references to `team-spawning-and-review-gates ## Baseline SHA capture` for the orchestrator-side pattern
  ~50-70 lines.

- [TASK-2] In each of `architect-team-pipeline`, `bug-fix-pipeline`, `mini-architect-team-pipeline` SKILL.md bodies, add a one-line anti-pattern entry: *"Teammates MUST NOT run destructive git operations (`git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>`, `git clean -f`). Per `common-pipeline-conventions` `## Teammate git discipline`."*

- [TASK-3] For EACH of the 27 `agents/*.md` files, INSERT a `## Forbidden git operations` section in the body. Uniform 5-line block:

```markdown
## Forbidden git operations

You MUST NOT run destructive git operations: `git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>`, `git clean -f`. These manipulate shared state across teammates and have caused real-world clobbering (the v1.6.0 worked example in `common-pipeline-conventions` `## Teammate git discipline`). For baseline verification, use the orchestrator-provided `$BASELINE_SHA` with `git diff $BASELINE_SHA -- <your-files>` instead of stash.
```

  Frontmatter (`name`, `description`, `tools`, `model`, `color`) MUST NOT change.

- [TASK-4] In `skills/team-spawning-and-review-gates/SKILL.md`, add a `## Baseline SHA capture` sub-section documenting:
  - At run start, orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)`
  - Each teammate's spawn brief includes `$BASELINE_SHA` (e.g., as a field in the teammate manifest)
  - Teammates use `git diff $BASELINE_SHA -- <my-files>` for verification
  - Pointer to `common-pipeline-conventions ## Teammate git discipline` for the forbidden-ops list

- [TASK-5] Author `tests/test_teammate_git_discipline.py` with ≥ 8 tests:
  - `common-pipeline-conventions` has `## Teammate git discipline` exactly once
  - The section names all 6 forbidden operations (parametrize over the 6)
  - The section documents the baseline-SHA pattern
  - The section references the heirship-app-v2 worked example
  - Each of the 3 pipeline bodies references the canonical section (parametrize over 3)
  - All 27 agents have `## Forbidden git operations` section (parametrize over 27)
  - No agent body documents running forbidden ops as its own action (parametrize over 27 × 6 ops = audit)
  - `team-spawning-and-review-gates` has `## Baseline SHA capture` sub-section

- [TASK-6] Version bumps in `plugin.json` + `marketplace.json` → `1.6.0`.

- [TASK-7] Docs:
  - CHANGELOG: prepend v1.6.0 entry (Added: discipline section + 27-agent forbidden-ops + baseline-SHA pattern + tests; Migration: backwards-compatible — well-behaved teammates already comply)
  - CLAUDE.md: replace v1.5.0 lead with v1.6.0 lead naming the teammate-git-discipline + worked example reference; bump test count
  - README: banner v1.6.0, badges, NEW IN v1.6.0 row, status timeline
  - CODEBASE_MAP: last_mapped 2026-05-28T07:00:00Z; add new test file to inventory; bump test counts + file count to 78
  - INTEGRATION_MAP: last_synthesized 2026-05-28T07:00:00Z; note the discipline addition

- [TASK-8] Commits (4 logical groups):
  1. common-pipeline-conventions Teammate git discipline + tests/test_teammate_git_discipline.py
  2. 3 pipeline anti-pattern entries + team-spawning-and-review-gates baseline-SHA sub-section
  3. 27 agents/*.md Forbidden git operations sections (batch in 1 commit)
  4. Version bump + docs

- [TASK-9] Phase 3 review-evidence at `.architect-team/reviews/v1.6.0-teammate-git-discipline.json` per v6. teammate = "v1.6.0-implementer", task_id = "v1.6.0-teammate-git-discipline". No `independent_review` block.

- [TASK-10] Final test:
  ```bash
  python3 -m pytest -q 2>&1 | tail -3
  ```
  Expected: 1765 + N net new (likely ~1775-1810 depending on parametrize amplification).

## Acceptance

All 7 acceptance criteria from `proposal.md` `## QA Guidance`.
