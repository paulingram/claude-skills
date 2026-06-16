## Why

When a user invokes a pipeline-driving plugin command (`/architect-team:architect-team`, `/architect-team:bug-fix`, `/architect-team:ux-test`, `/architect-team:mini`, `/architect-team:refine-prompt`), the command body *instructs* the model to invoke the underlying Skill via the Skill tool — but nothing FORCES it. The model can "drive the pipeline by hand" and never call the Skill. The only existing guard, `hooks/skill_invocation_audit.py` (Layer 6), is an after-the-fact auditor: it flags a missed Skill invocation only at end-of-turn, and it is not even wired into `hooks.json`. Soft prompts (the user's CLAUDE.md directive, the command body, the using-superpowers skill) are routinely rationalized past. This run converts enforcement from after-the-fact DETECTION to real-time PREVENTION via a deterministic PreToolUse hook that cannot be rationalized past.

The hard constraint from the user is non-negotiable: the enforcement must be UNIVERSAL / GLOBAL to the plugin — no reference to any specific codebase, repo, app, or project — keyed off the plugin's own discovered command set and the Skill-tool ledger only, working in any repository the plugin is installed into.

## What Changes

- **New PreToolUse hard-gate** — `hooks/pretool_skill_gate.py` (stdlib-only): when the session transcript's most-recent GENUINE user prompt is an unsatisfied pipeline-command request, it BLOCKS (exit 2) the first non-Skill tool call until a matching Skill call appears. (REQ-001)
- **Reuse, not duplication** — detection reuses `find_skill_requests` + `COMMAND_TO_SKILLS` from `hooks/skill_invocation_audit.py` via a dual-form import; a precise `<command-name>` marker detector keys on the unambiguous genuine-invocation signal. (REQ-002)
- **Scoped + false-positive-safe** — only the five pipeline-driving commands gate (expected skill ∈ the pipeline skill set); read-only plugin commands and built-in REPL commands never gate. Injected/meta records (`isMeta` body echoes, `promptSource:"system"` task-notifications, `isSidechain` subagent transcripts) are excluded from the anchor so a session is never bricked. (REQ-003)
- **Fail-open + Skill escape** — the Skill tool itself is always allowed; missing/unreadable transcript, no pending request, or ANY internal error allows the tool call. (REQ-004)
- **Wiring** — registered in `hooks/hooks.json` as a `PreToolUse` `*` matcher using `${CLAUDE_PLUGIN_ROOT}` and the detect-once Python shim. (REQ-005)
- **Tests + docs + version** — a new pytest file proving gate open/close, user-precedence, the real nested transcript shape, the injected-meta brick regressions, fail-open, and end-to-end subprocess; the suite stays green under cp1252 AND `PYTHONUTF8=1`; docs (CODEBASE_MAP, INTEGRATION_MAP, CLAUDE.md, README, CHANGELOG) brought current; version bumped. (REQ-006)

## Capabilities

### New Capabilities

- `hooks/pretool_skill_gate.py` — real-time, plugin-universal enforcement that a user-invoked pipeline command is satisfied by a Skill invocation before any other tool runs.

### Modified Capabilities

- `hooks/hooks.json` gains a PreToolUse `*` entry. No existing skill/agent/command behavior changes. The Layer-6 `skill_invocation_audit.py` detection is reused unchanged.
