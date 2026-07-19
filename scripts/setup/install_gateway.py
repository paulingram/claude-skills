#!/usr/bin/env python3
"""install_gateway.py — the full-lifecycle installer for the CT6 external-LLM gateway.

Run from `/architect-team:architect-team-setup --external-llm` (or standalone).
Stdlib-only. Mirrors the `install_librarian.py` pattern: a step-summary printer,
`--json`, `--check-only`, and the same "never auto-register / never auto-enable
without a key" safety posture.

WHAT THIS INSTALLS: a local LiteLLM proxy (MIT-licensed, `pip install
"litellm[proxy]"`) configured so the secondary role split (v3.35.0; provider
registry v3.40.0) has a real backend — the neutral `ct6-secondary` alias
routes to the CHOSEN provider from the lever's SECONDARY_PROVIDERS registry
(OpenAI Codex 5.6 / Z.ai GLM), while Anthropic models either pass through the
same gateway (api-key mode) or keep Claude Code's native sign-in auth
(subscription mode).

PROVIDER SELECTION (v3.40.0): the secondary provider resolves through a
ladder — the `--secondary` flag > `$CT6_SECONDARY_PROVIDER` > the recorded
`gateway.json` choice > the v3.39 grandfather (an `openai_model`-only state
reads as openai) > the interactive prompt > the openai default. An unknown
name FAILS the run (it never falls through to a different provider);
`--re-ask-provider` suppresses the recorded/grandfathered choice so the
question is asked again. EVERY install — with or without `--activate` —
migrates an on-disk LEGACY split alias (`codex-5.6-sol`) to the neutral alias
the just-regenerated config routes, and CARRIES a prior activated/split state
forward: a plain re-install never silently deactivates a machine (uninstall
is the only downgrade path).

AUTH MODES (resolved, never probed against a live API):
  * ``api-key``       — an `ANTHROPIC_API_KEY` resolves (process env, gateway env
                        file, or `--anthropic-key`). The gateway fronts BOTH
                        providers: explicit Anthropic routes + a catch-all, plus
                        the `ct6-secondary` → chosen-provider route. `--activate`
                        may then point Claude Code at the gateway
                        (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` in
                        `~/.claude/settings.json`, consent-gated) and apply the
                        secondary role split via `set_default_model.py`.
  * ``subscription``  — NO Anthropic key anywhere. Fable (and every Anthropic
                        model) keeps Claude Code's native subscription sign-in —
                        `ANTHROPIC_BASE_URL` is deliberately NEVER written, since
                        rerouting subscription OAuth traffic through a local proxy
                        is not supported by the harness. The gateway still runs,
                        secondary-provider-only, for the service tier and direct
                        callers. The secondary role split stays OFF (the harness
                        cannot split-route only secondary traffic); the printed
                        remediation is to add an `ANTHROPIC_API_KEY` and re-run
                        with `--activate`.

SECRETS: keys live ONLY in `<state>/gateway.env` (chmod 0600 best-effort) and are
masked to their last 4 chars in every report. The generated `config.yaml` carries
`os.environ/...` references, never raw keys. Nothing under the repo is touched.

KEY PROMPTS (v3.38.0, ask-then-apply): an INTERACTIVE install prompts for a
missing key instead of punting to a printed remediation — hidden (getpass)
entry, degrading to visible input with a one-line warning ONLY when hidden
entry is unachievable (getpass's non-console fallback), never on an import
check. Interactivity is the `--interactive-prompts` flag, set only by
interactive callers: `main()` on a real TTY without `--json`/`--check-only`,
or `setup_entry(assume_yes=False, check_only=False)` on a TTY. A blank entry
skips (today's absent-key path runs verbatim) and records the slot in
`<state>/key-declines.json` (via=prompt-skip); the `decline` subcommand is the
wrapper flow's deterministic record channel (via=wrapper). A recorded decline
suppresses the PROMPT on re-runs — never the `status` truth — auto-resets the
moment that slot's key resolves on any path, and `--re-ask-keys` clears it so
prompts fire again. Non-interactive, non-TTY, `--check-only`, and `--json`
runs never prompt, never block, never invent a key.

Subcommands:
  install (default)  Provision state + config + env file + launcher + the per-OS
                     boot descriptor, install `litellm[proxy]` through setup.py's
                     PEP-668-aware ladder, and (v3.37.0) REGISTER + START the
                     gateway itself — user-level (schtasks onlogon / `systemctl
                     --user` / LaunchAgents), never sudo/admin; `--no-register`
                     opts back to the printed hint. Enabled ONLY when the chosen
                     secondary provider's key resolves; otherwise
                     install-but-disabled (registration deferred) with an
                     explicit remediation.
  status             Report auth mode / provider / keys (masked) / litellm
                     presence / file layout / registration / activation + the
                     agents' model policy state. With `--live`, probe the
                     RUNNING gateway for the STATE-RECORDED alias
                     (`secondary_alias`, falling back to the legacy
                     `codex_alias`) — a working legacy v3.39 install probes
                     green.
  uninstall          Deactivate (remove OUR settings.json env keys, restore the
                     uniform-fable model state if the secondary split is
                     applied), stop + UNREGISTER the gateway, remove the boot
                     descriptor. With `--purge`, remove state too (incl.
                     key-declines.json).
  decline            Record (or `--clear`) a per-key decline —
                     `decline <anthropic|openai|zai>` — the wrapper flow's
                     deterministic channel for an explicit "don't ask again".

Flags:
  --base-dir PATH     State dir (default: $CT6_GATEWAY_HOME, else
                      ~/.architect-team/gateway/).
  --secondary NAME    Secondary provider from the SECONDARY_PROVIDERS registry
                      (openai|zai); see the resolution ladder above.
  --secondary-model ID  Upstream model id override for the chosen provider
                      (default: the registry entry's model, e.g. gpt-5.6-sol).
  --<provider>-key KEY  One flag per registry provider (--openai-key /
                      --zai-key): store that provider's key in gateway.env
                      (else its key_env in the process env, else an existing
                      gateway.env entry).
  --anthropic-key KEY Store an Anthropic key in gateway.env (opts into api-key mode).
  --openai-model ID   Deprecated synonym for `--secondary-model` with
                      `--secondary openai`.
  --port N            Gateway port (default: 4000).
  --activate          api-key mode only: write the Claude Code env block to
                      settings.json AND apply the secondary role split. In
                      subscription mode this degrades to an honest note.
  --settings-path P   Claude settings.json location (tests inject a tmp path).
  --agents-dir P      agents/ dir for the model split (tests inject a tmp dir).
  --no-install        Skip the pip install (state-only provisioning).
  --no-register       Skip the automatic boot registration (print the hint).
  --interactive-prompts  Allow the interactive missing-key prompt (set only by
                      interactive callers; never under --check-only/--json).
  --re-ask-keys       Clear the recorded key declines so prompts fire again.
  --re-ask-provider   Ignore the recorded/grandfathered provider choice and
                      resolve it again.
  --check-only        Report intent only; provision nothing.
  --live              (status) probe the RUNNING gateway's /v1/models and
                      confirm it serves what the mode needs.
  --json              Machine-readable JSON report.
  --purge             (uninstall) also remove the state dir.

Exit codes: 0 success; 1 a real failure (actionable message).

HONEST BOUNDARY: registration is EXECUTED by default (v3.37.0 owner directive —
the enable signal is the consent; user-level only, never sudo/admin; a failure
degrades to a fail step + the manual hint). Model availability stays an INPUT
(the resolve_model convention): activation applies the split because YOU
asserted the backend exists by enabling external-LLM usage — nothing here
probes a live API to DECIDE anything. v3.39.0 adds the post-install live
CONFIRMATION (the step the v3.38.1 field bug proved necessary): after a
registered install the installer polls the LOCAL gateway's /v1/models and
asserts the split's ids are actually served — verifying what was just
installed, never deciding policy from a probe. v3.41.0 upgrades the probe to
the hop callers actually use: a bounded /v1/messages COMPLETION (spawn alias
first, neutral-alias fallback) must return a non-empty content block before
anything reports CONFIRMED — the /v1/models-only check was how a broken
completion hop shipped as "CONFIRMED live" (the wrong-hop bug). Iteration 2
(SR-glm-fix-iter2) closes the two residual wrong-hop members the first deploy
exposed: a config-REgenerating install now RESTARTS a running gateway before
confirming (register/start is start-if-not-running, so a stale process kept
serving the prior config), and the completion probe verifies the serving
DEPLOYMENT — the response's x-litellm-model-id is resolved via GET /model/info
and must map to the registry-derived dialect route, so a completion answered
by the anthropic/* wildcard's dynamically-instantiated real-Haiku deployment
FAILS with the observed upstream named, instead of silently billing Anthropic
while reporting the split live. Iteration 3 (SR-glm-fix-iter3) closes the two
escapes the SECOND deploy exposed: the confirm is now SPAWN-ALIAS-MANDATORY —
when the state records a spawn alias, the completion + identity probe runs ON
that alias and its failure FAILS the confirm (the ct6-secondary fallback green
survives only for legacy states with no recorded spawn alias) — and staleness
is judged against the SERVED state, not the prior file: the generated config's
model-group set and the secondary/spawn routes' expected upstreams are compared
against GET /model/info, so a file-current-process-stale gateway (the state a
byte diff can never see — iteration 1 had already regenerated the file while
the pre-deploy process kept serving the older config) restarts before the
confirm. Iteration 4 (SR-glm-fix-iter4) makes the restart itself honest: the
third deploy detected the staleness and failed closed exactly as designed,
but the "restart" was a no-op — the port was held by an UNTRACKED process
(a manually-started diagnostic instance) the tracked stop never touches, and
each blocked start leaked a doomed instance. A restart carrying the
verification context now STOPS BY PORT (only after the tracked stop fails to
free the gateway's own configured port: resolve the LISTENING pid — netstat
on Windows, lsof elsewhere — and stop THAT pid, image-agnostic by design,
with the resolved pid+image named honestly on success AND on refusal) and
VERIFIES THE BIND (reports restarted only after the new instance answers
/model/info with a state matching the generated config — a still-held port
is a named failure after at most ONE start attempt, never a doomed-instance
spawn loop). Iteration 5 (SR-glm-fix-iter5, the user mandate "make sure that
never happens on install") closes the process-population escapes the FOURTH
deploy's aftermath exposed — 8 accumulated instances (~12 GB), an env-broken
zombie stealing the port in the post-kill race window, state-match bind-verify
passing on it (same config file) while every real-token request failed into
LiteLLM's no-DB 400/500 path: (11a) EXACTLY-ONE-INSTANCE — before its single
start, install stops EVERY process whose cmdline carries THIS state dir's
config path (an ownership PROOF: every generated launcher passes
``--config <state>/config.yaml``; image- and launcher-agnostic; Windows
cmdlines are normalized for case, separators, and 8.3 short names before
matching), and the register step never blind-starts over a held port (the
``schtasks /run``-every-install blind start was the accumulation source);
(11b) START-OWNERSHIP — after the one start, the port-holding pid must BE the
instance the restart just launched (per-launcher pid resolution: systemd
MainPID / launchctl print; pid-opaque launchers use the owned-instance
launch-window match), so a zombie winning the bind race is a NAMED failure,
never silent service; (11c) AUTH ENFORCEMENT — the confirm sends a
deliberately-invalid key (random, never echoed) and REQUIRES that it be
DENIED service: a 4xx is clean enforcement; a crash-5xx is enforcement with
a NAMED WARNING (the LiteLLM no-DB prisma quirk — every healthy DB-less
gateway answers this way, so confirm proceeds, warning carried in the
detail); only a 200 (service granted — the env-broken-zombie state) FAILS
the confirm, and the rung fires only after a passed completion, so a down
gateway can never surface the 5xx-warn green; and
(11d) the master key NEVER rotates on a re-install (pinned — rotation would
invalidate the settings.json auth token every live session depends on).
Iteration 6 (SR-glm-fix-iter6, the 2026-07-18 OFFLINE incident: every deploy
was stop-then-start on the LIVE port every active Claude session routes
through — a dark window and a port race per deploy — and the winner among 8
piled-up instances had an UNRESOLVED master key, answering everything with
LiteLLM's DB-less 400 no_db_connection): the deploy is now VERIFY-THEN-SWAP,
never dark. Before ANY live-instance stop, a STAGING instance of the
identical generated config (only the launch port swapped; launched through
the SAME env-sourcing launcher template as the cutover start) must pass the
FULL ladder on the staging port — bind + served-state, staging-bind
ownership, the REAL-key completion with upstream identity (an unresolved
master key denies the real key service and fails exactly here), then the
auth-enforcement rung — structurally proving config AND env health. Only on
staging-green does the cutover fire (the existing iteration-4/5 machinery),
followed by a post-cutover ladder re-verify with ONE bounded retry for a
port-race winner (via the iteration-4 port-holder stop); retry exhaustion is
an honest failure EMBEDDING the codified recovery procedure. Any staging
failure leaves the old instance serving. The staged instance is stopped on
ALL exit paths (green / ladder failure / exception — try/finally,
test-pinned), so staging can never reintroduce the iteration-5 accumulation
class. The generated launchers close the pile-up vector at its root: each
REFUSES to launch when the port THIS launch binds is already LISTENING
(naming the holder pid; a staging launcher checks its own staging port, so
it is never refused by a busy live port) and logs masked master-key presence
(first 8 chars, or an explicit MISSING) before exec'ing litellm.
Iteration 7 (SR-glm-fix-iter7, CRITICAL — deploy-6 darkened the port a
SECOND time) corrects the two identity primitives the whole discipline
stack stands on. (13a) An owned INSTANCE is a process TREE, not a pid: the
launcher chain (cmd → litellm.exe → python.exe) presents multiple owned
pids, and the deploy-6 sweep kept only the LISTENER pid while stopping its
parent — killing the parent killed the listener; port dark. Owned pids are
now grouped by parent chain (Windows: CIM ParentProcessId with pid-reuse
validation via creation-time ordering — a "parent" born after its child is
a recycled pid and the link is severed; POSIX: ppid), membership bounded to
INSTANCE-AFFILIATED processes (cmdline carries this state dir's path — the
config or the generated launcher), so an interactive shell that launched a
gateway by hand, and every system ancestor, never joins a tree. Stop
semantics carry TWO distinct predicates (both test-pinned): the
accumulation-clearing SWEEP never touches ANY pid in the port-holder's
tree (conservative per-pid kills, root-first, no /T — a link we failed to
see must never cascade into the listener), while the DELIBERATE
port-freeing stops (the iteration-4 port-holder repair, the iteration-6
cutover and staging teardown) act on the holder's WHOLE tree root-first
with tree-kill semantics (taskkill /T) so no respawn-capable orphan
survives. (13b) Served-state staleness is ROUTE-CONTRADICTION, not
name-set membership: /model/info advertises the catch-all's wildcard
EXPANSIONS (23 anthropic/<id> groups on a fresh instance), which a bare
group-set diff read as unrouted extras (false stale — the accelerant
behind the forced restarts and race windows), while bare NAME matching
would blind the true marker (the catch-all matches its NAME). The
comparison is now TWO-ARMED: each served group's SERVING ROUTE must agree
with the generated config's route for that name — explicit routes take
precedence over catch-all expansion, wildcard patterns are derived from
the generated config at comparison time (provider-neutral) — AND every
explicitly-routed config group must be present in the served state
(config→served completeness: a newly added alias silently absorbed by a
stale process's catch-all is stale). The split now
writes the spawn-compatible IMPERSONATION alias (`SPAWN_ALIAS_MODEL_ID`, a
real Claude id the Agent-Teams spawn gate accepts — the gate rejects custom
ids client-side with zero HTTP) into dev-class frontmatter; the generated
config routes that id to the chosen secondary, disclosed in gateway.json
(`spawn_alias`/`spawn_alias_maps_to`), the status row, and the README. The
split targets the
INSTALLED plugin copy (the agents Claude Code actually runs), falling back to
the repo agents/ when none exists; `~/.architect-team/gateway/gateway.json`
records the desired policy AND the served aliases (`spawn_alias`,
`secondary_alias`, legacy `codex_alias`) so the SessionStart self-heal
survives plugin updates and re-applies the alias the recorded gateway config
actually routes (heal-to-recorded-alias — never an alias the running gateway
would 404, and never a custom id the harness spawn gate would reject).
"""
from __future__ import annotations

import argparse
import fnmatch
import importlib.util
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(__file__).resolve().parents[2]

ENV_HOME = "CT6_GATEWAY_HOME"
# Tri-state enable signal read by setup.py (truthy=enable, set-falsy=disable,
# absent=no signal) — the same convention as CT6_CODEX_56_AVAILABLE.
ENV_SIGNAL = "CT6_EXTERNAL_LLM"
ENV_SECONDARY_PROVIDER = "CT6_SECONDARY_PROVIDER"
SERVICE_NAME = "ct6-llm-gateway"
DEFAULT_PORT = 4000

# Anthropic model ids given EXPLICIT gateway routes in api-key mode (v3.38.1).
# The '*' catch-all alone was observed non-functional on a real LiteLLM
# install (SR-gateway-wildcard-route); these are the ids a real key listed via
# /v1/models on 2026-07-16, fable first (the plugin default), opus-4-8 second
# (the implemented fallback). Extend here when Anthropic ships new ids — the
# catch-all remains as a best-effort tail for anything unlisted.
ANTHROPIC_EXPLICIT_MODELS = (
    "claude-fable-5",
    "claude-opus-4-8",
    "claude-sonnet-5",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
)

CONFIG_NAME = "config.yaml"
ENV_FILE_NAME = "gateway.env"
STATE_NAME = "gateway.json"
DECLINES_NAME = "key-declines.json"
DESCRIPTOR_DIRNAME = "descriptor"
MASTER_KEY_VAR = "CT6_GATEWAY_MASTER_KEY"

# Provider-independent key slot, followed by the chosen secondary provider's slot.
ANTHROPIC_SLOT = ("anthropic", "ANTHROPIC_API_KEY")

AUTH_MODE_API_KEY = "api-key"
AUTH_MODE_SUBSCRIPTION = "subscription"

LITELLM_PACKAGE = "litellm[proxy]"
# Force a binary wheel for litellm itself: its sdist grew a Rust component
# (litellm-rust python-bridge) whose build needs a full MSVC/cargo toolchain —
# observed failing on a real Windows install ("linker `link.exe` not found").
# With --only-binary the resolver backtracks to the newest version that ships
# a compatible wheel instead of attempting a source build.
LITELLM_INSTALL_ARGS = ["--only-binary", "litellm", LITELLM_PACKAGE]


def _load(name: str, rel: str):
    """Load an in-repo sibling module by file path (mirrors install_librarian.py)."""
    spec = importlib.util.spec_from_file_location(name, _REPO_ROOT / rel)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {name} from {rel}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Reused substrate: the model lever (codex alias + split), the bg-runtime
# descriptor generator, and setup.py's PEP-668-aware pip ladder.
_lever = _load("ct6_model_lever", "scripts/setup/set_default_model.py")
_bg = _load("ct6_bg_runtime", "services/common/bg_runtime.py")
_setup = _load("ct6_setup_module", "scripts/setup/setup.py")

SECONDARY_ALIAS = _lever.SECONDARY_ALIAS
SECONDARY_PROVIDERS = _lever.SECONDARY_PROVIDERS
# v3.41.0 (BUG-B, glm-secondary-route-fix): the spawn-compatible impersonation
# alias — a REAL Claude model id the harness accepts at teammate spawn, which
# the generated config rewrites to the chosen secondary provider (disclosed in
# gateway.json + status + README). Single-sourced from the lever (the split
# writes the same id into dev-class frontmatter); re-exported here because the
# gateway is the component that EMITS the impersonation route.
SPAWN_ALIAS_MODEL_ID = _lever.SPAWN_ALIAS_MODEL_ID
# Deprecated external-reader name. New code uses SECONDARY_ALIAS; CODEX_ALIAS
# intentionally remains the historical upstream model id for one transition.
CODEX_ALIAS = _lever.CODEX_MODEL
DEFAULT_OPENAI_MODEL = str(SECONDARY_PROVIDERS["openai"]["model"])

# Model-policy strings — single-sourced from the lever (ADV3-5): the gateway
# never spells these literals itself, so they cannot drift from the emitter.
POLICY_SECONDARY_SPLIT = _lever.POLICY_SECONDARY_SPLIT
POLICY_UNIFORM_FABLE = _lever.POLICY_UNIFORM_FABLE
LEGACY_POLICY_CODEX_SPLIT = _lever.LEGACY_POLICY_CODEX_SPLIT


# --------------------------------------------------------------------------- #
# base-dir / auth-mode / key resolution
# --------------------------------------------------------------------------- #

def resolve_base_dir(explicit: Optional[str], env: Optional[dict[str, str]] = None) -> Path:
    """Resolve the state base dir: explicit `--base-dir` > `$CT6_GATEWAY_HOME` >
    `~/.architect-team/gateway/`."""
    env = os.environ if env is None else env
    if explicit:
        return Path(explicit)
    from_env = env.get(ENV_HOME)
    if from_env:
        return Path(from_env)
    return Path.home() / ".architect-team" / "gateway"


def read_env_file(path: Path) -> dict[str, str]:
    """Parse a KEY=VALUE env file (comments + blank lines ignored; first `=` splits)."""
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    except OSError:
        return {}
    return out


