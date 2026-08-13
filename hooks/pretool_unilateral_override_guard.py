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
import os
import sys
import pathlib
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
_RUN_MARKER_FILENAME = "active-run.json"

# v3.60.0 (S-1, adversarial) — the settings files are the MASTER KEY, and were
# the largest hole in the whole gate. Measured: the guard refused the ledger, the
# marker and the task store while permitting `.claude/settings.json`,
# `.claude/settings.local.json` and `~/.claude/settings.json` — Write and Edit
# both exit 0.
#
# That matters because the `env` block reaches spawned processes, which is not a
# theory: `~/.claude/settings.json` on this machine carries
# CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS and the session that found this was in
# Agent Teams mode BECAUSE of it. So one Write sets any kill-switch, and from a
# baseline where the lock was firing, `CT6_COMPLETION_LOCK_DISABLED`,
# `CT6_UNREGISTERED_RUN_GATE_DISABLED` and `CT6_RUN_CONTINUITY_DISABLED` each
# released the stop to exit 0.
#
# Worse if Claude Code does not re-read settings mid-session: the effect is then
# PERSISTENT, disarming the lock for every later session in every project — the
# quietest possible failure.
#
# Refused UNCONDITIONALLY, on the same footing as the v3.44.0 deploy config: a
# human may edit these, an agent may not. The parent-directory requirement keeps
# it from becoming a filename ban — a fixture called `settings.json` in a source
# tree is ordinary work.
_SETTINGS_DIRNAME = ".claude"
_SETTINGS_FILENAMES = frozenset({"settings.json", "settings.local.json"})

# v3.60.0 (H1) — the MANAGED settings file is the HIGHEST-precedence env carrier,
# above user and project. It was allowed. The directory does not exist on this
# machine but is creatable WITHOUT elevation, so "absent" is not "unreachable".
# Matched by full path rather than by parent-dir, since its home is not `.claude`.
_MANAGED_SETTINGS_PATHS: tuple[pathlib.Path, ...] = tuple(
    pathlib.Path(p) for p in (
        r"C:/ProgramData/ClaudeCode/managed-settings.json",
        "/Library/Application Support/ClaudeCode/managed-settings.json",
        "/etc/claude-code/managed-settings.json",
    )
)


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


def _default_tasks_root() -> Path | None:
    """The REAL harness task store, resolved WITHOUT consulting the environment.

    N3 (adversarial): `_harness_tasks_root()` goes through the substrate's own
    resolver, and that resolver honours `CT6_TASKS_ROOT`. So ONE environment
    variable relocated both the gate's ground truth AND the guard protecting it
    — pointed at a decoy, the guard faithfully protected an empty directory
    while the store the lock reads stayed writable.

    A guard may never derive its protected set from the value under attack.
    This is the fixed half of the pair: the real default, always.
    """
    try:
        return (Path.home() / ".claude" / "tasks").resolve()
    except Exception:
        return None


def _harness_tasks_roots() -> tuple[Path, ...]:
    """Every task root the guard PROTECTS — the UNION, not a choice.

    The real default root is always in the set; whatever `CT6_TASKS_ROOT` names
    is ADDED to it, because that override is the suite's test seam and a
    legitimate operator lever, so it has to keep working. The asymmetry is the
    entire fix: an environment variable may add to the protected set, it may
    never remove the real store from it. Protecting the union is strictly safer
    than protecting either root alone.
    """
    roots: list[Path] = []
    for root in (_default_tasks_root(), _harness_tasks_root()):
        if root is not None and root not in roots:
            roots.append(root)
    return tuple(roots)


# --- N2b: identity, not spelling ---------------------------------------------
#
# `Path.resolve()` collapses SPELLINGS of one path — case folding, `..`
# traversal, symlinks, junctions — which is what closed F-B. A hardlink is not a
# spelling: it is a second real directory entry for the same bytes, with no
# "true" name to resolve to, so `resolve()` hands back the alias's own path and
# every name-based arm sees an unrelated file. `notes/evil.json` hardlinked onto
# the ask-ledger writes the ledger.
#
# `(st_dev, st_ino)` is what a file IS rather than what it is called, so it
# catches the alias under any name. Everything below fails SAFE: a stat that
# cannot answer yields None, a None identity matches nothing, and this arm can
# therefore only ever ADD a block — never remove one and never raise. A guard
# that crashes is a guard that is not there, since PreToolUse treats exit 1 as
# non-blocking.

#: Hard ceiling on the task-store identity scan. Only ever reached when the
#: write target genuinely carries more than one name, which no ordinary write
#: does — see `_may_be_a_link_alias`.
_IDENTITY_SCAN_CAP = 4096


def _file_identity(path: Path) -> tuple[int, int] | None:
    """``(st_dev, st_ino)`` for an existing path, or None when unavailable.

    None for a path that does not exist — the common case for `Write`, and the
    one `os.stat` raises on — for any stat failure, and for the ``st_ino == 0``
    sentinel some filesystems report, which would otherwise make every
    identity-less file compare equal to every other.
    """
    try:
        st = os.stat(path)
        dev = int(getattr(st, "st_dev", 0) or 0)
        ino = int(getattr(st, "st_ino", 0) or 0)
    except Exception:
        return None
    if not ino:
        return None
    return (dev, ino)


