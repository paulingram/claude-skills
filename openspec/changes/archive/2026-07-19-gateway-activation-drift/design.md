# Design — gateway-activation-drift

## Context

Activation = `apply_claude_env()` merging `{ANTHROPIC_BASE_URL: http://127.0.0.1:<port>, ANTHROPIC_AUTH_TOKEN: <master key>}` into `~/.claude/settings.json` (`install_gateway.py:878-888`), verified by `claude_env_applied(settings_path, port)` (`:908-911`), recorded as `activated: true` in `gateway.json` (`:3364`). The three consuming surfaces are the status report, the install carry-forward path, and (missing entirely) a SessionStart heal.

## Call-map (frozen scope — .architect-team/bug-isolation/gateway-activation-drift/scope.json)

```
setup.py --external-llm
  └─ setup_entry (install_gateway.py:3630-3695)
       └─ _cmd_install
            ├─ activate? → apply_claude_env (878) → report.activated=True
            ├─ elif prior_state.activated (3201-3209)  ← BUG B: trusts state, no verify
            │    └─ report.activation_carried=True → ok row
            ├─ state write (3364): activated = report.activated OR prior.activated
            └─ setup row (3664-3670): "activated=carried-forward"  ← green lie surface

install_gateway.py status
  └─ _cmd_status (3374-3475)
       ├─ report.activated = claude_env_applied(settings, port) (3397)  ← honest bool
       ├─ summary "activated={bool}" (3408-3414)      ← BUG A: no recorded-vs-actual compare
       └─ footer "Claude Code activation: not applied" (3858)  ← indistinguishable from clean

SessionStart hook (hooks/sessionstart-run-continuity.py)
  └─ main() (238-259)
       └─ maybe_heal_model_split (136-235)   ← heals split only; BUG C: no activation heal
```

## Root cause (class statement)

The class of bug: **a recorded-consent flag (`gateway.json.activated`) is treated as ground truth for the live client-side wiring it merely remembers, on every surface that reports or depends on it, with no verify-against-reality step and no heal.** Any non-merge-preserving writer of settings.json (observed 2026-07-18→19) silently severs the wire while all surfaces stay green. The fix addresses the whole class: every consumer of `activated` either verifies against `claude_env_applied()` or heals from the recorded consent — never trusts the flag bare.

## Proposed fix

### A. `_cmd_status` — detect + name the drift (report-only; status observes, install repairs)

After `report.activated = claude_env_applied(...)` (`:3397`), compute `drifted = bool(state.get("activated")) and not fully_applied`, where **fully-applied = `ANTHROPIC_BASE_URL` equals the gateway URL AND `ANTHROPIC_AUTH_TOKEN` is present** (B4 supplement-2: a rewrite that drops only the token is half-drift — it fails loud rather than silent, but the predicate covers it cheaply; `claude_env_applied()` itself keeps its BASE_URL-only semantics for its other callers). Carry it as `report.activation_drift`. **The `--json` payload (`_emit`, `:3819-3840`) gains an explicit `activation_drift` field** (B4 supplement-1: the dict is hand-built, so the drift must be first-class on the machine-readable surface, not implicit in `steps[]`). Surface it three ways:

1. Summary token: `activated=False (DRIFTED)` instead of `activated=False`.
2. A dedicated step row: `[x] activation-drift  recorded activated=true but settings.json lacks the gateway env block (a settings rewrite dropped it); heal: re-run `install --activate`, or simply start a new session — the SessionStart self-heal re-applies it`. Status stays fail-row-only — it never writes.
3. Footer: `Claude Code activation: DRIFTED (recorded activated; env block missing)` replacing `not applied` in the drift case only.

A machine with `state.activated` falsy keeps today's output byte-identical (the replication tests' markers deliberately exclude the generic `not applied` / `activated=False` strings; drift text appears ONLY on genuine drift).

### B. Install carry-forward — verify, then heal from recorded consent

In the `elif prior_state.get("activated"):` branch (`:3201`):

1. Resolve `settings_path` (same `args.settings_path or _setup.DEFAULT_USER_SETTINGS_PATH` pattern as `:3395`) and use **`args.port`** — the port THIS install serves and records into the state write (`:3352`); verifying against a stale `prior_state` port would print green "verified" against a port the new install no longer serves (B4 gap-3).
2. `claude_env_applied(...)` true → keep the carry-forward ok row, now reworded to state it was VERIFIED ("activation carried forward (verified against settings.json)").
3. False → drift. **Corrupt-settings abort first (B4 gap-4)**: if settings.json EXISTS but is unparseable JSON, emit a FAIL row ("settings.json is unparseable — refusing to auto-heal over it; repair the file or re-run install --activate") and do NOT call `apply_claude_env` (whose `_read_settings` would silently treat corrupt as `{}` and overwrite — acceptable only under an EXPLICIT `--activate`, never under an automatic heal). Otherwise read the persisted master key: `read_env_file(base / ENV_FILE_NAME).get(MASTER_KEY_VAR)`. Key present → `apply_claude_env(settings_path, args.port, key)`, set `report.activated = True`, ok row "activation drift healed — settings.json had lost the gateway env block; re-applied from the served port + persisted master key (recorded activated=true is the prior consent)". Key absent/unreadable → FAIL row naming the drift + remediation (`install --activate`), and `report.activation_carried` stays False so no surface prints a green carried-forward.
4. State-write (`:3364`) is unchanged in shape — `activated` keeps recording consent — but on the healed path `report.activated` is now genuinely true; on the unhealable path the fail row is the loud signal while consent stays recorded (so the SessionStart heal stays armed).
5. `setup_entry` display (`:3664-3666`): `carried-forward` prints only when `activation_carried` is genuinely verified; the healed path prints `activated=True`-shaped output via the existing `report.activated` field; the unhealable path surfaces the fail row via the existing failed-steps branch (`:3652-3655`, degrades the setup row to warn) — never a green `carried-forward`.

