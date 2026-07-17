#!/usr/bin/env python3
"""SessionStart hook — run-continuity resume directive (v3.30.0).

Fires on every session start (`startup` / `resume` / `clear` / `compact`
sources). When the workspace's `.architect-team/active-run.json` marker says a
pipeline run is ACTIVE (see hooks/run_continuity.py), this hook injects a
short directive into the session's context: re-invoke the run-driving Skill
FIRST, then continue the run — do not solve by hand.

This is the PROACTIVE half of the v3.30.0 run-continuity pair (the sticky arm
in hooks/pretool_skill_gate.py is the enforcement half): a resumed session, a
fresh session opened in a mid-run workspace, and — critically — the same
session right after a context compaction (`source: "compact"`, where the
pipeline playbook text has just been dropped from context) all get told,
before their first action, that a run is in flight and how to resume it.

Output contract: plain stdout on exit 0 is added to the session context (the
documented SessionStart behaviour). No marker / inactive marker / kill-switch
/ ANY error => print nothing, exit 0. This hook never blocks anything.

v3.39.0 adds the MODEL-SPLIT SELF-HEAL: a plugin update ships uniform-fable
agent files into a fresh cache dir, silently reverting an applied codex role
split. When the gateway state (`~/.architect-team/gateway/gateway.json`) says
the split is the desired policy (activated + api-key + a split model_policy —
the v3.40 `secondary-split` or the legacy `codex-split`) and THIS hook is
running from an INSTALLED plugin copy (under ~/.claude/plugins/ — a dev
checkout is never rewritten) whose agents/ has drifted off the split, the
hook re-applies it via the model lever and notes the heal in the session
context. Fail-open everywhere.

v3.40.0 (ADV3-1, heal-to-recorded-alias): the heal restores the split to the
alias the gateway STATE records as served (`secondary_alias`, falling back to
the legacy `codex_alias`) — it never writes an alias the running gateway
config doesn't route. A legacy install therefore keeps its working
codex-5.6-sol split after a plugin update; migration to the neutral alias
happens at install time (any `install`, --activate or not, migrates an
on-disk legacy split in the same run it regenerates the config — ADV3B-1).
No recorded alias => no-op (never guess); recorded values are
whitespace-trimmed before the truthiness check (ADV3B-2), so a corrupt
whitespace-only alias reads as absent.

Stdlib-only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

# Dual-form import per house convention (package shape, then bare-module).
try:  # pragma: no cover - exercised by both import paths
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module fallback
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]


def _read_stdin_utf8() -> str:
    """Raw-bytes UTF-8 payload read (cp1252-safe; the A8 pattern)."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


def build_directive(payload: dict) -> str:
    """The resume directive for this payload, or "" when nothing applies.

    Pure function — safe to call from tests with any payload shape."""
    if _rc is None or _rc.continuity_disabled():
        return ""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd.strip():
        return ""
    marker = _rc.read_marker(cwd)
    if not isinstance(marker, dict) or marker.get("status") != "active":
        return ""
    skill = marker.get("skill") or "architect-team-pipeline"
    slug = marker.get("slug") or marker.get("run_id") or "(unnamed)"
    phase = marker.get("phase") or "(unknown)"
    started = marker.get("started_at") or "(unknown)"
    source = str(payload.get("source") or "")
    hooks_dir = Path(__file__).resolve().parent
    if _rc.marker_is_stale(marker):
        # An abandoned run's marker no longer gates anything (the sticky arm
        # and Stop guard stand down on staleness) — inform, don't direct.
        return (
            "[CT6 run-continuity] A STALE active-run marker was found in this "
            f"workspace: slug={slug} phase={phase} skill={skill} "
            f"last-activity={marker.get('updated_at') or '(unknown)'}. It no "
            "longer gates any tools. If the run should RESUME, invoke "
            f"Skill(skill=\"{skill}\"); if it was abandoned, clear the marker: "
            f"python \"{hooks_dir / 'run_continuity.py'}\" --stand-down "
            "\"<why>\" (or --mark-complete if it actually finished)."
        )
    compact_note = (
        "Your context was just COMPACTED - the pipeline playbook text is no "
        "longer in context. "
    ) if source == "compact" else ""
    return (
        "[CT6 run-continuity] An architect-team run is ACTIVE and incomplete "
        f"in this workspace: slug={slug} phase={phase} skill={skill} "
        f"started={started}.\n"
        f"{compact_note}"
        f"REQUIRED: invoke Skill(skill=\"{skill}\") as your FIRST action - "
        "before any build/dispatch tool - to load the pipeline playbook, then "
        "resume the run from its recorded state and drive it to completion "
        "(the PreToolUse run-continuity gate enforces this; the Stop-hook "
        "continuation guard keeps the run working until it is marked "
        "complete). Do NOT solve the run's work by hand and do NOT ask the "
        "user whether to continue.\n"
        "Exceptions: if the USER explicitly directs work outside the "
        "pipeline, record it via\n"
        f"    python \"{hooks_dir / 'run_continuity.py'}\" --stand-down \"<the user's words>\"\n"
        "If this session is a CT6 pipeline TEAMMATE (your first message is a "
        "spawn brief / carries the CT6-TEAMMATE token), IGNORE this notice "
        "and execute your brief."
    )


