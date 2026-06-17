## Why

CT6-6 §7 (CMD-1…CMD-4) asks that, when MemPalace is installed, `CLAUDE.md` stop being a container of full context and become a thin POINTER: it tells the agent WHERE to find things so context is loaded on demand, it stays very small, and it carries two parts — standards that point to a reference MemPalace, and customizations the user can toggle on/off. The repo already has `mempalace-integration` to point INTO; this adds the pointer-style discipline reuse-first. Component 3 of the in-repo CT6-6 tier.

## What Changes

- **New deterministic engine** — `scripts/claude_md/claude_md_efficiency.py` (stdlib-only): `assess_claude_md(text)` scores a `CLAUDE.md` for pointer-shape (a marker heuristic) + size (a byte budget) and emits advisory signals; `generate_pointer_claude_md(...)` emits a minimal, correctly-shaped pointer doc (a wake-up first step + standards + customizations). (REQ-001)
- **New skill contract** — `skills/claude-md-efficiency/SKILL.md`: the CMD-1…CMD-4 workflow, with CMD-1 (only when MemPalace is installed) as a hard precondition that delegates detection to `mempalace-integration`. (REQ-002)
- **Honest boundary** — the signals are heuristics (not proof the pointers resolve); context is NEVER deleted from `CLAUDE.md` unless first stored in MemPalace. (REQ-003)
- **Reuse-first + currency** — modelled on the skill-support-module pattern; Python stays stdlib-only; version bump to 3.19.0; skill count 43→44. (REQ-004)
- **Tests** — `tests/test_claude_md_efficiency.py` (assessor + generate→assess round-trip + CLI + boundary pins); suite green both encodings. (REQ-005)

## Capabilities

### New Capabilities

- `claude-md-efficiency` — make `CLAUDE.md` a thin, MemPalace-backed pointer (load context on demand) instead of a full-context container, with an assessor + generator.

### Modified Capabilities

- None removed. The skill inventory grows by one; no new command/agent/Layer-3 tool.
