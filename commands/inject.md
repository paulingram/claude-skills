---
description: Inject an in-flight clarification or scope amendment into the currently running architect-team pipeline. The message lands in the per-run inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` and is picked up at the next phase boundary, where the orchestrator classifies it as `scope-amendment` (triggers an upstream re-run) or `clarification` (folds into the next phase) per v2.5.0. Works from the same Claude Code session at a turn boundary OR from a separate terminal session.
argument-hint: "<message>"
---

# /architect-team:inject

Append a clarification or scope amendment to the in-flight pipeline run's inbox.
The orchestrator reads the inbox at every phase boundary per the v2.19.0
phase-boundary check protocol; new messages are classified + acted on, not
silently ignored.

## Dispatch mode banner — runs first

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:inject" || python "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:inject"
```

## Argument parsing

The argument is the user's verbatim message — everything after `/architect-team:inject`.
Quote the message if it contains shell special characters.

```bash
MESSAGE="$*"
if [ -z "$MESSAGE" ]; then
  echo "Usage: /architect-team:inject <your message here>"
  echo "Example: /architect-team:inject also include CSV export on the dashboard"
  exit 0
fi
```

## Phase 1 — Resolve workspace + active run

```bash
WORKSPACE="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Read the active run-id from `<workspace>/.architect-team/intake-state.json` via the
v2.19.0 helper:

```bash
RUN_ID="$(python3 -c "from hooks.inflight_inbox import current_run_id; from pathlib import Path; rid = current_run_id(Path('${WORKSPACE}')); print(rid or '')" 2>/dev/null || python -c "from hooks.inflight_inbox import current_run_id; from pathlib import Path; rid = current_run_id(Path('${WORKSPACE}')); print(rid or '')" 2>/dev/null)"
```

If `$RUN_ID` is empty, report cleanly and exit:

```
▸ /architect-team:inject — no active run detected in <workspace>.
  (The inbox channel only accepts messages while a pipeline is running.
   If you intended to start a new pipeline, use /architect-team instead.)
```

## Phase 2 — Append to the inbox

```bash
python3 -c "
from hooks.inflight_inbox import append_clarification
from pathlib import Path
import json, sys
ws = Path('${WORKSPACE}')
rid = '${RUN_ID}'
msg = append_clarification(ws, rid, '''${MESSAGE}''', injected_via='slash-command')
print(json.dumps(msg, indent=2))
" || python -c "
from hooks.inflight_inbox import append_clarification
from pathlib import Path
import json, sys
ws = Path('${WORKSPACE}')
rid = '${RUN_ID}'
msg = append_clarification(ws, rid, '''${MESSAGE}''', injected_via='slash-command')
print(json.dumps(msg, indent=2))
"
```

## Phase 3 — Report

Print a one-block confirmation showing:
- The message that was queued (verbatim)
- The run-id it was attached to
- The inbox path on disk
- A reminder that the orchestrator will process at the next phase boundary

```
╔════════════════════════════════════════════════════════════════╗
║  ◆  Clarification queued                                       ║
║                                                                ║
║  Message: <verbatim message>                                   ║
║  Run-id:  <run-id>                                             ║
║  Inbox:   .architect-team/inbox/<run-id>.jsonl                 ║
║                                                                ║
║  The orchestrator will process this at the next phase          ║
║  boundary (Phase −1 / Phase 0 / Phase 2 dispatch return / ...) ║
║  and classify it as scope-amendment, clarification, or         ║
║  out-of-scope per v2.5.0.                                      ║
╚════════════════════════════════════════════════════════════════╝
```

## Safety rules

- Read-only on intake-state.json. The command never modifies pipeline state directly — the orchestrator owns processing.
- Append-only on the inbox JSONL. Never rewrites, deletes, or reorders existing lines.
- Empty / whitespace-only messages are rejected at the helper layer (`ValueError`).
- The command works from a separate terminal — no Claude Code session required. Use this when you're outside the running pipeline's REPL.

## Cross-references

- `skills/common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` — the canonical home.
- `hooks/inflight_inbox.py` — the helper module.
- `hooks/vao_tools.py::verify_inflight_clarifications_processed` — the 17th Layer 3 tool that gates Phase 8 against silently-ignored messages.
- `skills/architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — the orchestrator-side wiring.
