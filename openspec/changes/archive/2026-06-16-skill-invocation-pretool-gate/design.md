## Context

The plugin already ships a Layer-6 skill-invocation auditor (`hooks/skill_invocation_audit.py`) that DETECTS, after a turn ends, when an explicit user skill-invocation request had no matching `Skill` tool call. It is not wired as an active hook and cannot prevent a bypass in real time. This change adds the PREVENTION layer.

## Goals / Non-Goals

- **Goal:** deterministically block the first non-`Skill` tool call after an unsatisfied pipeline-command request, in real time, universally across any repo the plugin is installed into.
- **Goal:** never false-block a normal session (fail-open by construction; the catastrophic failure mode is a spurious block, since the hook fires on every tool call).
- **Non-Goal:** enforcing the EXACT pipeline tier (mini vs full). The gate prevents driving-by-hand, not tier choice — engaging any pipeline skill satisfies it.
- **Non-Goal:** changing the Layer-6 auditor or wiring it into `hooks.json` (separate concern).

## Reuse Decision Log

| Proposed unit | Decision | Rationale |
|---|---|---|
| Request detection (command set, command→skill map, prose/slash matching) | **REUSE** `find_skill_requests` + `COMMAND_TO_SKILLS` from `hooks/skill_invocation_audit.py` (dual-form import) | Single source of truth for the plugin's command set; no duplication of the regex/mapping. Verified present in `skill_invocation_audit.py`. |
| UTF-8 stdin read, `check_payload` pure-function shape, fail-open `main()` | **REUSE pattern** from `hooks/pretool_unilateral_override_guard.py` | Matches the existing PreToolUse hook convention; cp1252-safe. |
| `<command-name>` marker detection | **BUILD NEW** (small regex) | The audit's slash regex requires a whitespace boundary and does NOT match `<command-name>/...`; the marker is the unambiguous genuine-invocation signal that eliminates the false-positive class (pasted docs / system-reminders). Justified new detection on a better-scoped signal, not duplication. |
| JSONL/array transcript reader | **BUILD NEW** (tail-capped) | The hook fires on every tool call; a tail-capped reader bounds latency on long transcripts. The shared `read_jsonl` is not tail-aware. |

## Key Decisions

- **Anchor to the single most-recent GENUINE user prompt.** Genuine = role `user`, not `isMeta`, `promptSource != "system"`, not `isSidechain`. This excludes the harness's `isMeta` body-echo (which the harness writes right AFTER the Skill call with a newer timestamp and full of pipeline text) — the record that, if treated as a prompt, re-raises the mandate and bricks the session. Confirmed against real transcripts: `userType` is `"external"` for ALL user records, so `isMeta`/`promptSource`/`isSidechain` are the real discriminators.
- **Satisfaction = engaging any pipeline skill after the anchor** (or the exact expected skill), with timestamp ordering implementing user-precedence (a new request needs its own Skill call). Verified against 9 real transcripts: zero spurious blocks where a pipeline skill was engaged; genuine historical bypasses (no skill engaged) are correctly caught.
- **Fail-open everywhere; the `Skill` tool is always allowed** (else the mandate would be unsatisfiable).

## Risks / Mitigations

- **Risk: false-block bricking a session.** Mitigation: anchor excludes injected/meta records; fail-open on every error; self-clearing (a non-pipeline follow-up prompt stands the gate down); validated against real transcripts (0 spurious blocks).
- **Risk: latency on every tool call.** Mitigation: tail-capped transcript read (2 MB).
