#!/usr/bin/env python3
"""v3.0.0 PreToolUse runtime guardrail.

Fires BEFORE Edit / Write / NotebookEdit tool calls when:

  1. An active pipeline run is in flight (workspace's `.architect-team/
     intake-state.json` exists with `status: in_progress` and `phase < 8`).
  2. The about-to-fire tool targets a source file (NOT under
     `.architect-team/` / `.mempalace/` / `openspec/changes/`).
  3. No `Skill(architect-team-pipeline)` (or sibling pipeline skill)
     invocation appears in the run's toolcall ledger yet.

When all three conditions hold, exit 2 to block the tool call. The stderr
message names the violation + the disclosure-required alternative.

Use:
  Registered in hooks/hooks.json as PreToolUse[Edit|Write|NotebookEdit].
  Payload is read from stdin as JSON.

Backwards-compat: when no active pipeline state is detected, the hook is a
silent no-op (exit 0). Stdlib-only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _read_stdin_utf8() -> str:
    """Read the hook payload from stdin as UTF-8 (A8 review-remediation).

    Decodes the raw stdin bytes as `utf-8` with `errors="replace"` instead of
    the locale codec so a UTF-8 payload (e.g. an emoji in a tool-input field)
    cannot raise `UnicodeDecodeError` under cp1252 and degrade this guard to a
    silent no-op. Falls back to the text stream when `sys.stdin.buffer` is
    unavailable (e.g. a test that replaced `sys.stdin` with a StringIO)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


_PIPELINE_SKILL_NAMES = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
    "architect-team",  # plugin-prefixed slug
)


_BYPASS_ALLOWED_PATH_FRAGMENTS = (
    "/.architect-team/",
    "/.mempalace/",
    "/openspec/changes/",
    "\\.architect-team\\",
    "\\.mempalace\\",
    "\\openspec\\changes\\",
)


# v3.44.0 — the deploy config is human-authored and IMMUTABLE to agents once it
# exists. Canonical filename mirrors hooks/deploy_config.py::DEPLOY_CONFIG_FILENAME
# (kept as a local literal so this hook carries no import dependency).
_DEPLOY_CONFIG_FILENAME = ".architect-team-deploy.json"


def _find_workspace(start: Path) -> Path | None:
    """Walk up from `start` looking for a directory containing `.architect-team/`.

    Returns the workspace root or None if no such ancestor exists. The bare
    filesystem root (drive anchor on Windows, `/` on POSIX) is never treated
    as a workspace: a stray `C:\\.architect-team` / `/.architect-team` must not
    capture an unrelated subtree. The walk terminates at the root and returns
    None when no real marker is found.
    """
    start = start.resolve()
    root = Path(start.anchor)
    for candidate in (start, *start.parents):
        if candidate == root:
            continue
        if (candidate / ".architect-team").is_dir():
            return candidate
    return None


