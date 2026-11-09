# Non-overlapping file scopes

Two teammates MUST NEVER edit the same file. Period.

### How to assign scopes

1. Read `tasks.md` and the coverage map.
2. For each task, list every file it will create or modify (use the design.md's Reuse Decisions as the canonical list).
3. Group tasks by overlapping file sets. Each non-overlapping group becomes one teammate's scope.
4. If a single task forces overlap (e.g., a contract file that backend writes and frontend consumes), assign the task to ONE owner and have the other consume the result — see "Direct messaging" below.

### What to put in the teammate's brief

**First line (MANDATORY, v3.30.0): the run-continuity teammate token.** Every teams-mode spawn brief AND every subagents-mode dispatch prompt begins with the literal line:

```
[CT6-TEAMMATE <teammate-name> RUN <run-id-or-slug>]
```

The `CT6-TEAMMATE` token is how the run-continuity enforcement (`common-pipeline-conventions` `## Run continuity discipline (v3.30.0)`) recognizes a teammate session and stands down — teammates never invoke Skills, so without the token the PreToolUse sticky arm could block the run's own workers. A brief that omits the token risks its teammate being told to resume the pipeline instead of executing its slice; the Lead re-issues the brief with the token if a teammate reports that block.

Then the brief fields:

- `task_ids`: the exact task IDs from `tasks.md` it owns.
- `files_owned`: the explicit list of files it may write. Anything not in this list is read-only for this teammate.
- `files_consumed`: files it reads but does not write (with the owning teammate's name where relevant).
- `acceptance_criteria`: verbatim from the coverage map.
- `relevant_codebase_map_sections`: paths into CODEBASE_MAP.md.
- `reuse_decisions`: the relevant entries from `design.md`'s Reuse Decisions section.
- `plan_approval_mode`: `true` if any of the triggers below apply.
- `vao_adversarial_role`: the adversarial-reviewer shape paired with this teammate (see the selection rules below).

**Every brief MUST carry the message-payload rule** (see `## Direct teammate-to-teammate messaging` → `### Message payload discipline`). A teammate that does not know `SendMessage` is user-visible will route its evidence through it by default, and the human running the pipeline pays for that in attention. State it in the brief in one line — *escalate through `SendMessage` with the decision and the single fact that forces it, plus the path to your evidence file; put measurement in the file, not the message; never send a completion report — your final report already reaches the Lead.* The escalation obligation itself is unchanged and outranks brevity: a brief that is wrong, or an approach that cannot work, is still reported rather than absorbed.

### Adversarial-reviewer shape selection (v2.0.0 + v3.10.0 `security-hunter`)

Every Phase 3 teammate is paired with an `adversarial-reviewer` whose `vao_adversarial_role` is chosen by the task shape (the agent body `agents/adversarial-reviewer.md` documents the six shapes). The pairing rules:

| Task shape | `vao_adversarial_role`(s) to spawn |
|---|---|
| `parity-verb` (match / rebuild / mirror / parity / replicate) | `oracle-divergence-hunter` |
| `backend-dep` (the slice depends on a backend endpoint / data) | **BOTH `fake-data-hunter` AND `security-hunter`** |
| `dynamic-value` (renders per-user / per-record values) | `hardcoded-literal-hunter` |
| `shared-tree` (always-on, every teammate) | `git-discipline-hunter` |
| any other | `general-anti-pattern-hunter` |

**`security-hunter` trigger rules (v3.10.0) — mandatory when ANY holds:**

1. The task is a **`backend-dep`** shape → spawn BOTH `fake-data-hunter` AND `security-hunter` (a backend-touching slice is exactly where authz / injection / secret defects land).
2. The teammate's diff **touches `auth/` or any security-sensitive path** (auth, session, crypto, permission, RBAC, token, password, secret) → `security-hunter` is mandatory regardless of task shape.
3. The change **adds a third-party dependency** (a new entry in any package manifest) → `security-hunter` is mandatory; it checks the dependency-addition justification (a Reuse Decision + a stated reason).

A confirmed `security-hunter` finding is routed as a solution requirement with `origin.kind: "security-finding"` (see `## Solution Requirements`); it is NOT a Layer 3 `verify_*` verdict severity.
