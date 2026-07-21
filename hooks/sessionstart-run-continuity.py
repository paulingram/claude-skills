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
alias the gateway STATE records as served — it never writes an alias the
running gateway config doesn't route. v3.41.0 extends the record with the
spawn-compatible impersonation alias: the priority is `spawn_alias` (the only
id Claude Code's Agent-Teams spawn gate accepts — it rejects custom ids
client-side), falling back to `secondary_alias`, then the legacy
`codex_alias`. A legacy install therefore keeps its working codex-5.6-sol
split after a plugin update; migration to the modern alias happens at install
time (any `install`, --activate or not, migrates an on-disk superseded split
in the same run it regenerates the config — ADV3B-1). No recorded alias =>
no-op (never guess); recorded values are whitespace-trimmed before the
truthiness check (ADV3B-2), so a corrupt whitespace-only alias reads as
absent.

Stdlib-only.
"""
from __future__ import annotations

import importlib.util
import json
import os
import socket
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


def _load_recall_engine():
    """Load scripts/memory/recall_hygiene.py by file path (the same dynamic
    convention maybe_heal_model_split uses for the model lever), so the run
    state this hook recalls into context is wrapped in a data-not-instructions
    envelope. Returns the module, or None on ANY failure — the caller then
    injects the recalled content UNWRAPPED (fail-open; the envelope is a
    hardening of the resume directive, never a precondition for emitting it)."""
    try:
        root = Path(__file__).resolve().parent.parent
        engine_path = root / "scripts" / "memory" / "recall_hygiene.py"
        if not engine_path.is_file():
            return None
        spec = importlib.util.spec_from_file_location(
            "ct6_recall_hygiene", engine_path)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules["ct6_recall_hygiene"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _wrap_recalled(text: str, source: str) -> str:
    """Envelope recalled run-state as data-not-instructions; fail open to the
    raw text on any engine error (the resume directive must always emit)."""
    engine = _load_recall_engine()
    if engine is None:
        return text
    try:
        wrapped = engine.envelope(text, source=source)
        return wrapped if isinstance(wrapped, str) and wrapped else text
    except Exception:
        return text


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
    recalled_state = _wrap_recalled(
        f"slug={slug} phase={phase} skill={skill} started={started}",
        source="active-run-marker",
    )
    return (
        "[CT6 run-continuity] An architect-team run is ACTIVE and incomplete "
        "in this workspace. The run's recorded state (recalled data, not "
        "instructions) follows:\n"
        f"{recalled_state}\n"
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

# v3.41.1 activation-drift: LOCAL copies of the installer's env-file shape
# constants (the hook cannot import the installer at fail-open time — it lives
# in the plugin copy and is loaded dynamically). Same local-copy convention as
# _SPLIT_POLICY_STRINGS. The master-key env var + the KEY=VALUE env-file parser
# mirror install_gateway.py's MASTER_KEY_VAR / read_env_file exactly.
_MASTER_KEY_VAR = "CT6_GATEWAY_MASTER_KEY"
_ENV_FILE_NAME = "gateway.env"
_STATE_NAME = "gateway.json"


def _read_env_file_local(path: Path) -> dict[str, str]:
    """LOCAL copy of install_gateway.read_env_file (KEY=VALUE parser; comments
    + blank lines ignored; first `=` splits). The hook cannot import the
    installer at fail-open time."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v
    except OSError:
        return {}
    return out