# Model-policy strings that mean "the split is desired". These mirror the
# lever's POLICY_SECONDARY_SPLIT / LEGACY_POLICY_CODEX_SPLIT constants; the
# hook keeps a LOCAL copy (guarded fallback) because the lever lives in the
# plugin copy and is loaded dynamically only AFTER this cheap state check —
# fail-open must not depend on that load succeeding.
_SPLIT_POLICY_STRINGS = ("secondary-split", "codex-split")


def maybe_heal_model_split(
    plugin_root: Path | None = None,
    plugins_base: Path | None = None,
    gateway_state_path: Path | None = None,
) -> str:
    """Re-apply the secondary role split to THIS installed plugin copy when the
    gateway state says it is the desired policy (v3.39.0), returning a one-line
    note for the session context ("" when nothing applies).

    Guards, in order: the hook must be running from an INSTALLED plugin copy
    (under ~/.claude/plugins/ — a dev checkout is NEVER rewritten); the gateway
    state must record activated + api-key + a split model_policy; the state
    must RECORD a served alias (ADV3-1: the heal writes only the alias the
    recorded config routes — `secondary_alias`, else the legacy `codex_alias`,
    else no-op); the plugin's agents/ must exist and have drifted off that
    alias's split. Every failure path returns "" — this can never wedge a
    session start."""
    try:
        root = Path(plugin_root) if plugin_root \
            else Path(__file__).resolve().parent.parent
        base = Path(plugins_base) if plugins_base \
            else Path.home() / ".claude" / "plugins"
        try:
            root.relative_to(base)
        except ValueError:
            return ""  # dev checkout / anywhere else — never rewritten
        state_path = Path(gateway_state_path) if gateway_state_path else (
            Path(os.environ.get("CT6_GATEWAY_HOME")
                 or Path.home() / ".architect-team" / "gateway") / "gateway.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not (isinstance(state, dict)
                and state.get("activated")
                and state.get("auth_mode") == "api-key"
                and state.get("model_policy") in _SPLIT_POLICY_STRINGS):
            return ""
        # ADV3-1 (heal-to-recorded-alias): restore the split to the alias the
        # gateway STATE records as served — never write an alias the running
        # config doesn't route. v3.40 installs record `secondary_alias`; a
        # legacy (v3.39) state records only `codex_alias`, and its config.yaml
        # routes ONLY that alias, so the heal RETAINS it (migration to the
        # neutral alias happens at install time, which regenerates the
        # config). No recorded alias at all => never guess: fail-open no-op.
        # ADV3B-2: each candidate is trimmed BEFORE the truthiness check, so a
        # corrupt whitespace-only `secondary_alias` never masks a valid legacy
        # `codex_alias` (an all-whitespace record still reads as absent).
        alias = ""
        for key in ("secondary_alias", "codex_alias"):
            value = state.get(key)
            if isinstance(value, str) and value.strip():
                alias = value.strip()
                break
        if not alias:
            return ""
        agents_dir = root / "agents"
        lever_path = root / "scripts" / "setup" / "set_default_model.py"
        if not agents_dir.is_dir() or not lever_path.is_file():
            return ""
        spec = importlib.util.spec_from_file_location("ct6_heal_lever", lever_path)
        if spec is None or spec.loader is None:
            return ""
        lever = importlib.util.module_from_spec(spec)
        sys.modules["ct6_heal_lever"] = lever
        spec.loader.exec_module(lever)
        changed = lever.apply_split(agents_dir, alias)
        if not changed:
            return ""  # agents already match the recorded alias — silent no-op
        neutral = getattr(lever, "SECONDARY_ALIAS", alias)
        legacy_tail = "" if alias == neutral else (
            " The RECORDED legacy alias was retained (the running gateway "
            "config routes only that alias); re-run `python scripts/setup/"
            f"install_gateway.py install --activate` to migrate to {neutral} "
            "with a regenerated config."
        )
        return (
            "[CT6 model-split self-heal] The installed plugin copy had drifted "
            "off the secondary role split; re-applied it from the recorded "
            f"gateway state: {len(changed)} agent file(s) rewritten in "
            f"{agents_dir} (dev/checking/testing agents -> {alias})."
            + legacy_tail
        )
    except Exception:  # fail open — never wedge a session start on a bug here
        return ""


def main() -> int:
    try:
        raw = _read_stdin_utf8() if not sys.stdin.isatty() else ""
    except (OSError, ValueError):
        raw = ""
    payload: dict = {}
    if raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                payload = parsed
        except json.JSONDecodeError:
            pass
    try:
        directive = build_directive(payload)
    except Exception:  # fail open — never wedge a session start on a bug here
        directive = ""
    heal_note = maybe_heal_model_split()
    for line in (directive, heal_note):
        if line:
            print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