def write_env_file(path: Path, values: dict[str, str]) -> None:
    """Write the gateway env file (sorted KEY=VALUE) and chmod 0600 best-effort.
    This file is the ONLY place a raw key is persisted — outside the repo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f"{k}={v}" for k, v in sorted(values.items()) if v) + "\n"
    path.write_text(body, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover - platform-dependent best-effort
        pass


def provider_key_slots(secondary_provider: str) -> tuple[tuple[str, str], ...]:
    """Promptable key slots for a provider: chosen secondary first, Anthropic second."""
    entry = SECONDARY_PROVIDERS[secondary_provider]
    return ((secondary_provider, str(entry["key_env"])), ANTHROPIC_SLOT)


def preserved_env_keys() -> tuple[str, ...]:
    """gateway.env keys an install rewrite must never drop (ADV3-2): EVERY
    registry provider's key slot — switching --secondary must not delete the
    other provider's stored key — plus the Anthropic slot and the master key."""
    return tuple(str(SECONDARY_PROVIDERS[name]["key_env"])
                 for name in sorted(SECONDARY_PROVIDERS)) + (
        "ANTHROPIC_API_KEY", MASTER_KEY_VAR)


def resolve_secondary_provider(
    explicit: Optional[str],
    base: Path,
    *,
    env: Optional[dict[str, str]] = None,
    re_ask: bool = False,
    interactive: bool = False,
    prompt_fn=None,
    isatty_fn=None,
) -> tuple[Optional[str], str, Optional[str]]:
    """Resolve provider by flag > env > state > grandfather > ask > openai.

    Returns ``(provider, source, error)``. Unknown inputs never fall through to a
    different provider; callers surface the error and perform no state write.
    ``--re-ask-provider`` suppresses both recorded and grandfathered choices.
    """
    env = os.environ if env is None else env
    state = _read_state(base)
    candidate: Optional[str] = None
    source = ""
    if explicit is not None:
        candidate, source = str(explicit).strip().lower(), "flag"
    elif ENV_SECONDARY_PROVIDER in env:
        candidate = str(env.get(ENV_SECONDARY_PROVIDER, "")).strip().lower()
        source = "env"
    elif not re_ask and state.get("secondary_provider"):
        candidate = str(state["secondary_provider"]).strip().lower()
        source = "recorded"
    elif not re_ask and "openai_model" in state and "secondary_provider" not in state:
        candidate, source = "openai", "grandfather"
    elif interactive:
        candidate = _prompt_for_provider(prompt_fn=prompt_fn, isatty_fn=isatty_fn)
        source = "interactive"
    else:
        candidate, source = "openai", "default"
    if candidate not in SECONDARY_PROVIDERS:
        valid = ", ".join(sorted(SECONDARY_PROVIDERS))
        return None, source, (
            f"unknown secondary provider {candidate!r} from {source}; valid: {valid}")
    return candidate, source, None


def resolve_keys(
    base: Path,
    openai_arg: Optional[str] = None,
    anthropic_arg: Optional[str] = None,
    env: Optional[dict[str, str]] = None,
    *,
    secondary_provider: str = "openai",
    provider_args: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, str]:
    """Resolve Anthropic + the chosen provider: args > process env > gateway.env."""
    env = os.environ if env is None else env
    existing = read_env_file(base / ENV_FILE_NAME)
    provider_args = dict(provider_args or {})
    if openai_arg is not None:
        provider_args["openai"] = openai_arg
    entry = SECONDARY_PROVIDERS[secondary_provider]
    provider_env = str(entry["key_env"])
    provider_key = (provider_args.get(secondary_provider) or env.get(provider_env)
                    or existing.get(provider_env))
    anthropic = (anthropic_arg or env.get("ANTHROPIC_API_KEY")
                 or existing.get("ANTHROPIC_API_KEY"))
    master = existing.get(MASTER_KEY_VAR)
    out: dict[str, str] = {}
    if provider_key:
        out[provider_env] = provider_key
    if anthropic:
        out["ANTHROPIC_API_KEY"] = anthropic
    out[MASTER_KEY_VAR] = master or ("sk-ct6-" + secrets.token_urlsafe(24))
    return out


def resolve_auth_mode(keys: dict[str, str]) -> str:
    """``api-key`` when an Anthropic key resolved; else ``subscription`` — the mode
    where fable is used via Claude Code's native sign-in and the gateway serves
    OpenAI only. This is a KEY-PRESENCE check, never a live-API probe."""
    return AUTH_MODE_API_KEY if keys.get("ANTHROPIC_API_KEY") else AUTH_MODE_SUBSCRIPTION


def _mask(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    return ("…" + secret[-4:]) if len(secret) >= 4 else "set"


# --------------------------------------------------------------------------- #
# interactive key prompt + per-key decline record (v3.38.0)
# --------------------------------------------------------------------------- #
#
# Ask-then-apply: an interactive TTY install PROMPTS for a missing key (hidden
# getpass entry) instead of punting to a printed remediation. A blank entry
# skips and records the slot in key-declines.json (via=prompt-skip); the
# wrapper flow's AskUserQuestion decline is recorded via the `decline`
# subcommand (via=wrapper). A recorded decline suppresses the PROMPT on
# re-runs, never the `status` truth; it auto-resets the moment the slot's key
# resolves on any path, and --re-ask-keys clears it so prompts fire again.


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z")


def _read_declines(base: Path) -> dict[str, Any]:
    """Read <state>/key-declines.json — slot → {declined_at, via}. Missing or
    malformed reads as no declines (fail open: worst case we ask again)."""
    path = base / DECLINES_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_declines(base: Path, declines: dict[str, Any]) -> None:
    """Persist the decline record. An emptied record removes the file, so a
    fully-cleared state dir and a fresh one look identical."""
    path = base / DECLINES_NAME
    if not declines:
        try:
            path.unlink()
        except OSError:
            pass
        return
    base.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(declines, indent=2, sort_keys=True),
                    encoding="utf-8")


def _record_decline(base: Path, slot: str, via: str) -> None:
    """Record a slot decline. `via` is 'wrapper' (the decline subcommand — the
    slash-command flow's deterministic channel) or 'prompt-skip' (a blank entry
    at the installer prompt)."""
    declines = _read_declines(base)
    declines[slot] = {"declined_at": _utc_now_iso(), "via": via}
    _write_declines(base, declines)


def _clear_declines(base: Path, slot: Optional[str] = None) -> bool:
    """Clear one slot's decline, or ALL of them with slot=None (the
    --re-ask-keys path). Returns True when something was actually cleared."""
    declines = _read_declines(base)
    if not declines:
        return False
    if slot is None:
        _write_declines(base, {})
        return True
    if slot in declines:
        declines.pop(slot)
        _write_declines(base, declines)
        return True
    return False


def _stdin_isatty() -> bool:
    try:
        return bool(sys.stdin.isatty())
    except Exception:  # pragma: no cover - a closed/replaced stdin is non-TTY
        return False


def _hidden_prompt(message: str) -> str:
    """Hidden (getpass) key entry. Degrades to visible input() with a one-line
    warning ONLY when hidden entry is unachievable — getpass's non-console
    fallback path, surfaced as GetPassWarning — never on an import check
    (getpass always imports)."""
    import getpass
    import warnings
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            return getpass.getpass(message)
    except getpass.GetPassWarning:
        print("[!] hidden entry is not available on this console -- "
              "the key will be VISIBLE as you type")
        return input(message)


_default_prompt_fn = _hidden_prompt   # injectable seam — tests stub this
_default_isatty_fn = _stdin_isatty    # injectable seam — tests stub this
_default_provider_prompt_fn = input    # visible provider-choice seam


def _prompt_for_provider(*, prompt_fn=None, isatty_fn=None) -> str:
    """Visible provider choice prompt. Blank selects OpenAI; non-TTY also defaults."""
    prompt_fn = prompt_fn or _default_provider_prompt_fn
    isatty_fn = isatty_fn or _default_isatty_fn
    if not isatty_fn():
        return "openai"
    choices = ", ".join(
        f"{name} ({entry['label']})" for name, entry in SECONDARY_PROVIDERS.items())
    try:
        entered = prompt_fn(
            f"Secondary provider [{choices}] (blank for openai): ")
    except (EOFError, KeyboardInterrupt):
        print()
        return "openai"
    return (entered or "").strip().lower() or "openai"


def _prompt_for_key(slot: str, *, prompt_fn=None, isatty_fn=None) -> Optional[str]:
    """Prompt for one slot's key on an interactive TTY. Returns the entered key
    (stripped) or None (blank entry, or stdin is not a TTY). The caller gates
    on --interactive-prompts / --check-only / --json and the decline record;
    this seam owns the TTY check and the hidden entry. The entered value is
    NEVER echoed — every report line masks via _mask."""
    prompt_fn = prompt_fn or _default_prompt_fn
    isatty_fn = isatty_fn or _default_isatty_fn
    if not isatty_fn():
        return None
    if slot == "anthropic":
        env_key = "ANTHROPIC_API_KEY"
    else:
        env_key = str(SECONDARY_PROVIDERS[slot]["key_env"])
    try:
        entered = prompt_fn(f"{env_key} for the CT6 gateway (blank to skip): ")
    except (EOFError, KeyboardInterrupt):
        # Ctrl-C / Ctrl-D at the prompt is a SKIP, not an abort — the same
        # semantics as the setup.py _prompt_user_consent house pattern (an
        # interrupt reads as a "no") and the librarian seam: the absent-key
        # path runs verbatim and a setup run never dies at a key prompt.
        print()
        return None
    entered = (entered or "").strip()
    return entered or None


# --------------------------------------------------------------------------- #
# generated artifacts: config.yaml / launcher / claude env block
# --------------------------------------------------------------------------- #

def _secondary_route_model(entry: dict[str, Optional[str]], model: str) -> str:
    """The LiteLLM route for a secondary entry: ``<route_dialect>/<model>``.

    v3.41.0 (BUG-A): the dialect comes from the REGISTRY, never a hard-coded
    prefix — LiteLLM's proxy drives Anthropic-format calls for ``openai/*``
    models through the OpenAI Responses API, which api.z.ai does not implement
    (live 404 at /v4/responses); zai's entry names the strict chat-completions
    ``hosted_vllm`` dialect instead."""
    return f"{entry['route_dialect']}/{model}"


def build_gateway_config(
    auth_mode: str,
    secondary_alias: str = SECONDARY_ALIAS,
    secondary_model: Optional[str] = None,
    secondary_provider: str = "openai",
) -> str:
    """The LiteLLM proxy config. Deterministic text (no yaml dep); secrets are
    `os.environ/...` references resolved from gateway.env by the launcher —
    NEVER raw values.

    * Always: the neutral secondary alias → the registry-dialect route (the
      v3.35.0 role-split backend; direct/scripted callers).
    * Always (v3.41.0, BUG-B): the spawn-compatible IMPERSONATION route —
      `SPAWN_ALIAS_MODEL_ID` → the SAME dialect-prefixed secondary model — so
      the real Claude id the harness accepts at teammate spawn is served by
      the secondary. Emitted ahead of every Anthropic route; in api-key mode
      the anthropic explicit-route loop SKIPS this id (a duplicate model_name
      would form a LiteLLM load-balancing group mixing the secondary with the
      real Anthropic model).
    * api-key mode only: an EXPLICIT route per known Anthropic model id
      (ANTHROPIC_EXPLICIT_MODELS — fable first) plus a catch-all tail, so
      ANTHROPIC_BASE_URL can front the whole harness. Explicit routes are
      REQUIRED, not decorative: the catch-all alone was field-observed broken
      (v3.38.1, SR-gateway-wildcard-route).
    * Always: a master key, so the local proxy never runs unauthenticated.
    """
    entry = SECONDARY_PROVIDERS[secondary_provider]
    model = secondary_model or str(entry["model"])
    route = _secondary_route_model(entry, model)
    lines = [
        "# CT6 external-LLM gateway (LiteLLM) — GENERATED by",
        "# scripts/setup/install_gateway.py; edit by re-running the installer.",
        "model_list:",
        f"  - model_name: {secondary_alias}",
        "    litellm_params:",
        f"      model: {route}",
        f"      api_key: os.environ/{entry['key_env']}",
    ]
    if entry.get("api_base"):
        lines.append(f"      api_base: {entry['api_base']}")
    lines += [
        f"  - model_name: {SPAWN_ALIAS_MODEL_ID}",
        "    litellm_params:",
        f"      model: {route}",
        f"      api_key: os.environ/{entry['key_env']}",
    ]
    if entry.get("api_base"):
        lines.append(f"      api_base: {entry['api_base']}")
    if auth_mode == AUTH_MODE_API_KEY:
        # v3.38.1 (SR-gateway-wildcard-route, field-verified 2026-07-16): a
        # config that relies ONLY on the '*' catch-all was observed broken on a
        # real Windows LiteLLM install — the proxy exposed just the codex alias
        # and rejected every Anthropic id with "Invalid model name ... Call
        # /v1/models". Explicit per-model routes fixed it live (fable + opus
        # verified through the gateway). Each known Anthropic id therefore gets
        # its own route, emitted BEFORE the catch-all; the catch-all stays as a
        # best-effort tail for ids that ship after this list was written.
        for anthropic_id in ANTHROPIC_EXPLICIT_MODELS:
            if anthropic_id == SPAWN_ALIAS_MODEL_ID:
                # The impersonation route above IS this id's explicit route —
                # emitting the real Anthropic route too would create a
                # duplicate model_name (a LiteLLM load-balancing group) that
                # round-robins the secondary with the real Anthropic model.
                continue
            lines += [
                f"  - model_name: {anthropic_id}",
                "    litellm_params:",
                f"      model: anthropic/{anthropic_id}",
                "      api_key: os.environ/ANTHROPIC_API_KEY",
            ]
        lines += [
            '  - model_name: "*"',
            "    litellm_params:",
            '      model: "anthropic/*"',
            "      api_key: os.environ/ANTHROPIC_API_KEY",
        ]
    lines += [
        "general_settings:",
        f"  master_key: os.environ/{MASTER_KEY_VAR}",
        "",
    ]
    return "\n".join(lines)


def _litellm_command() -> str:
    """The command the launcher runs: the resolved `litellm` console script when
    present, else the bare name (resolved again at launch time via PATH)."""
    return shutil.which("litellm") or "litellm"


def build_launcher(platform_key: str, base: Path, port: int) -> tuple[str, str]:
    """Return (filename, content) of the gateway launcher for `platform_key`.
    The launcher loads gateway.env into the process env and execs the proxy —
    so a boot-descriptor-started gateway sees its keys without them living in
    the descriptor or the shell profile.

    v3.41.0 iteration 6 (SR-glm-fix-iter6): the launcher is the ONE chokepoint
    every launch path funnels through (schtasks /run, the startup shim, a
    manual double-launch) — all 8 of the 2026-07-18 incident's piled-up
    instances entered here. It now (a) REFUSES to launch when the port THIS
    launch binds is already LISTENING, naming the holder pid — keyed on its
    OWN embedded port, so a staging launcher (generated with the staging port)
    is never refused by a busy live port; and (b) logs masked master-key
    presence (first 8 chars, or an explicit MISSING) after sourcing
    gateway.env and before exec'ing litellm — the incident's winning instance
    had an UNRESOLVED master key and nothing recorded whether the env ever
    loaded. Never the full key, never wider than 8 chars."""
    cmd = _litellm_command()
    if platform_key == "windows":
        # joined with "\n": the text-mode write translates to CRLF on Windows
        # (a literal "\r\n" here would double to "\r\r\n" through that layer)
        content = "\n".join([
            "@echo off",
            "REM CT6 external-LLM gateway launcher — GENERATED by install_gateway.py",
            "REM PYTHONUTF8: litellm's startup banner is not cp1252-encodable and",
            "REM crashes app startup on a legacy-codepage Windows console without it.",
            'set "PYTHONUTF8=1"',
            "REM Port guard (SR-glm-fix-iter6): refuse to launch when the port THIS",
            f"REM launch binds ({port}) is already LISTENING — one instance per port;",
            "REM a staging launcher carries its own port, so it is never refused by",
            "REM a busy live port.",
            f"for /f \"tokens=5\" %%p in ('netstat -ano ^| findstr /r /c:\":{port} .*LISTENING\"') do (",
            f"  echo [ct6-gateway] REFUSING to launch: port {port} is already LISTENING - held by pid %%p. One instance per port; stop it first ^(taskkill /pid %%p /f^) or use the installer's verified restart.",
            "  exit /b 1",
            ")",
            f'for /f "usebackq eol=# tokens=1,* delims==" %%a in ("{base / ENV_FILE_NAME}") do set "%%a=%%b"',
            "REM Masked key-presence log (SR-glm-fix-iter6, incident recommendation):",
            "REM first 8 chars only — never the full key, never wider.",
            f"if defined {MASTER_KEY_VAR} (",
            f"  echo [ct6-gateway] {MASTER_KEY_VAR} resolved: %{MASTER_KEY_VAR}:~0,8%... ^(masked^)",
            ") else (",
            f"  echo [ct6-gateway] {MASTER_KEY_VAR} MISSING - gateway.env did not load or lacks the key; every request will fail auth ^(the no_db_connection incident state^)",
            ")",
            f'"{cmd}" --config "{base / CONFIG_NAME}" --port {port}',
            "",
        ])
        return "run_gateway.bat", content
    content = "\n".join([
        "#!/bin/sh",
        "# CT6 external-LLM gateway launcher — GENERATED by install_gateway.py",
        "PYTHONUTF8=1",
        "export PYTHONUTF8",
        "# Port guard (SR-glm-fix-iter6): refuse to launch when the port THIS",
        f"# launch binds ({port}) is already LISTENING — one instance per port; a",
        "# staging launcher carries its own port, so it is never refused by a busy",
        "# live port. Best-effort: no lsof = the guard stands down (the installer's",
        "# verified restart machinery remains the backstop).",
        "if command -v lsof >/dev/null 2>&1; then",
        f"  ct6_holder=\"$(lsof -ti tcp:{port} -sTCP:LISTEN 2>/dev/null | head -n 1)\"",
        '  if [ -n "$ct6_holder" ]; then',
        f"    echo \"[ct6-gateway] REFUSING to launch: port {port} is already LISTENING - held by pid $ct6_holder. One instance per port; stop it first (kill $ct6_holder) or use the installer's verified restart.\" >&2",
        "    exit 1",
        "  fi",
        "fi",
        "set -a",
        f'. "{base / ENV_FILE_NAME}"',
        "set +a",
        "# Masked key-presence log (SR-glm-fix-iter6, incident recommendation):",
        "# first 8 chars only — never the full key, never wider.",
        f'if [ -n "${MASTER_KEY_VAR}" ]; then',
        f"  echo \"[ct6-gateway] {MASTER_KEY_VAR} resolved: $(printf '%.8s' \"${MASTER_KEY_VAR}\")... (masked)\"",
        "else",
        f"  echo \"[ct6-gateway] {MASTER_KEY_VAR} MISSING - gateway.env did not load or lacks the key; every request will fail auth (the no_db_connection incident state)\"",
        "fi",
        f'exec "{cmd}" --config "{base / CONFIG_NAME}" --port {port}',
        "",
    ])
    return "run_gateway.sh", content


def gateway_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def build_claude_env_block(port: int, master_key: str) -> dict[str, str]:
    """The settings.json `env` entries that point Claude Code at the gateway.
    Written ONLY in api-key mode and only on explicit --activate — in
    subscription mode rerouting native sign-in auth is unsupported."""
    return {
        "ANTHROPIC_BASE_URL": gateway_url(port),
        "ANTHROPIC_AUTH_TOKEN": master_key,
    }


# --------------------------------------------------------------------------- #
# settings.json activation (merge-preserving, mirrors setup.py's flag write)
# --------------------------------------------------------------------------- #

def _read_settings(settings_path: Path) -> dict[str, Any]:
    if settings_path.is_file():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def apply_claude_env(settings_path: Path, port: int, master_key: str) -> None:
    """Merge the gateway env block into settings.json (idempotent; every other
    key preserved — the same merge posture as setup.py's teams-mode write)."""
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_settings(settings_path)
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        env_block = {}
    env_block.update(build_claude_env_block(port, master_key))
    data["env"] = env_block
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def remove_claude_env(settings_path: Path, port: int) -> bool:
    """Remove OUR env entries from settings.json — only when ANTHROPIC_BASE_URL
    still points at THIS gateway's URL (a user-customized value is never
    clobbered). Returns True when something was removed."""
    data = _read_settings(settings_path)
    env_block = data.get("env")
    if not isinstance(env_block, dict):
        return False
    if env_block.get("ANTHROPIC_BASE_URL") != gateway_url(port):
        return False
    env_block.pop("ANTHROPIC_BASE_URL", None)
    env_block.pop("ANTHROPIC_AUTH_TOKEN", None)
    data["env"] = env_block
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True


def claude_env_applied(settings_path: Path, port: int) -> bool:
    env_block = _read_settings(settings_path).get("env")
    return isinstance(env_block, dict) and env_block.get(
        "ANTHROPIC_BASE_URL") == gateway_url(port)


# --------------------------------------------------------------------------- #
# auto-registration (v3.37.0 — the installer EXECUTES the registration)
# --------------------------------------------------------------------------- #
#
# Owner directive: enabling external-LLM usage must be one command, so the
# installer registers + starts the gateway itself (opt-out: --no-register).
# This deliberately extends the older print-the-hint posture; the enable signal
# is the consent, registration stays user-level (never sudo / admin), and a
# registration failure degrades to a fail step + the manual hint — never a crash.