def _may_be_a_link_alias(path: Path) -> bool:
    """True when `path` could be a second name for some other file.

    `st_nlink == 1` means exactly one directory entry points at these bytes, so
    the path cannot be an alias for anything and the scan below is skipped —
    that is every ordinary write, which is what keeps this arm free in the case
    that matters. A missing or zero `st_nlink` means "cannot tell", and
    cannot-tell runs the check: unknown state is not "safe". A nonexistent file
    is the one honest False — there are no bytes for it to be a second name for.
    """
    try:
        st = os.stat(path)
    except Exception:
        return False
    try:
        return int(getattr(st, "st_nlink", 0) or 0) != 1
    except Exception:
        return True


def _ledger_identity_candidates(target: Path) -> list[Path]:
    """Canonical ask-ledgers this write could be a second name for.

    A hardlink must live on the same volume as its target, so a realistic alias
    sits inside or beside the workspace that owns the ledger: walk the target's
    own ancestors, then the cwd's, for `<dir>/.architect-team/ask-ledger.json`.
    Bounded by path depth, and only ever reached for a multiply-named file.
    """
    starts: list[Path] = []
    try:
        starts.append(target.resolve().parent)
    except Exception:
        pass
    try:
        starts.append(Path.cwd().resolve())
    except Exception:
        pass

    out: list[Path] = []
    seen: set[str] = set()
    for start in starts:
        for directory in (start, *start.parents):
            ledger = directory / _STATE_DIRNAME / _ASK_LEDGER_FILENAME
            key = str(ledger).casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(ledger)
    return out


def _settings_identity_candidates(target: Path) -> list[Path]:
    """Settings files this write could be a second name for (H1).

    A hardlink must live on the same volume as its target, so the realistic
    aliases are the settings files of the workspaces above this path plus the
    user-level and machine-level ones. Same shape as
    `_ledger_identity_candidates`; bounded by path depth.
    """
    starts: list[Path] = []
    for getter in (lambda: target.resolve().parent, lambda: Path.cwd().resolve()):
        try:
            starts.append(getter())
        except Exception:
            pass
    dirs: list[Path] = []
    for start in starts:
        dirs.extend([start, *start.parents])
    try:
        dirs.append(Path.home())
    except Exception:
        pass
    # v3.60.0 (R3/R4) — SIBLING workspaces. The ancestor walk missed them, and
    # that is not an exotic gap for CT6: run worktrees land at
    # `<parent-of-repo>/<repo-name>-<slug>/`, so a run worktree and the main
    # checkout are siblings BY DESIGN. An agent in a worktree could hardlink to
    # the main checkout's settings and poison the env for the next run there.
    # Measured before the fix: `projA/.claude/settings.json` was absent from all
    # 21 candidates generated from `projB`.
    #
    # Bounded deliberately — only directories that ALREADY look like a workspace
    # (they carry a `.claude/`), and only one level out from each ancestor, so
    # this is a directory listing of a handful of parents rather than a volume
    # scan.
    siblings: list[Path] = []
    for directory in list(dirs):
        try:
            if not directory.is_dir():
                continue
            for entry in directory.iterdir():
                if len(siblings) >= _IDENTITY_SCAN_CAP:
                    break
                if entry.is_dir() and (entry / _SETTINGS_DIRNAME).is_dir():
                    siblings.append(entry)
        except Exception:
            continue
    dirs.extend(siblings)

    out: list[Path] = []
    seen: set[str] = set()
    for directory in dirs:
        for name in sorted(_SETTINGS_FILENAMES):
            candidate = directory / _SETTINGS_DIRNAME / name
            key = str(candidate).casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
    for extra in _MANAGED_SETTINGS_PATHS:
        key = str(extra).casefold()
        if key not in seen:
            seen.add(key)
            out.append(extra)
    return out


def _task_store_identity_candidates(roots: tuple[Path, ...]) -> list[Path]:
    """Files under the protected task roots, in the harness's own layout.

    The store is `<root>/session-<8-of-session-id>/<taskId>.json` (see
    `hooks/open_work.py::read_harness_tasks`), so two shallow globs cover it
    without an unbounded walk, and `_IDENTITY_SCAN_CAP` bounds even a
    pathological root.
    """
    out: list[Path] = []
    for root in roots:
        try:
            if not root.is_dir():
                continue
        except Exception:
            continue
        for pattern in ("*", "*/*"):
            try:
                for entry in root.glob(pattern):
                    out.append(entry)
                    if len(out) >= _IDENTITY_SCAN_CAP:
                        return out
            except Exception:
                continue
    return out