def _read_intake_state(workspace: Path) -> dict[str, Any] | None:
    intake_path = workspace / ".architect-team" / "intake-state.json"
    if not intake_path.exists():
        return None
    try:
        return json.loads(intake_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _ledger_has_pipeline_skill_invocation(workspace: Path, run_id: str | None) -> bool:
    """True iff the toolcall ledger contains a Skill call for a pipeline-driving skill."""
    if not run_id:
        return False
    ledger_path = workspace / ".architect-team" / "run-history" / f"{run_id}-toolcalls.jsonl"
    if not ledger_path.exists():
        return False
    try:
        text = ledger_path.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        tool = (entry.get("tool") or entry.get("tool_name") or "").strip()
        if tool != "Skill":
            continue
        inp = entry.get("tool_input") or entry.get("input") or entry.get("args") or {}
        if not isinstance(inp, dict):
            continue
        skill_name = (inp.get("skill") or inp.get("skill_name") or "").strip().lower()
        if any(p in skill_name for p in _PIPELINE_SKILL_NAMES):
            return True
    return False


def _is_allowed_path(file_path: str) -> bool:
    """True iff writing this path does NOT count as a source-code bypass.

    Writes under `.architect-team/` / `.mempalace/` / `openspec/changes/`
    are pipeline-managed state and never trigger the guardrail.
    """
    if not isinstance(file_path, str) or not file_path:
        return True
    lower = file_path.lower().replace("\\", "/")
    return any(frag.replace("\\", "/") in lower for frag in _BYPASS_ALLOWED_PATH_FRAGMENTS)


def _targets_existing_deploy_config(file_path: str) -> bool:
    """True iff the tool targets an EXISTING ``.architect-team-deploy.json``.

    Modifying / overwriting / deleting an existing human-authored deploy config
    is the "override" the v3.44.0 discipline forbids — only a human may edit or
    disable it. Creating a fresh config (the file does not exist yet) is NOT a
    violation: it only ADDS the prod constraint, never removes it.
    """
    if not isinstance(file_path, str) or not file_path:
        return False
    try:
        p = Path(file_path)
    except (TypeError, ValueError):
        return False
    return p.name == _DEPLOY_CONFIG_FILENAME and p.exists()


# v3.56.0 (ADV-3 / ADV-5, adversarial review) — the completion lock's GROUND
# TRUTH is immutable to agents. The whole gate rests on one property: the
# stopping condition is read from files the agent does not write. The
# adversarial pass defeated that twice with a single tool call each:
#
#   ADV-3  one Write flips every ask-ledger entry to "resolved"
#   ADV-5  writing "status": "completed" straight into a harness task JSON
#          bypasses review-gate-task.py entirely, because that hook is
#          PostToolUse(TaskUpdate) and only ever sees the TOOL, never a
#          filesystem write
#
# Closing a task through `TaskUpdate` stays entirely legitimate — that is the
# harness's own surface and the gate reads its result. What is forbidden is
# reaching around it and editing the record directly.
#
# HONEST BOUNDARY: this raises the cost and makes the bypass a deliberate,
# visible act rather than an accident. An agent with unrestricted Bash can
# still write these files by other means; no hook-tier guard can prevent that.
_ASK_LEDGER_FILENAME = "ask-ledger.json"
_STATE_DIRNAME = ".architect-team"


def _harness_tasks_root() -> Path | None:
    """The harness task store, via the substrate's own resolver when available."""
    try:  # the substrate owns the resolution order (explicit > env > home)
        from hooks.open_work import tasks_root  # type: ignore
    except Exception:
        try:
            from open_work import tasks_root  # type: ignore
        except Exception:
            tasks_root = None  # type: ignore[assignment]
    if tasks_root is not None:
        try:
            return Path(tasks_root()).resolve()
        except Exception:
            pass
    try:  # last-resort fallback mirroring open_work.tasks_root's default
        return (Path.home() / ".claude" / "tasks").resolve()
    except Exception:
        return None


def _targets_completion_lock_ground_truth(file_path: str) -> str | None:
    """The ground-truth source this write targets, or None.

    Returns a short label naming WHICH source, so the block message can be
    specific about what the agent was about to overwrite.
    """
    if not isinstance(file_path, str) or not file_path:
        return None
    try:
        p = Path(file_path)
    except (TypeError, ValueError):
        return None

    # The ask-ledger, matched on name + its .architect-team/ parent so an
    # unrelated file that happens to share the basename is not caught.
    if p.name == _ASK_LEDGER_FILENAME and p.parent.name == _STATE_DIRNAME:
        return "ask-ledger"

    # Any path under the harness task store.
    root = _harness_tasks_root()
    if root is not None:
        try:
            resolved = p.resolve()
        except Exception:
            resolved = None
        if resolved is not None:
            try:
                resolved.relative_to(root)
                return "harness-task-store"
            except ValueError:
                pass
    return None


def check_payload(payload: dict[str, Any]) -> tuple[int, str]:
    """Inspect a PreToolUse payload and return (exit_code, stderr_message).

    Pure function — safe to call from tests with any payload shape.
    """
    tool = (payload.get("tool_name") or payload.get("tool") or "").strip()
    if tool not in ("Edit", "Write", "NotebookEdit"):
        return 0, ""

    tool_input = payload.get("tool_input") or payload.get("input") or payload.get("args") or {}
    if not isinstance(tool_input, dict):
        return 0, ""

    file_path = (
        tool_input.get("file_path")
        or tool_input.get("path")
        or tool_input.get("notebook_path")
        or ""
    )
    if not file_path:
        return 0, ""

    # v3.56.0 completion-lock ground-truth immutability (ADV-3 / ADV-5) — fires
    # UNCONDITIONALLY, like the deploy-config rule below and for the same
    # reason: an agent rewriting the record the gate reads is a violation
    # whether or not a pipeline run is active. The reported failure happens in
    # plain Agent Teams sessions with no CT6 run at all, so a run-gated check
    # would miss exactly the case that matters.
    _ground_truth = _targets_completion_lock_ground_truth(file_path)
    if _ground_truth is not None:
        if _ground_truth == "ask-ledger":
            what = (
                "the ask-ledger — the record of the directives you were given. "
                "Editing it lets a session mark its own outstanding asks "
                "resolved, which is the self-asserted exit the completion lock "
                "exists to remove"
            )
            instead = (
                "Do the work the entry names. A ledger entry is released by "
                "recording its resolution through the substrate's own CLI "
                "(hooks/open_work.py), not by hand-editing the file; an "
                "ambiguous entry stays open on purpose."
            )
        else:
            what = (
                "the harness task store — the list the completion lock reads to "
                "decide whether work is still open. Writing a status directly "
                "into a task file reaches around TaskUpdate, so the "
                "PostToolUse(TaskUpdate) review gate never sees it"
            )
            instead = (
                "Use the TaskUpdate tool. Closing a task through the harness is "
                "entirely legitimate and the lock reads the result; only "
                "editing the record behind the harness's back is forbidden."
            )
        message = (
            "CT6 v3.56.0 PreToolUse guardrail BLOCKED — completion-lock ground "
            "truth is immutable to agents.\n"
            "\n"
            f"  - tool about to fire: {tool}\n"
            f"  - target file: {file_path}\n"
            f"  - source: {_ground_truth}\n"
            "\n"
            f"This file is {what}.\n"
            "\n"
            "The completion lock works because its stopping condition lives in "
            "files the agent does not write. A session that can edit its own "
            "ground truth has no gate at all — it just has a file it is "
            "trusted not to touch.\n"
            "\n"
            f"REQUIRED ACTION: {instead}\n"
            "\n"
            "If the gate is genuinely misfiring, that is the HUMAN's call and "
            "the kill-switches are their lever "
            "(CT6_COMPLETION_LOCK_DISABLED / CT6_TASK_LIST_GATE_DISABLED / "
            "CT6_ASK_LEDGER_GATE_DISABLED / CT6_TURN_OUTPUT_GATE_DISABLED) — "
            "never an agent rewriting the record."
        )
        return 2, message

    # v3.44.0 deploy-config immutability — fires UNCONDITIONALLY (before the
    # pipeline-state gate below), because an agent editing/disabling the deploy
    # config is a violation whether or not a pipeline run is active. Only a human
    # may change it once it exists.
    if _targets_existing_deploy_config(file_path):
        message = (
            "CT6 v3.44.0 PreToolUse guardrail BLOCKED — deploy config immutability.\n"
            "\n"
            f"  - tool about to fire: {tool}\n"
            f"  - target file: {file_path}\n"
            "\n"
            f"'{_DEPLOY_CONFIG_FILENAME}' is a HUMAN-AUTHORED opt-in for the "
            "dev -> test-on-dev -> prod discipline. Once it exists it is IMMUTABLE "
            "to agents: the pipeline and every subagent may READ it but may NEVER "
            "edit, disable, delete, or overwrite it on their own initiative.\n"
            "\n"
            "REQUIRED ACTION: do NOT modify this file. If the prod-deploy policy "
            "must change, the HUMAN edits it themselves (or passes --no-prod / "
            "'don't touch prod' for a single run). An agent deciding to disable or "
            "skip the prod mandate is exactly the buck-the-command override this "
            "guard forbids."
        )
        return 2, message

    if _is_allowed_path(file_path):
        return 0, ""

    # Resolve workspace. Prefer payload-provided workspace; fall back to cwd
    # and walk up looking for `.architect-team/`.
    workspace_hint = payload.get("workspace") or payload.get("cwd")
    start = Path(workspace_hint) if workspace_hint else Path.cwd()
    workspace = _find_workspace(start)
    if workspace is None:
        return 0, ""

    intake = _read_intake_state(workspace)
    if intake is None:
        return 0, ""

    status = (intake.get("status") or "").strip().lower()
    phase = intake.get("phase")
    try:
        phase_int = int(phase) if phase is not None else 99
    except (TypeError, ValueError):
        phase_int = 99

    if status != "in_progress":
        return 0, ""
    if phase_int >= 8:
        return 0, ""

    run_id = intake.get("run_id") or intake.get("runId")
    if _ledger_has_pipeline_skill_invocation(workspace, run_id):
        return 0, ""  # Pipeline IS invoked; the edit is part of the pipeline's work

    # Active pipeline + no Skill invocation + source-file edit = unilateral bypass
    message = (
        "CT6 v3.0.0 PreToolUse guardrail BLOCKED — pipeline-bypass detected.\n"
        "\n"
        f"  - active pipeline run: {run_id!r}\n"
        f"  - current phase: {phase!r}\n"
        f"  - tool about to fire: {tool}\n"
        f"  - target file: {file_path}\n"
        f"  - no Skill(pipeline) invocation found in toolcall ledger\n"
        "\n"
        "REQUIRED ACTION — choose one:\n"
        "\n"
        "  (a) Invoke the pipeline Skill first:\n"
        "      Skill(skill='architect-team-pipeline')  [or bug-fix-pipeline / "
        "mini-architect-team-pipeline / ux-test-builder]\n"
        "\n"
        "  (b) Explicitly disclose the bypass to the user BEFORE editing:\n"
        "      'I am not invoking the pipeline because [verbatim user "
        "authorization]. Want the full pipeline? Reply \"use the pipeline\".'\n"
        "\n"
        "Silent bypass is forbidden under v2.22.0 + v3.0.0 unilateral-override "
        "discipline. The post-hoc virtuous confession ('I owe you a straight "
        "answer', 'I should be straight about that', 'the honest framing is') "
        "is NOT an acceptable substitute for pre-action disclosure."
    )
    return 2, message


def main(argv: list[str] | None = None) -> int:
    """Read PreToolUse payload from stdin, run the check, write any stderr,
    return the exit code."""
    try:
        if not sys.stdin.isatty():
            stdin_text = _read_stdin_utf8()
        else:
            stdin_text = ""
    except (OSError, ValueError):
        stdin_text = ""

    payload: dict[str, Any] = {}
    if stdin_text.strip():
        try:
            parsed = json.loads(stdin_text)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass

    exit_code, message = check_payload(payload)
    if message:
        print(message, file=sys.stderr)
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