_default_runner = subprocess.run     # injectable seam — tests stub this
_default_spawner = subprocess.Popen  # injectable seam — the detached start-now


def _run(cmd: list[str], runner=None):
    runner = runner or _default_runner
    return runner(cmd, capture_output=True, text=True, encoding="utf-8",
                  errors="replace")


def _spawn_detached(cmd: list[str], spawner=None) -> bool:
    """Start a long-running process WITHOUT inheriting our pipes and WITHOUT
    waiting (a captured-pipe `subprocess.run` would block until the gateway
    itself exits — observed hanging a real install for its full timeout).
    Windows gets its own minimized console so the daemon survives us."""
    spawner = spawner or _default_spawner
    kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    if os.name == "nt":  # pragma: no cover - exercised on the real install
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7  # SW_SHOWMINNOACTIVE
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        kwargs["startupinfo"] = si
    try:
        spawner(cmd, **kwargs)
        return True
    except OSError:
        return False


def _windows_startup_dir(home: Optional[Path] = None) -> Path:
    """The current user's Startup folder — a plain-file autostart mechanism
    that needs NO privilege at all (observed: `schtasks /create` is denied
    from a non-elevated shell on a real Windows 11 box)."""
    if home is not None:
        return (Path(home) / "AppData" / "Roaming" / "Microsoft" / "Windows"
                / "Start Menu" / "Programs" / "Startup")
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return base / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def register_gateway(
    platform_key: str,
    launcher_path: Path,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
    *,
    base: Optional[Path] = None,
    port: Optional[int] = None,
) -> tuple[bool, str]:
    """Register the gateway to start automatically AND start it now. User-level
    on every OS (schtasks onlogon / Startup-folder shim / `systemctl --user` /
    LaunchAgents) — no admin/sudo, matching a per-user gateway. Returns
    (ok, detail).

    v3.41.0 iteration 5 (SR-glm-fix-iter5): when the ownership context is
    given (``base`` + ``port`` — the install call site passes it), the
    start-now half runs the exactly-one-instance gate: every OWNED instance
    not serving the port (cmdline carries this state dir's config path) is
    stopped first, and the start fires ONLY on a free port — never blindly
    over a serving instance (the unconditional every-install start was how
    8 instances accumulated). Without the context (legacy call shape) the
    behavior is the pre-iteration-5 register + start, byte-identical."""
    do_start, gate_notes = (True, [])
    if base is not None and port is not None:
        do_start, gate_notes = _exactly_one_owned_start_gate(
            platform_key, base, port, runner)
    gate = ("; " + "; ".join(gate_notes)) if gate_notes else ""
    if platform_key == "windows":
        # First choice: a direct /tr onlogon registration (NOT the XML
        # descriptor: its boot trigger needs admin). schtasks task creation is
        # itself denied from a non-elevated shell on some boxes, so on failure
        # fall back to a Startup-folder shim — a plain file write that always
        # works and runs the launcher minimized at logon.
        res = _run(["schtasks", "/create", "/tn", name,
                    "/tr", f'"{launcher_path}"', "/sc", "onlogon", "/f"], runner)
        if res.returncode == 0:
            if not do_start:
                return True, "scheduled task registered (onlogon)" + gate
            started = _run(["schtasks", "/run", "/tn", name], runner).returncode == 0
            return True, ("scheduled task registered (onlogon)"
                          + (" + started" if started
                             else f' — start it: schtasks /run /tn "{name}"')
                          + gate)
        err = (res.stderr or res.stdout or "").strip() or "schtasks /create failed"
        startup_dir = _windows_startup_dir(home)
        try:
            startup_dir.mkdir(parents=True, exist_ok=True)
            shim = startup_dir / f"{name}.cmd"
            shim.write_text(
                f'@start "" /min "{launcher_path}"\n', encoding="utf-8")
        except OSError as exc:
            return False, f"{err}; startup-folder fallback also failed: {exc}"
        if not do_start:
            return True, (f"startup-folder shim registered at {shim} "
                          f"(schtasks denied: {err})" + gate)
        started = _spawn_detached(["cmd", "/c", str(launcher_path)])
        return True, (f"startup-folder shim registered at {shim} "
                      f"(schtasks denied: {err})"
                      + (" + started" if started else " — start it by running the launcher")
                      + gate)
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        unit_dir = home / ".config" / "systemd" / "user"
        unit_dir.mkdir(parents=True, exist_ok=True)
        unit = _bg.systemd_unit(name, str(launcher_path)).replace(
            "WantedBy=multi-user.target", "WantedBy=default.target")
        unit_path = unit_dir / f"{name}.service"
        unit_path.write_text(unit, encoding="utf-8")
        enable_cmd = (["systemctl", "--user", "enable", "--now", name]
                      if do_start else ["systemctl", "--user", "enable", name])
        for cmd in (["systemctl", "--user", "daemon-reload"], enable_cmd):
            res = _run(cmd, runner)
            if res.returncode != 0:
                return False, (res.stderr or "").strip() or f"{' '.join(cmd)} failed"
        if not do_start:
            return True, f"user systemd unit enabled ({unit_path})" + gate
        return True, f"user systemd unit enabled + started ({unit_path})" + gate
    if platform_key == "darwin":
        agents_dir = home / "Library" / "LaunchAgents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        plist_path = agents_dir / f"{name}.plist"
        plist_path.write_text(_bg.launchd_plist(name, [str(launcher_path)]),
                              encoding="utf-8")
        if not do_start:
            # Loading a RunAtLoad agent IS a start — deferring the load keeps
            # the no-blind-start invariant; the plist in LaunchAgents is
            # picked up at the next login regardless.
            return True, (f"launchd agent plist written ({plist_path}) — "
                          f"load deferred (loading a RunAtLoad agent would "
                          f"start a second instance)" + gate)
        res = _run(["launchctl", "load", "-w", str(plist_path)], runner)
        if res.returncode != 0:
            return False, (res.stderr or "").strip() or "launchctl load failed"
        return True, f"launchd agent loaded ({plist_path})" + gate
    return False, f"unsupported platform {platform_key!r}"


def unregister_gateway(
    platform_key: str,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
) -> tuple[bool, str]:
    """Stop + unregister the gateway (an absent registration is a no-op)."""
    if platform_key == "windows":
        _run(["schtasks", "/end", "/tn", name], runner)  # stop if running
        res = _run(["schtasks", "/delete", "/tn", name, "/f"], runner)
        shim = _windows_startup_dir(home) / f"{name}.cmd"
        shim_removed = False
        if shim.exists():
            try:
                shim.unlink()
                shim_removed = True
            except OSError:  # pragma: no cover
                pass
        if res.returncode == 0 and shim_removed:
            return True, "scheduled task + startup-folder shim removed"
        if res.returncode == 0:
            return True, "scheduled task stopped + removed"
        if shim_removed:
            return True, "startup-folder shim removed"
        return True, "not registered (no-op)"
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        _run(["systemctl", "--user", "disable", "--now", name], runner)
        unit_path = home / ".config" / "systemd" / "user" / f"{name}.service"
        if unit_path.exists():
            try:
                unit_path.unlink()
            except OSError:  # pragma: no cover
                pass
            _run(["systemctl", "--user", "daemon-reload"], runner)
            return True, "user systemd unit disabled + removed"
        return True, "not registered (no-op)"
    if platform_key == "darwin":
        plist_path = home / "Library" / "LaunchAgents" / f"{name}.plist"
        if plist_path.exists():
            _run(["launchctl", "unload", "-w", str(plist_path)], runner)
            try:
                plist_path.unlink()
            except OSError:  # pragma: no cover
                pass
            return True, "launchd agent unloaded + removed"
        return True, "not registered (no-op)"
    return False, f"unsupported platform {platform_key!r}"


def is_gateway_registered(
    platform_key: str,
    name: str = SERVICE_NAME,
    home: Optional[Path] = None,
    runner=None,
) -> bool:
    if platform_key == "windows":
        if _run(["schtasks", "/query", "/tn", name], runner).returncode == 0:
            return True
        return (_windows_startup_dir(home) / f"{name}.cmd").exists()
    home = Path(home) if home else Path.home()
    if platform_key == "linux":
        return (home / ".config" / "systemd" / "user" / f"{name}.service").exists()
    if platform_key == "darwin":
        return (home / "Library" / "LaunchAgents" / f"{name}.plist").exists()
    return False


# --------------------------------------------------------------------------- #
# litellm install (through setup.py's PEP-668-aware ladder)
# --------------------------------------------------------------------------- #

def litellm_installed() -> bool:
    try:
        return importlib.util.find_spec("litellm") is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def install_litellm(installer=None) -> tuple[bool, Optional[str]]:
    """Install `litellm[proxy]` via setup.py's `_install_packages` ladder
    (uv → pip --user → --break-system-packages), forcing a binary wheel for
    litellm (see LITELLM_INSTALL_ARGS — the ladder appends the args verbatim
    after `install`, so the flag rides along on every rung). `installer` is
    injectable so tests never touch pip for real."""
    installer = installer or _setup._install_packages
    return installer(LITELLM_INSTALL_ARGS)


# --------------------------------------------------------------------------- #
# step / report scaffolding (mirrors install_librarian.py)
# --------------------------------------------------------------------------- #

@dataclass
class StepResult:
    name: str
    status: str  # "ok" | "skipped" | "fail"
    detail: str = ""