def _targets_completion_lock_ground_truth(file_path: str) -> str | None:
    """The ground-truth source this write targets, or None.

    Returns a short label naming WHICH source, so the block message can be
    specific about what the agent was about to overwrite.

    Both arms RESOLVE before matching (F-B, independent review). The first cut
    of the ask-ledger arm compared `p.name` / `p.parent.name` as raw strings
    while its harness-task-store sibling resolved — an inconsistency inside one
    function, and two confirmed one-Write bypasses on the platform this repo is
    developed on:

      .ARCHITECT-TEAM\\ASK-LEDGER.JSON            (NTFS is case-insensitive)
      .architect-team\\reviews\\..\\ask-ledger.json  (traversal re-entry)
      a junction or hardlink to either                (mklink /J needs no admin)

    Each reached the SAME real file and returned exit 0 where the canonical
    spelling returned 2. The tests only ever exercised the canonical spelling,
    which is how it survived. Resolution collapses all of them: `Path.resolve()`
    canonicalizes case on Windows, normalizes `..`, and follows links.
    """
    if not isinstance(file_path, str) or not file_path:
        return None
    try:
        p = Path(file_path)
    except (TypeError, ValueError):
        return None
    try:
        resolved: Path | None = p.resolve()
    except Exception:
        resolved = None

    # The ask-ledger. Match the RESOLVED path so case, `..` and links cannot
    # spell around it; keep the `.architect-team/` parent requirement so an
    # unrelated file sharing the basename is still not caught.
    for candidate in (resolved, p):
        if candidate is None:
            continue
        try:
            name = candidate.name.casefold()
            same_parent = candidate.parent.name.casefold() == _STATE_DIRNAME.casefold()
        except Exception:
            continue
        if not same_parent:
            continue
        if name == _ASK_LEDGER_FILENAME.casefold():
            return "ask-ledger"
        # v3.60.0 — the run marker is ground truth too, and was left out. The
        # v3.57.0 unregistered-run arm triggers on an ACTIVE marker, so editing
        # or blanking this file disarms it; the arm's own report named the gap
        # and an independent check confirmed the guard returned None for it.
        # Protecting it closes the edit-the-marker and corrupt-the-marker
        # routes on the Edit/Write/NotebookEdit surface.
        #
        # HONEST BOUNDARY, unchanged: `Bash` can still remove the file. This
        # raises the cost and makes it a deliberate act; it does not make it
        # impossible, and no hook tier can.
        if name == _RUN_MARKER_FILENAME.casefold():
            return "run-marker"

    # v3.60.0 (S-1) — the settings files, under `.claude/` rather than the state
    # dir, so they need their own parent check.
    for candidate in (resolved, p):
        if candidate is None:
            continue
        try:
            if (candidate.name.casefold() in _SETTINGS_FILENAMES
                    and candidate.parent.name.casefold() == _SETTINGS_DIRNAME):
                return "settings"
            cf = str(candidate).replace("\\", "/").casefold()
            if any(cf == str(m).replace("\\", "/").casefold()
                   for m in _MANAGED_SETTINGS_PATHS):
                return "settings"
        except Exception:
            continue

    # Any path under the harness task store. The UNION of roots (N3), never the
    # single value `CT6_TASKS_ROOT` happens to name — see `_harness_tasks_roots`.
    roots = _harness_tasks_roots()
    if resolved is not None:
        for root in roots:
            try:
                resolved.relative_to(root)
                return "harness-task-store"
            except ValueError:
                continue
            except Exception:
                continue

    # N2b — identity, not spelling. Only reached for a path that genuinely
    # carries more than one name, so an ordinary write pays one `os.stat`.
    target = resolved if resolved is not None else p
    if _may_be_a_link_alias(target):
        identity = _file_identity(target)
        if identity is not None:
            for candidate in _ledger_identity_candidates(target):
                if _file_identity(candidate) == identity:
                    return "ask-ledger"
            for candidate in _task_store_identity_candidates(roots):
                if _file_identity(candidate) == identity:
                    return "harness-task-store"
            # v3.60.0 (H1) — settings were added to the PATH arm and left out of
            # the IDENTITY arm, which defeated the whole guard: `mklink /H`
            # needs no admin on Windows, and a hardlink has no link to follow,
            # so resolution cannot see it. Proven end to end — a write to an
            # innocuous filename changed settings.json's env block through the
            # shared inode. This is N2b, already solved for the ledger and the
            # task store, simply not extended here.
            for candidate in _settings_identity_candidates(target):
                if _file_identity(candidate) == identity:
                    return "settings"
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
        elif _ground_truth == "settings":
            what = (
                "a Claude Code settings file — the MASTER KEY to every gate in "
                "this plugin. Its `env` block is exported to spawned processes, "
                "so one write sets any kill-switch and disarms the completion "
                "lock, the run-continuity guard, and the marker staleness "
                "window at once. If settings are not re-read mid-session the "
                "effect is worse, not better: it persists into every later "
                "session in every project"
            )
            instead = (
                "Ask the human to make the change. Every kill-switch is "
                "deliberately the operator's lever and not the agent's, and a "
                "session that can set its own switches is not gated at all. "
                "This is the same rule the human-authored deploy config "
                "already carries."
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
            "CT6_ASK_LEDGER_GATE_DISABLED / CT6_TURN_OUTPUT_GATE_DISABLED / "
            "CT6_UNREGISTERED_RUN_GATE_DISABLED, and CT6_RUN_MARKER_STALE_HOURS "
            "which stands the arms down by ageing the marker) — "
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