### C. SessionStart `maybe_heal_activation()` — symmetric self-heal

New function in `hooks/sessionstart-run-continuity.py`, mirroring `maybe_heal_model_split`'s structure and guards:

- **Installed-copy guard with explicit-injection bypass (B4 gap-1i)**: identical guard, injectable `plugin_root`/`plugins_base` — a dev checkout NEVER heals the REAL settings.json. BUT when BOTH `gateway_state_path` AND `settings_path` are explicitly passed (the programmatic/test seam), the copy guard is bypassed: explicit injection of both paths is itself the consent to operate on those sandbox paths, and the real SessionStart wiring (`main()`) never injects anything. This keeps the guard's purpose (protecting the real machine from dev/test sessions) without making the seam untestable. `plugin_root`/`plugins_base` remain for guard-behavior tests.
- **State guards**: `gateway.json` (via injectable `gateway_state_path`, else `CT6_GATEWAY_HOME`, else `~/.architect-team/gateway/gateway.json`) must record `activated` truthy AND `enabled` truthy AND `auth_mode == "api-key"` (the env block exists only in api-key mode).
- **Gateway-liveness guard (B4 gap-2 — the audited class must not recur inside the fix)**: the recorded `enabled` flag is NOT trusted bare. Before any write, probe `127.0.0.1:<port>` with a short (~0.25s) TCP connect via an injectable `port_probe` seam (default: real `socket.create_connection`). Nothing listening → fail-open no-op — re-pointing sessions at a dead gateway would convert silent drift into hard-broken sessions. The probe is read-only liveness, not an HTTP request.
- **Settings guard** (injectable `settings_path`, default `~/.claude/settings.json`): heal when `env.ANTHROPIC_BASE_URL` is ABSENT, or when it EQUALS the recorded gateway URL but `ANTHROPIC_AUTH_TOKEN` is absent (half-drift, B4 supplement-2 — the URL is provably ours, so completing the pair is safe). Present-and-equal with token → no-op (healthy). Present-but-DIFFERENT → no-op returning `""` — a user-customized BASE_URL is never clobbered (the same posture as `remove_claude_env`, `install_gateway.py:891-905`).
- **Heal**: port from `state.get("port", 4000)`; master key = the PERSISTED `CT6_GATEWAY_MASTER_KEY` parsed from `<state dir>/gateway.env` (tiny local KEY=VALUE parser — the hook keeps local copies per its existing `_SPLIT_POLICY_STRINGS` convention; the key is never re-derived). Merge-preserving write: read settings JSON (missing/corrupt → treat as `{}` only when missing; a CORRUPT existing file aborts fail-open — never overwrite a file we cannot parse), update `env` dict with both entries, write back `indent=2`.
- **Fail-open**: every failure path (missing state, corrupt JSON, absent key, unwritable file) returns `""` — a session start can never wedge on this.
- **Note**: returns `"[CT6 activation self-heal] settings.json had lost the gateway env block while gateway state records activation; re-applied ANTHROPIC_BASE_URL=http://127.0.0.1:<port> + the persisted auth token (merge-preserving). New sessions route through the gateway; restart Claude Code for this machine's other live sessions."`
- `main()` invokes the activation heal FIRST, then the split heal, and prints both notes (order test-pinned — B4 supplement-3: the wire heal precedes the policy heal so the notes read coherently on a machine recovering from both drifts).

### D. Suite machine-state isolation (REQ-004 — the root clobberer)

The CLI's default-path resolution is CORRECT production behavior (a real `uninstall` must deactivate the real settings); the defect is test-side: one test omitted injection, and nothing structural prevented the omission. Three layers, smallest first:

