# No pipeline-bypass discipline (v2.22.0)

When the user invokes `/architect-team` (or any pipeline-driving slash command), the orchestrator MUST follow the pipeline. "Follow" means actually executing the multi-agent dispatch, the OpenSpec ceremony, the worktree isolation, the independent review gates, and the completion audit — NOT applying the methodology by hand because the orchestrator decided the prior session's mapping was sufficient.

**Failure shape** (verbatim case in CHANGELOG v2.22.0): after running `/architect-team` — whose purpose is parallel backend/frontend teammates, independent review gates, OpenSpec specs, worktree isolation, Playwright tests, and a completion audit — the agent confessed *"I bypassed all of that and built it solo. I wrote the code, tested it myself, and committed it directly — no subagents, no independent review, no OpenSpec, no worktree … but the honest framing is: I overrode your explicit choice to use the pipeline."* v2.0.0 Layer 6 checked only that the Skill APPEARED in the ledger; the agent may invoke it briefly THEN bypass everything it dictated. v2.22.0 strengthens the detection: the pipeline must not only be **invoked** but also **followed** (Agent dispatches > 0, task-reviewer evidence > 0, OpenSpec calls > 0, worktree creation > 0).

### The 5 mandatory pipeline elements

When `pipeline_invoked == true` (the user typed `/architect-team` / `/architect-team:bug-fix` / `/architect-team:mini` / `/architect-team:ux-test`), the toolcall ledger MUST contain:

| Element | Required count | Detection |
|---|---|---|
| **Skill invocation** | ≥ 1 | A `Skill` tool call with `skill_name` matching `architect-team-pipeline` / `bug-fix-pipeline` / `mini-architect-team-pipeline` / `ux-test-builder` |
| **Subagent dispatches** | ≥ 2 | `Agent` tool calls dispatching CT6 subagents (architect-team:backend / frontend / system-architect / etc.). Solo implementation means 0 Agent dispatches — the bypass case |
| **Independent review evidence** | ≥ 1 per task group | `.architect-team/reviews/<task-id>.json`, `independent_review.reviewer != teammate` per v7, bound via `task_subject` (ids reused; `<id>.<slug>.json` on clash) |
| **OpenSpec ceremony** | ≥ 1 `openspec` Bash call | `openspec init` / `openspec validate` / `openspec archive` Bash calls. Skipping = openspec-bypassed |
| **Worktree isolation** | ≥ 1 `git worktree add` call OR `--no-worktree` flag in user prompt | The v1.2.0 auto-worktree creation should fire as the first action |

### 5 named severities

| Severity | Trigger |
|---|---|
| `pipeline-bypassed-after-slash-command` | User typed `/architect-team*` BUT the ledger has Edit/Write/Bash source modifications WITHOUT an intervening `Skill(architect-team-pipeline)` or `Skill(bug-fix-pipeline)` invocation. The agent applied methodology by hand. |
| `solo-implementation-instead-of-team-dispatch` | `pipeline_invoked == true` AND `Agent` tool call count == 0 (zero subagents dispatched). The agent did all the work itself. |
| `independent-review-bypassed` | `pipeline_invoked == true` AND no files under `.architect-team/reviews/` with `independent_review.reviewer != teammate`. Producer === checker is the failure shape. |
| `openspec-bypassed` | `pipeline_invoked == true` AND zero `openspec` Bash calls. |
| `pipeline-confession-language-detected` | The agent's final_report contains any of the canonical bypass-confession markers (text-detector backup) |

### Canonical bypass-confession markers (`_PIPELINE_CONFESSION_MARKERS`)

| Class | Patterns |
|---|---|
| **Bypass admission** | `I bypassed all of that`, `bypassed all of`, `built it solo`, `built solo`, `I built solo`, `I overrode your`, `overrode your explicit choice`, `overrode your choice`, `I overrode`, `wrote the code, tested it myself`, `committed it directly` |
| **Element confession** | `no subagents`, `no independent review`, `no OpenSpec`, `no worktree`, `no producer-checker`, `the producer is never its own checker` (when used in past-tense confession context), `the producer was the checker`, `I tested it myself` |
| **Rationalization** | `driving directly from the plan`, `tokens into code instead of`, `the mapping/spec ceremony`, `re-running the mapping/spec`, `skipped the ceremony`, `I'd already mapped the`, `put tokens into code` |
| **Post-hoc framing** | `the honest framing is`, `I told you I was`, `your call to make`, `not mine to make silently`, `deserve to know`, `straight about that` |

### New SR origin kind

`pipeline-bypassed-needs-rerun` — fires when the audit catches a bypass. The orchestrator MUST then either (a) re-run the actual pipeline against the same prompt OR (b) confirm with the user that the bypass was intentional and they accept the unreviewed work.

### Cross-references

- `hooks/vao_tools.py::verify_no_pipeline_bypass` — the 20th Layer 3 tool.
- `hooks/skill_invocation_audit.py` — v2.0.0 Layer 6 Stop-hook auditor, STRENGTHENED in v2.22.0 to also fire `solo-implementation-instead-of-team-dispatch` when the Skill was invoked but no Agent dispatches followed.
- `agents/system-architect.md` `## No pipeline-bypass discipline (v2.22.0)` — Team Lead must NOT silently override when reasoning says "I already mapped the codebases" / "I'll drive directly from the plan".
- `tests/fixtures/vao/pipeline-bypassed-solo-implementation.json` — verbatim case (user typed /architect-team twice; ledger has Edit/Write/Bash but zero Agent dispatches; final_report contains the 11+ confession markers).
- Companion to v2.0.0 Layer 6 (catches Skill-not-invoked surface) — v2.22.0 catches the FOLLOWED-BUT-NOT-EXECUTED surface AND the post-hoc-confession surface.
