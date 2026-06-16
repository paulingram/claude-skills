---
description: Inject an in-flight clarification, scope amendment, or separable parallel problem into the currently running architect-team pipeline. The message lands in the per-run inbox at `<workspace>/.architect-team/inbox/<run-id>.jsonl` and is picked up promptly — on the orchestrator's next wake / dispatch-return, not only at a phase boundary (v3.16.0) — where it is classified as `scope-amendment` (upstream re-run), `clarification` (folds into the next phase), `out-of-scope` (recorded), or `parallel-problem` (opens a concurrent in-run lane) per v2.5.0. Works from the same Claude Code session at a turn boundary OR from a separate terminal session.
argument-hint: "<message>"
---

# /architect-team:inject

Append a clarification or scope amendment to the in-flight pipeline run's inbox.
The orchestrator reads the inbox at every phase boundary AND on every wake /
dispatch-return (v3.16.0) per the v2.19.0 check protocol; new messages are
classified + acted on, not silently ignored — a `parallel-problem` may spawn a
concurrent lane (a dedicated background team with a disjoint file-scope lock)
that works alongside the in-flight team(s).

## Dispatch mode banner — runs first

The interpreter is selected ONCE via `$(command -v python3 || command -v python)`
(Unix: `python3`; default Windows python.org: `python`) and the script runs
**exactly once** — the v2.16.0 detect-once form, never the `python3 X || python X`
double-invocation. The banner is best-effort (always exits 0); a subprocess
failure surfaces a one-line note and the command continues.

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/scripts/setup/teams_mode.py" --banner --command "/architect-team:inject"
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
v2.19.0 helper. Each snippet inserts `${CLAUDE_PLUGIN_ROOT}` onto `sys.path` FIRST
so `from hooks.inflight_inbox import ...` resolves regardless of the cwd (the
helper module lives under the plugin root, not necessarily the workspace). These
helper snippets stay in the polyglot `python3 -c "..." || python -c "..."` form
(they are read-only and never exit 2):

```bash
RUN_ID="$(python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}'); from hooks.inflight_inbox import current_run_id; from pathlib import Path; rid = current_run_id(Path('${WORKSPACE}')); print(rid or '')" 2>/dev/null || python -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}'); from hooks.inflight_inbox import current_run_id; from pathlib import Path; rid = current_run_id(Path('${WORKSPACE}')); print(rid or '')" 2>/dev/null)"
```

If `$RUN_ID` is empty, report cleanly and exit:

```
▸ /architect-team:inject — no active run detected in <workspace>.
  (The inbox channel only accepts messages while a pipeline is running.
   If you intended to start a new pipeline, use /architect-team instead.)
```

## Phase 2 — Append to the inbox

The message is passed via the `AT_INJECT_MESSAGE` **environment variable** and read
with `os.environ` inside the snippet — NOT interpolated into the Python source as
`'''${MESSAGE}'''`. Direct interpolation breaks the moment the message contains a
`'''`, a `"`, a `$`, or a backtick (it terminates the string literal or triggers
shell expansion); routing through the environment makes the message fully
quote-safe and `$`-safe. The snippet also inserts `${CLAUDE_PLUGIN_ROOT}` onto
`sys.path` so `from hooks.inflight_inbox import ...` resolves. These helper snippets
stay polyglot (read-only; never exit 2):

```bash
AT_INJECT_MESSAGE="$MESSAGE" python3 -c "
import sys, os
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}')
from hooks.inflight_inbox import append_clarification
from pathlib import Path
import json
ws = Path('${WORKSPACE}')
rid = '${RUN_ID}'
msg = append_clarification(ws, rid, os.environ['AT_INJECT_MESSAGE'], injected_via='slash-command')
print(json.dumps(msg, indent=2))
" || AT_INJECT_MESSAGE="$MESSAGE" python -c "
import sys, os
sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}')
from hooks.inflight_inbox import append_clarification
from pathlib import Path
import json
ws = Path('${WORKSPACE}')
rid = '${RUN_ID}'
msg = append_clarification(ws, rid, os.environ['AT_INJECT_MESSAGE'], injected_via='slash-command')
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
║  The orchestrator processes this promptly — on its next wake / ║
║  dispatch return, not only at a phase boundary (v3.16.0) — then║
║  classifies it: scope-amendment / clarification / out-of-scope ║
║  / parallel-problem (which opens a concurrent in-run lane).    ║
╚════════════════════════════════════════════════════════════════╝
```

## Safety rules

- Read-only on intake-state.json. The command never modifies pipeline state directly — the orchestrator owns processing.
- Append-only on the inbox JSONL. Never rewrites, deletes, or reorders existing lines.
- Empty / whitespace-only messages are rejected at the helper layer (`ValueError`).
- The message is passed to Python via the `AT_INJECT_MESSAGE` environment variable, never interpolated into the snippet source. A message containing `'''`, `"`, `$`, or a backtick is handled verbatim — no string-literal breakage, no shell expansion.
- The command works from a separate terminal — no Claude Code session required. Use this when you're outside the running pipeline's REPL.

## Cross-references

- `skills/common-pipeline-conventions/SKILL.md` `## In-flight clarification injection mechanism (v2.19.0)` — the canonical home.
- `hooks/inflight_inbox.py` — the helper module.
- `hooks/vao_tools.py::verify_inflight_clarifications_processed` — the 17th Layer 3 tool that gates Phase 8 against silently-ignored messages.
- `skills/architect-team-pipeline/SKILL.md` `## Phase-boundary inbox check (v2.19.0)` — the orchestrator-side wiring.