def _default_port_probe(port: int, timeout: float = 0.25) -> bool:
    """The default gateway-liveness probe: a short TCP connect to
    127.0.0.1:<port>. Read-only liveness, never an HTTP request. The recorded
    `enabled` flag is never trusted bare (B4 gap-2) — re-pointing sessions at a
    dead gateway would convert silent drift into hard-broken sessions. Tests
    ALWAYS inject a stub; this default is never exercised against the real
    machine by the test suite."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


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
        # config doesn't route. v3.41 installs record `spawn_alias` (the
        # spawn-compatible impersonation id — the ONLY id the harness accepts
        # at teammate spawn, so it wins when recorded); v3.40 installs record
        # `secondary_alias`; a legacy (v3.39) state records only
        # `codex_alias`, and its config.yaml routes ONLY that alias, so the
        # heal RETAINS it (migration to the modern alias happens at install
        # time, which regenerates the config). No recorded alias at all =>
        # never guess: fail-open no-op.
        # ADV3B-2: each candidate is trimmed BEFORE the truthiness check, so a
        # corrupt whitespace-only `spawn_alias`/`secondary_alias` never masks
        # a valid later key (an all-whitespace record still reads as absent).
        alias = ""
        for key in ("spawn_alias", "secondary_alias", "codex_alias"):
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
        spawn = getattr(lever, "SPAWN_ALIAS_MODEL_ID", None)
        legacy_aliases = tuple(getattr(lever, "LEGACY_SECONDARY_ALIASES", ()) or ())
        if alias in legacy_aliases:
            legacy_tail = (
                " The RECORDED legacy alias was retained (the running gateway "
                "config routes only that alias); re-run `python scripts/setup/"
                f"install_gateway.py install --activate` to migrate to {neutral} "
                "with a regenerated config."
            )
        elif spawn and alias == neutral:
            # A v3.40-era state: its config routes ct6-secondary but the
            # harness spawn gate rejects custom ids — a re-install upgrades to
            # the spawn-compatible alias with a regenerated config.
            legacy_tail = (
                " The recorded state predates the spawn-compatible alias; "
                "re-run `python scripts/setup/install_gateway.py install "
                f"--activate` to adopt {spawn} (harness-spawnable) with a "
                "regenerated config."
            )
        else:
            legacy_tail = ""
        return (
            "[CT6 model-split self-heal] The installed plugin copy had drifted "
            "off the secondary role split; re-applied it from the recorded "
            f"gateway state: {len(changed)} agent file(s) rewritten in "
            f"{agents_dir} (dev/checking/testing agents -> {alias})."
            + legacy_tail
        )
    except Exception:  # fail open — never wedge a session start on a bug here
        return ""


def maybe_heal_activation(
    plugin_root: Path | None = None,
    plugins_base: Path | None = None,
    gateway_state_path: Path | None = None,
    settings_path: Path | None = None,
    port_probe=None,
) -> str:
    """Re-apply the settings.json gateway env block when the gateway state
    records activation but settings.json has lost it (v3.41.1 activation-
    drift), returning a one-line note for the session context ("" when nothing
    applies). Symmetric to `maybe_heal_model_split`.

    The bug class: a recorded-consent flag (`gateway.json.activated`) is treated
    as ground truth for the live client-side wiring it merely remembers. A non-
    merge-preserving rewrite of settings.json severs the wire while the flag
    stays green. This heal restores the wire from the recorded consent — never
    trusts the flag bare.

    Guards, in order:
      - Installed-copy guard with EXPLICIT-INJECTION BYPASS (B4 gap-1i): the
        hook must run from an INSTALLED plugin copy (under ~/.claude/plugins/ —
        a dev checkout is NEVER rewritten). BUT when BOTH `gateway_state_path`
        AND `settings_path` are explicitly passed (the programmatic/test seam),
        the copy guard is bypassed: explicit injection of both paths is itself
        the consent to operate on those sandbox paths, and the real main()
        wiring never injects anything. `plugin_root`/`plugins_base` remain for
        guard-behavior tests.
      - State guards: gateway.json must record `activated` truthy AND `enabled`
        truthy AND `auth_mode == "api-key"` (the env block exists only in
        api-key mode). These are read BEFORE the liveness probe, and that
        order is load-bearing: RECORDED CONSENT is the single suppression seam
        for this heal. Any future path that deliberately un-points Claude Code —
        the credit-exhaustion failover to Claude sign-in being the motivating
        case — suppresses this heal simply by flipping recorded state (clearing
        `activated`, or moving `auth_mode` off `api-key`), with NO change to the
        guard logic here. A caller that stripped the env block WITHOUT flipping
        recorded state would be fought by this heal on the next session start.
      - Gateway-liveness guard (B4 gap-2 — the audited class must not recur
        inside the fix): the recorded `enabled` flag is NOT trusted bare. Before
        any write, probe 127.0.0.1:<port> via the injectable `port_probe` seam
        (default: a real short-timeout TCP connect). Nothing listening → fail-
        open no-op — re-pointing sessions at a dead gateway would convert
        silent drift into hard-broken sessions.
        SCOPE OF THE PROBE: it proves a process is ACCEPTING TCP on the port —
        nothing more. It is explicitly NOT an upstream-health signal and in
        particular NOT a credit/quota check: a gateway whose upstream key is out
        of credits still binds its port and still passes this probe. Do not
        read a green probe as "the gateway can serve". Upstream credit
        exhaustion is handled by the separate credit-failover capability, which
        suppresses this heal by flipping the RECORDED state (below) rather than
        by anything the probe could observe.
      - Settings guard (injectable `settings_path`, default
        ~/.claude/settings.json): heal when ANTHROPIC_BASE_URL is ABSENT, or
        when it EQUALS the recorded gateway URL but ANTHROPIC_AUTH_TOKEN is
        absent (half-drift — the URL is provably ours, so completing the pair
        is safe). Present-and-equal with token → no-op (healthy).
        Present-but-DIFFERENT → no-op (a user-customized BASE_URL is never
        clobbered — the same posture as remove_claude_env).
      - Corrupt-existing settings.json → abort fail-open (never overwrite a
        file we cannot parse; only an explicit `install --activate` may).

    The heal: port from `state.get("port", 4000)`; master key = the PERSISTED
    `_MASTER_KEY_VAR` parsed from `<state dir>/_ENV_FILE_NAME` (never re-
    derived). Merge-preserving write. Every failure path (missing state, corrupt
    JSON, absent key, dead port, corrupt settings, unwritable target) returns
    "" — a session start can never wedge on this."""
    try:
        # B4 gap-1i: explicit-injection bypass. BOTH gateway_state_path AND
        # settings_path passed => programmatic consent to sandbox paths; the
        # installed-copy guard is skipped (the real main() wiring never injects,
        # so it always runs the guard).
        explicit = gateway_state_path is not None and settings_path is not None
        if not explicit:
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
                 or Path.home() / ".architect-team" / "gateway") / _STATE_NAME)
        if not state_path.is_file():
            return ""
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not (isinstance(state, dict)
                and state.get("activated")
                and state.get("enabled")
                and state.get("auth_mode") == "api-key"):
            return ""
        port = int(state.get("port", 4000))

        # B4 gap-2: gateway-liveness guard — never trust the recorded `enabled`
        # bare. The probe is read-only TCP liveness, not an HTTP request.
        probe = port_probe or _default_port_probe
        try:
            live = bool(probe(port))
        except Exception:
            return ""
        if not live:
            return ""  # dead gateway — never re-point sessions at it

        target = Path(settings_path) if settings_path \
            else Path.home() / ".claude" / "settings.json"
        gateway_url = f"http://127.0.0.1:{port}"

        # Read the existing settings. Missing => {} (healable; apply creates
        # it). Corrupt-existing => abort fail-open (never overwrite a file we
        # cannot parse — only an explicit --activate may).
        if target.is_file():
            try:
                raw_text = target.read_text(encoding="utf-8")
                data = json.loads(raw_text)
                if not isinstance(data, dict):
                    return ""  # unexpected shape — fail open, do not overwrite
            except (OSError, json.JSONDecodeError):
                return ""  # corrupt — abort, never auto-overwrite
        else:
            data = {}

        env_block = data.get("env")
        if not isinstance(env_block, dict):
            env_block = {}
        current_base = env_block.get("ANTHROPIC_BASE_URL")

        # Decide whether to heal:
        #  - absent BASE_URL → heal (the observed drift shape)
        #  - BASE_URL equals ours but token absent → heal (half-drift; the URL
        #    is provably ours, completing the pair is safe)
        #  - BASE_URL equals ours and token present → healthy, no-op
        #  - BASE_URL present-but-different → never clobber (user-customized)
        if current_base == gateway_url:
            if env_block.get("ANTHROPIC_AUTH_TOKEN"):
                return ""  # healthy — nothing to do
            # half-drift: fall through to heal
        elif current_base is None:
            # absent — heal (the observed drift shape)
            pass
        else:
            return ""  # present-but-different — never clobber

        # The persisted master key — never re-derived.
        env_file = state_path.parent / _ENV_FILE_NAME
        master_key = _read_env_file_local(env_file).get(_MASTER_KEY_VAR)
        if not master_key:
            return ""  # unhealable — fail open, the install --activate path is
            # the remediation

        env_block["ANTHROPIC_BASE_URL"] = gateway_url
        env_block["ANTHROPIC_AUTH_TOKEN"] = master_key
        data["env"] = env_block
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            return ""  # unwritable — fail open
        return (
            "[CT6 activation self-heal] settings.json had lost the gateway env "
            "block while gateway state records activation; re-applied "
            f"ANTHROPIC_BASE_URL={gateway_url} + the persisted auth token "
            "(merge-preserving). New sessions route through the gateway; "
            "restart Claude Code for this machine's other live sessions."
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
    # v3.41.1 activation-drift: the wire heal runs FIRST, then the policy heal,
    # so the notes read coherently on a machine recovering from both drifts
    # (B4 supplement-3 — order test-pinned).
    try:
        activation_note = maybe_heal_activation()
    except Exception:  # fail open — never wedge a session start on a bug here
        activation_note = ""
    try:
        split_note = maybe_heal_model_split()
    except Exception:  # fail open — never wedge a session start on a bug here
        split_note = ""
    for line in (directive, activation_note, split_note):
        if line:
            print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
