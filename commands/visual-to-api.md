---
description: Run the visual-to-API design pipeline against a visual codebase (UI present, requirements absent OR only partially specified). Drives a 4-stage structured workflow — context discovery → per-persona research → page catalog → backend design from frontend — with 3-reviewer convergence per stage and per-stage checklists that gate the next stage's freeze. Each stage's output is a frozen structured JSON artifact at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-<N>-<name>.json`. Use this when /architect-team's heuristic detection might not match — when you want to FORCE the visual-to-API pipeline regardless of whether a requirements folder is present. Auto-commits + pushes the produced artifacts on Phase 8 (unless --no-commit / --no-push) and emits a /compact prompt at end (unless --no-compact).
argument-hint: "<codebase-path> [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default]"
---

# /architect-team:visual-to-api — Force Visual-to-API Design Pipeline

You are running the visual-to-API design pipeline against a visual codebase. The user invoked this with `$ARGUMENTS` = the codebase path + optional flags. This command is the explicit entry point for the `visual-to-api-design` skill (shipped in v2.13.0) — it SHORT-CIRCUITS the architect-team-pipeline's Phase 0 heuristic detection by setting `intake_mode: "visual-to-api"` as an explicit signal. Use this when the heuristic might not match (an existing partial requirements folder, ambiguous prose, or you want to be unambiguous about the pipeline shape).

## Dispatch mode banner — runs first

As the very first user-visible action, print the dispatch-mode banner (Agent Teams vs subagents fallback) so the user knows which dispatch primitive will drive the 3-reviewer convergence per stage. Best-effort — subprocess failure surfaces a one-line note and the run continues.

```!
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:visual-to-api"
```

## Auto-cleanup merged worktrees — runs before argument parsing

Per v1.3.0 — auto-cleanup any merged `architect-team/*` worktrees from prior runs before this run creates a new one. `exclude_current=True` keeps the cwd safe. Best-effort — cleanup failures never block this new run.

```!
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/worktree_lifecycle.py" cleanup-merged --against origin/main
```

## Argument parsing

Parse `$ARGUMENTS` into tokens.

- **First non-flag token** → the codebase path. Resolve to absolute. Assert `git -C <path> rev-parse --is-inside-work-tree` (or, if no git, that the path is a directory on disk). If the path does NOT exist OR is not a directory, emit a structured error and stop: this command REQUIRES a codebase path; it does not accept free-text prose (use `/architect-team review this codebase…` for the prose path, OR run this command with the right path).
- **If `$ARGUMENTS` is empty** → ask the user once: *"What codebase should the visual-to-API pipeline analyze? Provide an absolute path to a UI codebase directory (or run from inside the codebase with `/architect-team:visual-to-api .`)."*

Flags (each independent — natural-language phrasings count as the matching flag — opt-outs: "don't commit" / "no push" / "don't compact" / "leave it uncommitted"; opt-in: "propose first" / "review before implementing" trigger `--proposal-first` but the visual-to-api-design skill's per-stage 3-reviewer convergence already provides multi-stage gates, so `--proposal-first` adds an additional pause before Stage 1 begins):

- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false` (default `true`).
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true` (default `false`).
- `--proposal-first` → `PROPOSAL_FIRST = true` (default `false`). Pauses before Stage 1 begins.
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`.

Bind `$REQ_DIR` to the codebase path.

## Skip pre-pipeline refinement

The `proposal-refiner` skill (v0.9.33) is **explicitly skipped** for this command. The visual-to-API pipeline produces its own structured artifacts at each stage; the refiner's free-text-prose-grading loop is the wrong shape for a structured-codebase input.

## Set intake-mode signal — runs before invoking the pipeline

The architect-team-pipeline at Phase 0 reads `<workspace>/.architect-team/intake-state.json::intake_mode`. When set to `"visual-to-api"`, the pipeline routes the run unconditionally to the `visual-to-api-design` skill — overriding the heuristic prose-pattern detection. Write the signal:

```!
python3 -c "
import json, os, pathlib
ws = pathlib.Path(os.environ.get('CLAUDE_WORKSPACE_DIR', '.'))
state_path = ws / '.architect-team' / 'intake-state.json'
state_path.parent.mkdir(parents=True, exist_ok=True)
state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text())
    except Exception:
        state = {}
state['intake_mode'] = 'visual-to-api'
state['invoked_via'] = '/architect-team:visual-to-api'
state_path.write_text(json.dumps(state, sort_keys=True, indent=2))
print(f'intake_mode=visual-to-api persisted to {state_path}')
" || python -c "
import json, os, pathlib
ws = pathlib.Path(os.environ.get('CLAUDE_WORKSPACE_DIR', '.'))
state_path = ws / '.architect-team' / 'intake-state.json'
state_path.parent.mkdir(parents=True, exist_ok=True)
state = {}
if state_path.exists():
    try:
        state = json.loads(state_path.read_text())
    except Exception:
        state = {}
state['intake_mode'] = 'visual-to-api'
state['invoked_via'] = '/architect-team:visual-to-api'
state_path.write_text(json.dumps(state, sort_keys=True, indent=2))
print(f'intake_mode=visual-to-api persisted to {state_path}')
"
```

The `python3 ... || python ...` polyglot pattern is the v2.9.0 audited convention — `python3` is the Unix idiom; the fallback handles default Windows python.org installs.

## Invoke the pipeline

Invoke the `architect-team-pipeline` skill from this plugin (use the Skill tool with `skill: architect-team-pipeline`). Pass `$REQ_DIR` as the input. The pipeline begins at Phase −1 (Intake & Mapping) and proceeds through Phase 8 (Final Report).

The pipeline reads `intake_mode: "visual-to-api"` at Phase 0 and routes the run to the `visual-to-api-design` skill which executes the **4-stage workflow**:

1. **Stage 1 — Context discovery.** application_purpose / industry / use_case / pages_count / personas_count. 3-reviewer convergence; frozen artifact at `<workspace>/.architect-team/visual-to-api-design/<feature-slug>/stage-1-context.json`.
2. **Stage 2 — Per-persona research.** For each persona enumerated in Stage 1, research_sources + expected_workflows + expected_data_needs + expected_affordances. Checklisted against Stage 1's `personas_count`.
3. **Stage 3 — Page catalog.** Every page → every element with classification + blurb + `is_dynamic` + `needs_backend` + `backend_endpoint_hint` + `affordance_kind`. Checklisted against Stage 1's `pages_count` + Stage 2's expected workflows + expected affordances.
4. **Stage 4 — Backend design from frontend.** 4 nested layers (data → services → schema → api) each checklisted against the prior + against Stage 3's elements with `needs_backend: true`.

Each stage runs the v0.9.19 3-reviewer convergence protocol (Round 1 independent → Round 2 round-robin → Round 3 architect review) before its artifact is frozen. The frozen chain carries `based_on_stage_<N-1>: "<sha>"` so cross-stage references are provable.

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, `ALLOW_PUSH_TO_DEFAULT`, and `PROPOSAL_FIRST` flags to the skill.** Phase 8 reads these for commit/push behavior.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase 8, after the visual-to-api-design pipeline has frozen all 4 stage artifacts and produced its final report:

1. `git -C <repo-root> status --porcelain` to enumerate what changed.
2. `git -C <repo-root> add` the produced artifacts under `.architect-team/visual-to-api-design/` + any updated CODEBASE_MAP / ROUTE_MAP / DESIGN_MAP / INTEGRATION_MAP / persona-inventory files. Do NOT use `git add -A`.
2b. **Default-branch guard:** if the current branch is `main` / `master` and `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/visual-to-api-<feature-slug>` before committing.
3. Commit with a message of the form:

```
visual-to-api-design: <one-line summary>

- Stage 1 (context discovery): pages_count=<N>, personas_count=<N>, industry=<industry>
- Stage 2 (per-persona research): <N> personas with research recorded
- Stage 3 (page catalog): <N> pages × <N> elements; <N> with needs_backend=true
- Stage 4 (backend design): <N> data points / <N> services / <N> tables / <N> endpoints
- Per-stage checklists: all green
- Frozen artifacts: <list paths>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

4. `git push -u origin <branch>`.

If `AUTO_COMMIT = false`: skip steps 2-4; mention in the final report that artifacts are uncommitted at user request.

If `AUTO_COMMIT = true` AND `AUTO_PUSH = false`: do steps 1-3 only.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase 8 completed cleanly, emit the canonical `/compact` block as the LAST thing the user sees in this turn:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  Visual-to-API design pipeline complete.                       ║
║  Context is now full of stage-artifact state. Run /compact     ║
║  NOW to free space for the next architect-team invocation.     ║
║  Type exactly:                                                 ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

## Safety rules (non-negotiable)

- NEVER force-push. NEVER skip git hooks. NEVER amend the previous commit.
- If `git push` fails, surface the error and stop — never escalate to force-push.
- If the working tree had unstaged changes BEFORE this command ran, treat them as the user's in-progress work; do NOT stage them in the pipeline's commit.
- NEVER schedule arbitrary wall-clock wakeups, cron jobs, or background timer tools from inside the pipeline.

## Cross-references

- `skills/visual-to-api-design/SKILL.md` — the canonical skill body documenting all 4 stages + 3-reviewer convergence + per-stage checklists + new SR origin kind `api-design-stage-incomplete`.
- `commands/architect-team.md` — the general-purpose entry point that uses heuristic detection (this command is the explicit-routing alternative).
- v2.9.0 polyglot Python invocation convention (`python3 ... || python ...`).
- v2.13.0 — the release that introduced `visual-to-api-design` as the framework's 30th skill.