@dataclass
class Report:
    action: str = "install"
    base_dir: str = ""
    auth_mode: str = AUTH_MODE_SUBSCRIPTION
    secondary_provider: str = "openai"
    secondary_model: str = DEFAULT_OPENAI_MODEL
    secondary_key_present: bool = False
    openai_key_present: bool = False
    anthropic_key_present: bool = False
    litellm_present: bool = False
    enabled: bool = False
    activated: bool = False
    # v3.40.0 ADV3C-1: a plain re-install carries a prior activation forward
    # (state honesty) — this flag lets the wording say so without claiming
    # THIS run performed an activation.
    activation_carried: bool = False
    registered: bool = False
    split_applied: bool = False
    # v3.40.0 ADV3C-1: the on-disk agents policy IS the split (e.g. carried
    # from a prior activation) even though THIS run did not apply it.
    split_on_disk: bool = False
    split_confirmed: Optional[bool] = None  # v3.39.0: live /v1/models verdict
    descriptor_path: Optional[str] = None
    register_hint: Optional[str] = None
    remediation: Optional[str] = None
    check_only: bool = False
    steps: list[StepResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.steps.append(StepResult(name=name, status=status, detail=detail))


def _platform_key() -> str:
    return {"Linux": "linux", "Darwin": "darwin", "Windows": "windows"}.get(
        platform.system(), "linux")


def _write_state(base: Path, payload: dict[str, Any]) -> None:
    """Persist the non-secret installer state (gateway.json). NEVER a raw key."""
    base.mkdir(parents=True, exist_ok=True)
    (base / STATE_NAME).write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_state(base: Path) -> dict[str, Any]:
    path = base / STATE_NAME
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _recorded_secondary_alias(state: dict[str, Any]) -> str:
    """The alias the RECORDED gateway config routes: `secondary_alias`, falling
    back to the legacy `codex_alias`, else the current SECONDARY_ALIAS. Each
    candidate is trimmed BEFORE the truthiness check (ADV3B-2) so a corrupt
    whitespace-only value reads as absent — it never masks the legacy key and
    never becomes a literal-whitespace probe expectation."""
    for key in ("secondary_alias", "codex_alias"):
        value = state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return SECONDARY_ALIAS


def _recorded_spawn_alias(state: dict[str, Any]) -> Optional[str]:
    """The spawn-compatible impersonation alias the RECORDED config routes
    (v3.41.0), or ``None`` for a pre-spawn-alias state (whose config does not
    route it — never probe or heal to an unrecorded alias). Whitespace-trimmed
    before the truthiness check, same as ``_recorded_secondary_alias``."""
    value = state.get("spawn_alias")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _default_agents_dir() -> Path:
    """The agents/ dir the model split targets (v3.39.0: runtime-first).

    Claude Code runs the INSTALLED plugin cache copy, not the dev checkout —
    a split applied to the repo's agents/ never reaches the runtime and is
    reverted by the next git operation (ship state is uniform fable). Resolve
    the installed copy via the lever; fall back to the repo agents/ when no
    installed copy exists (a --plugin-dir dev install, or tests)."""
    return _lever.runtime_agents_dir()


# --------------------------------------------------------------------------- #
# live split confirmation + gateway restart (v3.39.0)
# --------------------------------------------------------------------------- #
#
# The v3.38.1 field bug proved a generated config can be broken while every
# install step reports ok. The confirm step closes that gap: after a
# registered install the installer polls the LIVE gateway's /v1/models and
# asserts the ids the split needs are actually SERVED — the neutral secondary
# alias always (install probes the alias the just-written config routes;
# status --live instead probes the STATE-RECORDED alias, so a working legacy
# v3.39 config still confirms green), claude-fable-5 additionally in api-key
# mode. An already-running gateway that predates a
# config regeneration serves the OLD config; on a failed confirm the installer
# restarts the gateway once (through the same user-level registration
# machinery) and re-probes before degrading to a warn. Never gates.
FABLE_MODEL = ANTHROPIC_EXPLICIT_MODELS[0]  # "claude-fable-5"
CONFIRM_ATTEMPTS = 15   # litellm cold-start on a real Windows box takes ~10-30s
CONFIRM_DELAY = 2.0
# v3.41.0 iteration 4 (SR-glm-fix-iter4) — the verified-restart polls. The
# port poll is the grace window after the tracked stop (schtasks /end &
# friends return before the process actually exits); the bind poll gives the
# restarted litellm the same cold-start budget the confirm poll does. All four
# resolve at CALL time (tests monkeypatch them, mirroring CONFIRM_*).
RESTART_PORT_ATTEMPTS = 5
RESTART_PORT_DELAY = 1.0
RESTART_BIND_ATTEMPTS = 15
RESTART_BIND_DELAY = 2.0


def _http_models_probe(port: int, master_key: str, timeout: float = 5.0) -> list[str]:
    """GET the live gateway's /v1/models and return the served model ids.
    Raises on any transport/shape failure (the caller retries)."""
    req = urllib.request.Request(
        gateway_url(port) + "/v1/models",
        headers={"Authorization": f"Bearer {master_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - localhost
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", []) if isinstance(payload, dict) else []
    return [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]


_default_models_prober = _http_models_probe  # injectable seam — tests stub this


def _http_model_info(port: int, master_key: str, timeout: float = 5.0) -> list[dict]:
    """GET the live gateway's /model/info deployment listing (same auth as the
    models probe). Each entry carries model_name / litellm_params / model_info;
    the completion probe resolves a response's x-litellm-model-id against
    model_info.id to identify the deployment that actually answered."""
    req = urllib.request.Request(
        gateway_url(port) + "/model/info",
        headers={"Authorization": f"Bearer {master_key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - localhost
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data", []) if isinstance(payload, dict) else []
    return [d for d in data if isinstance(d, dict)]


_default_model_info_prober = _http_model_info  # injectable seam — tests stub this


def _config_model_groups(config_text: str) -> set[str]:
    """The model-group names a generated config routes, parsed from its
    ``- model_name:`` lines (quoted or bare). The parser is deliberately
    narrow — it reads OUR deterministic generator output, and a coupling test
    pins it against the real ``build_gateway_config`` so a generator shape
    change breaks the test instead of silently blinding staleness detection."""
    groups: set[str] = set()
    for raw in config_text.splitlines():
        line = raw.strip()
        if line.startswith("- model_name:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            if value:
                groups.add(value)
    return groups


def _config_model_routes(config_text: str) -> list[tuple[str, str]]:
    """The (model_name, route) pairs a generated config prescribes — every
    entry INCLUDING wildcard patterns (the ``"*"`` → ``anthropic/*``
    catch-all), parsed from OUR deterministic generator output: a
    ``- model_name:`` line binds to the first ``model:`` line that follows
    it. Deliberately narrow, like ``_config_model_groups``; a coupling test
    pins it against the real ``build_gateway_config`` so a generator shape
    change breaks the test instead of silently blinding route-contradiction
    staleness (v3.41.0 iteration 7)."""
    pairs: list[tuple[str, str]] = []
    pending: Optional[str] = None
    for raw in config_text.splitlines():
        line = raw.strip()
        if line.startswith("- model_name:"):
            value = line.split(":", 1)[1].strip().strip('"').strip("'")
            pending = value or None
        elif pending and line.startswith("model:"):
            route = line.split(":", 1)[1].strip().strip('"').strip("'")
            if route:
                pairs.append((pending, route))
            pending = None
    return pairs


def _served_state_staleness(
    generated_config: str,
    deployments: list[dict],
    expected_upstreams: dict[str, str],
) -> Optional[str]:
    """Judge whether the RUNNING gateway serves the GENERATED config — the
    iteration-3 (SR-glm-fix-iter3) authoritative staleness trigger, rebuilt
    in iteration 7 (SR-glm-fix-iter7) as a ROUTE-CONTRADICTION comparison.
    The name-set diff it replaces false-staled a FRESH instance: /model/info
    advertises the catch-all's wildcard EXPANSIONS (23 anthropic/<id> groups
    in the deploy-6 forensics) which membership arithmetic reads as unrouted
    extras — the accelerant behind the forced restarts and their race
    windows — while bare NAME matching would blind the true stale marker
    (the catch-all matches its NAME; only its serving ROUTE contradicts).

    TWO-ARMED (the B4 auditor's pin 2), pure, hermetic:

      * served→config — each served group's SERVING ROUTE must agree with
        the config's prescription for that name. An EXPLICITLY routed name
        compares against its explicit route ONLY (explicit precedence: the
        spawn alias absorbed by the catch-all's real-Anthropic expansion is
        a contradiction even though ``anthropic/*`` matches it); any other
        name is routed iff some config pattern pair matches BOTH the name
        and the serving route (wildcard patterns are read from the generated
        config at comparison time — provider-neutral, never hard-coded).
      * config→served completeness — every explicitly-routed config group
        must be present in the served state; a stale process missing a newly
        added explicit route silently absorbs that alias into its catch-all.

    Returns a staleness description naming every mismatch, or None. Served
    groups named ``*`` are skipped (the pattern advertisement itself, not a
    deployment; its /model/info representation varies by LiteLLM version)."""
    explicit: dict[str, str] = {}
    patterns: list[tuple[str, str]] = []
    for name, route in _config_model_routes(generated_config):
        if "*" in name:
            patterns.append((name, route))
        else:
            explicit.setdefault(name, route)
    served: dict[str, list[str]] = {}
    for dep in deployments:
        name = dep.get("model_name")
        if not isinstance(name, str) or not name.strip() or "*" in name:
            continue
        params = dep.get("litellm_params")
        upstream = params.get("model") if isinstance(params, dict) else None
        served.setdefault(name.strip(), []).append(
            upstream if isinstance(upstream, str) and upstream
            else "<unknown upstream>")
    reasons: list[str] = []
    missing = sorted(set(explicit) - set(served))
    if missing:
        reasons.append("generated group(s) the running gateway does not "
                       "serve: " + ", ".join(missing))
    contradicted: set[str] = set()
    unrouted: list[str] = []
    for name in sorted(served):
        routes = served[name]
        if name in explicit:
            bad = sorted({r for r in routes if r != explicit[name]})
            if bad:
                reasons.append(
                    f"{name} is served by {', '.join(bad)} — the generated "
                    f"config routes {explicit[name]}")
                contradicted.add(name)
            continue
        if any(not any(fnmatch.fnmatchcase(name, pn)
                       and fnmatch.fnmatchcase(r, pr)
                       for pn, pr in patterns)
               for r in set(routes)):
            unrouted.append(name)
    if unrouted:
        reasons.append(
            "served group(s) the generated config does not route: "
            + ", ".join(sorted(unrouted))
            + " (no explicit route, and the serving route matches no config "
              "route pattern — a consistent catch-all expansion would)")
    for alias in sorted(expected_upstreams):
        if alias in explicit or alias in contradicted:
            continue  # already judged by the served→config arm
        expected = expected_upstreams[alias]
        upstreams = served.get(alias)
        if upstreams is None or expected in upstreams:
            continue
        reasons.append(
            f"{alias} is served by {', '.join(sorted(set(upstreams)))} — "
            f"the generated config routes {expected}")
    return "; ".join(reasons) if reasons else None


def _assert_expected_deployment(
    served_id: str, deployments: list[dict], expected_upstream: str
) -> str:
    """Assert the deployment that served a completion (its x-litellm-model-id)
    maps to ``expected_upstream`` — the registry-derived dialect route computed
    at probe time, never a constant. Pure (hermetic tests exercise it
    directly). Returns the observed upstream on match; raises ValueError
    naming the observed upstream on mismatch — e.g. "served by
    anthropic/claude-haiku-4-5, expected hosted_vllm/glm-5.2", the exact B6
    incident shape (the anthropic/* wildcard's dynamically-instantiated
    real-Haiku deployment answering the spawn alias)."""
    for dep in deployments:
        info = dep.get("model_info")
        if not (isinstance(info, dict) and info.get("id") == served_id):
            continue
        params = dep.get("litellm_params")
        observed = params.get("model") if isinstance(params, dict) else None
        if observed == expected_upstream:
            return observed
        raise ValueError(
            f"served by {observed or 'an unknown upstream'}, expected "
            f"{expected_upstream} (deployment {served_id})")
    raise ValueError(
        f"deployment {served_id} absent from /model/info — cannot verify the "
        f"serving upstream (expected {expected_upstream})")


def _http_completion_probe(
    port: int, master_key: str, model: str, timeout: float = 30.0,
    expected_upstream: Optional[str] = None,
) -> str:
    """POST a bounded Anthropic-format completion to the live gateway's
    /v1/messages and return the first non-empty content-block text (thinking
    blocks count — some secondary models spend tiny budgets thinking). Raises
    on any transport/shape failure or an empty completion; the caller falls
    back / retries. max_tokens stays tiny: this proves the HOP, not quality.

    v3.41.0 iteration 2 (SR-glm-fix-iter2): a bare completion is UPSTREAM-
    BLIND — the B6 witness caught the anthropic/* wildcard serving real Haiku
    to the spawn alias (6/6 probes, real-Haiku response cost) while setup
    reported the split live. When ``expected_upstream`` is given, the
    response's ``x-litellm-model-id`` is resolved through GET /model/info and
    the serving deployment's ``litellm_params.model`` must equal it; any other
    deployment fails the probe with the observed upstream named."""
    body = json.dumps({
        "model": model,
        "max_tokens": 32,
        "messages": [{"role": "user", "content": "Reply with the word: ok"}],
    }).encode("utf-8")
    req = urllib.request.Request(
        gateway_url(port) + "/v1/messages",
        data=body,
        headers={
            "Authorization": f"Bearer {master_key}",
            "x-api-key": master_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - localhost
        served_id = resp.headers.get("x-litellm-model-id")
        payload = json.loads(resp.read().decode("utf-8"))
    blocks = payload.get("content") if isinstance(payload, dict) else None
    completion_text: Optional[str] = None
    if isinstance(blocks, list):
        for block in blocks:
            if not isinstance(block, dict):
                continue
            text = block.get("text") or block.get("thinking") or ""
            if isinstance(text, str) and text.strip():
                completion_text = text.strip()
                break
    if completion_text is None:
        raise ValueError("completion returned no non-empty content block")
    if expected_upstream:
        if not served_id:
            raise ValueError(
                "completion response carried no x-litellm-model-id header — "
                f"cannot verify the serving deployment "
                f"(expected {expected_upstream})")
        _assert_expected_deployment(
            served_id, _http_model_info(port, master_key), expected_upstream)
    return completion_text


_default_completion_prober = _http_completion_probe  # injectable seam — tests stub this


def _http_auth_enforcement_probe(port: int, timeout: float = 10.0) -> tuple[bool, str]:
    """v3.41.0 iteration 5 (SR-glm-fix-iter5, arms corrected in iteration
    5b): prove the serving process ENFORCES the master key. The deploy-4
    zombie loaded the same config file with a BROKEN env (master key
    unresolvable), passed every state-match probe, and failed every real
    session token into LiteLLM's no-DB 400/500 path. The rung's question is
    "was the deliberately-invalid key DENIED SERVICE?": a 4xx is clean
    enforcement; a crash-5xx is ALSO enforcement — service was denied — but
    via the LiteLLM no-DB prisma quirk (a failed auth falls into a database
    token lookup with no DB configured; see the README gateway
    troubleshooting note), so it returns True with a NAMED WARNING rather
    than failing. Iteration 5b's captured evidence: a DB-less LiteLLM — every
    healthy CT6 install — ALWAYS answers an invalid key with the prisma
    crash-500 and cannot emit a clean 4xx, so a 5xx-FAIL arm would fail-close
    every healthy install. Only a 200 (service GRANTED to a bad key — exactly
    the env-broken-zombie state) FAILS. The probe key is random and NEVER
    echoed, logged, or included in any detail string (the _mask posture,
    applied as total omission). Returns ``(enforced, detail)``; never
    raises."""
    bogus = "sk-ct6-auth-probe-" + secrets.token_urlsafe(12)
    req = urllib.request.Request(
        gateway_url(port) + "/v1/models",
        headers={"Authorization": f"Bearer {bogus}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout):  # nosec - localhost
            pass
    except urllib.error.HTTPError as exc:
        if 400 <= exc.code < 500:
            return True, ("auth enforcement VERIFIED — a deliberately-invalid "
                          f"key was rejected with HTTP {exc.code}")
        return True, (
            "auth enforcement HELD with a named warning — the deliberately-"
            f"invalid key was DENIED service, but via a crash (HTTP "
            f"{exc.code}) rather than a clean 4xx: the LiteLLM no-DB prisma "
            "quirk (a failed auth falls into a database token lookup with "
            "no DB configured; see the README gateway troubleshooting note; "
            "every DB-less gateway answers an invalid key this way)")
    except Exception as exc:
        return False, f"the auth-enforcement probe could not run ({exc})"
    return False, (
        "auth is NOT ENFORCED — the gateway ACCEPTED a deliberately-invalid "
        "key (HTTP 200): the serving process is not enforcing the master key "
        "(an env-broken instance whose master key never resolved — the "
        "deploy-4 zombie state)")


_default_auth_prober = _http_auth_enforcement_probe  # injectable seam — tests stub this


def confirm_gateway_serving(
    port: int,
    master_key: str,
    expect: list[str],
    prober=None,
    attempts: Optional[int] = None,
    delay: Optional[float] = None,
    sleeper=time.sleep,
    completion_models: Optional[list[str]] = None,
    completion_prober=None,
    expected_upstream: Optional[str] = None,
    mandatory_completion_model: Optional[str] = None,
    auth_prober=None,
) -> tuple[bool, str]:
    """Poll the live gateway until every id in ``expect`` is served, or the
    attempts run out. Returns ``(ok, detail)`` — detail names what's missing
    or why the gateway was unreachable. Never raises. ``attempts``/``delay``
    default to the module constants AT CALL TIME (tests monkeypatch them).

    v3.41.0 (the wrong-hop fix): a /v1/models listing proves model LISTING,
    not completion SERVING — the exact gap that let setup print "CONFIRMED
    live" while every real call 404'd. When ``completion_models`` is given,
    a passing listing must ALSO produce a real bounded /v1/messages completion
    through the same gateway: candidates are tried in order (the spawn alias
    first, falling back to the neutral alias) and the first alias returning a
    non-empty content block wins. Both probes ride injectable seams, so
    key-less CI stays hermetic.

    Iteration 2 (SR-glm-fix-iter2): ``expected_upstream`` — the registry-
    derived dialect route computed at the call site — is handed to the
    completion prober, which must verify the SERVING DEPLOYMENT against it
    (x-litellm-model-id resolved via /model/info). A wildcard-served
    completion now fails the candidate with the observed upstream named in
    the detail instead of confirming a hop the secondary never answered.

    Iteration 3 (SR-glm-fix-iter3): ``mandatory_completion_model`` names the
    candidate whose completion + identity verification is REQUIRED — its
    failure fails the whole confirm without trying any later candidate, and
    a completion that arrived via a different alias is rejected. The second
    deploy went green via the ct6-secondary fallback (correct in BOTH the old
    and new configs, so TRUE but irrelevant) while the spawn alias — the id
    the harness actually spawns — was still anthropic-served; fallback green
    is now reserved for legacy call shapes that declare no mandatory
    candidate (a pre-spawn-alias state whose config never routed one).

    Iteration 5 (SR-glm-fix-iter5, arms corrected in iteration 5b): a
    confirmed completion must ALSO prove auth is ENFORCED — ``auth_prober``
    (default: the invalid-key probe on the same injectable-seam discipline)
    must report that a deliberately-invalid key was DENIED service. A 4xx
    denial is clean; a crash-5xx denial is enforcement-with-a-named-warning
    (the LiteLLM no-DB prisma quirk — every healthy DB-less CT6 gateway
    answers this way, so it PROCEEDS with the warning carried into the
    success detail); only a 200 (service granted to a bad key — exactly the
    env-broken-zombie state the deploy-4 aftermath exposed) fails the
    confirm, immediately and naming the auth state — a broken auth env is
    deterministic per instance, not a cold-start transient worth re-polling
    (the install's one restart repair cycle is the remediation: a fresh
    instance re-reads gateway.env). ORDERING PIN (the 5b auditor note): the
    auth rung fires ONLY after the real-key completion rung has passed in
    the same iteration (and never on the /v1/models-only legacy shape, which
    stays byte-identical), so the 5xx-warn can only ever accompany a
    proven-serving instance — a down gateway can never surface a
    5xx-warn green."""
    prober = prober or _default_models_prober
    completion_prober = completion_prober or _default_completion_prober
    auth_prober = auth_prober or _default_auth_prober
    attempts = CONFIRM_ATTEMPTS if attempts is None else attempts
    delay = CONFIRM_DELAY if delay is None else delay
    last = "no probe attempted"
    for i in range(max(1, attempts)):
        try:
            served = prober(port, master_key)
            missing = [m for m in expect if m not in served]
            if not missing:
                listing = (f"gateway serving {len(served)} model(s) incl. "
                           + ", ".join(expect))
                if not completion_models:
                    return True, listing
                completion_errors: list[str] = []
                confirmed = None
                for alias in completion_models:
                    try:
                        text = completion_prober(
                            port, master_key, alias,
                            expected_upstream=expected_upstream)
                        confirmed = (alias, text)
                        break
                    except Exception as exc:
                        completion_errors.append(f"{alias}: {exc}")
                        if alias == mandatory_completion_model:
                            completion_errors.append(
                                f"{alias} is the MANDATORY completion "
                                "candidate (the id the harness actually "
                                "spawns) — no fallback alias may confirm in "
                                "its place")
                            break
                if (confirmed is not None and mandatory_completion_model
                        and confirmed[0] != mandatory_completion_model):
                    completion_errors.append(
                        f"completed via {confirmed[0]} but "
                        f"{mandatory_completion_model} is the MANDATORY "
                        "completion candidate — a fallback completion "
                        "cannot confirm it")
                    confirmed = None
                if confirmed is not None:
                    alias, text = confirmed
                    auth_ok, auth_detail = auth_prober(port)
                    if not auth_ok:
                        return False, (
                            f"{listing}; the /v1/messages completion "
                            f"succeeded via {alias} BUT the auth-enforcement "
                            f"probe FAILED — {auth_detail}")
                    upstream_note = (
                        f", upstream deployment verified = {expected_upstream}"
                        if expected_upstream else "")
                    return True, (
                        f"{listing}; /v1/messages completion CONFIRMED via "
                        f"{alias} ({len(text)} chars{upstream_note}); "
                        f"{auth_detail}. "
                        "Spawn-hop boundary: "
                        "harness teammate-spawn routing is verifiable only "
                        "from a fresh session (spawn a dev-class teammate, "
                        "then check the gateway log).")
                last = ("gateway lists the expected models but the "
                        "/v1/messages completion hop FAILED — "
                        + "; ".join(completion_errors))
            else:
                last = (f"gateway up but NOT serving {', '.join(missing)} "
                        f"(served: {', '.join(served) or 'none'})")
        except Exception as exc:
            last = f"gateway unreachable at {gateway_url(port)} ({exc})"
        if i < attempts - 1:
            sleeper(delay)
    return False, last


def _gui_uid() -> int:
    getuid = getattr(os, "getuid", None)
    return getuid() if getuid else 501


def _windows_port_listener_pid(netstat_text: str, port: int) -> Optional[int]:
    """Parse ``netstat -ano -p tcp`` output for the pid LISTENING on ``port``
    (IPv4 or IPv6 local address; a near-miss port like :14000 never matches
    :4000). Pure and deliberately narrow — returns None when no listener row
    parses, which the caller treats as port-free/cannot-resolve (fail-open;
    the bind verification downstream is the fail-closed backstop)."""
    suffix = f":{port}"
    for raw in netstat_text.splitlines():
        parts = raw.split()
        if (len(parts) >= 5 and parts[0].upper() == "TCP"
                and parts[1].endswith(suffix)
                and parts[3].upper() == "LISTENING"
                and parts[4].isdigit()):
            return int(parts[4])
    return None


def _posix_port_listener_pid(lsof_text: str) -> Optional[int]:
    """First pid line of ``lsof -ti tcp:<port> -sTCP:LISTEN`` output (one
    numeric pid per line; anything else is ignored)."""
    for raw in lsof_text.splitlines():
        line = raw.strip()
        if line.isdigit():
            return int(line)
    return None


def _pid_image(platform_key: str, pid: int, runner=None) -> str:
    """Best-effort image/command name for the honest report row — resolved
    ONLY for reporting, NEVER as a kill precondition (an image-name guard
    would reintroduce launcher-shape special-casing; port ownership is the
    class boundary)."""
    try:
        if platform_key == "windows":
            res = _run(["tasklist", "/fi", f"PID eq {pid}",
                        "/fo", "csv", "/nh"], runner)
            lines = (res.stdout or "").strip().splitlines()
            if res.returncode == 0 and lines and lines[0].startswith('"'):
                return lines[0].split('","')[0].strip('"') or "<unknown image>"
        else:
            res = _run(["ps", "-p", str(pid), "-o", "comm="], runner)
            if res.returncode == 0 and (res.stdout or "").strip():
                return (res.stdout or "").strip().splitlines()[0]
    except OSError:
        pass
    return "<unknown image>"


def _resolve_port_listener(
    platform_key: str, port: int, runner=None,
) -> Optional[tuple[int, str]]:
    """The (pid, image) LISTENING on the gateway's OWN configured port, or
    None when the port is free — or when the listener cannot be resolved
    (missing tool / unparseable output). Cannot-resolve is fail-open by
    design, mirroring the staleness seam: no kill fires on a guess, and the
    bind verification downstream names any residual holder honestly."""
    try:
        if platform_key == "windows":
            res = _run(["netstat", "-ano", "-p", "tcp"], runner)
            pid = (_windows_port_listener_pid(res.stdout or "", port)
                   if res.returncode == 0 else None)
        else:
            res = _run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], runner)
            pid = (_posix_port_listener_pid(res.stdout or "")
                   if res.returncode == 0 else None)
    except OSError:
        return None
    if pid is None:
        return None
    return pid, _pid_image(platform_key, pid, runner)


def _stop_pid(platform_key: str, pid: int, runner=None,
              tree: bool = False) -> tuple[bool, str]:
    """Stop a process by PID ONLY (taskkill /f on Windows, kill -9
    elsewhere), image-agnostic by design: the pid was resolved from LISTENING
    on the gateway's own configured port — or from this state dir's ownership
    proof — in an owner-consented restart, and that resource/ownership basis,
    not a process-name pattern, is the kill's whole basis. ``tree=True``
    (v3.41.0 iteration 7, the DELIBERATE-stop predicate) adds Windows
    ``/t`` — tree-kill semantics, so descendants our enumeration cannot see
    (opaque-cmdline workers) die with their root and no respawn-capable
    orphan survives a cutover/teardown stop. The SWEEP never passes it: a
    tree link the enumeration failed to see must never cascade a sweep kill
    into the serving listener."""
    if platform_key == "windows":
        cmd = ["taskkill", "/pid", str(pid)] + (["/t"] if tree else []) + ["/f"]
    else:
        cmd = ["kill", "-9", str(pid)]
    try:
        res = _run(cmd, runner)
    except OSError as exc:
        return False, str(exc)
    return res.returncode == 0, (res.stderr or res.stdout or "").strip()


def _looks_already_gone(kill_detail: str) -> bool:
    """A failed kill whose detail says the process no longer exists is a
    SUCCESS in tree terms — a root-first tree stop routinely finds later
    members already cascaded down with their root (taskkill: 'not found';
    kill: 'No such process')."""
    lowered = (kill_detail or "").lower()
    return "not found" in lowered or "no such process" in lowered


def _kill_hint(platform_key: str, pid: int) -> str:
    return (f"taskkill /pid {pid} /t /f from an elevated shell"
            if platform_key == "windows" else f"kill -9 {pid}")


# --------------------------------------------------------------------------- #
# v3.41.0 iteration 5 (SR-glm-fix-iter5) — the owned-instance population.
# The fourth deploy's aftermath: 8 accumulated gateway instances (~12 GB) —
# register's start-now half ran `schtasks /run` on EVERY install — and after
# the iteration-4 port-holder kill an env-broken zombie stole the port in the
# race window, passing the state-match bind-verify (same config file) while
# failing every real token. OWNERSHIP identity: a process belongs to THIS
# state dir iff its cmdline carries this state dir's config path (every
# generated launcher passes ``--config <state>/config.yaml``) — image- and
# launcher-agnostic (litellm console script, python -m, any future wrapper),
# and scoped: other state dirs' gateways and unrelated litellm processes
# never match. This is deliberately a DIFFERENT identity key from the
# iteration-4 port-holder stop (resource-based: whoever holds the port blocks
# it regardless of identity); the two cover each other's blind spots.
# --------------------------------------------------------------------------- #

_WINDOWS_PROCESS_LIST_CMD = [
    # CIM, not wmic: wmic is removed from current Windows 11 builds. One
    # "pid|ppid|creation|cmdline" line per process (v3.41.0 iteration 7:
    # ParentProcessId + CreationDate.ToFileTimeUtc feed tree-based instance
    # identity — the parse splits on the first THREE pipes so a cmdline
    # containing '|' survives; creation is a sortable FILETIME integer used
    # to sever recycled-pid parent links).
    "powershell", "-NoProfile", "-Command",
    "Get-CimInstance Win32_Process | ForEach-Object "
    "{ $c = if ($_.CreationDate) { $_.CreationDate.ToFileTimeUtc() } "
    "else { '' }; "
    "'{0}|{1}|{2}|{3}' -f $_.ProcessId, $_.ParentProcessId, $c, "
    "$_.CommandLine }",
]

def _windows_process_rows(text: str) -> list[tuple[int, Optional[int], Optional[int], str]]:
    """Parse the ``pid|ppid|creation|cmdline`` listing into process rows.
    Pure; garbage lines are ignored (a fail-open empty parse means 'no owned
    instances found', and the downstream ownership checks stay honest about
    what they could see). Legacy two-field ``pid|cmdline`` rows still parse
    — ppid/creation None — so a listing without tree columns degrades to
    one-node trees (the pre-iteration-7 per-pid identity), never to a
    guessed tree."""
    out: list[tuple[int, Optional[int], Optional[int], str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "|" not in line:
            continue
        parts = line.split("|", 3)
        if not parts[0].strip().isdigit():
            continue
        pid = int(parts[0].strip())
        if (len(parts) == 4
                and (parts[1].strip().isdigit() or not parts[1].strip())
                and (parts[2].strip().isdigit() or not parts[2].strip())):
            ppid = int(parts[1].strip()) if parts[1].strip() else None
            created = int(parts[2].strip()) if parts[2].strip() else None
            out.append((pid, ppid, created, parts[3].strip()))
        else:
            out.append((pid, None, None, line.split("|", 1)[1].strip()))
    return out


def _posix_process_rows(text: str) -> list[tuple[int, Optional[int], Optional[int], str]]:
    """Parse ``ps -axo pid=,ppid=,args=`` output into process rows (no
    creation ordinal on POSIX — the auditor-accepted ppid basis). Legacy
    ``<pid> <args>`` rows (no ppid column) still parse with ppid None."""
    out: list[tuple[int, Optional[int], Optional[int], str]] = []
    for raw in text.splitlines():
        parts = raw.strip().split(None, 2)
        if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
            out.append((int(parts[0]), int(parts[1]), None, parts[2].strip()))
        elif len(parts) >= 2 and parts[0].isdigit():
            out.append((int(parts[0]), None, None,
                        raw.strip().split(None, 1)[1].strip()))
    return out


def _windows_pid_cmdlines(text: str) -> list[tuple[int, str]]:
    """The (pid, cmdline) projection of the Windows process listing —
    the iteration-5 ownership-matching shape."""
    return [(pid, cmd) for pid, _pp, _cr, cmd in _windows_process_rows(text)]


def _posix_pid_cmdlines(text: str) -> list[tuple[int, str]]:
    """The (pid, cmdline) projection of the POSIX process listing."""
    return [(pid, cmd) for pid, _pp, _cr, cmd in _posix_process_rows(text)]


def _process_table(
    platform_key: str, runner=None,
) -> Optional[list[tuple[int, Optional[int], Optional[int], str]]]:
    """The live process table as rows, or None when it could NOT be
    enumerated (missing tool / listing failure): fail-open, mirroring the
    port-listener seam — no kill fires on a guess, and tree grouping
    degrades to one-node trees rather than inventing membership."""
    try:
        if platform_key == "windows":
            res = _run(_WINDOWS_PROCESS_LIST_CMD, runner)
            if res.returncode != 0:
                return None
            return _windows_process_rows(res.stdout or "")
        res = _run(["ps", "-axo", "pid=,ppid=,args="], runner)
        if res.returncode != 0:
            return None
        return _posix_process_rows(res.stdout or "")
    except OSError:
        return None


def _normalize_cmdline_path_text(text: str) -> str:
    """Path-comparison normal form for cmdline matching: case-folded with
    forward-slash separators (Windows paths are case-insensitive and appear
    with either separator in real cmdlines)."""
    return text.replace("\\", "/").lower()


def _windows_short_path(path: Path) -> Optional[str]:  # pragma: no cover - live Windows only
    """The 8.3 short form of an existing path (GetShortPathNameW), or None.
    Best-effort by design: on failure the long-form match key still stands."""
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(1024)
        n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 1024)
        if 0 < n < 1024 and buf.value:
            return buf.value
    except Exception:
        return None
    return None


_default_short_path_fn = _windows_short_path  # injectable seam — tests stub this


def _config_match_keys(platform_key: str, base: Path,
                       short_path_fn=None) -> set[str]:
    """The normalized substrings that PROVE a process was launched against
    THIS state dir: the config path's long form, plus (Windows, per the B4
    auditor note) its 8.3 short form when resolvable — a cmdline like
    ``C:\\Users\\PAUL~1\\.ARCHI~1\\gateway\\config.yaml`` must still match.
    A mixed short/long component form that GetShortPathNameW does not emit is
    the documented residual; the port-holder stop and the start-ownership
    check backstop it."""
    config_path = base / CONFIG_NAME
    keys = {_normalize_cmdline_path_text(str(config_path))}
    if platform_key == "windows":
        short_path_fn = short_path_fn or _default_short_path_fn
        try:
            short = short_path_fn(config_path)
        except Exception:
            short = None
        if short:
            keys.add(_normalize_cmdline_path_text(str(short)))
    return keys


def _owned_from_table(
    platform_key: str, base: Path,
    table: list[tuple[int, Optional[int], Optional[int], str]],
    short_path_fn=None,
) -> list[tuple[int, str]]:
    """The OWNED projection of a process table: every row whose cmdline
    carries this state dir's config path, our own pid excluded."""
    keys = _config_match_keys(platform_key, base, short_path_fn)
    self_pid = os.getpid()
    return [(pid, cmd) for pid, _pp, _cr, cmd in table
            if pid != self_pid
            and any(k in _normalize_cmdline_path_text(cmd) for k in keys)]


def _owned_gateway_instances(
    platform_key: str, base: Path, runner=None, short_path_fn=None,
) -> Optional[list[tuple[int, str]]]:
    """Every live process whose cmdline carries this state dir's config path
    — ``[(pid, cmdline), ...]``, our own pid excluded. None means the
    population could NOT be enumerated (missing tool / listing failure):
    fail-open, mirroring the port-listener seam — no kill fires on a guess,
    and the callers say so instead of claiming an empty population."""
    table = _process_table(platform_key, runner)
    if table is None:
        return None
    return _owned_from_table(platform_key, base, table, short_path_fn)


# --------------------------------------------------------------------------- #
# v3.41.0 iteration 7 (SR-glm-fix-iter7) — tree-based instance identity.
# Deploy-6 forensics: the sweep kept listener pid 54032 (python.exe) and
# stopped pid 30828 (litellm.exe) as a non-holder — but they were the SAME
# instance (cmd → litellm.exe → python.exe); killing the parent killed the
# listener and the port went dark a second time (the iteration-5 deploy's
# kill of 81780/9716 was the same class). An owned INSTANCE is a process
# TREE: pids grouped by parent chain, membership bounded to INSTANCE-
# AFFILIATED processes — cmdline carries this state dir's path (the config
# file or the generated launcher living under it) — so a user's interactive
# shell and every system ancestor (svchost, explorer) never joins a tree,
# and two separate instances never merge through a shared service parent.
# Parent links are validated against pid reuse (Windows: a "parent" whose
# creation FILETIME is later than its child's is a recycled pid — link
# severed, the child roots its own tree; POSIX: ppid, auditor-accepted); a
# dead root leaves the tree rooted at the surviving ancestor. Two stop
# predicates (the B4 auditor's pin 1): the SWEEP is port-holder-tree IMMUNE,
# while DELIBERATE port-freeing stops act on the holder's WHOLE tree
# root-first with tree-kill semantics.
# --------------------------------------------------------------------------- #


def _affiliation_keys(platform_key: str, base: Path,
                      short_path_fn=None) -> set[str]:
    """The normalized substrings that mark a process INSTANCE-AFFILIATED:
    its cmdline references this state dir's path at all — the config file
    (ownership proper) or the generated launcher (``cmd /c
    <base>/run_gateway.bat``, the tree root of every launcher-started
    instance). Broader than ``_config_match_keys`` by design: affiliation
    only ever BOUNDS tree membership; it never selects a kill target by
    itself."""
    keys = {_normalize_cmdline_path_text(str(base))}
    if platform_key == "windows":
        short_path_fn = short_path_fn or _default_short_path_fn
        try:
            short = short_path_fn(base)
        except Exception:
            short = None
        if short:
            keys.add(_normalize_cmdline_path_text(str(short)))
    return keys


def _instance_tree(
    seed: int,
    table: Optional[list[tuple[int, Optional[int], Optional[int], str]]],
    keys: set[str],
) -> list[int]:
    """The instance tree containing ``seed``, ordered ROOT-FIRST — the
    connected component of the validated parent-link graph restricted to
    instance-affiliated pids (plus the seed itself, which belongs even when
    its own cmdline is opaque). Falls back to the one-node tree ``[seed]``
    when the table is unavailable — the pre-iteration-7 per-pid identity,
    never a guessed tree. Our own pid never joins (the installer spawns the
    staged instance, so an affiliated installer would otherwise root the
    staged tree and a teardown would kill the installer itself)."""
    if not table:
        return [seed]
    by_pid: dict[int, tuple[Optional[int], Optional[int], str]] = {}
    for pid, ppid, created, cmd in table:
        by_pid.setdefault(pid, (ppid, created, cmd))
    if seed not in by_pid:
        return [seed]
    self_pid = os.getpid()
    members = {seed} | {
        pid for pid, (_pp, _cr, cmd) in by_pid.items()
        if pid != self_pid
        and any(k in _normalize_cmdline_path_text(cmd) for k in keys)}

    def vparent(pid: int) -> Optional[int]:
        ppid, created, _cmd = by_pid[pid]
        if ppid is None or ppid == pid or ppid not in by_pid:
            return None
        if ppid not in members:
            return None
        p_created = by_pid[ppid][1]
        if (created is not None and p_created is not None
                and p_created > created):
            return None  # recycled pid: the "parent" was born after the child
        return ppid

    children: dict[int, list[int]] = {}
    parent_of: dict[int, Optional[int]] = {}
    for pid in members:
        p = vparent(pid)
        parent_of[pid] = p
        if p is not None:
            children.setdefault(p, []).append(pid)
    component = {seed}
    frontier = [seed]
    while frontier:
        cur = frontier.pop()
        neighbors = list(children.get(cur, []))
        if parent_of.get(cur) is not None:
            neighbors.append(parent_of[cur])
        for nxt in neighbors:
            if nxt not in component:
                component.add(nxt)
                frontier.append(nxt)
    root = seed
    while parent_of.get(root) is not None and parent_of[root] in component:
        root = parent_of[root]
    ordered = [root]
    queue = [root]
    while queue:
        cur = queue.pop(0)
        for child in sorted(children.get(cur, [])):
            if child in component and child not in ordered:
                ordered.append(child)
                queue.append(child)
    for pid in sorted(component):  # a severed-link island still gets stopped
        if pid not in ordered:
            ordered.append(pid)
    return ordered


def _stop_holder_tree(
    platform_key: str, base: Path, pid: int, runner=None,
    exclude: Optional[set[int]] = None,
) -> tuple[bool, str, list[int]]:
    """The DELIBERATE port-freeing stop (pin 1's second predicate): stop the
    holder's WHOLE instance tree, root-first, with tree-kill semantics —
    no respawn-capable orphan may survive a cutover/repair/teardown stop.
    ``exclude`` shields the LIVE instance's tree during a staging teardown.
    Returns ``(holder_stopped, holder_kill_detail, tree)``: the holder's own
    verdict gates the caller (a member already cascaded down with its root
    counts as stopped); non-holder refusals ride the caller's residual
    checks and the next run's sweep."""
    exclude = exclude or set()
    table = _process_table(platform_key, runner)
    tree = [p for p in _instance_tree(
        pid, table, _affiliation_keys(platform_key, base)) if p not in exclude]
    holder_stopped, holder_detail = False, "the holder was excluded"
    for member in tree:
        killed, detail = _stop_pid(platform_key, member, runner, tree=True)
        if not killed and _looks_already_gone(detail):
            killed = True
        if member == pid:
            holder_stopped, holder_detail = killed, detail
    return holder_stopped, holder_detail, tree


def _exactly_one_owned_start_gate(
    platform_key: str, base: Path, port: int, runner=None,
) -> tuple[bool, list[str]]:
    """The iteration-5 exactly-one-instance gate for register's start-now
    half, tree-aware since iteration 7 (SR-glm-fix-iter7). Sweeps every
    OWNED instance that is not part of the SERVING TREE (the accumulated-
    zombie population), then decides whether the one start may fire: never
    over a held port — an owned holder keeps serving (a blind re-start was
    the accumulation source), a foreign holder is left to the verified
    restart's port-holder stop (starting over it would only leak a doomed
    instance). PIN 1 (sweep direction): the sweep NEVER touches any pid in
    the port-holder's tree — deploy-6 stopped the listener's parent
    (litellm.exe) as a 'non-holder' and killed the listener with it; port
    dark. Kills are per-pid (never /t — a tree link the enumeration failed
    to see must never cascade into the listener), root-first within each
    disjoint zombie tree. Returns ``(should_start, notes)``; every stop,
    keep, and skip is named honestly (pid + image), refusals with a
    remediation."""
    notes: list[str] = []
    table = _process_table(platform_key, runner)
    owned = (_owned_from_table(platform_key, base, table)
             if table is not None else None)
    holder = _resolve_port_listener(platform_key, port, runner)
    aff_keys = _affiliation_keys(platform_key, base)
    holder_tree: set[int] = set()
    if holder is not None:
        holder_tree = set(_instance_tree(holder[0], table, aff_keys))
    owned_pids = {p for p, _ in (owned or [])}
    keep: Optional[int] = None
    if (holder is not None and owned is not None
            and (holder[0] in owned_pids or (owned_pids & holder_tree))):
        keep = holder[0]
    swept: set[int] = set()
    for pid, _cmd in (owned or []):
        if pid == keep or pid in swept:
            continue
        if pid in holder_tree:
            notes.append(
                f"kept owned instance pid {pid} "
                f"({_pid_image(platform_key, pid, runner)}) — it is in the "
                f"port-holder's process tree (pid {holder[0]}): killing any "
                f"member of the serving tree can take the listener down "
                f"(the deploy-6 tree-kill incident)")
            continue
        zombie_tree = _instance_tree(pid, table, aff_keys)
        for member in zombie_tree:  # root-first; owned members only
            if member in swept or member not in owned_pids:
                continue
            if member == keep or member in holder_tree:
                continue  # structurally disjoint, but never on a guess
            swept.add(member)
            image = _pid_image(platform_key, member, runner)
            killed, kill_detail = _stop_pid(platform_key, member, runner)
            if not killed and _looks_already_gone(kill_detail):
                killed = True
            if killed:
                notes.append(
                    f"stopped owned instance pid {member} ({image}) — its "
                    f"cmdline runs this state dir's {CONFIG_NAME} and its "
                    f"process tree is not the one serving port {port} "
                    f"(exactly-one-instance sweep)")
            else:
                notes.append(
                    f"stopping owned instance pid {member} ({image}) was "
                    f"REFUSED ({kill_detail or 'no detail'}) — stop it "
                    f"manually ({_kill_hint(platform_key, member)})")
    if holder is None:
        return True, notes
    h_pid, h_image = holder
    if keep is not None:
        notes.append(
            f"start skipped — an owned instance already serves port {port} "
            f"(pid {h_pid}, {h_image}); a blind re-start would accumulate "
            f"instances (the 8-instance incident)")
        return False, notes
    notes.append(
        f"start skipped — port {port} is held by pid {h_pid} ({h_image}), "
        f"which this state dir does not own; starting over a held port would "
        f"only leak a doomed instance (the verified restart repair stops the "
        f"holder by pid first)")
    return False, notes


def _tracked_launched_pid(platform_key: str, name: str = SERVICE_NAME,
                          runner=None) -> Optional[int]:
    """The pid of the instance the tracked launcher just started, where the
    launcher EXPOSES it: systemd's MainPID, launchd's ``launchctl print`` pid
    row. schtasks and the detached shim are pid-opaque — None, and the caller
    falls back to the launch-window match (a NEW owned pid that appeared
    across the start; the B4 auditor's documented per-launcher seam)."""
    try:
        if platform_key == "linux":
            res = _run(["systemctl", "--user", "show", "-p", "MainPID",
                        "--value", name], runner)
            val = (res.stdout or "").strip()
            if res.returncode == 0 and val.isdigit() and int(val) > 0:
                return int(val)
        elif platform_key == "darwin":
            res = _run(["launchctl", "print", f"gui/{_gui_uid()}/{name}"],
                       runner)
            if res.returncode == 0:
                for raw in (res.stdout or "").splitlines():
                    line = raw.strip().replace(" ", "")
                    if line.startswith("pid=") and line[4:].isdigit():
                        return int(line[4:])
    except OSError:
        return None
    return None


def _judge_bound_instance(
    port_pid: Optional[int],
    launcher_pid: Optional[int],
    pre_owned: Optional[set[int]],
    post_owned: Optional[set[int]],
) -> tuple[str, str]:
    """The iteration-5 start-ownership judgment — WHO holds the port after
    the one start, where iteration 4's bind-verify judged only WHAT is served
    (the deploy-4 zombie re-bound first with the SAME config file and passed
    the state match while its broken env failed every real token). Pure;
    returns ``(verdict, note)`` with verdict one of:

      * ``verified``   — the port-holder IS the just-launched instance
                         (direct launcher pid, or the launch-window match:
                         an owned pid that appeared across the start);
      * ``raced``      — the port-holder is positively NOT the just-launched
                         instance (a pre-existing owned zombie, or a process
                         outside the launch window) — a named failure;
      * ``unresolved`` — identity could not be established (port listener or
                         population unresolvable): fail-open with the honest
                         note, mirroring the iteration-4 resolution posture —
                         the served-state match remains the fail-closed
                         backstop."""
    if port_pid is None:
        return "unresolved", (
            "bound-instance identity unresolved (the port listener could "
            "not be resolved) — verified on the served state only")
    if launcher_pid is not None and port_pid == launcher_pid:
        return "verified", (
            f"bound by the just-launched instance (pid {port_pid})")
    if pre_owned is not None and post_owned is not None:
        if port_pid in (post_owned - pre_owned):
            return "verified", (
                f"bound by the just-launched instance (pid {port_pid}, "
                f"launch-window match)")
        if port_pid in pre_owned:
            return "raced", (
                f"port claimed by pid {port_pid} — a PRE-EXISTING owned "
                f"instance, not the one this restart just launched")
        return "raced", (
            f"port claimed by pid {port_pid} — a process outside this "
            f"restart's launch window")
    if launcher_pid is not None:
        return "raced", (
            f"port claimed by pid {port_pid} but the launcher reports the "
            f"just-launched pid as {launcher_pid}")
    return "unresolved", (
        "bound-instance identity unresolved (no launcher-reported pid and "
        "the owned-instance launch window could not be enumerated) — "
        "verified on the served state only")


def _tracked_stop_gateway(platform_key: str, name: str = SERVICE_NAME,
                          runner=None) -> None:
    """The tracked stop half — fire-and-forget (an unregistered or already-
    stopped service is a no-op; the port poll judges the outcome)."""
    if platform_key == "windows":
        _run(["schtasks", "/end", "/tn", name], runner)
    elif platform_key == "linux":
        _run(["systemctl", "--user", "stop", name], runner)
    elif platform_key == "darwin":
        _run(["launchctl", "kill", "SIGTERM", f"gui/{_gui_uid()}/{name}"],
             runner)


def _tracked_start_gateway(platform_key: str, launcher_path: Path,
                           name: str = SERVICE_NAME,
                           runner=None) -> tuple[bool, str]:
    """The tracked start half — the ONE start attempt of a verified restart
    (the Windows detached-spawn fallback is the same single attempt through
    its second mechanism, exactly as the legacy restart behaves)."""
    if platform_key == "windows":
        if _run(["schtasks", "/run", "/tn", name], runner).returncode == 0:
            return True, "scheduled task restarted"
        ok = _spawn_detached(["cmd", "/c", str(launcher_path)])
        return ok, ("launcher restarted (detached)" if ok
                    else "restart failed (no schtasks task; detached spawn failed)")
    if platform_key == "linux":
        res = _run(["systemctl", "--user", "start", name], runner)
        if res.returncode == 0:
            return True, "user systemd unit restarted"
        return False, (res.stderr or "").strip() or "systemctl --user start failed"
    if platform_key == "darwin":
        res = _run(["launchctl", "kickstart", f"gui/{_gui_uid()}/{name}"],
                   runner)
        if res.returncode == 0:
            return True, "launchd agent restarted"
        return False, (res.stderr or "").strip() or "launchctl kickstart failed"
    return False, f"unsupported platform {platform_key!r}"


def _verified_restart_gateway(
    platform_key: str,
    launcher_path: Path,
    name: str,
    runner,
    port: int,
    master_key: str,
    generated_config: str,
    expected_upstreams: dict[str, str],
    sleeper,
) -> tuple[bool, str]:
    """The iteration-4 (SR-glm-fix-iter4) verified restart. The third deploy
    proved the tracked stop is a no-op against an UNTRACKED port-holder (PID
    68724, a manually-started diagnostic instance, survived two 'restarts'
    while each blocked start leaked a doomed litellm zombie). Sequence:

      1. tracked stop, then a bounded grace poll for the port to free;
      2. ONLY when the tracked stop leaves the port held (the ordering the
         B4 auditor pinned — the port-kill must never drift into being the
         primary path): resolve the LISTENING pid on the gateway's own
         configured port and stop THAT pid's WHOLE instance tree, root-first
         with tree-kill semantics (iteration 7, pin 1's deliberate-stop
         predicate — stopping only the listener leaves a respawn-capable
         parent; stopping only a parent was the deploy-6 darkening) —
         image-agnostic; pid+image named honestly on success AND refusal
         (refusal = no start attempted);
      3. ONE tracked start attempt;
      4. bind verification: 'restarted' is reported ONLY after the new
         instance answers /model/info with a state matching the generated
         config (the iteration-3 served-state seam). A still-held port or a
         still-stale serve is a NAMED failure — never a doomed-instance
         spawn loop;
      5. iteration 5 (SR-glm-fix-iter5) start-ownership: the state match
         alone is spoofable — the deploy-4 zombie re-bound the port with the
         SAME config file and passed it while its broken env failed every
         real token. On bind success the port-holding pid is judged against
         the instance this restart just launched (the per-launcher pid where
         the launcher exposes it, else the owned-instance launch-window
         match); a race winner is a NAMED failure, unresolvable identity is
         fail-open with the honest note (``_judge_bound_instance``)."""
    _tracked_stop_gateway(platform_key, name, runner)
    port_attempts = max(1, RESTART_PORT_ATTEMPTS)
    holder: Optional[tuple[int, str]] = None
    for i in range(port_attempts):
        holder = _resolve_port_listener(platform_key, port, runner)
        if holder is None:
            break
        if i < port_attempts - 1:
            sleeper(RESTART_PORT_DELAY)
    stop_note = None
    if holder is not None:
        pid, image = holder
        killed, kill_detail, holder_tree = _stop_holder_tree(
            platform_key, launcher_path.parent, pid, runner)
        if not killed:
            return False, (
                f"the tracked stop left port {port} held by pid {pid} "
                f"({image}) and stopping it by pid was REFUSED "
                f"({kill_detail or 'no detail'}) — no start attempted (a "
                f"blocked start would only leak a doomed instance); stop "
                f"that process manually ({_kill_hint(platform_key, pid)}), "
                f"then re-run the install")
        residual = None
        for i in range(port_attempts):
            residual = _resolve_port_listener(platform_key, port, runner)
            if residual is None:
                break
            if i < port_attempts - 1:
                sleeper(RESTART_PORT_DELAY)
        if residual is not None:
            r_pid, r_image = residual
            return False, (
                f"the tracked stop left port {port} held by pid {pid} "
                f"({image}); the pid stop was issued but the port is STILL "
                f"held (by pid {r_pid} ({r_image})) — no start attempted (a "
                f"blocked start would only leak a doomed instance); stop the "
                f"holder manually ({_kill_hint(platform_key, r_pid)}), then "
                f"re-run the install")
        stop_note = (f"the tracked stop left port {port} held — stopped the "
                     f"untracked holder pid {pid} ({image})")
        if len(holder_tree) > 1:
            stop_note += (
                f" and its whole process tree, root-first "
                f"(pids {', '.join(str(p) for p in holder_tree)}) — a "
                f"deliberate port-freeing stop takes the instance TREE, "
                f"never a lone pid (the deploy-6 tree-kill class)")
    note = f"; {stop_note}" if stop_note else ""
    # Iteration 5: capture the owned population BEFORE the start so the
    # launch-window match can tell the just-launched instance from a zombie
    # (base dir = the launcher's home; every launcher runs <base>/config.yaml).
    pre_owned_list = _owned_gateway_instances(
        platform_key, launcher_path.parent, runner)
    pre_owned = ({p for p, _ in pre_owned_list}
                 if pre_owned_list is not None else None)
    started, start_detail = _tracked_start_gateway(
        platform_key, launcher_path, name, runner)
    if not started:
        return False, start_detail + note
    launcher_pid = _tracked_launched_pid(platform_key, name, runner)
    bind_attempts = max(1, RESTART_BIND_ATTEMPTS)
    last = f"never answered /model/info on port {port}"
    for i in range(bind_attempts):
        try:
            deployments = _default_model_info_prober(port, master_key)
        except Exception as exc:
            last = f"never answered /model/info on port {port} ({exc})"
        else:
            stale = _served_state_staleness(
                generated_config, deployments, expected_upstreams)
            if stale is None:
                holder_now = _resolve_port_listener(platform_key, port, runner)
                post_owned_list = _owned_gateway_instances(
                    platform_key, launcher_path.parent, runner)
                post_owned = ({p for p, _ in post_owned_list}
                              if post_owned_list is not None else None)
                verdict, owner_note = _judge_bound_instance(
                    holder_now[0] if holder_now else None,
                    launcher_pid, pre_owned, post_owned)
                if verdict == "raced":
                    r_pid = holder_now[0] if holder_now else -1
                    r_image = holder_now[1] if holder_now else "<unknown image>"
                    return False, (
                        f"{start_detail} but the restart is NOT verified — "
                        f"{owner_note} ({r_image}): a zombie won the bind "
                        f"race — its served state can match the generated "
                        f"config while its environment is broken (the "
                        f"deploy-4 400 no_db_connection incident); stop it "
                        f"({_kill_hint(platform_key, r_pid)}) and re-run the "
                        f"install; no further start attempted{note}")
                return True, (
                    f"{start_detail}; bind VERIFIED — the new instance on "
                    f"port {port} serves the generated config "
                    f"({owner_note}){note}")
            last = ("still serves a state that does not match the "
                    f"generated config ({stale})")
        if i < bind_attempts - 1:
            sleeper(RESTART_BIND_DELAY)
    return False, (
        f"{start_detail} but the restart is NOT verified — the instance "
        f"{last}; no further start attempted (a held port must never leak "
        f"doomed instances — at most one start per restart); check the "
        f"gateway log{note}")


# --------------------------------------------------------------------------- #
# v3.41.0 iteration 6 (SR-glm-fix-iter6) — verify-then-swap, never dark.
# The 2026-07-18 offline incident: every deploy was stop-then-start on the
# LIVE port — the one every active Claude session routes through — so each
# deploy opened a dark window and a port race, and the eventual winner among
# 8 piled-up instances had an UNRESOLVED master key (LiteLLM's DB-less auth
# fallback answered every request 400 no_db_connection). The fix inverts the
# order: the replacement is PROVEN on a staging port — the full accumulated
# ladder, which structurally proves config AND env health (an unresolved
# master key denies the REAL key service and fails the completion rung) —
# before the serving instance is ever touched. Any staging failure leaves the
# old instance serving. The staging instance is stopped on ALL exit paths
# (green, ladder failure, exception — the B4 auditor's required pin), so
# verify-then-swap can never reintroduce the iteration-5 instance-
# accumulation class on the staging port.
# --------------------------------------------------------------------------- #

STAGING_PORT_OFFSET = 1  # staging port = the gateway's own port + this offset

RECOVERY_PROCEDURE = (
    "RECOVERY (the 2026-07-18 offline-incident procedure): 1) kill every "
    "instance launched against THIS gateway's config — match the config path "
    "in the process cmdline, never a bare image name (Windows PowerShell: "
    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match "
    "'litellm' -and $_.CommandLine -match 'gateway\\\\config\\.yaml' } | "
    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }; POSIX: kill "
    "the pids `ps -axo pid=,args=` lists against <state-dir>/config.yaml); "
    "2) verify the gateway port is free (netstat -ano | findstr :<port> on "
    "Windows, lsof -ti tcp:<port> elsewhere); 3) start exactly ONE instance "
    "via the generated launcher (run_gateway.bat / run_gateway.sh); 4) "
    "verify: python scripts/setup/install_gateway.py status --live")


def _staging_launcher_name(launcher_name: str) -> str:
    """run_gateway.bat -> run_gateway_staging.bat (and the .sh twin)."""
    stem, dot, ext = launcher_name.rpartition(".")
    return f"{stem}_staging.{ext}" if dot else f"{launcher_name}_staging"


def _launch_staging_instance(platform_key: str, staging_path: Path) -> bool:
    """Launch the staged replacement DETACHED, through the generated staging
    launcher — the SAME env-sourcing path the cutover start uses (the
    launcher template itself loads gateway.env; the B4 auditor's launch-path-
    fidelity note), so staging-green predicts the replacement's env, not just
    its config."""
    if platform_key == "windows":
        return _spawn_detached(["cmd", "/c", str(staging_path)])
    return _spawn_detached(["/bin/sh", str(staging_path)])


def _teardown_staging(
    platform_key: str, base: Path, staging_port: int, live_port: int,
    pre_owned: Optional[set[int]], runner=None,
) -> list[str]:
    """Stop the staged instance — the B4 auditor's REQUIRED pin runs this on
    ALL exit paths (green cutover, every ladder-rung failure, exception).
    Two sweeps, neither of which can touch the live instance — iteration 7
    hardens that exclusion to the live holder's whole TREE (a live-instance
    relative appearing inside the staging launch window must never be swept
    as residue; killing any serving-tree member can take the listener down):
    the staging-port holder is stopped with its whole tree (root-first,
    deliberate-stop semantics — a lone-pid stop leaves a respawn-capable
    parent), and any OWNED pid that appeared across the staging launch
    window (a staged instance that never bound, or already lost the staging
    port) is stopped unless it is in the live tree. Returns honest per-stop
    notes; a refusal names the pid + remediation."""
    notes: list[str] = []
    stopped: set[int] = set()
    table = _process_table(platform_key, runner)
    aff_keys = _affiliation_keys(platform_key, base)
    live_holder = _resolve_port_listener(platform_key, live_port, runner)
    live_tree: set[int] = set()
    if live_holder is not None:
        live_tree = set(_instance_tree(live_holder[0], table, aff_keys))
    holder = _resolve_port_listener(platform_key, staging_port, runner)
    if holder is not None:
        pid, image = holder
        killed, kill_detail, holder_tree = _stop_holder_tree(
            platform_key, base, pid, runner, exclude=live_tree)
        if killed:
            stopped.update(holder_tree)
            notes.append(
                f"staging instance stopped (pid {pid}, {image}"
                + (f", with its process tree pids "
                   f"{', '.join(str(p) for p in holder_tree)}"
                   if len(holder_tree) > 1 else "") + ")")
        else:
            notes.append(
                f"stopping the staging instance pid {pid} ({image}) was "
                f"REFUSED ({kill_detail or 'no detail'}) — stop it manually "
                f"({_kill_hint(platform_key, pid)})")
    post_owned_list = _owned_gateway_instances(platform_key, base, runner)
    if post_owned_list is not None and pre_owned is not None:
        for pid, _cmd in post_owned_list:
            if pid in pre_owned or pid in stopped or pid in live_tree:
                continue
            image = _pid_image(platform_key, pid, runner)
            killed, kill_detail = _stop_pid(platform_key, pid, runner,
                                            tree=True)
            if not killed and _looks_already_gone(kill_detail):
                killed = True
            if killed:
                notes.append(
                    f"staging residue stopped (pid {pid}, {image} — launched "
                    f"for staging, never released the launch window)")
            else:
                notes.append(
                    f"stopping staging residue pid {pid} ({image}) was "
                    f"REFUSED ({kill_detail or 'no detail'}) — stop it "
                    f"manually ({_kill_hint(platform_key, pid)})")
    return notes


def _staging_ladder(
    platform_key: str, base: Path, staging_port: int, master_key: str,
    generated_config: str, expected_upstreams: dict[str, str],
    completion_model: str, pre_owned: Optional[set[int]], runner, sleeper,
) -> tuple[bool, str]:
    """The FULL verification ladder re-aimed at the staging port — the same
    provider-neutral rungs the live confirm accumulated across iterations
    2-5b, in the same order: bind + served-state match, staging-bind
    ownership (a stale staging-port squatter cannot answer on behalf of a
    dead staged instance), the REAL-key completion with upstream identity
    (an unresolved master key denies the real key service — the exact
    incident state — and fails HERE, before the live instance is touched),
    then the auth-enforcement rung (which fires only after a passed
    completion, the 5b ordering pin)."""
    bind_attempts = max(1, RESTART_BIND_ATTEMPTS)
    last = f"never answered /model/info on staging port {staging_port}"
    bound = False
    for i in range(bind_attempts):
        try:
            deployments = _default_model_info_prober(staging_port, master_key)
        except Exception as exc:
            last = (f"never answered /model/info on staging port "
                    f"{staging_port} ({exc})")
        else:
            stale = _served_state_staleness(
                generated_config, deployments, expected_upstreams)
            if stale is None:
                bound = True
                break
            last = ("serves a state that does not match the generated "
                    f"config ({stale})")
        if i < bind_attempts - 1:
            sleeper(RESTART_BIND_DELAY)
    if not bound:
        return False, (
            f"the bind/served-state rung FAILED — the staged instance {last}")
    holder_now = _resolve_port_listener(platform_key, staging_port, runner)
    post_owned_list = _owned_gateway_instances(platform_key, base, runner)
    post_owned = ({p for p, _ in post_owned_list}
                  if post_owned_list is not None else None)
    verdict, owner_note = _judge_bound_instance(
        holder_now[0] if holder_now else None, None, pre_owned, post_owned)
    if verdict == "raced":
        return False, (
            f"the staging ownership rung FAILED — {owner_note}: a stale "
            f"staging-port squatter must never answer the ladder on behalf "
            f"of the staged instance")
    try:
        text = _default_completion_prober(
            staging_port, master_key, completion_model,
            expected_upstream=expected_upstreams.get(completion_model))
    except Exception as exc:
        return False, (
            f"the real-key completion rung FAILED on {completion_model} — "
            f"{exc}. The staged instance runs the exact config + env the "
            f"replacement would: a completion DENIED to the real key is the "
            f"2026-07-18 offline-incident state (an unresolved "
            f"{MASTER_KEY_VAR} falls into LiteLLM's DB-less auth fallback — "
            f"400 no_db_connection on everything)")
    auth_ok, auth_detail = _default_auth_prober(staging_port)
    if not auth_ok:
        return False, f"the auth-enforcement rung FAILED — {auth_detail}"
    return True, (
        f"staging VERIFIED on port {staging_port} — bind + served-state "
        f"match, completion via {completion_model} ({len(text)} chars), "
        f"{auth_detail} ({owner_note})")


def _staging_verify(
    platform_key: str, base: Path, staging_port: int, live_port: int,
    master_key: str, generated_config: str,
    expected_upstreams: dict[str, str], completion_model: str,
    runner, sleeper,
) -> tuple[bool, str]:
    """Launch + verify + ALWAYS tear down the staged replacement. The staging
    launcher is generated from the SAME template as the live one (identical
    config file — the config carries no port — with only the launch port
    swapped), so the env-sourcing path is byte-for-byte the cutover start's.
    The teardown runs in ``finally`` — green, ladder failure, or exception —
    the B4 auditor's required pin: verify-then-swap must never reintroduce
    instance accumulation on the staging port."""
    staging_name, staging_body = build_launcher(platform_key, base, staging_port)
    staging_path = base / _staging_launcher_name(staging_name)
    staging_path.write_text(staging_body, encoding="utf-8")
    if not staging_path.name.endswith(".bat"):
        try:
            os.chmod(staging_path, 0o755)
        except OSError:  # pragma: no cover
            pass
    preflight = ""
    holder = _resolve_port_listener(platform_key, staging_port, runner)
    if holder is not None:
        pid, image = holder
        owned = _owned_gateway_instances(platform_key, base, runner)
        if owned is None or pid not in {p for p, _ in owned}:
            return False, (
                f"staging port {staging_port} is held by pid {pid} ({image}), "
                f"which this state dir does not provably own — cannot stage "
                f"the replacement; stop the holder "
                f"({_kill_hint(platform_key, pid)}) or free the port, then "
                f"re-run the install")
        live_holder = _resolve_port_listener(platform_key, live_port, runner)
        live_tree: set[int] = set()
        if live_holder is not None:
            live_tree = set(_instance_tree(
                live_holder[0], _process_table(platform_key, runner),
                _affiliation_keys(platform_key, base)))
        killed, kill_detail, _tree = _stop_holder_tree(
            platform_key, base, pid, runner, exclude=live_tree)
        if not killed:
            return False, (
                f"staging port {staging_port} is held by leaked staging "
                f"residue pid {pid} ({image}) and stopping it was REFUSED "
                f"({kill_detail or 'no detail'}) — stop it manually "
                f"({_kill_hint(platform_key, pid)}), then re-run the install")
        preflight = (f"; cleared leaked staging residue pid {pid} ({image}) "
                     f"from port {staging_port} first")
    pre_owned_list = _owned_gateway_instances(platform_key, base, runner)
    pre_owned = ({p for p, _ in pre_owned_list}
                 if pre_owned_list is not None else None)
    if not _launch_staging_instance(platform_key, staging_path):
        return False, (
            "the staged replacement failed to LAUNCH (detached spawn "
            "failed) — nothing to verify")
    try:
        ok, detail = _staging_ladder(
            platform_key, base, staging_port, master_key, generated_config,
            expected_upstreams, completion_model, pre_owned, runner, sleeper)
    except Exception as exc:  # defensive: a crashed ladder must still tear down
        ok, detail = False, f"the staging ladder crashed ({exc})"
    finally:
        teardown_notes = _teardown_staging(
            platform_key, base, staging_port, live_port, pre_owned, runner)
    if teardown_notes:
        detail = f"{detail} [staging teardown: {'; '.join(teardown_notes)}]"
    return ok, detail + preflight


def _post_cutover_ladder(
    port: int, master_key: str, expected_upstreams: dict[str, str],
    completion_model: str,
) -> tuple[bool, str]:
    """Re-verify the two rungs the cutover machinery does not already prove —
    the real-key completion with upstream identity, then (5b ordering pin)
    the auth-enforcement rung — on the LIVE port. The cutover itself already
    proved bind + served-state + bound-instance ownership; this catches a
    port-race winner whose served state matches while its env is broken (the
    deploy-4 zombie shape) at the moment it matters: after the swap."""
    try:
        text = _default_completion_prober(
            port, master_key, completion_model,
            expected_upstream=expected_upstreams.get(completion_model))
    except Exception as exc:
        return False, (f"the post-cutover completion rung FAILED on "
                       f"{completion_model} — {exc}")
    auth_ok, auth_detail = _default_auth_prober(port)
    if not auth_ok:
        return False, f"the post-cutover auth-enforcement rung FAILED — {auth_detail}"
    return True, (f"post-cutover ladder re-verified — completion via "
                  f"{completion_model} ({len(text)} chars), {auth_detail}")


def _verify_then_swap_restart(
    platform_key: str,
    launcher_path: Path,
    name: str,
    runner,
    port: int,
    master_key: str,
    generated_config: str,
    expected_upstreams: dict[str, str],
    sleeper,
    staging_port: int,
    completion_model: str,
) -> tuple[bool, str]:
    """The iteration-6 (SR-glm-fix-iter6) never-dark deploy: STAGE the
    replacement (identical generated config, staging port, same env-sourcing
    launch path) and run the FULL ladder against it; only on staging-green
    tear staging down and perform the now-low-risk live cutover through the
    EXISTING iteration-4/5 machinery, then re-verify the ladder on the live
    port with ONE bounded retry for a port-race winner (remediated via the
    iteration-4 port-holder stop). ANY staging failure leaves the old
    instance serving and fails honestly, naming the staging failure. Retry
    exhaustion is the one honest-fail path that can leave the box dark — its
    message EMBEDS the codified recovery procedure."""
    base = launcher_path.parent
    staging_ok, staging_detail = _staging_verify(
        platform_key, base, staging_port, port, master_key,
        generated_config, expected_upstreams, completion_model,
        runner, sleeper)
    if not staging_ok:
        return False, (
            f"NEVER-DARK: the serving instance was NOT touched — the staging "
            f"verification failed, so the replacement is unproven and the "
            f"live cutover never started. Staging failure: {staging_detail}")
    retry_note = ""
    last = ""
    for attempt in range(2):  # the ONE bounded post-cutover retry
        ok, detail = _verified_restart_gateway(
            platform_key, launcher_path, name, runner, port, master_key,
            generated_config, expected_upstreams, sleeper)
        if ok:
            ladder_ok, ladder_detail = _post_cutover_ladder(
                port, master_key, expected_upstreams, completion_model)
            if ladder_ok:
                return True, (f"{staging_detail}; cutover: {detail}; "
                              f"{ladder_detail}{retry_note}")
            detail = f"{detail}; BUT {ladder_detail}"
        last = detail
        if attempt == 0:
            holder = _resolve_port_listener(platform_key, port, runner)
            if holder is None:
                retry_note = " (after one bounded retry; the port was free)"
                continue
            pid, image = holder
            killed, kill_detail, _tree = _stop_holder_tree(
                platform_key, base, pid, runner)
            if not killed:
                return False, (
                    f"the staging-green cutover FAILED ({last}) and stopping "
                    f"the port holder pid {pid} ({image}) for the ONE "
                    f"bounded retry was REFUSED "
                    f"({kill_detail or 'no detail'}) — stop it manually "
                    f"({_kill_hint(platform_key, pid)}). The gateway may be "
                    f"DARK. {RECOVERY_PROCEDURE}")
            retry_note = (f" (after one bounded retry that stopped the "
                          f"port-race holder pid {pid} ({image}))")
    return False, (
        f"the staging-green cutover FAILED and the ONE bounded retry is "
        f"EXHAUSTED — {last}. The gateway may be DARK (staging proved the "
        f"replacement, but the live swap could not be verified on port "
        f"{port}). {RECOVERY_PROCEDURE}")


def restart_gateway(
    platform_key: str,
    launcher_path: Path,
    name: str = SERVICE_NAME,
    runner=None,
    port: Optional[int] = None,
    master_key: Optional[str] = None,
    generated_config: Optional[str] = None,
    expected_upstreams: Optional[dict[str, str]] = None,
    sleeper=time.sleep,
    staging_port: Optional[int] = None,
    completion_model: Optional[str] = None,
) -> tuple[bool, str]:
    """Restart the gateway so a regenerated config takes effect. User-level on
    every OS — never sudo/admin. Returns (ok, detail).

    v3.41.0 iteration 4 (SR-glm-fix-iter4): when the verification context is
    given (``port`` + ``master_key`` + ``generated_config`` — the install
    call sites pass it), the restart is VERIFIED: the stop half falls back to
    stopping the resolved LISTENING pid when the tracked stop leaves the
    gateway port held, and the start half reports restarted ONLY after the
    new instance binds and serves the generated config (see
    ``_verified_restart_gateway``). Iteration 6 (SR-glm-fix-iter6): when the
    context ALSO carries ``staging_port`` + ``completion_model`` (the install
    call sites now pass both), the restart is VERIFY-THEN-SWAP — the
    replacement is proven on the staging port through the full ladder BEFORE
    the serving instance is touched, and the swap is re-verified with one
    bounded retry (see ``_verify_then_swap_restart``); a staging failure
    leaves the old instance serving. Without the context (legacy call shape)
    the behavior is the pre-iteration-4 tracked stop+start, unchanged
    (schtasks /end+/run, ``systemctl --user restart``, ``launchctl
    kickstart -k``; the Startup-folder-shim case falls back to a detached
    launcher spawn)."""
    if (port is not None and master_key is not None
            and generated_config is not None):
        if staging_port is not None and completion_model is not None:
            return _verify_then_swap_restart(
                platform_key, launcher_path, name, runner, port, master_key,
                generated_config, expected_upstreams or {}, sleeper,
                staging_port, completion_model)
        return _verified_restart_gateway(
            platform_key, launcher_path, name, runner, port, master_key,
            generated_config, expected_upstreams or {}, sleeper)
    if platform_key == "windows":
        _run(["schtasks", "/end", "/tn", name], runner)  # stop if task-managed
        if _run(["schtasks", "/run", "/tn", name], runner).returncode == 0:
            return True, "scheduled task restarted"
        ok = _spawn_detached(["cmd", "/c", str(launcher_path)])
        return ok, ("launcher restarted (detached)" if ok
                    else "restart failed (no schtasks task; detached spawn failed)")
    if platform_key == "linux":
        res = _run(["systemctl", "--user", "restart", name], runner)
        if res.returncode == 0:
            return True, "user systemd unit restarted"
        return False, (res.stderr or "").strip() or "systemctl --user restart failed"
    if platform_key == "darwin":
        res = _run(["launchctl", "kickstart", "-k",
                    f"gui/{_gui_uid()}/{name}"], runner)
        if res.returncode == 0:
            return True, "launchd agent restarted"
        return False, (res.stderr or "").strip() or "launchctl kickstart failed"
    return False, f"unsupported platform {platform_key!r}"


SUBSCRIPTION_MODE_NOTE = (
    "subscription mode — no ANTHROPIC_API_KEY resolved, so Anthropic models "
    "(fable) keep Claude Code's native sign-in auth: ANTHROPIC_BASE_URL is NOT "
    "written and the secondary role split stays OFF (the harness cannot route "
    "only secondary traffic through the gateway while sign-in auth handles the "
    "rest). The gateway still serves the chosen secondary provider to direct "
    "callers. For the full gateway + secondary split: set ANTHROPIC_API_KEY and "
    "re-run install --activate."
)


# --------------------------------------------------------------------------- #
# subcommand handlers
# --------------------------------------------------------------------------- #

def _cmd_install(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="install", base_dir=str(base),
                    check_only=bool(args.check_only))
    allow_provider_prompt = bool(
        getattr(args, "interactive_prompts", False)
        and not args.check_only and not getattr(args, "json", False))
    provider, provider_source, provider_error = resolve_secondary_provider(
        getattr(args, "secondary", None), base,
        re_ask=bool(getattr(args, "re_ask_provider", False)),
        interactive=allow_provider_prompt,
    )
    if provider_error or provider is None:
        report.add("secondary", "fail", provider_error or "provider resolution failed")
        return report
    report.secondary_provider = provider
    entry = SECONDARY_PROVIDERS[provider]
    if args.openai_model is not None:
        if provider != "openai":
            report.add(
                "secondary", "fail",
                "--openai-model is scoped to --secondary openai; use --secondary-model")
            return report
        print("NOTE: --openai-model is deprecated; use --secondary-model.", file=sys.stderr)
    report.secondary_model = (
        args.secondary_model or args.openai_model or str(entry["model"]))
    provider_args = {
        name: getattr(args, f"{name}_key", None)
        for name in SECONDARY_PROVIDERS
    }
    keys = resolve_keys(
        base, anthropic_arg=args.anthropic_key,
        secondary_provider=provider, provider_args=provider_args)
    provider_env = str(entry["key_env"])
    report.secondary_key_present = bool(keys.get(provider_env))
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = resolve_auth_mode(keys)
    report.litellm_present = litellm_installed()

    if args.check_only:
        would = "api-key (full gateway)" if report.auth_mode == AUTH_MODE_API_KEY \
            else "subscription (fable via sign-in; gateway secondary-only)"
        report.add("check-only", "skipped",
                   f"would install in {would} mode; "
                   f"secondary={provider}/{report.secondary_model} ({provider_source}); "
                   "no state provisioned")
        return report

    # 0a. decline bookkeeping (v3.38.0): a slot's decline auto-resets whenever
    # that slot's key resolves on any path (args > env > gateway.env — checked
    # here, the resolve_keys caller, so resolution stays pure); --re-ask-keys
    # clears the whole record so prompts fire again.
    if getattr(args, "re_ask_keys", False):
        _clear_declines(base)
    for slot, env_key in provider_key_slots(provider):
        if keys.get(env_key):
            _clear_declines(base, slot)

    # 0b. interactive key prompt (v3.38.0 ask-then-apply): fires ONLY for an
    # interactive caller (--interactive-prompts) on a real TTY — never under
    # --check-only (already returned) or --json — and per slot only when
    # unresolved and not declined, openai then anthropic (D1 order). A captured
    # key folds into `keys` BEFORE write_env_file, so 0600 / masking /
    # config-reference behavior is inherited unchanged. Blank skips: today's
    # absent-key path runs verbatim and the decline is recorded.
    if (getattr(args, "interactive_prompts", False)
            and not getattr(args, "json", False) and _default_isatty_fn()):
        declines = _read_declines(base)
        for slot, env_key in provider_key_slots(provider):
            if keys.get(env_key):
                continue
            if slot in declines:
                report.add("prompt", "skipped",
                           f"{slot}: previously declined "
                           f"(via={declines[slot].get('via', 'unknown')}) -- not "
                           f"re-asking; pass --re-ask-keys to prompt again")
                continue
            entered = _prompt_for_key(slot)
            if entered:
                keys[env_key] = entered
                report.add("prompt", "ok",
                           f"{env_key} captured interactively "
                           f"({_mask(entered)}); raw value stored only in gateway.env")
            else:
                _record_decline(base, slot, via="prompt-skip")
                report.add("prompt", "skipped",
                           f"{slot}: blank entry -- skipped; decline recorded "
                           f"(via=prompt-skip; --re-ask-keys re-prompts)")
        report.secondary_key_present = bool(keys.get(provider_env))
        report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
        report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
        report.auth_mode = resolve_auth_mode(keys)

    # 1. litellm through the setup.py install ladder.
    if report.litellm_present and not args.force_reinstall:
        report.add("litellm", "ok", "already installed")
    elif args.no_install:
        report.add("litellm", "skipped", "--no-install (state-only provisioning)")
    else:
        ok, detail = install_litellm()
        report.litellm_present = ok
        if ok:
            report.add("litellm", "ok",
                       f"pip install \"{LITELLM_PACKAGE}\""
                       + (f" — {detail}" if detail else ""))
        else:
            report.add("litellm", "fail",
                       f"install failed: {detail}. Remediation: "
                       f"pip install \"{LITELLM_PACKAGE}\" then re-run.")

    # 2. secrets → gateway.env (the only raw-key location; chmod 0600).
    # ADV3-2: merge, never replace — a provider switch must not delete the
    # OTHER provider's stored key. Every preserved slot (each registry
    # provider's key_env + Anthropic + master) carries forward; the freshly
    # resolved values win.
    existing_env = read_env_file(base / ENV_FILE_NAME)
    persisted = {k: v for k, v in existing_env.items()
                 if k in preserved_env_keys()}
    persisted.update(keys)
    write_env_file(base / ENV_FILE_NAME, persisted)
    # honesty: the report's openai flag reflects the FILE (a retained OpenAI
    # key on a zai run is still present), matching what status reports.
    report.openai_key_present = bool(persisted.get("OPENAI_API_KEY"))
    report.add("secrets", "ok",
               f"gateway.env written ({provider_env}: "
               f"{_mask(keys.get(provider_env)) or 'ABSENT'}, ANTHROPIC_API_KEY: "
               f"{_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent — subscription mode'})")

    # 3. config + launcher + state.
    # Iteration 2 (SR-glm-fix-iter2): remember what the config file said
    # BEFORE this run rewrites it. ANY byte-level content change — not just a
    # model-group set change; an api_base or dialect edit keeps the group set
    # identical — marks this a config-REgenerating install, and step 7
    # restarts a running gateway so the process serves what this run wrote
    # (register/start is start-if-not-running; the B6 witness caught a stale
    # pre-deploy process still serving the prior config after regeneration).
    config_path = base / CONFIG_NAME
    prior_config: Optional[str] = None
    if config_path.is_file():
        try:
            prior_config = config_path.read_text(encoding="utf-8")
        except OSError:
            prior_config = None
    new_config = build_gateway_config(
        report.auth_mode, SECONDARY_ALIAS, report.secondary_model, provider)
    config_path.write_text(new_config, encoding="utf-8")
    config_regenerated = prior_config is not None and prior_config != new_config
    launcher_name, launcher_body = build_launcher(_platform_key(), base, args.port)
    (base / launcher_name).write_text(launcher_body, encoding="utf-8")
    if not launcher_name.endswith(".bat"):
        try:
            os.chmod(base / launcher_name, 0o755)
        except OSError:  # pragma: no cover
            pass
    report.add("config", "ok",
               f"{CONFIG_NAME} ({report.auth_mode} mode) + {launcher_name} written")

    # 3b. serving-side consistency (v3.40.0 ADV3B-1; spawn alias v3.41.0):
    # the config just written routes the neutral alias + the spawn alias, and
    # the harness spawn gate rejects any custom frontmatter id (BUG-B) — so an
    # on-disk split carrying EITHER superseded frontmatter alias (a legacy
    # provider id, or the raw ct6-secondary) migrates to the spawn alias in
    # the SAME run, with or without --activate: consistency maintenance of an
    # already-activated machine, not a new activation.
    # migrate_legacy_split rewrites ONLY files carrying a superseded alias, so
    # a split-neutral machine (a fresh install, a manual lever state) never
    # has its agents touched. prior_state is read here, BEFORE this run's
    # state write, so a non-activate install can carry forward what it does
    # not change (only uninstall downgrades activated/model_policy).
    prior_state = _read_state(base)
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    migrated: list[str] = []
    if agents_dir.is_dir():
        migrated = _lever.migrate_legacy_split(agents_dir)
        if migrated:
            report.add("alias-migration", "ok",
                       f"{len(migrated)} agent file(s) migrated from a "
                       f"superseded secondary alias to {SPAWN_ALIAS_MODEL_ID} "
                       f"in {agents_dir} (the spawn-compatible id the "
                       f"regenerated {CONFIG_NAME} routes; the harness spawn "
                       f"gate rejects custom frontmatter ids)")
        # ADV3C-1: record whether the disk policy IS the split (e.g. carried
        # from a prior activation) so the confirm wording can be honest about
        # a split this run did not itself apply.
        report.split_on_disk = (
            _lever.policy_state(agents_dir) == POLICY_SECONDARY_SPLIT)
    elif not args.activate:
        # ADV3C-4: never skip step 3b silently — the --activate path already
        # surfaces a missing/typo'd agents dir (its secondary-split row); the
        # plain path gets the symmetric row.
        report.add("alias-migration", "skipped",
                   f"agents dir not found at {agents_dir} — legacy-alias "
                   f"migration not performed; check --agents-dir or apply the "
                   f"split manually: python scripts/setup/set_default_model.py "
                   f"--split secondary")

    # 4. boot descriptor (written + hint printed; NEVER registered for you).
    desc_dir = base / DESCRIPTOR_DIRNAME
    desc_dir.mkdir(parents=True, exist_ok=True)
    descriptor = _bg.install_descriptor(
        _platform_key(), SERVICE_NAME, str(base / launcher_name))
    desc_path = desc_dir / descriptor["filename"]
    desc_path.write_text(descriptor["content"], encoding="utf-8")
    report.descriptor_path = str(desc_path)
    report.register_hint = descriptor["register_hint"]
    report.add("descriptor", "ok",
               f"{descriptor['kind']} descriptor written to {desc_path}")

    # 5. enablement: only the chosen provider's key controls the secondary route.
    report.enabled = report.secondary_key_present
    if not report.enabled:
        provider_flag = f"--{provider}-key"
        report.remediation = (
            f"set {provider_env} (env) or re-run with {provider_flag} …; state dir: {base}")
        report.add("enable", "skipped",
                   f"no {provider} key resolved; provisioned but NOT enabled")
    else:
        report.add("enable", "ok", "gateway enabled")

    # 5b. auto-registration (v3.37.0): the installer registers + starts the
    # gateway itself (user-level; --no-register opts back to the printed hint).
    if args.no_register:
        report.add("register", "skipped",
                   "--no-register — register manually with the printed hint")
    elif not report.enabled:
        report.add("register", "skipped",
                   f"not enabled (no {provider_env}) — registration deferred")
    else:
        # Iteration 5 (SR-glm-fix-iter5): the ownership context arms the
        # exactly-one-instance gate — owned zombies swept before the one
        # start, and no blind start over a port an instance already serves.
        reg_ok, reg_detail = register_gateway(
            _platform_key(), base / launcher_name, base=base, port=args.port)
        report.registered = reg_ok
        if reg_ok:
            report.add("register", "ok", reg_detail)
        else:
            report.add("register", "fail",
                       f"{reg_detail} — register manually: {descriptor['register_hint']}")

    # 6. activation (api-key mode only; consent came from the explicit flag).
    if args.activate:
        if report.auth_mode == AUTH_MODE_API_KEY and report.enabled:
            settings_path = Path(args.settings_path) if args.settings_path \
                else _setup.DEFAULT_USER_SETTINGS_PATH
            apply_claude_env(settings_path, args.port, keys[MASTER_KEY_VAR])
            report.activated = True
            report.add("activate", "ok",
                       f"ANTHROPIC_BASE_URL={gateway_url(args.port)} + auth token "
                       f"written to {settings_path}")
            # legacy-alias files were already migrated at step 3b (the same-run
            # consistency pass); apply_split then repairs any remaining drift.
            if agents_dir.is_dir():
                changed = _lever.apply_split(agents_dir)
                report.split_applied = True
                report.add("secondary-split", "ok",
                           f"role split applied to {agents_dir} "
                           f"({len(changed)} policy rewrite(s), {len(migrated)} legacy "
                           f"alias migration(s); dev/checking/testing agents → "
                           f"{SPAWN_ALIAS_MODEL_ID}, the spawn-compatible "
                           f"impersonation alias served by the {SECONDARY_ALIAS} "
                           f"backend route)")
            else:
                report.add("secondary-split", "skipped",
                           f"agents dir not found at {agents_dir}; apply manually: "
                           f"python scripts/setup/set_default_model.py --split secondary")
        elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            report.add("activate", "skipped", SUBSCRIPTION_MODE_NOTE)
        else:
            report.add("activate", "skipped",
                       f"cannot activate: no {provider_env} (see enable remediation)")
    elif report.auth_mode == AUTH_MODE_SUBSCRIPTION:
        report.add("mode", "ok", SUBSCRIPTION_MODE_NOTE)
    elif prior_state.get("activated"):
        # ADV3C-1: this plain install neither activated nor deactivated —
        # the machine's prior activation carries forward (step 8 records it),
        # so the row must not read as "unactivated; needs consent".
        report.activation_carried = True
        report.add("activate", "ok",
                   "activation carried forward from the prior install "
                   "(settings.json untouched this run; uninstall is the only "
                   "downgrade path)")

    # 7. live confirmation (v3.39.0): assert the RUNNING gateway actually
    # serves the ids the split needs — the step the v3.38.1 field bug proved
    # necessary (a broken config passed every install step). Only when this
    # run registered/started the gateway (--no-register opts out of the
    # probe too — that pin means NO schtasks at all); a stale process serving
    # a pre-regeneration config gets ONE restart + re-probe before the honest
    # warn. Never gates.
    if report.enabled and report.registered:
        expect = [SECONDARY_ALIAS]
        if report.auth_mode == AUTH_MODE_API_KEY:
            expect.append(FABLE_MODEL)
        # The just-written config always routes the impersonation alias too.
        expect.append(SPAWN_ALIAS_MODEL_ID)
        # v3.41.0 (wrong-hop fix): the CONFIRMED claim requires a real
        # /v1/messages completion. Iteration 2: the completion must come from
        # the SECONDARY's deployment — expected upstream derived from the
        # registry at probe time (never a constant). Iteration 3
        # (SR-glm-fix-iter3): the probe is SPAWN-ALIAS-MANDATORY — the
        # just-written config routes the spawn alias and step 8 records it,
        # so the confirm must prove THAT id, the one the harness actually
        # spawns; the second deploy went green via the ct6-secondary fallback
        # (correct in both configs) while the spawn alias stayed
        # anthropic-served. Fallback completion green survives only for
        # legacy states with no recorded spawn alias (status --live).
        completion = [SPAWN_ALIAS_MODEL_ID]
        expected_upstream = _secondary_route_model(entry, report.secondary_model)
        # 7a. restart triggers. Iteration 2: ANY byte-level config-content
        # change restarts the running process (register/start is start-if-
        # not-running; the B6 witness caught a stale pre-deploy process
        # still serving the prior config). Iteration 3: the byte diff is only
        # the CHEAP first check — a file already regenerated by a prior run
        # with the PROCESS still serving the older config matches no byte
        # diff (exactly the second deploy's state) — so the AUTHORITATIVE
        # trigger judges the SERVED state: the generated config's model-group
        # set + the secondary/spawn routes' expected upstreams vs GET
        # /model/info (the injectable _default_model_info_prober seam keeps
        # keyless pytest hermetic). An unreachable /model/info cannot judge
        # (a cold-starting fresh gateway looks exactly like that) — no
        # proactive restart; the spawn-mandatory confirm below stays the
        # fail-closed backstop and its repair cycle still restarts on a
        # wrong-upstream completion.
        restart_reason = None
        if config_regenerated:
            restart_reason = (f"{CONFIG_NAME} content changed since the "
                              f"prior install")
        else:
            try:
                served_deployments = _default_model_info_prober(
                    args.port, keys[MASTER_KEY_VAR])
            except Exception:
                served_deployments = None
            if served_deployments is not None:
                stale = _served_state_staleness(
                    new_config, served_deployments,
                    {SECONDARY_ALIAS: expected_upstream,
                     SPAWN_ALIAS_MODEL_ID: expected_upstream})
                if stale:
                    restart_reason = ("the RUNNING gateway serves a STALE "
                                      f"state ({stale})")
        # Iteration 4 (SR-glm-fix-iter4): both restart hops carry the
        # verification context, so restart_gateway stops the actual
        # port-holder when the tracked stop is a no-op (the third deploy's
        # untracked PID survived two 'restarts') and reports restarted only
        # after the new instance binds and serves the generated config.
        # Iteration 6 (SR-glm-fix-iter6): the context also carries the
        # staging port + the mandatory completion model, so every install
        # restart is VERIFY-THEN-SWAP — the replacement is proven on the
        # staging port (full ladder, incl. the real-key completion an
        # unresolved master key fails: the 2026-07-18 offline incident)
        # BEFORE the serving instance is touched; a staging failure leaves
        # the old instance serving.
        restart_context = dict(
            port=args.port, master_key=keys[MASTER_KEY_VAR],
            generated_config=new_config,
            expected_upstreams={SECONDARY_ALIAS: expected_upstream,
                                SPAWN_ALIAS_MODEL_ID: expected_upstream},
            staging_port=args.port + STAGING_PORT_OFFSET,
            completion_model=SPAWN_ALIAS_MODEL_ID)
        if restart_reason:
            restarted, r_detail = restart_gateway(
                _platform_key(), base / launcher_name, **restart_context)
            report.add(
                "restart", "ok" if restarted else "fail",
                (f"{restart_reason} — gateway restarted so the running "
                 f"process serves the regenerated config ({r_detail})")
                if restarted else
                (f"{restart_reason} but the restart failed ({r_detail}) — "
                 f"a running gateway may still serve a stale state; the "
                 f"spawn-mandatory confirm probe below catches it"))
        ok, detail = confirm_gateway_serving(
            args.port, keys[MASTER_KEY_VAR], expect,
            completion_models=completion,
            expected_upstream=expected_upstream,
            mandatory_completion_model=SPAWN_ALIAS_MODEL_ID)
        if not ok:
            restarted, r_detail = restart_gateway(
                _platform_key(), base / launcher_name, **restart_context)
            if restarted:
                ok, detail = confirm_gateway_serving(
                    args.port, keys[MASTER_KEY_VAR], expect,
                    completion_models=completion,
                    expected_upstream=expected_upstream,
                    mandatory_completion_model=SPAWN_ALIAS_MODEL_ID)
                detail = f"{detail} (after restart: {r_detail})"
            else:
                detail = f"{detail}; restart attempt failed: {r_detail}"
        report.split_confirmed = ok
        if ok:
            # ADV3C-1: the split phrasing also applies when the disk policy is
            # a CARRIED split (this run confirmed it live without applying it).
            report.add("confirm", "ok",
                       ("CONFIRMED: CT6 runs the split — "
                        if report.split_applied or report.split_on_disk
                        else "CONFIRMED: ") + detail)
        else:
            report.add("confirm", "fail",
                       f"{detail} — verify keys in {base / ENV_FILE_NAME}, then "
                       f"restart the gateway and re-check: python "
                       f"scripts/setup/install_gateway.py status --live. "
                       f"{RECOVERY_PROCEDURE}")
    elif report.enabled:
        report.add("confirm", "skipped",
                   "gateway not started this run (registration skipped or "
                   "failed) — start it, then verify: python "
                   "scripts/setup/install_gateway.py status --live")

    # 8. state (v3.40.0 ADV3B-1, carry-forward): a non-activate install
    # neither activated nor deactivated anything, so the prior `activated` and
    # a prior split `model_policy` carry FORWARD instead of downgrading —
    # uninstall (and a future explicit deactivate) is the ONLY downgrade path.
    # This keeps the SessionStart self-heal armed and `status --live` truthful
    # on an already-activated machine (and closes ADV3B-5, the modern-machine
    # heal-disarm on a plain re-install). The `{**prior_state}` merge carries
    # every key this run does not rewrite. `secondary_alias` records what the
    # just-regenerated config routes; step 3b migrated any on-disk legacy
    # split to that alias in the same run, so the record mirrors the disk.
    prior_split_desired = prior_state.get("model_policy") in (
        POLICY_SECONDARY_SPLIT, LEGACY_POLICY_CODEX_SPLIT)
    _write_state(base, {
        **prior_state,
        "auth_mode": report.auth_mode,
        "port": args.port,
        "secondary_provider": provider,
        "secondary_model": report.secondary_model,
        "secondary_alias": SECONDARY_ALIAS,
        "codex_alias": SECONDARY_ALIAS,
        # v3.41.0 impersonation disclosure: the spawn-compatible alias the
        # just-written config routes, and the secondary model it maps to —
        # the record status prints and the SessionStart self-heal targets.
        "spawn_alias": SPAWN_ALIAS_MODEL_ID,
        "spawn_alias_maps_to": report.secondary_model,
        # Preserve the grandfather marker for one transition version.
        "openai_model": report.secondary_model if provider == "openai" else None,
        "activated": bool(report.activated or prior_state.get("activated")),
        "enabled": report.enabled,
        "registered": report.registered,
        "model_policy": POLICY_SECONDARY_SPLIT
        if (report.split_applied or prior_split_desired)
        else POLICY_UNIFORM_FABLE,
    })
    return report


def _cmd_status(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="status", base_dir=str(base))
    state = _read_state(base)
    provider, _, error = resolve_secondary_provider(
        getattr(args, "secondary", None), base, re_ask=False, interactive=False)
    if error or provider is None:
        report.add("secondary", "fail", error or "provider resolution failed")
        return report
    entry = SECONDARY_PROVIDERS[provider]
    provider_env = str(entry["key_env"])
    report.secondary_provider = provider
    report.secondary_model = str(
        state.get("secondary_model") or state.get("openai_model") or entry["model"])
    keys = read_env_file(base / ENV_FILE_NAME)
    port = int(state.get("port", args.port))
    report.secondary_key_present = bool(keys.get(provider_env))
    report.openai_key_present = bool(keys.get("OPENAI_API_KEY"))
    report.anthropic_key_present = bool(keys.get("ANTHROPIC_API_KEY"))
    report.auth_mode = state.get("auth_mode", resolve_auth_mode(keys))
    report.litellm_present = litellm_installed()
    report.enabled = report.secondary_key_present and (base / CONFIG_NAME).is_file()
    settings_path = Path(args.settings_path) if args.settings_path \
        else _setup.DEFAULT_USER_SETTINGS_PATH
    report.activated = claude_env_applied(settings_path, port)
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    report.descriptor_path = str(descs[0]) if descs else None
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    policy = _lever.policy_state(agents_dir) if agents_dir.is_dir() else "unknown"
    report.split_applied = policy == POLICY_SECONDARY_SPLIT
    report.registered = is_gateway_registered(_platform_key())
    if not report.secondary_key_present:
        report.remediation = (
            f"set {provider_env} or re-run install --{provider}-key …")
    summary = (
        f"mode={report.auth_mode}; secondary={provider}/{report.secondary_model}; "
        f"enabled={report.enabled}; activated={report.activated}; "
        f"registered={report.registered}; litellm={report.litellm_present}; "
        f"model-policy={policy}; {provider_env}="
        f"{_mask(keys.get(provider_env)) or 'absent'}; "
        f"ANTHROPIC_API_KEY={_mask(keys.get('ANTHROPIC_API_KEY')) or 'absent'}")
    # v3.38.0: report recorded declines — the decline suppresses the PROMPT,
    # never the truth (the absent-key fields above stay verbatim).
    declines = _read_declines(base)
    if declines:
        summary += f"; declined={','.join(sorted(declines))}"
    report.add("status", "ok", summary)
    # v3.41.0 impersonation disclosure: a state that records the spawn alias
    # gets its mapping printed plainly — requests labeled with that Claude id
    # through THIS gateway are served by the secondary provider's model.
    spawn = _recorded_spawn_alias(state)
    if spawn:
        maps_to = str(state.get("spawn_alias_maps_to")
                      or report.secondary_model)
        report.add("spawn-alias", "ok",
                   f"{spawn} -> {maps_to} (impersonated secondary)")
    report.add("agents", "ok", f"model policy read from {agents_dir}")
    # v3.39.0: --live probes the RUNNING gateway's /v1/models and reports
    # whether it serves what the current mode needs (one attempt burst, no
    # restart — status observes, install repairs).
    if getattr(args, "live", False):
        if report.enabled:
            # ADV3-3: expect the STATE-RECORDED alias(es) — a working legacy
            # (v3.39) install whose config routes only codex-5.6-sol must
            # probe green; a hard-coded newest alias false-failed it.
            # ADV3B-2: whitespace-trimmed via _recorded_secondary_alias /
            # _recorded_spawn_alias, so a corrupt whitespace value never
            # masks the legacy key. The spawn alias joins the expectation
            # (and the completion candidates) ONLY when the state records it.
            expect = [_recorded_secondary_alias(state)]
            if report.auth_mode == AUTH_MODE_API_KEY:
                expect.append(FABLE_MODEL)
            if spawn:
                expect.append(spawn)
            # Iteration 3 (SR-glm-fix-iter3): spawn-alias-MANDATORY — a state
            # that records the spawn alias must prove THAT id end-to-end (it
            # is the id the harness actually spawns); the ct6-secondary
            # completion green survives only for legacy states whose config
            # never routed a spawn alias.
            completion = [spawn] if spawn else [_recorded_secondary_alias(state)]
            # Iteration 2 (SR-glm-fix-iter2): the live probe verifies the
            # serving DEPLOYMENT too — expected upstream derived from the
            # registry + the state-recorded model at probe time (a legacy
            # v3.39 openai config derives openai/<model>, so it still
            # confirms green; a wildcard-served completion fails with the
            # observed upstream named).
            expected_upstream = _secondary_route_model(
                entry, report.secondary_model)
            ok, detail = confirm_gateway_serving(
                port, keys.get(MASTER_KEY_VAR, ""), expect, attempts=3,
                completion_models=completion,
                expected_upstream=expected_upstream,
                mandatory_completion_model=spawn)
            report.split_confirmed = ok
            report.add("confirm", "ok" if ok else "fail",
                       (("CONFIRMED: CT6 runs the split — " if report.split_applied
                         else "CONFIRMED: ") + detail) if ok
                       else f"{detail} — restart the gateway or re-run install")
        else:
            report.add("confirm", "skipped",
                       "gateway not enabled — nothing to probe")
    return report


def _cmd_uninstall(args: argparse.Namespace, base: Path) -> Report:
    report = Report(action="uninstall", base_dir=str(base),
                    check_only=bool(args.check_only))
    state = _read_state(base)
    port = int(state.get("port", args.port))

    if args.check_only:
        report.add("check-only", "skipped",
                   "would deactivate settings.json, restore uniform fable if the "
                   "codex split is applied, stop + unregister the gateway, and "
                   "remove the boot descriptor; nothing touched")
        return report

    # 1. deactivate settings.json (only OUR values are ever removed).
    settings_path = Path(args.settings_path) if args.settings_path \
        else _setup.DEFAULT_USER_SETTINGS_PATH
    if remove_claude_env(settings_path, port):
        report.add("deactivate", "ok",
                   f"gateway env entries removed from {settings_path}")
    else:
        report.add("deactivate", "skipped",
                   "no gateway env entries in settings.json (no-op)")

    # 2. restore from current or legacy split state. policy_state recognizes a
    # complete legacy-alias split as secondary-split; the recorded legacy policy
    # is an additional mixed-version guard.
    agents_dir = Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    disk_policy = _lever.policy_state(agents_dir) if agents_dir.is_dir() else "unknown"
    recorded_policy = state.get("model_policy")
    wants_restore = disk_policy == POLICY_SECONDARY_SPLIT or recorded_policy in {
        POLICY_SECONDARY_SPLIT, LEGACY_POLICY_CODEX_SPLIT}
    if agents_dir.is_dir() and wants_restore:
        changed = _lever.set_model(agents_dir, "fable")
        report.add("model-restore", "ok",
                   f"uniform fable restored ({len(changed)} file(s) rewritten)")
    else:
        report.add("model-restore", "skipped",
                   "model state is not a secondary split (left untouched)")

    # 3. unregistration (v3.37.0: EXECUTED, symmetric with install) +
    #    descriptor removal.
    unreg_ok, unreg_detail = unregister_gateway(_platform_key())
    report.add("unregister", "ok" if unreg_ok else "fail", unreg_detail)
    if not unreg_ok:
        report.register_hint = {
            "linux": f"systemctl --user disable --now {SERVICE_NAME}",
            "darwin": f"launchctl unload -w ~/Library/LaunchAgents/{SERVICE_NAME}.plist",
            "windows": f'schtasks /delete /tn "{SERVICE_NAME}" /f',
        }[_platform_key()]
    desc_dir = base / DESCRIPTOR_DIRNAME
    descs = list(desc_dir.glob(f"{SERVICE_NAME}.*")) if desc_dir.exists() else []
    if descs:
        for d in descs:
            try:
                d.unlink()
            except OSError:  # pragma: no cover
                pass
        report.add("descriptor", "ok", "boot descriptor removed")
    else:
        report.add("descriptor", "skipped", "no boot descriptor present (no-op)")

    if args.purge:
        if base.exists():
            shutil.rmtree(base, ignore_errors=True)
            report.add("purge", "ok", f"removed state dir {base}")
        else:
            report.add("purge", "skipped", "state dir already absent (no-op)")
    elif state:
        # v3.39.0: record the deactivated state so the sessionstart self-heal
        # never re-applies a split the user uninstalled.
        _write_state(base, {**state, "activated": False,
                            "model_policy": POLICY_UNIFORM_FABLE})
    return report


def _cmd_decline(args: argparse.Namespace, base: Path) -> Report:
    """Record (or --clear) a wrapper-level key decline — the deterministic
    channel for the slash-command flow's AskUserQuestion decline disposition
    (v3.38.0 D3; the wrapper cannot type into a stdin prompt)."""
    report = Report(action="decline", base_dir=str(base))
    state = _read_state(base)
    report.auth_mode = state.get("auth_mode", report.auth_mode)
    report.enabled = bool(state.get("enabled", False))
    report.registered = bool(state.get("registered", False))
    slot = args.slot
    if getattr(args, "clear", False):
        if _clear_declines(base, slot):
            report.add("decline", "ok",
                       f"{slot}: decline cleared -- the installer may prompt again")
        else:
            report.add("decline", "skipped", f"{slot}: no decline recorded (no-op)")
        return report
    _record_decline(base, slot, via="wrapper")
    report.add("decline", "ok",
               f"{slot}: decline recorded (via=wrapper) -- the installer will not "
               f"prompt for this key; undo with `decline {slot} --clear` or "
               f"install --re-ask-keys")
    return report


_HANDLERS = {
    "install": _cmd_install,
    "status": _cmd_status,
    "uninstall": _cmd_uninstall,
    "decline": _cmd_decline,
}


# --------------------------------------------------------------------------- #
# setup.py integration
# --------------------------------------------------------------------------- #

def resolve_external_llm_signal(
    enable_flag: bool, disable_flag: bool, env: Optional[dict[str, str]] = None,
) -> Optional[bool]:
    """Tri-state enable signal for setup.py: True (--external-llm or truthy
    CT6_EXTERNAL_LLM), False (--no-external-llm — the flag overrides the env —
    or a SET-but-falsy env var), None (no signal: leave everything untouched)."""
    if disable_flag:
        return False
    if enable_flag:
        return True
    env = os.environ if env is None else env
    if ENV_SIGNAL not in env:
        return None
    return str(env.get(ENV_SIGNAL, "")).strip().lower() in {"1", "true", "yes"}


def setup_entry(
    enable: bool,
    check_only: bool,
    assume_yes: bool,
    base_dir: Optional[str] = None,
    settings_path: Optional[str] = None,
    agents_dir: Optional[str] = None,
    interactive: Optional[bool] = None,
    secondary: Optional[str] = None,
) -> tuple[str, str, Optional[str]]:
    """The setup.py hook: run install (enable=True) or uninstall (enable=False)
    and fold the result into one (name, status, detail) report row. NEVER raises
    and never gates setup — any failure (including a raising prompt seam)
    degrades to a 'warn' row with the manual remediation (the same posture as
    apply_model_policy).

    v3.38.0: passes interactivity through — `--interactive-prompts` is appended
    ONLY when NOT assume_yes AND NOT check_only AND stdin is a TTY. `interactive`
    is an explicit override for callers that already resolved it (setup.py
    forwards --no-prompt as False); the assume_yes/check_only guards are
    unconditional either way."""
    name = "external-llm (LiteLLM gateway)"
    manual = "python scripts/setup/install_gateway.py install --activate"
    try:
        base = resolve_base_dir(base_dir)
        argv = ["install" if enable else "uninstall", "--base-dir", str(base)]
        if secondary is not None:
            argv += ["--secondary", secondary]
        if check_only:
            argv.append("--check-only")
        if enable and assume_yes:
            # --activate writes settings.json + the model split; consent came
            # from --yes / CT6_SETUP_ASSUME_YES (the setup consent convention).
            argv.append("--activate")
        if enable and not assume_yes and not check_only:
            allow = interactive if interactive is not None else _default_isatty_fn()
            if allow:
                argv.append("--interactive-prompts")
        if settings_path:
            argv += ["--settings-path", settings_path]
        if agents_dir:
            argv += ["--agents-dir", agents_dir]
        parser = _build_parser()
        args = parser.parse_args(argv)
        handler = _HANDLERS[args.command or "install"]
        report = handler(args, base)
        failed = [s for s in report.steps if s.status == "fail"]
        if failed:
            return name, "warn", (
                f"{failed[0].name}: {failed[0].detail} — finish manually: {manual}")
        if check_only:
            return name, "note", "; ".join(
                f"{s.name}: {s.detail}" for s in report.steps) or "check-only"
        if not enable:
            return name, "applied", "gateway deactivated + descriptor removed"
        # ADV3C-1: a carried-forward activation must not read as "unactivated"
        # (the machine stays activated + split; this run just did not
        # RE-activate it — no activation is claimed for this run).
        activated_display = ("carried-forward"
                             if report.activation_carried and not report.activated
                             else report.activated)
        summary = (
            f"mode={report.auth_mode}; secondary={report.secondary_provider}/"
            f"{report.secondary_model}; enabled={report.enabled}; "
            f"activated={activated_display}"
            + ("; secondary split applied" if report.split_applied else "")
            + ("; CONFIRMED live — CT6 runs the split"
               if report.split_confirmed
               and (report.split_applied or report.split_on_disk)
               else "; CONFIRMED serving live" if report.split_confirmed
               else "; live confirmation FAILED (see confirm step)"
               if report.split_confirmed is False else "")
            + (f"; NOT enabled — {report.remediation}" if report.remediation else "")
        )
        if report.auth_mode == AUTH_MODE_SUBSCRIPTION:
            # Provider-neutral: the served-provider prose is single-sourced
            # from the lever registry entry (label carries provider + model),
            # never a hand-written per-provider string.
            entry = SECONDARY_PROVIDERS.get(report.secondary_provider, {})
            served = str(entry.get("label") or report.secondary_provider)
            summary += f" (fable via Claude sign-in; gateway serves {served} only)"
        elif (report.enabled and not report.activated
                and not report.activation_carried):
            summary += (
                " (activation needs consent: rerun with --yes, or run manually: "
                + manual + ")"
            )
        return name, "applied", summary
    except Exception as exc:  # never gate setup on the gateway installer
        return name, "warn", f"external-llm setup not applied ({exc}); run manually: {manual}"


def check_external_llm_option() -> tuple[str, str, Optional[str]]:
    """Informational row shown by setup.py when NO external-llm signal is present."""
    name = "external-llm (LiteLLM gateway — not requested)"
    detail = (
        "no external-LLM signal — nothing installed. To enable out-of-the-box "
        "OpenAI/Codex usage rerun setup with --external-llm (or set "
        f"{ENV_SIGNAL}=1); --no-external-llm uninstalls. Fable keeps working "
        "either via your Claude sign-in (no key) or via ANTHROPIC_API_KEY."
    )
    return name, "note", detail


# --------------------------------------------------------------------------- #
# argparse + emit
# --------------------------------------------------------------------------- #

def _add_shared_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--base-dir", default=None,
                        help=f"state dir (default ${ENV_HOME} or ~/.architect-team/gateway)")
    provider_names = "|".join(sorted(SECONDARY_PROVIDERS))
    parser.add_argument("--secondary", default=None,
                        help=f"secondary provider name ({provider_names})")
    parser.add_argument("--secondary-model", default=None,
                        help="upstream model id override for the chosen secondary provider")
    for name, entry in SECONDARY_PROVIDERS.items():
        parser.add_argument(
            f"--{name}-key", default=None,
            help=f"{entry['label']} API key to store in gateway.env")
    parser.add_argument("--anthropic-key", default=None,
                        help="Anthropic API key to store in gateway.env (api-key mode)")
    parser.add_argument("--openai-model", default=None,
                        help="deprecated synonym for --secondary-model with --secondary openai")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"gateway port (default: {DEFAULT_PORT})")
    parser.add_argument("--activate", action="store_true",
                        help="api-key mode: write the Claude Code env block + "
                             "apply the secondary role split")
    parser.add_argument("--settings-path", default=None,
                        help="Claude settings.json path (default: ~/.claude/settings.json)")
    parser.add_argument("--agents-dir", default=None,
                        help="agents/ dir for the model split (default: the INSTALLED "
                             "plugin copy's agents/, else the repo's agents/)")
    parser.add_argument("--no-install", action="store_true",
                        help="skip the pip install (state-only provisioning)")
    parser.add_argument("--no-register", action="store_true",
                        help="skip the automatic boot registration (print the hint instead)")
    parser.add_argument("--interactive-prompts", action="store_true",
                        help="allow the interactive missing-key prompt (set only by "
                             "interactive callers: a TTY main() run or an interactive "
                             "setup run; never under --check-only/--json)")
    parser.add_argument("--re-ask-keys", action="store_true",
                        help="clear the recorded key declines so prompts fire again")
    parser.add_argument("--re-ask-provider", action="store_true",
                        help="ignore the recorded provider and ask/select it again")
    parser.add_argument("--force-reinstall", action="store_true",
                        help="reinstall litellm even when already importable")
    parser.add_argument("--check-only", action="store_true",
                        help="report intent only; provision nothing")
    parser.add_argument("--live", action="store_true",
                        help="(status) probe the RUNNING gateway's /v1/models and "
                             "confirm it serves what the mode needs")
    parser.add_argument("--json", action="store_true",
                        help="emit a machine-readable JSON report")
    parser.add_argument("--purge", action="store_true",
                        help="(uninstall) also remove the state dir")


def _build_parser() -> argparse.ArgumentParser:
    shared = argparse.ArgumentParser(add_help=False)
    _add_shared_flags(shared)
    parser = argparse.ArgumentParser(
        prog="install_gateway.py", parents=[shared],
        description="Install / manage the CT6 external-LLM gateway (LiteLLM).")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("install", parents=[shared], add_help=False)
    sub.add_parser("status", parents=[shared], add_help=False)
    sub.add_parser("uninstall", parents=[shared], add_help=False)
    dec = sub.add_parser("decline", parents=[shared], add_help=False)
    dec.add_argument("slot", choices=("anthropic", *SECONDARY_PROVIDERS),
                     help="the key slot to decline (anthropic or a secondary provider)")
    dec.add_argument("--clear", action="store_true",
                     help="clear the recorded decline for the slot instead")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    # Ensure Unicode output works on Windows consoles (cp1252 default) — the
    # masked-key ellipsis and pip's own output are not cp1252-encodable
    # (the same guard as setup.py's main()).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - console-dependent best-effort
            pass
    parser = _build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    command = args.command or "install"
    # v3.38.0 (D1): a DIRECT terminal run is an interactive caller — main()
    # opts into prompting when stdin is a real TTY and neither --json nor
    # --check-only is present, so a direct install never stays punt-only.
    # setup_entry appends the flag itself; the handler never prompts without it.
    if (command == "install" and not args.interactive_prompts
            and not args.check_only and not getattr(args, "json", False)
            and _default_isatty_fn()):
        args.interactive_prompts = True
    base = resolve_base_dir(args.base_dir)
    handler = _HANDLERS[command]
    try:
        report = handler(args, base)
    except Exception as exc:
        msg = f"{command} failed: {exc!r}"
        if getattr(args, "json", False):
            print(json.dumps({"action": command, "error": msg}, indent=2))
        else:
            print(f"\n[x] {msg}\n")
        return 1
    return _emit(report, getattr(args, "json", False))


def _emit(report: Report, as_json: bool) -> int:
    if as_json:
        payload = {
            "action": report.action,
            "base_dir": report.base_dir,
            "auth_mode": report.auth_mode,
            "secondary_provider": report.secondary_provider,
            "secondary_model": report.secondary_model,
            "secondary_key_present": report.secondary_key_present,
            "openai_key_present": report.openai_key_present,
            "anthropic_key_present": report.anthropic_key_present,
            "litellm_present": report.litellm_present,
            "enabled": report.enabled,
            "activated": report.activated,
            "registered": report.registered,
            "split_applied": report.split_applied,
            "split_confirmed": report.split_confirmed,
            "descriptor_path": report.descriptor_path,
            "register_hint": report.register_hint,
            "remediation": report.remediation,
            "check_only": report.check_only,
            "steps": [{"name": s.name, "status": s.status, "detail": s.detail}
                      for s in report.steps],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    print()
    print("=" * 64)
    print(f"  CT6 external-LLM gateway {report.action} -- summary")
    print("=" * 64)
    for step in report.steps:
        marker = {"ok": "[+]", "skipped": "[-]", "fail": "[x]"}.get(step.status, "[?]")
        print(f"  {marker} {step.name:<14} {step.detail}")
    print("=" * 64)
    print(f"  State dir:   {report.base_dir}")
    print(f"  Auth mode:   {report.auth_mode}"
          + ("  (fable via Claude sign-in)" if report.auth_mode == AUTH_MODE_SUBSCRIPTION else ""))
    print(f"  Secondary:   {report.secondary_provider}/{report.secondary_model}")
    print(f"  Gateway:     {'enabled' if report.enabled else 'provisioned but NOT enabled'}"
          f"; auto-registered: {'yes' if report.registered else 'no'}"
          f"; Claude Code activation: "
          f"{'applied' if report.activated else 'carried forward (prior install)' if report.activation_carried else 'not applied'}")
    if report.register_hint and not report.registered:
        print("  Manual registration hint (auto-registration was skipped or failed):")
        print(f"    {report.register_hint}")
    if report.remediation:
        print(f"  Remediation: {report.remediation}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