1. **The leaking test** (`tests/test_install_gateway.py:855-860`) gains `--settings-path str(tmp_path / "settings.json")`.
2. **Module-level prevention**: an autouse function-scoped fixture in `tests/test_install_gateway.py` (depending on the `gw` fixture) monkeypatches `gw._setup.DEFAULT_USER_SETTINGS_PATH` to `tmp_path / "default-settings-sentinel.json"` — any test that omits `--settings-path` lands in the sentinel, never the real file. A probe regression test FIRST asserts the sentinel redirect is active (`!= Path.home()/".claude"/"settings.json"` — fails fast pre-fix with NO side effects), THEN executes the exact leaking invocation shape and asserts the deactivation landed in the sentinel.
3. **Suite-wide detection**: a session-scoped autouse tripwire in `tests/conftest.py` snapshots the real `~/.claude/settings.json` + `~/.architect-team/gateway/gateway.json` + `gateway.env` (bytes or absent-marker) at session start and compares at session end; any mutation fails the run loudly, naming the machine-state-isolation rule and the delta. Scope deliberately excludes log files (the live gateway appends constantly). This converts ANY future leak of the class — any module, any state file — into a named failure instead of silent machine damage.
4. `tests/test_install_librarian.py:347` — AUDITED (B4-delta): NOT leaky; `test_base_dir_env_override` monkeypatches `CT6_LIBRARIAN_HOME` to tmp before the call and the librarian never touches settings.json. No change.
5. B4-delta hardenings (g1/g2/g4, all folded): the module's `_scrub_signals` POINTS `CT6_GATEWAY_HOME` at a per-test tmp sentinel instead of DELETING it (an omitted `--base-dir` currently resolves the REAL `~/.architect-team/gateway/` — same class, one step over; mirrors the conftest `CT6_PLUGIN_REGISTRY` pin idiom); the tripwire snapshot set adds `key-declines.json`; the tripwire failure message names the concurrent-legitimate-writer possibility (a user running `install --activate` mid-suite) as a triage hint.
6. Probe implementation note (B4-delta): the sentinel settings file must be PRE-SEEDED with the port-4000 env block before the leaking-shape invocation so `remove_claude_env` has something to strip — the ordering constraint is assert-sentinel-active BEFORE the invocation; tmp-path prep writes are side-effect-free.

## Reuse decisions

- `claude_env_applied` / `apply_claude_env` / `read_env_file` / `MASTER_KEY_VAR` / `ENV_FILE_NAME` (`install_gateway.py:316-391, 878-911`) — REUSED verbatim on the installer side; no new helpers there.
- `maybe_heal_activation` is a NEW function in an EXISTING file, patterned line-for-line on `maybe_heal_model_split` (`hooks/sessionstart-run-continuity.py:136-235`): same guard order, same injectable params, same fail-open posture, same local-copy convention for constants the hook cannot import at fail-open time. Reuse Decision: extending the existing hook (not a new hook file) because SessionStart wiring, stdin handling, and the fail-open frame already live there; a second hook file would duplicate all three.
- Test seams REUSED from the B1 artifacts: `--base-dir`, `--settings-path`, `CT6_GATEWAY_HOME`, `_default_runner`/`_default_spawner` stubs, fake keys.

## Dev Environment

This repo IS the deliverable (a Claude Code plugin; stdlib-only Python). The live dev environment is the local machine:

- **Deploy** = the fix exists in repo source; verification runs the FULL pytest suite (`python -m pytest -v`, green under both Windows cp1252 and `PYTHONUTF8=1`) + the sandboxed end-to-end CLI subprocess tests (real `install_gateway.py` invocations against `--base-dir`/`--settings-path` sandboxes).
- **Read-only live check**: `python scripts/setup/install_gateway.py status` against the REAL machine state (no `--live`, no mutation) must show a healthy, drift-free report (the machine's env block was restored 2026-07-19 02:58) and must NOT print any drift text.
- **HARD RULE**: the LIVE gateway (port 4000, `~/.architect-team/gateway/`) and the REAL `~/.claude/settings.json` are never mutated, stopped, or restarted by this run — the fix touches no gateway config, and the never-dark discipline stands. The installed plugin copy is NOT rewritten by this run; the fix reaches it at the next plugin update (and the new heal is exercised in sandbox only).

## Test plan

1. B1 replication artifacts flip green — with ONE sanctioned repair (B4 gap-1ii): `test_sessionstart_main_does_not_restore_drifted_env` as originally authored is unsatisfiable (its HOME monkeypatch cannot redirect `Path.home()` on Windows, and its asserted path never matches the default resolution). The bug-replicator — the artifact's author — re-authors the FACET-C pair to a satisfiable shape BEFORE B5: (a) the drift-heal E2E asserts via the explicit-injection seam (`gateway_state_path` + `settings_path`), and (b) a `main()`-wiring test asserts the activation heal is invoked from `main()` (module-level monkeypatch returning a marker note asserted on stdout). B6 replays the repaired artifacts verbatim; no further edits after B5 begins.
2. New unit tests: heal guards (dev-checkout no-op WITHOUT full injection, explicit-injection bypass, subscription-mode no-op, enabled-false no-op, **gateway-not-listening no-op (injected `port_probe`)**, custom-BASE_URL never clobbered, corrupt-settings abort on BOTH heals, absent-key fail-open, merge-preservation of unrelated keys + the agent-teams flag), status clean-machine output unchanged, carry-forward verified-path wording **against `args.port`**, carry-forward unhealable-path fail row.
3. Full suite green under both encodings; test counts recorded in CHANGELOG.
