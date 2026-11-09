# Skill-invocation discipline (v2.0.0)

Layer 6 of the Verified Agent Output (VAO) framework — the gate that ensures the OTHER FIVE LAYERS get a chance to fire at all. The heirship-app-v2 session that triggered this discipline: a user typed `/architect-team:architect-team review the excel list`, but earlier in the same session an `architect-team` Skill had already been invoked. The harness's system reminder said *"this skill has been invoked earlier in this session"*. The agent interpreted that as a SESSION-WIDE ban on re-invocation and "applied the methodology by hand" — read files, edited code, ran tests, made commits — all WITHOUT calling the Skill tool. None of Layers 1-5 fired because the framework was never reinvoked. The user's explicit instruction got the work, but none of the structural verification.

### The rule

**User explicit instructions override `skill already invoked, do not re-execute` system notes.** If the user typed a slash-command form (`/architect-team`, `/architect-team:X`, `/bug-fix`, `/ux-test`, `/mini`, `/refine-prompt`, `/cleanup-worktrees`, `/mempalace-install`, `/mempalace-search`, `/mempalace-status`, `/status`, `/code-review`, `/editability-audit`) OR a prose form (*"use /architect-team"*, *"invoke /bug-fix"*, *"run /mini"*, *"using architect-team"*, *"with architect-team"*, *"fire architect-team"*), the agent MUST invoke the requested Skill via the Skill tool — **even if Skill X was invoked earlier in the session**.

The "do not re-execute" system note is a hint preventing accidental re-invocation within a single decision cycle, NOT a session-wide ban on re-invocation. User instructions take precedence per the `superpowers:using-superpowers` Instruction Priority rule: (1) user explicit instructions are highest priority; (2) Superpowers skills override default system behavior; (3) default system prompt is lowest priority.

**Applying methodology by hand is forbidden.** Reading the Skill's contents and executing them manually rather than invoking the Skill tool BYPASSES the entire VAO framework — no oracle-derivation runs, no adversarial review fires, no tool-mediated verdicts are written, schema v7 enforcement does not engage. The Skill IS the framework; the methodology-by-hand pattern IS the bypass.

### Surface forms the Stop-hook auditor detects

`hooks/skill_invocation_audit.py` parses the session transcript for two surface forms:

**Slash-command form (canonical).** Any of the 13 user-invocable command names preceded by `/`: `/architect-team`, `/architect-team:architect-team`, `/bug-fix`, `/ux-test`, `/mini`, `/refine-prompt`, `/cleanup-worktrees`, `/mempalace-install`, `/mempalace-search`, `/mempalace-status`, `/status`, `/code-review`, `/editability-audit`. Case-insensitive; sub-routes like `/architect-team:bug-fix` fall back to the base command's expected Skill set.

**Prose form.** A verb (`use`, `using`, `invoke`, `run`, `fire`, `with`) followed by an optional `the`, an optional `/`, and a command name. Examples — *"use architect-team"*, *"using the architect-team"*, *"invoke /bug-fix"*, *"run mini"*, *"fire architect-team"*. Conversational mentions WITHOUT a verb (*"we discussed the architect-team plugin earlier"*) DO NOT count — only explicit-request shapes count.

### The audit verdict

The Stop hook reads the session's tool-call ledger at `.architect-team/run-history/<run-id>-toolcalls.jsonl` (where `<run-id>` is the canonical run identifier). For every explicit Skill-invocation request, asserts the matching `Skill` tool invocation appears in the ledger AFTER the request's timestamp. If any request has no matching invocation, the audit exits 2 with the failure report and writes the verdict to `.architect-team/vao-verdicts/<run-id>-skill-invocation-audit.json`.

Schema v7's `skill_invocation_audit` field MUST cite this verdict path; a missing field or a `fail` verdict blocks the run at the review-evidence hook.

### Cross-references

- `hooks/skill_invocation_audit.py` — the auditor (Stop-hook + CLI form).
- `hooks/review_evidence_schema.py` — v7 schema declaring `skill_invocation_audit` as a required field.
- `tests/test_vao_skill_invocation_audit.py` — structural tests pinning the regex coverage + the audit verdict semantics + the user-precedence rule documentation.
- `tests/fixtures/vao/skill-not-invoked.json` — the canonical synthetic fixture reproducing the heirship "applied methodology by hand" failure.
- `superpowers:using-superpowers` Instruction Priority rule — the upstream authority for "user explicit instructions are highest priority".
