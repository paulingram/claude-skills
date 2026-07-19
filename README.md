# CLAUDE TEAM SIX
<!-- architect-team:readme-theme=midnight -->
<!-- internal plugin slug: architect-team — preserved for backward compatibility -->

```
       ██████ ██       █████  ██    ██ ██████  ███████
      ██      ██      ██   ██ ██    ██ ██   ██ ██
      ██      ██      ███████ ██    ██ ██   ██ █████
      ██      ██      ██   ██ ██    ██ ██   ██ ██
       ██████ ███████ ██   ██  ██████  ██████  ███████

       ████████ ███████  █████  ███    ███      ███████ ██ ██   ██
          ██    ██      ██   ██ ████  ████      ██      ██  ██ ██
          ██    █████   ███████ ██ ████ ██      ███████ ██   ███
          ██    ██      ██   ██ ██  ██  ██           ██ ██  ██ ██
          ██    ███████ ██   ██ ██      ██      ███████ ██ ██   ██

                        ─── C T 6 ───   v 3 . 41 . 1
```

> **CLAUDE TEAM SIX (CT6)** — spec-to-production multi-agent coding pipeline
> for Claude Code. Takes a requirements folder (OpenSpec / Superpowers / plain
> markdown), drives it through a 100%-coverage planning loop with reuse-first
> design, spawns **long-lived named teammates** (Claude Code Agent Teams
> primitive — Lead + N teammates, each with its own 1M context, shared task
> list, `SendMessage` for direct messaging) for backend / frontend, enforces
> review gates via hooks, **fixes design drift to spec autonomously**,
> **verifies the editable surface is complete**, **tests full-stack work
> against the real backend**, **auto-spawns fix teams from every surfaced
> issue**, **remembers what it learns in a local searchable memory**, and
> **auto-commits and pushes on a clean pass** — the dev loop closes itself
> end-to-end.

> The Claude Code plugin slug is `architect-team` (preserved for backward
> compatibility with existing installations + the 23 slash commands like
> `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`,
> `/architect-team:inject`). CLAUDE TEAM SIX is the user-facing name.

![version](https://img.shields.io/badge/version-3.41.1-2563EB?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-3FB950?style=flat-square)
![tests](https://img.shields.io/badge/tests-5689%20passing-3FB950?style=flat-square)
![claude code](https://img.shields.io/badge/Claude%20Code-plugin-7C3AED?style=flat-square)

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  REQUIREMENTS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

v1.0.0 makes Claude Code's experimental **Agent Teams** primitive the default
dispatch mode — long-lived named teammates with their own 1M context windows
and a shared task list, instead of the v0.10.0 ephemeral one-shot subagents.
Teams mode requires **two** things to be true; the pipeline auto-detects both
and falls back to subagents mode (the v0.10.0 behavior, unchanged) when either
is missing.

| Requirement | Detail |
|---|---|
| **`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`** | Set as a shell env var, or as `{"env": {"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"}}` in `~/.claude/settings.json`. `/architect-team:architect-team-setup` checks for it and (with your consent) offers to add it to your settings file. |
| **Claude Code ≥ 2.1.32** | Older versions don't ship the Agent Teams primitive. `/architect-team:architect-team-setup` checks `claude --version`. |
| **`--no-teams` fallback** | Forces subagents mode even when the flag + version qualify — escape hatch for users hitting experimental-flag instability. Pass it on `/architect-team`, `/architect-team:bug-fix`, or `/architect-team:mini`. |

Without the flag set or with Claude Code < 2.1.32, the pipeline runs in
subagents mode silently — same dispatch behavior as v0.10.0, no surprise. With
the flag set + version OK, the pipeline runs in teams mode automatically and
emits a one-line note at startup recording the choice in `intake-state.json`.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v3.41.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### v3.41.0 — the GLM secondary made real (per-provider route dialects + a spawn-compatible impersonation alias + a true completion-probe confirm)

The v3.40.0 selectable secondary was selectable but not **usable**: every Anthropic-format call to `ct6-secondary` 404'd at the provider (wrong API dialect), a teammate spawn on the alias died client-side before any HTTP (Claude Code's Agent-Teams spawn path accepts only known Claude model ids), and setup still printed "CONFIRMED live" because it probed model *listing*, not completion *serving*. v3.41.0 fixes the class, not the symptom — both live-verified on a real machine (2026-07-17).

| Capability | What it is |
|---|---|
| **Registry route dialects (BUG-A)** | Each `SECONDARY_PROVIDERS` entry now REQUIRES a `route_dialect` naming the LiteLLM provider prefix its API actually implements — `openai` → `openai/` (the Responses-API dialect codex-gen models require); `zai` → `hosted_vllm/` (strict chat-completions; api.z.ai has no `/responses` — live 404 at `/v4/responses`). The gateway route is DERIVED as `<route_dialect>/<model>` — the old `route_model` field is gone, so an entry can never carry a route string inconsistent with its dialect, and no hard-coded prefix survives in the generator. A future chat-completions-only provider stays ONE dict entry. |
| **The spawn-compatible impersonation alias (BUG-B) — DISCLOSED** | Claude Code's Agent-Teams spawn path validates teammate model ids client-side: a spawn on a custom alias emits ZERO gateway requests (gateway-log verified). The role split therefore now writes **`claude-haiku-4-5`** (`SPAWN_ALIAS_MODEL_ID`, a real harness-accepted Claude id) into dev-class agent frontmatter, and the generated config maps that id to the chosen secondary's model AHEAD of the anthropic catch-all. **Disclosure, stated plainly: requests labeled `claude-haiku-4-5` through THIS gateway are answered by the chosen secondary (e.g. GLM 5.2), not by Anthropic's Haiku.** The mapping is recorded in `gateway.json` (`spawn_alias` / `spawn_alias_maps_to`), printed by `status` ("claude-haiku-4-5 -> glm-5.2 (impersonated secondary)"), and the id is test-pinned so changing it is a deliberate act. `ct6-secondary` remains served for direct/scripted callers; the SessionStart self-heal now heals to the state-recorded spawn alias. |
| **The confirm probes the right hop** | `confirm_gateway_serving` now requires a real bounded `/v1/messages` completion (max_tokens 32, non-empty content block; spawn alias first, `ct6-secondary` fallback) on top of the `/v1/models` listing before anything says **"CONFIRMED live — CT6 runs the split"** — with one automatic gateway-restart repair cycle, and an honest two-hop report: the gateway completion is CONFIRMED; harness teammate-spawn routing is verifiable only from a fresh session. `--check-only` / `--no-register` still never probe; key-less CI stays hermetic through the same injectable seam. **Iteration 2 — the confirm is identity-verifying:** the completion response's `x-litellm-model-id` is resolved via `/model/info` and must map to the registry-derived dialect route, so a completion answered by the `anthropic/*` wildcard's real-Haiku deployment FAILS with the observed upstream named ("served by anthropic/claude-haiku-4-5, expected hosted_vllm/glm-5.2") instead of confirming — and a config-regenerating install now restarts a running gateway (any byte-level config change), so the process serves the config the installer just wrote. **Iteration 3 — the confirm is spawn-mandatory and served-state-aware:** when the state records a spawn alias, the completion + identity probe runs ON that alias and its failure FAILS the confirm — no `ct6-secondary` fallback green (the fallback survives only for legacy states with no recorded spawn alias) — and staleness is judged against the SERVED state, not the prior file: the generated config's model-group set + the secondary/spawn routes' expected upstreams are compared against the live `/model/info`, so a file-current-process-stale listener (the state a byte diff can never see) restarts before the confirm. **Iteration 4 — the restart is port-holder-stopping and bind-verified:** when the tracked stop leaves the gateway's own configured port held (an untracked process the task manager never touches), the LISTENING pid is resolved (netstat/lsof, stdlib) and stopped by pid — image-agnostic, with the resolved pid+image named honestly on success and on refusal (refusal = no start attempted) — and "restarted" is reported ONLY after the new instance answers `/model/info` with a state matching the generated config: a still-held port is a named failure after at most one start attempt, never a doomed-instance spawn loop. **Iteration 5 — the install is exactly-one-instance, ownership-verified, and auth-enforcing:** before its single start, install stops every process whose cmdline carries this state dir's config path (the ownership proof; Windows path forms — case, separators, 8.3 short names — normalized), and register never blind-starts over a held port (the every-install blind start was how 8 instances piled up); after the one start, the port-holding pid must BE the just-launched instance (per-launcher pid seam / launch-window match), so a zombie winning the bind race with a state-matching config is a NAMED failure, not silent service; the confirm additionally sends a deliberately-invalid key (never echoed) and requires that it be DENIED service — a 4xx is clean enforcement; a crash-500 (the prisma no-DB quirk below — how every healthy DB-less gateway answers an invalid key) is enforcement with a named warning and the confirm PROCEEDS; only a 200 (auth unenforced — service granted to a bad key) fails the confirm naming the auth state, and the auth rung fires only after a passed completion rung, so a down gateway can never surface the warning as green; and the master key NEVER rotates on a re-install (pinned), so redeploys never invalidate the settings.json auth token live sessions depend on. **Iteration 6 — the deploy is verify-then-swap, never dark:** before ANY live-instance stop, a STAGING instance of the identical generated config (only the launch port swapped; launched through the same env-sourcing launcher template as the cutover start) must pass the FULL ladder on the staging port — bind + served-state, staging-bind ownership, the REAL-key completion with upstream identity (an unresolved master key denies the real key service and fails exactly here — the 2026-07-18 offline-incident state), then auth enforcement — structurally proving config AND env health; only on staging-green does the cutover fire, followed by a post-cutover re-verify with ONE bounded retry for a port-race winner, and retry exhaustion embeds the recovery procedure below. Any staging failure leaves the old instance serving, and the staged instance is stopped on ALL exit paths (green / failure / exception — test-pinned), never accumulating on the staging port. The generated launchers close the pile-up vector at its root: each REFUSES to launch when the port THIS launch binds is already LISTENING (naming the holder pid; a staging launcher keys its own staging port) and logs masked master-key presence (first 8 chars, or an explicit MISSING) before exec'ing litellm. **Iteration 7 — instances are process TREES and staleness is route-contradiction:** the launcher chain (`cmd` → `litellm.exe` → `python.exe`) is ONE instance — owned pids are grouped by validated parent chain (recycled-pid links severed by creation-time ordering), the accumulation sweep NEVER touches any pid in the port-holder's tree (deploy-6 stopped the listener's parent as a "non-holder" and darkened the port), while the deliberate cutover/repair/teardown stops take the holder's WHOLE tree root-first (`taskkill /t` — no respawn-capable orphan); and the served-state comparison is two-armed route-contradiction — a fresh instance's wildcard-advertised `anthropic/<id>` expansions are ROUTED (not stale; the false-restart accelerant is gone), a served route contradicting the config's prescription for that name (explicit routes take precedence over catch-all expansion) is stale, and a served state missing any explicitly-routed config group is stale (the silently-absorbed-alias escape). |
| **Troubleshooting: the prisma no-DB auth 500** | A DB-less LiteLLM deployment (the CT6 gateway runs without a database) answers ANY failed auth with HTTP **500** + `ModuleNotFoundError: prisma` instead of a clean 401. If `/v1/messages` 500s with a prisma traceback, it is an AUTH failure in disguise: use the generated master key from `~/.architect-team/gateway/gateway.env` (`CT6_GATEWAY_MASTER_KEY`; `--activate` writes it into settings.json as `ANTHROPIC_AUTH_TOKEN`). |
| **Troubleshooting: `400 no_db_connection` on everything — the offline-incident recovery** | The error is misleading: it is NOT a database problem. On a DB-less gateway a FAILED master-key check falls into LiteLLM's `prisma_client is None` branch (`user_api_key_auth.py:1537`) — the serving instance's `CT6_GATEWAY_MASTER_KEY` never resolved (2026-07-18: the port winner among 8 piled-up instances). Recovery, in order: **1)** kill every instance launched against THIS gateway's config — match the config path in the cmdline, never a bare image name (PowerShell: `Get-CimInstance Win32_Process \| Where-Object { $_.CommandLine -match 'litellm' -and $_.CommandLine -match 'gateway\\config\.yaml' } \| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }`; POSIX: kill the pids `ps -axo pid=,args=` lists against `<state-dir>/config.yaml`); **2)** verify the port is free (`netstat -ano \| findstr :4000` / `lsof -ti tcp:4000`); **3)** start exactly ONE instance via the generated launcher (`run_gateway.bat` / `run_gateway.sh` — which now logs masked key presence, so a MISSING line diagnoses the env immediately); **4)** verify: `python scripts/setup/install_gateway.py status --live`. **Never-dark deploy note:** the installer now stages before it swaps — a manual stop-then-start against the live port is exactly the incident shape; prefer re-running the installer (or at minimum the launcher, whose port guard refuses a pile-up). |
| **Follow-ups (documented, not shipped)** | **Path B** — a claude-shaped NAMED alias (e.g. `claude-ct6-secondary`) as a future toggle if the harness relaxes id validation to prefix rules: would remove the impersonation trade-off while keeping spawn compatibility. **Path C** — upstream Claude Code support for custom teammate model ids (the root fix for BUG-B); until then the impersonation route is the standard LiteLLM pattern for harness-constrained callers. |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v3.41.1  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### v3.41.1 — activation-drift detection + SessionStart self-heal (the recorded-consent flag is never ground truth)

A non-merge-preserving rewrite of `~/.claude/settings.json` (observed 2026-07-18→19) silently dropped the gateway env block (`ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`) while `gateway.json` still recorded `activated: true` — and every consuming surface stayed green. The bug **class**: a recorded-consent flag is treated as ground truth for the live client-side wiring it merely remembers, with no verify-against-reality step and no heal. v3.41.1 fixes the whole class — every consumer of `activated` either **verifies** against `claude_env_applied()` or **heals** from the recorded consent, never trusts the flag bare.

| Capability | What it is |
|---|---|
| **Status names the drift (REQ-001)** | `install_gateway.py status` now computes `activation_drift` = recorded `activated` truthy AND the settings.json env block not FULLY applied (BASE_URL equal to the gateway URL AND the auth token present — a token-only loss is half-drift and counts). On drift, the summary carries `activated=False (DRIFTED)`, a dedicated `activation-drift` fail row names the recorded-vs-settings contradiction + the remediation, and the footer prints `Claude Code activation: DRIFTED (recorded activated; env block missing)` instead of the generic `not applied`. The `--json` payload gains a first-class `activation_drift` field. A machine whose recorded `activated` is falsy keeps today's output byte-identical — drift text appears ONLY on genuine drift. Status observes; it never writes. |
| **Carry-forward verifies + heals (REQ-002)** | A plain `install` (no `--activate`) on a machine whose `gateway.json` records `activated: true` no longer trusts the flag bare. It verifies `claude_env_applied()` against the resolved settings path + `args.port` (the port THIS install serves — never a stale prior-state port). Verified → the carry-forward row names the verification. Drifted → a corrupt settings.json ABORTS first (only an explicit `--activate` may overwrite a corrupt file), else the env block is re-applied via `apply_claude_env()` from the served port + the PERSISTED master key in `gateway.env` (the recorded `activated: true` IS the prior consent; the key is never re-derived), with a heal row + `report.activated=True`. Unhealable (no persisted key) → a FAIL row with the `install --activate` remediation, never a green carried-forward. |
| **SessionStart self-heal (REQ-003)** | A new `maybe_heal_activation()` in `hooks/sessionstart-run-continuity.py`, symmetric to `maybe_heal_model_split`. When the gateway state records `activated` + `enabled` + `auth_mode: api-key` and settings.json lacks the env block, it probes `127.0.0.1:<port>` (a short TCP liveness check via an injectable seam — the recorded `enabled` flag is never trusted bare; re-pointing sessions at a dead gateway would hard-break them) and only then re-applies the env block merge-preservingly from the recorded port + the persisted master key, printing a one-line heal note (with the restart caveat for already-running sessions). Guards: a dev checkout is never rewritten (explicit injection of both state + settings paths bypasses the copy guard for the programmatic/test seam); a present-but-different `ANTHROPIC_BASE_URL` is never clobbered (a user-customized value wins); a half-drift (BASE_URL ours, token absent) is completed; a corrupt settings.json aborts fail-open (never overwrite a file we cannot parse). Every failure path returns silently — a session start can never wedge on this. `main()` runs the activation heal FIRST, then the split heal. |
| **The root clobberer: the test suite itself (REQ-004)** | Found mid-run, and the actual origin of both incidents. `tests/test_install_gateway.py::test_uninstall_purge_removes_state_dir` ran a REAL `uninstall` with `--base-dir`/`--agents-dir` sandboxed but **no `--settings-path`**, so `_cmd_uninstall` resolved the DEFAULT `~/.claude/settings.json` and stripped the env block. On CI and never-activated machines it silently no-ops — which is why it went unnoticed — but on an ACTIVATED machine **every full `pytest` run deactivated the gateway**, producing exactly the drift the rest of this release detects and heals. (The product was never at fault: `uninstall` touching the real settings.json is correct for a real user. The defect was a TEST invoking it unsandboxed.) Fixed in three deliberately-redundant layers: **(a)** the leaker now names `--settings-path`; **(b)** a module-wide autouse fixture redirects `DEFAULT_USER_SETTINGS_PATH` to a per-test sentinel so no test in that file — present or future — can reach the real path, with a probe test proving the redirect absorbs the fallback; **(c)** a session-scoped tripwire in `tests/conftest.py` SHA-256-digests the real `settings.json` + `gateway.json` + `gateway.env` at suite start and fails LOUDLY at suite end on any mutation, turning any future leak of this class in any test file into a named failure. The tripwire was verified to actually fire against a simulated leak. |
| **Forward-compat: credit-exhaustion failover** | `maybe_heal_activation`'s state guards are read BEFORE the liveness probe, and that ordering is now test-pinned (parametrized, asserting the probe is never called). This makes **recorded consent** the single suppression seam: a future failover that un-points Claude Code when the upstream runs out of credits suppresses the heal by flipping recorded state, with zero guard-logic change — instead of being silently fought and undone on the next session start. TCP port-liveness is explicitly **not** a credit/upstream-health signal: a credit-dead gateway still binds its port. |
| **Counts + tests** | +43 hermetic tests — 8 replication (5 for REQ-001…003 + 3 for REQ-004, all RED pre-fix) + 33 unit + a sentinel-absorption probe + the session tripwire. Suite 5646 → **5689 passing + 4 skipped** (202 test files incl. the pytest-collected replication artifact), green under both Windows cp1252 AND `PYTHONUTF8=1` — and the tripwire staying silent across a full run is now itself the standing evidence that the suite no longer mutates real machine state. `pytest.ini` adds `--import-mode=importlib` so the two `tests/bug-fix-*/test_replication.py` files coexist. Skill / agent / command / hook / Layer-3-tool counts UNCHANGED (48 / 39 / 23 / 7 / 20); NO new skill / agent / command / hook / Layer-3 tool; stdlib-only holds (`socket`, `hashlib`). |

### v3.40.0 — the secondary API becomes a choice (OpenAI Codex or Z.ai GLM 5.2) + the provider-neutral `ct6-secondary` alias

The gateway's secondary model slot is now **selectable** — pick **OpenAI Codex (`gpt-5.6-sol`)** or **Z.ai GLM 5.2 (`glm-5.2`)** at setup — and the role split writes the provider-neutral **`ct6-secondary`** alias instead of a provider-specific id. The choice is asked once, remembered, and never re-asked; a pre-v3.40 install is grandfathered as openai and never sees a popup.

| Capability | What it is |
|---|---|
| **The provider registry** | `SECONDARY_PROVIDERS` in `scripts/setup/set_default_model.py` single-sources every provider (model id, key env var, gateway route, api_base, label): `openai` → `gpt-5.6-sol`; `zai` → `glm-5.2` via `https://api.z.ai/api/paas/v4`. A future provider is ONE new dict entry — help text, prompts, key slots, and config routes all derive from the registry (extensibility test-pinned with a fake provider; no hardcoded name lists). |
| **Choose once, remembered** | Resolution ladder: `--secondary <openai\|zai>` > `CT6_SECONDARY_PROVIDER` > the choice recorded in `gateway.json` > the v3.39-era grandfather (an `openai_model`-only state counts as a recorded openai choice) > an interactive ask (the wrapper's "Choose the secondary API" AskUserQuestion gate / the installer's TTY prompt, interrupt-skips). `--re-ask-provider` re-opens the choice (mirroring `--re-ask-keys`); `--zai-key` joins the v3.38.0 key machinery with FULL decline parity (`decline <anthropic\|openai\|zai>`); `--secondary-model` overrides the upstream id (`--openai-model` stays as a deprecated openai-scoped synonym). Subscription mode honors the choice — the gateway serves the chosen provider's model to direct callers; fable via sign-in unchanged. |
| **The provider-neutral alias** | The split now writes **`ct6-secondary`** under policy **`secondary-split`** (new exported constants `POLICY_SECONDARY_SPLIT` / `POLICY_UNIFORM_FABLE` / `LEGACY_POLICY_CODEX_SPLIT`); readers accept the legacy `codex-5.6-sol` / `codex-split` from a v3.39-era install, writers emit only the new, the uniform lever refuses BOTH aliases, and `--split secondary` is canonical (`--split codex` a deprecated synonym). Ship state UNCHANGED — all 39 committed agents stay `model: fable`. |
| **Adversarially-hardened migration** | 3 review rounds (FAIL → FAIL → PASS) caught 3 MAJOR field defects pre-ship: the SessionStart self-heal now restores the split to the alias `gateway.json` RECORDS as served — never an alias the running config doesn't route, so a legacy install keeps working and migrates on `install --activate`; legacy migration fires on EVERY config-regenerating install with prior-state carry-forward (a plain re-install never silently deactivates — uninstall is the only state downgrade); switching providers never deletes the other provider's stored key. `status --live` probes the state-recorded alias, so a working legacy install confirms green. |
| **Counts + tests** | Gateway tests 92 → 123, lever 37 → 44, fallbacks 35 → 38, sessionstart 13 → 18, commands 56 → 58. Suite 5494 → **5542 passing + 4 skipped** (199 test files). Skill / agent / command counts UNCHANGED (48 / 39 / 23); NO new skill / agent / command / hook / Layer-3 tool; stdlib-only holds. |

### v3.39.0 — one-call external-LLM setup (runtime split targeting + live split confirmation + self-heal)

`--external-llm --yes` is now genuinely **one call**: it asks for missing keys (v3.38.0), provisions + registers + activates the gateway, applies the codex split **where the runtime actually reads it**, and ends by **confirming against the live gateway that CT6 runs the split** — no surprise follow-up steps.

| Capability | What it is |
|---|---|
| **Runtime split targeting** | The split used to land on the dev checkout's `agents/` — which Claude Code never loads (it runs the installed plugin cache copy) and git promptly reverts (ship state is uniform fable). New `set_default_model.installed_plugin_agents_dir()` / `runtime_agents_dir()` resolve the INSTALLED plugin's `agents/` from Claude Code's `installed_plugins.json` (`$CT6_PLUGIN_REGISTRY` override, repo fallback); the gateway installer's activate/status/uninstall AND `setup.py --codex` now target it. The split step names its target dir; the repo stays on committed ship state. |
| **Live split confirmation** | The v3.38.1 field bug proved a generated config can be broken while every install step reports ok. A registered install now ends with a poll of the LIVE gateway's `/v1/models` asserting the mode's ids are actually SERVED (`codex-5.6-sol` always; `claude-fable-5` additionally in api-key mode), with ONE automatic user-level gateway restart + re-probe when a stale process serves a pre-regeneration config. The setup row states it plainly: **"CONFIRMED live — CT6 runs the split"** (or an honest fail row + remediation — never gates). `status --live` verifies any time. |
| **The split survives plugin updates** | A plugin update ships uniform-fable files into a fresh cache dir — previously a silent split revert. `gateway.json` now records the desired `model_policy`, and the SessionStart hook re-applies the split to a drifted INSTALLED copy automatically (a dev checkout is never rewritten; uninstall flips the record so an uninstalled split is never resurrected). |
| **Counts + tests** | Global `tests/conftest.py` registry scrub (no test can rewrite the real installed plugin) + the gateway tests' live-probe stub (no real sockets). Lever tests 29 → 37, gateway 79 → 92, fallbacks 34 → 35, sessionstart 8 → 13. Suite 5467 → **5494 passing + 4 skipped** (200 test files). Skill / agent / command counts UNCHANGED (48 / 39 / 23); NO new skill / agent / command / hook / Layer-3 tool; stdlib-only holds (`urllib`). |

### v3.38.0 — setup asks for missing keys (ask-then-apply, never punt-to-script)

When setup hits a state only you can resolve — a missing `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` — it now **asks for the key in the flow and applies it itself**, instead of printing a run-this-script-yourself remediation as the only path.

| Capability | What it is |
|---|---|
| **The wrapper asks in-session** | `/architect-team:architect-team-setup` and `/architect-team:librarian-install` gain **"Ask for missing keys — never punt"** sections: on an absent-key state (`ANTHROPIC_API_KEY` absent in subscription mode, `OPENAI_API_KEY` absent in provisioned-but-NOT-enabled, the librarian's no-key install) with no recorded decline, the executing agent MUST ask via AskUserQuestion with exactly two dispositions — **capture the key now** (the agent re-runs the installer itself with `--anthropic-key`/`--openai-key`, or the librarian's env-scoped `--enable` run; a `--yes` on the original setup invocation carries over as `--activate` consent) or **explicit decline** (recorded via the new `decline` subcommand so re-runs stop asking). |
| **The installer prompts on a real TTY** | Direct terminal runs need no wrapper: `install_gateway.py` and `install_librarian.py` prompt for a missing key themselves via a hidden (getpass) entry seam — interactive TTY only, blank entry skips, an interrupted prompt (Ctrl-C / EOF) skips too, and non-interactive / non-TTY / `--check-only` / `--json` runs NEVER prompt, never block, never invent a key. A captured key rides the existing env-file path — 0600, masked to last-4 in every report line, never echoed. |
| **Declines are remembered — re-runs never nag** | A per-key `key-declines.json` in each installer's state dir records both a wrapper decline and a blank-to-skip (`via: wrapper` / `prompt-skip`); the record auto-resets the moment that slot's key resolves; `install --re-ask-keys` clears it; `status` reports `declined=` honestly (a decline suppresses the PROMPT, never the truth); `uninstall --purge` removes it symmetrically. |
| **Every posture holds** | Never-gates-setup (a prompt failure degrades to the existing `warn` row), raw keys ONLY in the 0600 env files, consent-gated activation, uninstall symmetry, and subscription mode still a first-class deliberate outcome on decline. The REQ-005 sweep dispositions all 11 `scripts/setup/*.py` — only the gateway + librarian installers qualify; non-user-holdable remediations (plugin installs, npm / PEP-668 environment fixes) deliberately STAY printed. |
| **Counts + tests** | +56 hermetic prompt/decline tests via injectable input / isatty / getpass seams (`test_install_gateway.py` 47 → 77, `test_install_librarian.py` 23 → 39, `test_setup_install_fallbacks.py` 31 → 34, `test_commands.py` 49 → 56). Suite 5409 → **5465 passing + 5 skipped** (200 test files). Skill / agent / command counts UNCHANGED (48 / 39 / 23); NO new skill / agent / command / hook / Layer-3 tool; stdlib-only holds (`getpass`). |

### v3.37.0 — gateway auto-registration (the installer registers + starts it for you)

The external-LLM toggle becomes genuinely one command: when the gateway is enabled, the installer now **executes the boot registration itself and starts the gateway immediately** — user-level on every OS (`schtasks /sc onlogon` as the current user with a **Startup-folder-shim fallback** when schtasks is denied (observed live on a real non-elevated shell) and a detached start-now that never inherits the installer's pipes, `systemctl --user enable --now` with a `default.target` unit, a `~/Library/LaunchAgents` plist), never sudo or admin. `--no-register` opts back to the printed manual hint; a registration failure degrades to a fail step carrying the hint. Uninstall is symmetric — it stops and unregisters before removing state, so `--no-external-llm` fully reverses `--external-llm`. `status` now reports `registered=`. Tests 35 → 46 in `tests/test_install_gateway.py` (per-OS command shapes, never-sudo pins, failure degradation, uninstall symmetry — all through a stubbed runner so no test ever executes a real `schtasks`/`systemctl`); suite 5397 → **5408 passing + 5 skipped**.

### v3.36.0 — the external-LLM gateway (out-of-the-box OpenAI/Codex via LiteLLM, subscription-aware)

The v3.35.0 codex role split gets a **real backend, out of the box**: one setup flag installs and configures the MIT-licensed **LiteLLM** proxy so `codex-5.6-sol` routes to OpenAI — and enabling it **never breaks the Anthropic side**: fable stays usable either through your **Claude subscription sign-in** (no key needed) or through an `ANTHROPIC_API_KEY`.

| Capability | What it is |
|---|---|
| **One-flag enable, managed by setup** | `/architect-team:architect-team-setup --external-llm` (or `CT6_EXTERNAL_LLM=1`) runs the new `scripts/setup/install_gateway.py`: installs `litellm[proxy]` through the same PEP-668-aware ladder as the other Python deps, provisions `~/.architect-team/gateway/` (config, launcher, boot descriptor — register hint printed, never executed for you), and reports one setup row that **never gates** (failures degrade to `warn` + the manual remediation). `--no-external-llm` uninstalls symmetrically; NO signal touches nothing. |
| **Two auth modes — fable via sign-in OR API key** | Resolved from key presence, never a live probe. **api-key mode**: an `ANTHROPIC_API_KEY` resolves → the gateway fronts BOTH providers (`codex-5.6-sol` → OpenAI, everything else → Anthropic); with consent (`--yes`) setup activates Claude Code routing (`ANTHROPIC_BASE_URL` + auth token in `~/.claude/settings.json`) and applies the codex role split — the full out-of-the-box state. **subscription mode**: no Anthropic key → **fable keeps your normal Claude sign-in** (`ANTHROPIC_BASE_URL` deliberately never written), the codex split stays OFF (the harness can't split-route only codex traffic through a proxy — an honest, documented boundary), and the gateway serves OpenAI models to direct callers; the printed remediation is add-a-key + re-run. |
| **Secret hygiene** | Raw keys live ONLY in `gateway.env` (chmod 600, under your home dir, never the repo); `config.yaml` carries `os.environ/...` references; every report masks keys to their last 4 chars; the proxy always runs behind a generated master key. No OpenAI key ⇒ an honest provisioned-but-NOT-enabled state with the remediation printed. |
| **Symmetric lifecycle** | `install_gateway.py status` (mode / masked keys / activation / the agents' model-policy state) and `uninstall` (removes only OUR settings.json entries — a user-customized base URL is never clobbered; restores uniform fable only when the on-disk state is `codex-split` — a manual Opus state is left untouched). `--check-only` on both paths touches nothing. |
| **Counts + tests** | New `tests/test_install_gateway.py` (35 offline cases — per-mode config shape, the codex-alias cross-module pin, secret hygiene, activation both modes incl. the subscription-mode refusal, uninstall symmetry, setup routing + never-gates); the `test_setup_install_fallbacks.py` hermeticity scrub extends to `CT6_EXTERNAL_LLM`. Test files **199 → 200**; suite 5362 → **5397 passing + 5 skipped**. Skill / agent / command counts UNCHANGED (48 / 39 / 23); ship state unchanged (all 39 agents still commit `model: fable`); NO new skill / agent / command / hook / Layer-3 tool. |

### v3.35.0 — the Codex 5.6 model role split (availability-gated, one flag to deploy)

When your harness has **Codex 5.6** available, the agent models split by role: **Fable keeps every architecture, control, and design agent** and **`codex-5.6-sol` takes every development, code-checking, and testing agent**. When it isn't available, nothing changes — the current operating model stays exactly as it is today (uniform `fable`, with the Opus fallback lever where fable itself is unavailable). Setup manages the whole thing; deploying is one flag.

| Capability | What it is |
|---|---|
| **One-flag deploy, managed by setup** | `/architect-team:architect-team-setup --codex` (or `CT6_CODEX_56_AVAILABLE=1`) applies the split; `--no-codex` restores the uniform fable default; **no signal leaves the model state untouched** — the shipped uniform-fable default IS the operating model, and a manual lever state is never silently clobbered. The setup row never gates: any lever failure degrades to a `warn` row carrying the manual remediation. |
| **The role classification (18 / 21) — adversarially re-derived** | `scripts/setup/set_default_model.py` now carries `AGENT_ROLES` — all 39 agents classified per the owner directive, re-derived by 3 independent classifiers with majority-vote adjudication of the hard calls: architecture (system-architect, structure-analyst, route-mapper, endpoint-tracer, the integration explorers + master-synthesizer, codebase-map-reviewer) + control (bug-classifier, prompt-refiner, scaffold-agent, doc-updater, closeout-agent) + design/research (oracle-deriver, interaction-intuiter/observer, domain-researcher, diagnostic-researcher, mcp-design-agent) stay on **fable** (18); development (backend / frontend / integration + the reconciler's hands-on merges) + code checking (task/adversarial/editability/interaction reviewers, test-completeness-verifier, fix-sensibility-checker, the reference-closure + code-search-refutation tracers) + testing (qa-replayer, mini-qa, flow design + execution, bug-replicator, test-run watching + synthesis, visual capture + analysis) take **codex-5.6-sol** (21). An UNCLASSIFIED stem (e.g. a newly scaffolded agent) defaults to the fable bucket — never to codex — and is surfaced by `--check`. |
| **The lever grows split modes** | `--split codex` applies the role split directly; `--auto` is TRI-STATE on `CT6_CODEX_56_AVAILABLE` (truthy ⇒ the split; set-but-falsy ⇒ uniform fable; ABSENT ⇒ no-op — a manually applied Opus fallback is never silently clobbered); `--check` now reports the recognized policy state (`uniform-fable` / `codex-split` / `uniform-<m>` / `mixed`); `--codex-model <id>` overrides the written codex id for a harness that registers Codex 5.6 differently. The uniform `--model` lever still refuses the codex id — codex NEVER applies uniformly (architecture/control/design must stay on fable). |
| **Availability is an input, never probed** | The same injected-availability convention as the service tier's `resolve_model` (SETUP-ADV-1: a harness probe would be false precision): the flag / env var asserts availability; the Opus fallback (`set_default_model.py --model opus`) remains the separate uniform lever for a harness that predates the `fable` alias. Idempotent, line-ending-preserving, only the frontmatter `model:` line is ever touched. |
| **Counts + tests** | `tests/test_set_default_model.py` +18 cases (role-map completeness vs the real agents dir, split apply/revert/idempotence, policy-state transitions, truthy + tri-state env parsing, CLI split / auto both-signals + absent-no-op / check / override, uniform-codex refusal) + `tests/test_setup_install_fallbacks.py` +10 (signal precedence, check-only writes nothing, apply/restore, never-gates + missing-dir warn, main() routing, an autouse hermeticity scrub so an ambient deploy var can never make the suite rewrite tracked `agents/*.md` — a review-confirmed fix). Ship state UNCHANGED: all 39 agents still commit `model: fable` (the split is an install-time policy, like the Opus fallback; `test_agents.py` `VALID_MODELS` gains the codex id so the sanctioned split state is valid-but-not-ship-state). NO new skill / agent / command / hook / Layer-3 tool. |

### v3.34.0 — informative run notifications (emails that tell you what's happening, not just that something happened)

The email notifier's six bare status events become a **ten-event, content-carrying vocabulary**, wired into **every** pipeline — engaging ANY architect-team task now emails its stakeholders meaningfully: what is about to start, where the run stands, what was completed, when it's waiting on agents, and when it's done.

| Capability | What it is |
|---|---|
| **The kickoff email carries the plan itself** | New `run_start` event fires ONCE per run, the moment the architecture + solution plan first exists (Phase 1 / B3 / M3 / U4), and **embeds the plan artifacts** — proposal / design / tasks (or the fix proposal / the distilled flow catalog) — in that ONE email via the repeatable `--plan-file` flag (per-file 20k-char cap with an explicit truncation marker; a missing file degrades to a note, never an error). |
| **Informative, not just status** | Universal flags on EVERY event — `--details` (what's about to happen / what was accomplished), `--progress` (*"4 of 12 phases complete — …"*), `--next-step` — rendered as their own body blocks. The canonical content contract in `common-pipeline-conventions` `## Notifications wiring convention` makes a bare status-only invocation non-compliant wiring; the FIRST `phase_start` of a run carries the requirement summary (the engagement email). |
| **Waiting-on-agents visibility** | New dispatch-wait pair: `waiting_on_agents` fires at every dispatch-and-wait point naming each agent + its mission (`--agents "backend-auth — JWT middleware; frontend-dash — dashboard UI"`); `agents_complete` fires when the dispatch fully returns, with per-agent outcomes. Wired at the major named dispatch points of all four pipelines (team spawns, fix teams, explorers, executors). |
| **A real final email** | New `run_complete` event — the run's LAST notification: what shipped, the final commit SHA, elapsed time. Wired at Phase 8 / B8 / M7-green / U9, right after the v3.30.0 `--mark-complete`. |
| **ux-test joins the wired set** | `skills/ux-test-builder/SKILL.md` previously had ZERO notification wiring. It now carries the full `## Notifications` section — per-U-phase boundaries, `run_start` at U4 embedding `distilled-flows.json` (the test plan), the dispatch-wait pair at U3/U6, `issue_discovered` per routed bug at U8, `git_commit` + `run_complete` at U9. `deploy` is deliberately excluded (the UX test targets an already-live site) — documented, not silent. |
| **Counts + tests** | `scripts/notify/notify.py` `EVENT_TYPES` 6 → **10**; `tests/test_notify.py` + `tests/test_notify_wiring.py` + `tests/test_bug_fix_pipeline_notifications.py` + `tests/test_heartbeat.py` extended (wiring tests now cover FOUR pipelines). Opt-in + best-effort + stdlib-only + secrets-via-env contracts all preserved verbatim. NO new skill / agent / command / hook / Layer-3 tool. |

### v3.33.0 — native Claude Design import (a link, not a zip)

A Claude Design project offered via a LINK now imports NATIVELY — the user pastes a `claude.ai/design/p/<id>` link (and/or names the `claude_design` MCP) and the pipeline fetches the whole design project through the MCP instead of asking for a downloaded zip. The design flows into the EXISTING front-end oracle path with no new downstream consumer.

| Capability | What it is |
|---|---|
| **Detect the offer (both trigger forms)** | New skill `skills/claude-design-import/SKILL.md` over a new stdlib engine `scripts/claude_design/claude_design_import.py` (mirroring `scripts/claude_md/claude_md_efficiency.py`): `detect_claude_design_offer` fires on EITHER a `claude.ai/design/p/<id>` URL OR a `claude_design` MCP mention (an inclusive OR), parsing the `?file=` focus selector + a trailing `Implement:` target; `parse_design_url` reads the id case-insensitively. |
| **Fetch + materialize the WHOLE project** | `materialize_project` writes the fetched screens + assets path-safely to `<workspace>/.architect-team/claude-design/<project-id>/` (`_safe_relpath` REJECTS absolute paths + `..` traversal); `import_claude_design` orchestrates fetch-plus-materialize. The `?file=` / `Implement:` focus prioritizes which screen drives the build — it never drops the rest of the project. |
| **Reuse — no new downstream consumer** | The materialized directory is handed to the EXISTING `agents/oracle-deriver.md` `interactive-mockup` spec_shape (v2.1.0), which flows into `interactive-mockup-discovery` then `visual-to-api-design`. Wired ADDITIVELY into `skills/intake-and-mapping/SKILL.md` (input discovery), `skills/design-fidelity-mapping/SKILL.md` (a first-class design-input source), and the three design-consuming commands (`architect-team` / `visual-to-api` / `ux-test`). |
| **Honest injected-adapter boundary** | The engine is deterministic + OFFLINE — it NEVER calls the network or the MCP. The real `claude_design` fetch is INJECTED at runtime via ToolSearch as a `ClaudeDesignSource` (offline tests use `FakeClaudeDesignSource`); no MCP tokens are persisted. `plan_when_unavailable` gives an instruct-then-fallback (connect the MCP + `/design-login`, else auto-fall-back to the zip/local design path) so a run never dead-ends. Design + a stdlib core + tests, not a live-deployed integration. |
| **Counts + tests** | New `tests/test_claude_design_import.py` (47 offline tests). Skill count **47 → 48** (new `claude-design-import`); test files **198 → 199**. Folds in the stale `tests/test_dispatch_banner.py` version pin (stuck at 3.31.1 since v3.32.0) corrected to 3.33.0. Suite 5212 → **5263 passing + 5 skipped** (199 test files). NO new command / agent / hook / Layer-3 tool. |

### v3.32.0 — Fable 5 default + first-install setup hardening + two SR-driven infrastructure fixes

A real first install of CT6 on a fresh Linux VM hit five distinct setup failures, and the plugin's model defaults predated Fable 5. This release makes **Fable 5** (`claude-fable-5`) the default model everywhere — with an IMPLEMENTED **Opus 4.8** (`claude-opus-4-8`) fallback where the `fable` alias is unavailable — hardens the first-install path against the five observed friction points, and folds in two infrastructure fixes surfaced mid-session by the session-review loop.

| Capability | What it is |
|---|---|
| **Fable 5 agent default + the model lever** | All 39 `agents/*.md` now carry `model: fable`. NEW `scripts/setup/set_default_model.py` — a stdlib-only deterministic CLI lever (`--model fable\|opus\|sonnet\|haiku` / `--check`) that rewrites ONLY the frontmatter `model:` line uniformly (idempotent, line-ending-preserving), mirroring `sync_agent_boilerplate.py`; it is the IMPLEMENTED Opus fallback for a harness that predates the `fable` alias. `setup.py`'s new `check_model_default()` ALWAYS surfaces one informational note carrying that fallback lever — never version-gated (a threshold would be false precision, SETUP-ADV-1), never auto-applied, never gates the run. |
| **Fable 5 service default with an injected fallback** | `services/common/service_config.py`: `DEFAULT_MODEL = claude-fable-5`, new `FALLBACK_MODEL = claude-opus-4-8`, and `resolve_model(preferred, fallback, availability_checker=None)` — a pure function: no checker ⇒ `preferred` (the API errors informatively if a model is genuinely absent); a rejecting OR RAISING injected checker ⇒ `fallback`. `build_llm_client` routes the model through it. The live-availability probe stays an ADAPTER boundary (REPO-4: no network/SDK import in the stdlib core), so `check_separation()` stays green. |
| **First-install setup hardening** | `setup.py` — (a) a missing cartographer names its third-party marketplace source (`kingbootoshi/cartographer`) and prints the exact `/plugin marketplace add` + `/plugin install` remediation (the gap that cost a real install a GitHub search); (b) an npm EACCES/EPERM global-install failure retries ONCE non-persistently with `--prefix ~/.local` and surfaces the persistent `npm config set prefix` remediation (never mutating your npm config); (c) a PEP-668 install ladder — `uv pip --system` → `pip install --user` → `--break-system-packages` on the externally-managed error, with an actionable `python3-pip` hint (no traceback) when no pip exists — plus `tiktoken` (a cartographer runtime dep) added to the dep list; (d) `--yes` / `-y` AND `CT6_SETUP_ASSUME_YES=1` short-circuit every consent prompt for non-interactive installs (`--check-only` still never writes). README + `commands/architect-team-setup.md` document all four. |
| **Skill-gate teammate false-block fix (SR)** | `hooks/pretool_skill_gate.py` — arm 1 (the latest-genuine-prompt gate) previously lacked arm 2's worker-session standdown, so a teammate whose spawn brief carried the pipeline command as its latest prompt was blocked on every build/dispatch tool (M1); and an inbound `<teammate-message>` peer envelope re-anchored the genuine-prompt search PAST the Lead's satisfying Skill call, re-arming the gate mid-run (M2). Both arms now share one `_is_worker_session` standdown (via `run_continuity`, so the two cannot diverge) and the genuine-prompt anchor EXCLUDES `<teammate-message>` envelopes. Observed live 4× across two runs this session. 9 regression tests. |
| **Atomic lock publish (SR)** | `hooks/locks.py` — the identical-scope multi-winner race (a pre-existing ~20% flake in `test_locks_concurrency`, root-caused by a 3-researcher diagnostic loop with quantified attribution) is closed by an ATOMIC publish: an acquirer serializes the full payload into a per-acquirer `.inflight.tmp` and `os.link`s it onto the final path, so every reader observes a fully-populated lock — no empty create→write window for `_sweep_stale` or the Step-3 reclaim branch to clobber. A guarded EXCL-create-in-place fallback (no-hardlink filesystems) keeps a residual window, protected by an `_is_inflight` zero-length-and-recent grace guard + TOCTOU re-reads on both destroyer paths. 0/400 multi-winner post-fix; RT-1…RT-5 regression pins. |
| **Docs + tests** | Version → **v3.32.0**; README bare `/architect-team-setup` command forms fixed (5 sites → `/architect-team:architect-team-setup`, + one in `common-pipeline-conventions`). New `tests/test_setup_install_fallbacks.py` + `tests/test_set_default_model.py`; `test_agents.py` gains `fable` in `VALID_MODELS` + a uniform-fable pin; ~38 per-agent model pins flipped across 19 test files. Suite **5212 passing + 5 skipped** (198 test files; canonical Windows-with-PyYAML — macOS-without-PyYAML is 5213 + 4 skipped, the same 5217-collected total). Skill / agent / command counts unchanged; NO new skill / agent / command / hook / Layer-3 tool. |

### v3.31.0 — instruction-compliance standard: a rubric + a deterministic lint + an enforced suite gate

CLAUDE TEAM SIX IS a body of AI-facing instructions — 47 `skills/*/SKILL.md`, 39 `agents/*.md`, 23 `commands/*.md`, `CLAUDE.md`, and the two `docs/*_MAP.md` maps (112 files). An agent's compliance is only as reliable as those instructions are uniform, unambiguous, and internally consistent — yet there was no written standard for what "compliant" instruction text looks like, and the test pins checked only frontmatter *presence*, not *shape*, section structure, cross-reference validity, or wording. This release establishes the standard, mechanizes its machine-checkable half as a suite-enforced lint, remediates every in-scope file to a pass, and adds enforcement ONLY where wording alone cannot hold compliance (which, this run, was nowhere).

| Capability | What it is |
|---|---|
| **The rubric (the contract)** | `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` grades every in-scope file on **three equally-weighted dimensions** — a file passes only when all three pass: **(a) structural / format uniformity** [DETERMINISTIC] (frontmatter fence + `yaml.safe_load` parse, the house no-`': '`/no-`' #'` YAML-hazard rule, required fields per class, a uniform 1024-char raw-description cap, section structure, cross-reference validity); **(b) terminology + contradiction hygiene** [LLM-judgment] (one term = one meaning, no cross-file contradiction, canonical-home discipline, consistent inventory counts); **(c) literal-imperative wording** [LLM-judgment] (every load-bearing rule a followable imperative, hedges only on advisory text). |
| **The deterministic engine** | `scripts/compliance/instruction_compliance.py` (stdlib-only, `yaml.safe_load` when importable, no import-time side effects, mirroring `scripts/claude_md/claude_md_efficiency.py`): `assess_instruction_files(root)` checks dimension (a) + cross-reference validity across the in-scope set. The 1024-char cap is measured on the RAW authored description BEFORE any `' #'`/`': '` truncation can mask an over-length value, for all three frontmatter classes. The cross-reference grammar is NARROW (only unambiguous `skills/`/`agents/`/`commands/`/`hooks\|scripts\|services/`/`docs/*_MAP.md` path forms resolve); the invoke-form `/architect-team:<cmd>` and bare skill-name citations are the documented LLM-judgment carve-out, deliberately NOT machine-checked (prose-ambiguous — a false positive there is a wording fix, not an engine bug). |
| **The enforced gate + remediation** | New `tests/test_instruction_compliance.py` (199 cases: the enforced zero-findings suite gate + a `yaml.safe_load` real-parse pin + 62 per-file agents/commands cap pins + the engine unit cases) + 1 section-structure pin each in `tests/test_skills.py` / `test_agents.py` / `test_commands.py`. **17 files remediated in place** (6 skills, 9 agents, 2 commands) — including **7 over-cap descriptions** (`doc-updater` was 1381 raw chars) rewritten trigger-first to ≤ 1024, whose trailing trigger guidance had been silently truncated by the loader; a broken cross-reference; and stale v6→v7 evidence-schema labels. |
| **REQ-004: enforcement only where text can't hold it → NO hook** | The 3-round adversarial sweep expanded the flagged set 95 → the full 112 files and NAMED no dimension-(b)/(c) gap that clear wording alone cannot hold, so — per the change's discipline that enforcement is never added speculatively — **no `hooks/` change was made**; the discipline is held by the lint + the suite pins. Suite 4851 → **5159 passing + 5 skipped** (195 → 196 test files; both encodings). Skill / agent / command counts unchanged; NO new skill / agent / command / hook / Layer-3 tool. |

### v3.30.0 — run continuity: autonomous continuation + sticky resume-via-Skill

Closes the two run-abandonment gaps observed in real runs: *the pipeline arbitrarily stops mid-run* ("we've done a lot — say continue if you want me to keep going") and *a resumed session solves by hand instead of re-loading the pipeline skill*. Once the architect team is engaged for a run, the run is driven through the pipeline to completion — across turn ends, context compactions, and session restarts — unless the USER explicitly stands it down.

| Capability | What it is |
|---|---|
| **The lifecycle marker** | `hooks/run_continuity.py` + `.architect-team/active-run.json` (`active` / `complete` / `stood-down`). ENGAGED deterministically the moment a run-driving Skill completes (PostToolUse — a denied call never engages); completed ONLY by the worklist-guarded `--mark-complete` (the documented last state action of Phase 8 / B8 / M8 / U9); stood down ONLY on the user's explicit words via `--stand-down` (auditable `pipeline-stand-down.md`). |
| **Stop-hook continuation guard** | An ACTIVE marker blocks a Stop even with a momentarily clean worklist. Engaged sessions keep getting blocked while the run makes PROGRESS (fingerprint over `.architect-team/**` + git state — unbounded, per Unbounded solving); after `CT6_MAX_NO_PROGRESS_STOPS` (default 3) consecutive no-progress blocks it auto-writes `escalation-pending.md` and allows — a wedged run surfaces instead of looping. Non-engaged sessions: one nudge + the resume-via-Skill directive, never wedged. |
| **PreToolUse sticky run arm** | While a run is active, a user-facing session that has NOT invoked a pipeline skill since its last compact boundary is blocked from build/dispatch tools until it re-invokes the Skill (read-only + Bash never gate). Teammate sessions stand down via the new mandatory `[CT6-TEAMMATE <name> RUN <id>]` spawn-brief first line (+ a fail-open brief-shape fallback), recognized from a HEAD slice of the transcript so a long teammate's brief never scrolls out of recognition; stale markers (default 72h) and `escalation-pending.md` pauses also stand it down. |
| **SessionStart resume directive** | The first `SessionStart` hook (`sessionstart-run-continuity.py`, 8th wired event): on startup / resume / clear / **compact**, an active marker injects "invoke `Skill(<skill>)` FIRST, then resume the run" — sharpened post-compact, where the playbook text was just dropped from context. |
| **Escapes + tests** | `CT6_RUN_CONTINUITY_DISABLED=1` kill-switch; everything fails open; `--check` (the Phase 8 pre-commit gate) deliberately skips the lifecycle check. Adversarially reviewed (FIX-FIRST -> 3 MAJOR + 5 MINOR remediated). New `tests/test_run_continuity.py` (28) + `tests/test_pipeline_completion_audit_continuation.py` (17) + `tests/test_sessionstart_run_continuity.py` (8) + 18 sticky-arm gate cases; every legacy Stop-hook / gate pin preserved verbatim. Suite -> **4851 passing + 5 skipped** (195 test files; both encodings). +1 enforcement script (6 → 7); +1 wired event (SessionStart). |

### v3.29.0 — the Librarian becomes installable (CT6-6 server tier)

Makes the CT6-6 Librarian a first-class **installable**, mirroring the `mempalace-install` pattern, while REUSING the existing `bg_runtime` / `service_config` / `librarian` / `library_index` substrate (reuse-first — no new service logic). The Librarian is now installable and, once enabled with an API key, **runs as a background daemon on the local machine** — NOT a deployed/production service.

| Capability | What it is |
|---|---|
| **The command (23rd)** | `commands/librarian-install.md` → `/architect-team:librarian-install` — full-lifecycle: `install` / `status` / `add-topic` / `list-topics` / `remove-topic` / `run-once` / `uninstall`, with `--enable` / `--check-only` / `--json` / `--purge`. Slash-command count 22 → 23. |
| **The installer + CLI** | `scripts/setup/install_librarian.py` — stdlib-only. State under `~/.architect-team/librarian/` (`config.json`, `topics.json`, `index.sqlite`, `bodies/`, `metadata/`, `librarian.log.jsonl`). Uses the real Anthropic adapter when `ANTHROPIC_API_KEY` resolves, else falls back to `FakeLLMClient` in an honest **provisioned-but-disabled** state (no-key ⇒ `--enable` remediation). Generates the per-OS boot descriptor via `bg_runtime.install_descriptor` (launchd / systemd / schtasks) and PRINTS the register hint — never auto-loads. |
| **The daemon + source adapter** | `services/librarian/daemon.py` — the daemon entry point (a path-runnable script building `Librarian` + `Scheduler` + `run_forever`) + `UrlSource(Source)`, a stdlib `urllib` fetcher over the topic→URL registry with graceful skip-on-failure (the live HTTP fetch is the real network adapter; its stdlib fallback keeps the core testable). |
| **Honest boundary + tests** | The plugin core stays stdlib-only; `check_separation()` stays clean; nothing is described as "deployed/running in production." New `tests/test_install_librarian.py` (23 offline tests). Suite 4757 → **4780 passing + 3 skipped** (192 test files; both encodings). Skill / agent counts unchanged; +1 command; NO new Layer-3 tool. |

### v3.28.0 — the service-tier separation manifest (CT6-6 server tier, REPO-1 … REPO-4)

The final CT6-6 component — the two-repo separation plan + a machine-checkable separability invariant. **This completes the entire CT6-6 program** (the in-repo tier v3.17.0–v3.22.0 + the service tier v3.23.0–v3.28.0).

| Capability | What it is |
|---|---|
| **The manifest (REPO-1/2/3)** | `services/separation.py` (`SEPARATION_MANIFEST`) + `services/SEPARATION_MANIFEST.md` — the open-core-vs-paid-repo plan, each service marked separable, and the adapter SEAMS the closed/paid pieces plug into (the SEC-4 attestation algorithm; the SMP-4 phenotype entitlement / billing). |
| **The separability invariant (REPO-4)** | `check_separation()` parses every `services/**/*.py` and asserts each is import-clean — stdlib + in-repo only at module load (recursing through `try` / `if` / `with` / class bodies, allowing only genuinely-lazy in-function imports). Any external / closed dep MUST be injected via a seam, never hard-imported — that import-cleanliness is what makes each service liftable into its own repo. |
| **Review + tests** | Adversarial review FIX-FIRST → remediated a CRITICAL scanner soundness hole (a module-load import nested in `try/except` / `if` / a class body was invisible — a hard `try: import chromadb` would have passed; now caught) + a `validate_manifest` crash-on-malformed + a Python-3.10+ guard. New `tests/test_services_separation.py` (7 cases). Suite 4746 → **4753 passing + 5 skipped** (191 files; both encodings). Skill / agent / command counts unchanged; NO new Layer-3 tool. |

### v3.27.0 — the Seeded MemPalace service (CT6-6 server tier, SMP-1 … SMP-5)

The fourth service on the v3.23.0 substrate — an authenticated download of a seeded MemPalace (a defined schema + curated content + the phenotype catalog + the latest research synthesis), leaving room for the user's own projects. **Design + a runnable stdlib-only core + tests, NOT a live-deployed service** (ChromaDB, the live server, the network, and the billing system are adapters / operator-provided).

| Capability | What it is |
|---|---|
| **Bundle schema + merge (SMP-3/5)** | `services/seeded_mempalace/bundle.py` — the defined seeded-MemPalace bundle (schema + curated + phenotype catalog + a `research_synthesis` freshness section, SMP-5) + a merge that REFRESHES the seeded sections while PRESERVING every user top-level key (SMP-3 — a re-download never clobbers the user's projects). |
| **Phenotype catalog (SMP-4)** | `catalog.py` — reuses the existing phenotype store (`discover_phenotypes`) to build a browseable catalog; `gate_catalog` ships full records only for entitled phenotypes (a non-owner browses metadata, purchases to download) — the future purchase model. |
| **Authenticated client + server (SMP-1/2)** | `client.py` signs a download request with the local Ed25519 key (reusing `services/common/handshake.py`) + merges the result; `server.py` verifies the SEC handshake and resolves entitlements by the **verified public key**. The download runs during setup, before "MemTime" (the session-start MemPalace init). |
| **Review + tests** | Adversarial review FIX-FIRST → remediated (entitlements keyed on the verified public key, not a self-asserted name — closes an impersonation hole; `gate_catalog` deep-copies so a served record can't corrupt the master; `merge_into_local` preserves all user keys; served records strip the operator's filesystem paths; default replay protection). New `tests/test_services_seeded_mempalace.py` (15 cases). Suite 4731 → **4746 passing + 5 skipped** (190 files; both encodings). Skill / agent / command counts unchanged; NO new Layer-3 tool. |

### v3.26.0 — the Session Review service (CT6-6 server tier, SR-1 … SR-3)

The third service on the v3.23.0 substrate — a session-level review agent (of similar design to the Librarian) that summarizes a session and surfaces the issues the agents couldn't solve on the first attempt. **Design + a runnable stdlib-only core + tests, NOT a live-deployed service.**

| Capability | What it is |
|---|---|
| **Session-level review (SR-1)** | `services/session_review/session_review.py` — reviews a full agent session via the shared LLM (string-aware JSON parse) and runs on the shared `bg_runtime` (schedulable + a per-OS install descriptor), like the Librarian. |
| **Outbound summary push (SR-2)** | `review_and_push` produces a session summary and pushes it via an injected pusher — but **off by default** (EVAL-17): under `off` nothing is transmitted off-machine (no summary push, no issue filing); the operator opts in to `summary` / `full`. |
| **Issues agents couldn't solve (SR-3)** | Only the issues NOT solved on the first attempt are kept (a robust boolean coercion — a stringified `"false"` is correctly treated as not-solved) and filed through the **triage `sink`** as normalized triage issue records, so they follow the same triage process. |
| **Review + tests** | Adversarial review FIX-FIRST → remediated (an SR-3 truthiness bug dropping stringified-false issues; an SR-2 push that leaked the summary under `off`). New `tests/test_services_session_review.py` (11 cases) + a folded-in fix for a pre-existing Windows `inflight_inbox` lock flake (a concurrent-holder `PermissionError` on `O_CREAT\|O_EXCL` is now retried, not crashed). Suite 4719 → **4731 passing + 5 skipped** (189 files; both encodings). Skill / agent / command counts unchanged; NO new Layer-3 tool. |

### v3.25.0 — the Triage / Evaluator service (CT6-6 server tier, EVAL-1 … 17 + SEC)

The second service on the v3.23.0 substrate — capture, de-duplicate, and triage issues across versions to make the models self-correcting. **Design + a runnable stdlib-only core + tests, NOT a live-deployed service** (the live HTTP server / GitHub API / Postgres / Anthropic LLM are adapters / operator-provided).

| Capability | What it is |
|---|---|
| **Evaluator (EVAL-1/3)** | `services/triage/evaluator.py` — reviews Claude Code logs "as a senior agentic architect", categorizing + ROOT-CAUSING each issue (string-aware JSON parse); `build_optimization_task` is the ~hourly BG task that feeds issues to a sink. |
| **Tally + quarantine (EVAL-4/10/11/12)** | `tally_queue.py` batches duplicates by fingerprint and promotes recurring ones to a backlog; `triage.py` carries the **quarantine rule** (the "most important": an issue first seen on an old version may already be fixed by an intermediate release the reporter didn't upgrade to — hold + verify from the fixed version onward) + resolution / recurrence tracking + the two-stage core-issue review. |
| **SEC handshake + privacy (SEC-1…5 / EVAL-15…17)** | `server.py` verifies a signed Ed25519 submission envelope (reusing `services/common/handshake.py` — no per-user codes; replay / tamper rejected; the SEC-4 attestation is pluggable), then re-applies privacy (reusing the helpdesk `logit` engine — `full` / `summary` / `off`, **off by default**, EVAL-17) before storing. The GitHub-issue sink is an adapter (`sink.py`). |
| **Review + tests** | Adversarial review FIX-FIRST → remediated (privacy default → off per EVAL-17, a SEC-1 anti-spam overclaim, a fingerprint boundary collision, server top-level-key redaction). New `tests/test_services_triage.py` (30 cases). Suite 4689 → **4719 passing + 5 skipped** (188 files; both encodings). Skill / agent / command counts unchanged; NO new Layer-3 tool. |

### v3.24.0 — the Librarian service (CT6-6 server tier, LIB-1 … LIB-13)

The first concrete service on the v3.23.0 substrate — a background topic-research curation service under a new `services/librarian/`. **Design + a runnable stdlib-only core + tests, NOT a live-deployed service** (the data source / vector store / Anthropic LLM are adapters with stdlib fallbacks).

| Capability | What it is |
|---|---|
| **Read → extract (LIB-11/12)** | `services/librarian/extract.py` — per download, the shared LLM confirms relevance and returns a title, a summary (so an agent can decide whether to read the full doc), strong searchable keywords, and a CONCEPT CLOUD (what the doc is useful for); the JSON reply is parsed **string-aware** (`JSONDecoder.raw_decode`, so a brace inside a string value can't truncate it). |
| **Conceptual search (LIB-10/13)** | `services/librarian/library_index.py` — a stdlib `sqlite3` reference index over title / summary / keywords / concept-cloud; `conceptual_search` ranks by weighted overlap (concept ×3 / keyword ×2 / text ×1) over unicode-folded tokens. Honest: overlap, NOT semantic / synonym expansion — true relatedness is the LIB-9 vector adapter. |
| **Background curation (LIB-1…9)** | `services/librarian/librarian.py` — the fetch→extract→index→metadata flow on the shared `bg_runtime` (scheduled, restartable) + the LIB-8 file-folder body store (path-safe filename). The data SOURCE + the MemPalace VECTOR store + the LLM are adapters with stdlib fallbacks (`StaticSource` / `FakeLLMClient`). |
| **Review + tests** | Adversarial review FIX-FIRST → remediated (string-unaware parse, missing body store, over-claimed LIB-10, ASCII-only tokenizer). New `tests/test_services_librarian.py` (14 cases). Suite 4675 → **4689 passing + 5 skipped** (187 files; both encodings). Skill / agent / command counts unchanged; NO new Layer-3 tool. |

### v3.23.0 — Service-tier foundation (the CT6-6 server tier begins)

The first piece of the CT6-6 SERVICE / SERVER tier — a new top-level `services/`, written separable (REPO-3). **Design + a runnable stdlib-only core + tests, NOT a live-deployed service** (the live server / ChromaDB / Anthropic API are external infra).

| Capability | What it is |
|---|---|
| **SEC handshake (SEC-1…5)** | `services/common/ed25519.py` — a pure-Python, stdlib-only Ed25519 (RFC 8032, no 3rd-party dep; independently validated against libsodium + the RFC vectors) — under `handshake.py`'s signed submission envelopes with replay protection + a pluggable attestation hook (the separable SEC-4 "genuine logger" piece). |
| **BG runtime (BG-1…4)** | `services/common/bg_runtime.py` — a cron-like scheduler + a self-check (BG-3) + per-OS boot/restart install descriptors (systemd / launchd / Task Scheduler, injection-guarded) + a log-ship interface. |
| **Shared config** | `services/common/service_config.py` — the decided one-Anthropic-key model (LLM == sign-up) + an `LLMClient` adapter (the real Anthropic call is a documented boundary; `FakeLLMClient` for tests). |
| **Review + tests** | New `tests/test_services_common.py` (26 cases incl. the Ed25519 KAT + malleability + descriptor-injection guards). Suite 4649 → **4675 passing + 5 skipped** (186 files; both encodings). Adversarial **security** review: SHIP (crypto cross-validated vs libsodium + RFC 8032). |

### v3.22.0 — Token compression (CT6-6 component 6, TC-1 … TC-3)

Reduce the token cost of agents' INTERNAL communication ("talk like a caveman") without harming external output quality.

| Capability | What it is |
|---|---|
| **Caveman compression (TC-2)** | The new `token-compression` skill + `scripts/token_compression/caveman.py` engine: `compress` drops pure filler (articles / politeness / intensifiers + wordy phrases) and preserves content words, identifiers, numbers, line structure, and fenced / inline code verbatim; `compression_stats` measures the saving (~30% on realistic internal text). |
| **Internal-only boundary (TC-1)** | A hard rule — NEVER compress external output (the user answer, API payloads, commits, PRs, test output); it applies ONLY to inter-agent messages + an agent's own scratch / internal notes. |
| **Honest boundary + tests (TC-3)** | A lossy-of-filler heuristic, not a semantic ML compressor; the token counts are estimates; a heavier ML package (LLMLingua-style) is documented as a 3rd-party app-layer option over this stdlib floor. New `tests/test_token_compression.py` (15 cases). Suite 4632 → **4649 passing + 5 skipped** (185 files; both encodings). Adversarial review: SHIP. No new command / agent / Layer 3 tool. |

### v3.21.0 — Logit / Helpdesk (CT6-6 component 5, HD-1 … HD-3)

The user-run counterpart to the automatic issue logging — after a session goes badly, file a triage report with consent + a chosen privacy level.

| Capability | What it is |
|---|---|
| **Manual triage submission (HD-1/3)** | The new `helpdesk` skill + `/architect-team:logit` command (22nd) + `scripts/helpdesk/logit.py` engine: capture the issues the agents couldn't solve on the first attempt, build a triage submission stamped with the version + `source: manual-helpdesk` so the SAME triage process consumes it. |
| **Consent + privacy (HD-2 / EVAL-15…17)** | Asks consent before sending; `full` shares code/data, `summary` keeps only a safe allow-list (default-deny — code/data/nested/unknown keys dropped, with a validator backstop), `off` sends nothing. |
| **Honest boundary + tests** | The actual SEND to the triage server is the server-tier (the SEC handshake + the EVAL server), not in-repo — the skill produces the payload locally. New `tests/test_helpdesk.py` (18 cases incl. the allow-list leak regressions). Suite 4610 → **4632 passing + 5 skipped** (184 files; both encodings). Adversarial review FIX-FIRST → remediated (deny-list→allow-list privacy, non-dict crash, version guard). No new Layer 3 tool. |

### v3.20.0 — MCP design agents (CT6-6 component 4, MCP-1 … MCP-3)

Best-in-class output standardization for an LLM agent embedded in an application — an explicit output contract so the agent's output is guaranteed consistent to parse and consume.

| Capability | What it is |
|---|---|
| **Output contract (MCP-1/3)** | The new `mcp-output-contract-design` skill + `scripts/mcp_design/output_contract.py` engine: `build_output_contract` (a CLOSED JSON Schema — typed fields, a required set, enums, `additionalProperties: false`) + the structured-output tool the model is FORCED to call + `validate_against_contract` (the runtime guarantee — a non-conforming value is rejected before the app consumes it) + an `assess_contract` completeness check. |
| **The design worker (MCP-2)** | The new `mcp-design-agent` enumerates an app's agent producer points and designs a contract for each (bounded write to `.architect-team/mcp-design/`; never writes the app's code). Reuse boundary — `verified-agent-output` verifies CT6's OWN agents; this is the outward-facing counterpart for the user's embedded-agent application. |
| **Tests** | New `tests/test_mcp_design.py` (18 cases incl. the bool-is-not-integer / number-accepts-int type guards, the enum-type-mismatch build guard, and the CLI build→validate→assess round-trip). Suite 4588 → **4610 passing + 5 skipped** (183 files; both encodings). Adversarial review: SHIP. No new command / Layer 3 tool. |

### v3.19.0 — Claude.md efficiency (CT6-6 component 3, CMD-1 … CMD-4)

When MemPalace is installed, `CLAUDE.md` becomes a thin POINTER — it tells the agent WHERE to find things (loaded on demand) instead of CONTAINING the full context, and it stays very small.

| Capability | What it is |
|---|---|
| **Pointer, not container (CMD-1/2/3)** | The new `claude-md-efficiency` skill + `scripts/claude_md/claude_md_efficiency.py` engine: an assessor (pointer-shape + a byte budget → advisory staleness signals) and a generator that emits a minimal pointer `CLAUDE.md` (wake-up first step + standards + customizations). CONDITIONAL on MemPalace (CMD-1) — with none installed, a self-contained `CLAUDE.md` is correct and the discipline does not apply. |
| **Standards + customizations (CMD-4)** | Two parts: standards that point to a reference MemPalace (query on demand, never inline) + customizations the user toggles on/off. Reuses `mempalace-integration` for the availability check + the mine / wake-up flow it points INTO. |
| **Tests** | New `tests/test_claude_md_efficiency.py` (12 cases incl. the generate→assess round-trip + the empty / at-budget / byte-counting boundary pins). Suite 4574 → **4588 passing + 5 skipped** (182 files; both encodings). Adversarial review: SHIP. No new Layer 3 tool. |

### v3.18.0 — the `closeout` capability (CO-1 … CO-3)

A double-check at the END of a session: before context is compacted or work is declared done, confirm the documentation reflects what changed — and if a doc is lax, **update it, not just flag it**. The first CT6-6 service-tier discipline; the data counterpart of the Phase-8 doc-currency gate, but for *any* session.

| Capability | What it is |
|---|---|
| **Fires before compaction (CO-1)** | A new `PreCompact` hook (`hooks/precompact-closeout.py`) runs the deterministic staleness engine (`hooks/closeout_check.py`) against the working tree and, when docs look stale, injects a closeout reminder — non-blocking, fail-open, never delays compaction. |
| **Reviews + updates (CO-2/CO-3)** | The `closeout` skill + `closeout-agent` review the changes against the requirement, confirm every doc in the currency inventory, and perform the update via the `documentation-currency` + `doc-updater` whole-file pattern. Works from the working-tree diff, so it runs OUTSIDE a full pipeline run. Manual trigger: `/architect-team:closeout` (`--check` for read-only). |
| **Tests** | New `tests/test_closeout.py` (29 cases incl. the PreCompact-hook subprocess + the working-tree collector). Suite 4539 → **4574 passing + 5 skipped** (181 files; both encodings). Adversarial review FIX-FIRST → remediated (a CHANGELOG-touch false-negative, rename/copy detection, the repo-root fallback). No new Layer 3 tool. |

### v3.17.0 — the `data-dictionary` skill (CT6-6 component 1, DD-1 … DD-18)

A self-contextualizing data-dictionary builder: derive the data model from code / docs / a live DB, define every field, and record provenance + corroboration.

| Capability | What it is |
|---|---|
| **The engine** | `scripts/data_dictionary/data_dictionary.py` (stdlib-only): SQLite introspection + ~100-row sampling (DD-9/10), grain inference (DD-11), field inference (DD-12), the fixed provenance vocabulary `direct-user-input`/`direct-code-comment`/`inference`/`live-data` (DD-13), and value-level corroboration of EVERY provided definition against the live data (DD-14) — the classic customer_id-vs-hash key conflict is flagged + downgraded. |
| **The artifact** | `DATA_DICTIONARY_MAP.md` (+ `data-dictionary.json`): a by-field/by-table reference map + a relational/blend map incl. non-DB code joins, e.g. census merged onto customers on zip (DD-7). Honest live-DB boundary — the no-DB path never fabricates `live-data`. |
| **Tests** | `tests/test_data_dictionary.py` (21 cases incl. the local-SQLite end-to-end dogfood). |

### v3.16.0 — responsive + parallel `/architect-team:inject` (concurrent in-run lanes)

Closes *"inject just sits there passively … I need it to spawn more teams so we can have multiple problems worked on in parallel."* Before: the inbox was read only at phase boundaries (the Lead blocked synchronously on teammates), and spawning a parallel team for an injected problem was a *forbidden* anti-pattern — an inject could only be folded into the one sequential flow.

| Capability | What it is |
|---|---|
| **`parallel-problem` + concurrent lanes** | A new inbox classification (`hooks/inflight_inbox.py`) + a `lane_id` field. A separable, independent injected problem (disjoint file scope) opens a sanctioned concurrent in-run **lane** — a background team holding a disjoint `hooks/locks.py` file-scope lock — that works alongside the existing team(s) and converges via Phase 4. NOT a sibling `/architect-team` run: one coverage map / openspec change / commit range. |
| **Responsive (poll on every wake)** | The inbox is drained at every phase boundary AND after every background-dispatch return / wake (background dispatch frees the Lead's turn), not only at phase boundaries — so an inject is serviced promptly instead of sitting until the next phase. |
| **Honest about the limits** | Adversarial-review-driven: it is polling, not async push (a message injected mid-tool-call is serviced when that call returns); lane isolation is `globs_intersect` file-glob + advisory (`cdlg_overlap` is NOT wired into `acquire_lock` — keep lane scopes coarse; Phase 4 backstops a shared boundary); background lanes degrade to sequential in subagents-mode; a failed lane spawn downgrades the message rather than wedging Phase 8. |
| **Tests** | New `tests/test_parallel_lane_inject.py` (13 cases incl. the end-to-end dogfood: append → read → lock-isolated lane → processed → verified). Suite 4503 → **4516 passing + 5 skipped** (179 files; both encodings). No new Layer 3 tool. |

### v3.15.0 → v3.15.1 — skill-invocation hard-gate (real-time pipeline-bypass prevention)

A new `PreToolUse[*]` hook closing the *"sometimes when I call for the architect team, the AI doesnt load the skill"* gap — verbatim driver: *"you invoked the skill and I've been driving it by hand instead of running it."* The command body only *instructs* the model to invoke the Skill; nothing FORCED it, and the only prior guard (`hooks/skill_invocation_audit.py`, Layer 6) detects a miss after the turn ends. Soft prompts get rationalized past; deterministic code does not.

| Capability | What it is |
|---|---|
| **The gate** | `hooks/pretool_skill_gate.py` (stdlib-only), wired `PreToolUse[*]`. When the session transcript's most-recent GENUINE user prompt is an unsatisfied pipeline-command request (`/architect-team:architect-team` / `:bug-fix` / `:ux-test` / `:mini` / `:refine-prompt`, slash or prose), it BLOCKS (exit 2) the first BUILD/DISPATCH tool call (`Edit`/`Write`/`NotebookEdit`/`Agent`/`Task*`) until a pipeline skill is engaged — read-only investigation + the command wrapper's own `Bash` setup (banner/cleanup/worktree) are never blocked (**narrowed in v3.15.1** after the original all-non-`Skill` block over-fired on the wrapper's setup). Converts the Layer-6 audit from DETECTION to PREVENTION. |
| **Universal / global** | No reference to any specific codebase, repo, app, or project — keyed off the plugin's own discovered command set (`COMMAND_TO_SKILLS`, reused from `skill_invocation_audit.py`) + the Skill-tool ledger; works in any repo the plugin is installed into. Scoped to the 5 pipeline-driving commands only — read-only commands (`/status`, `/memory`) and built-in REPL commands (`/effort`, `/model`) never gate. |
| **False-block-safe** | The catastrophic failure for a `*`-matcher hook is a spurious block. The anchor excludes the harness's injected/meta records (`isMeta` command/skill body-echoes, `promptSource:"system"` task-notifications, `isSidechain` subagent transcripts); satisfaction = engaging ANY pipeline skill after the request (so `/architect-team`'s `proposal-refiner`-first step never false-blocks) with ts-ordered user-precedence; the `Skill` tool is always allowed; fail-open on any error. |
| **Adversarially verified on real data** | Independent review against two real transcripts caught a session-bricking `isMeta` body-echo bug + a refiner-first false-block before ship; the fix was re-verified across 9 real transcripts / 3822 simulated tool calls — **0 spurious blocks, 402 genuine historical bypasses correctly caught**. NEW `tests/test_pretool_skill_gate.py` (40 tests); suite **4503 passing + 5 skipped** (178 files; both encodings). NO new Layer 3 tool. **v3.15.1** re-verified the narrowed gate across 9 transcripts / 3939 calls — blocks only on build/dispatch tools, 0 non-build/dispatch blocked. |

### v3.14.0 — appearance-change policy (strict / propose / innovate)

A new cross-pipeline discipline closing the unsolicited frontend-appearance-change gap — verbatim driver: *"sometimes when asking for updates, the agent will arbitrarily change our front end, adding things we didnt explicitly ask for as part of an ask to improve."* By default every run is now **strict**: what a user SEES changes only when the user asked for it.

| Capability | What it is |
|---|---|
| **The three modes** | `strict` (DEFAULT — no appearance-affecting change beyond the explicit mandate; backend changes unrestricted; improvement ideas RECORDED as proposals, never implemented) / `propose` (proposals batched at ONE multi-select `AskUserQuestion` approval gate — only approved ones implemented, with the user's verbatim citation stored) / `innovate` (authorized — every visual delta logged `implemented-innovate` + `DESIGN_MAP.md`-reconciled in the same change). Selected via `--appearance <strict\|propose\|innovate>` on `/architect-team` + `:bug-fix` + `:mini` (+ natural-language equivalents); bound ONCE at Phase −2 / B−1 / M0 into `intake-state.json`; carried in every teammate spawn brief. |
| **The mandate boundary** | Three sanctioned sources under `strict`: **requirement text** (only the NAMED surfaces), **spec restoration** (`DESIGN_MAP.md` / the design source / the intended rendering a bug broke — always in scope in every mode), and the **mandated-capability minimum** (the smallest entry point a required capability needs, matching the existing design system, zero decorative extras). Everything else is out of mandate regardless of merit — "better" is the user's call. |
| **The proposals artifact** | `<workspace>/.architect-team/appearance-proposals/<run-id>.json` — statuses `recorded` / `approved` / `rejected` / `implemented-approved` / `implemented-innovate`. Strict runs list proposals READ-ONLY in the final report (imperative phrasing — never a v2.10.0 follow-up question). Completeness-audit SRs whose remediation would ADD new visible UI surface are `appearance_gated: true` and user-gated under strict/propose; pure-wiring SRs (dead buttons, mock data, missing APIs for existing elements) route unchanged in every mode. |
| **Review-gate enforcement** | Schema v7 gains its THIRD OPTIONAL field `appearance_scope_review` (string or `{verdict, verdict_path}`; the hook **BLOCKS `fail`**; `REQUIRED_EVIDENCE_FIELDS` stays at 17; older evidence files stay valid). The independent `task-reviewer` traces EVERY appearance-affecting delta to a mandate; the `system-architect` Master Review Audit walks the run-level diff + checks proposals-artifact integrity. NO new Layer 3 tool in v3.14.0 (`verify-no-unsolicited-appearance-change` is the named v3.14.x follow-up). NEW `tests/test_appearance_change_policy.py` (48 tests); suite 4415 → **4463 passing + 5 skipped** (177 files; both encodings). |

### v3.13.0 — code-wiki phenotype (absorbed from deepwiki-open)

A **fourth phenotype** seeded into the v2.3.0 subsystem via the `phenotype-absorption` skill: `code-wiki`, a self-hosted documentation-wiki application pattern absorbed (READ-ONLY) from [deepwiki-open](https://github.com/AsyncFuncAI/deepwiki-open.git) (MIT). Its presentation layer survives; its entire LLM stack is stripped.

| Capability | What it is |
|---|---|
| **NEW phenotype — `code-wiki`** | `phenotypes/code-wiki/` = `blueprint.md` (the 10 SCHEMA sections) + `phenotype.json` (`kind: singleton`; `match` keywords incl. "code wiki" / "documentation site" / "deepwiki"; `variation_points.hosting ∈ {local, aws, gcp}`; `provenance.absorbed_from` = the deepwiki URL) + a 30-template `scaffold/`. Discoverable via `phenotypes match` / `--phenotype code-wiki`. |
| **The absorbed pattern** | A lean generalized **Next.js** wiki (App Router, `output: 'standalone'`, **plain CSS** generalizing deepwiki's 10-var palette — Tailwind dropped to keep deps minimal): sidebar nav tree + markdown content pane + **client-rendered Mermaid** + dark/light theming + a multi-codebase selector with search + **URL-backed** deep links. Deps: `next` / `react` / `react-markdown` / `remark-gfm` / `mermaid`. |
| **The strip** | The whole LLM machinery dies — 9 provider clients, RAG (faiss/adalflow/tiktoken), the WebSocket chat / Ask / Deep Research, slides/workshop generation, the model-picker UI, every API key, and the entire `api/` Python tree. The content source is swapped to a `lib/maps-loader` that ingests a `codebases.json` registry → `docs/*_MAP.md` into deepwiki's kept wiki-cache JSON shape. |
| **Cloud via cross-seed** | `components.deploy.via = "config-management phenotype"` (the ai-management precedent — no schema change): cloud hosting composes with the `config-management` phenotype for the platform layers; the scaffold ships only the **service-layer** plug-ins (`iac/aws` ECS Fargate, `iac/gcp` Cloud Run). Both pass `tofu validate`. |
| **Proven by an executed demo** | Emit → `npm install`/`build`/`start` → HTTP **200** on the index + a CODEBASE_MAP page with real map content → a Playwright screenshot of **2 rendered Mermaid diagrams + the navigation tree**. Local hosting via `docker-compose` (single container, content volume, `/health` check). |
| **Upstream fix folded in** | The run's Phase 5 RCA caught a false positive in `hooks/discipline_registry.py`: absorbing a frontend repo clones it READ-ONLY into `.architect-team/reference/`, and the frontend-marker scan (skipping only `node_modules`/`.venv`/`venv`/`__pycache__`/`.git`) mistook the vendored clone for the plugin repo's own UI surface. Routed as an SR (`origin.kind: rca-product-bug`) through `diagnostic-research-team`; fixed by adding `.architect-team` to `_SKIP_DIR_PARTS` at all **3 scan sites** + **4 regression tests**. Suite **4411 passing + 5 skipped** both encodings. |

### v3.12.0 — structure-optimization performance + review remediation

A 3-lens review panel audited the v3.11.0 pipeline and verified 16 findings — all fixed **in place** (zero new files), every accuracy invariant preserved.

| Capability | What changed |
|---|---|
| **Correctness fixes (10)** | Partition snippet: `.split()` → `.splitlines()` (space-bearing filenames) + `os.path.normcase` on both sides (case-insensitive-FS safety) + once-per-codebase invocation + recoverable-duplicate routing + S0 `mkdir -p`; S8 notify `pipeline_complete` → `phase_complete`; `delete-dead` carries `"to": []`; S4 assembly validates every `movement_id` in exactly one shard; S6 per-failure-kind re-execution table; command arg precedence (explicit path wins; path + `--all` is a surfaced error). |
| **S5 cost optimizations** | **Adversary-round warm-start** (delta-scoped re-runs + carried `modalities_run` union + re-confirm-not-re-derive — the two-consecutive-clean exit is untouched); **per-round partition-recompute dedup** (orchestrator publishes `adversarial/round-<R>/partition-check.json`; adversaries consume it instead of three redundant LLM re-derivations); **payload-trimmed adversary briefs**. |
| **S3/S2/S1 cost optimizations** | **Structured agree/dispute convergence** with orchestrator-frozen agreed rows + explicit completion criterion; **per-draft + per-revision partition front-loading** (gate run unchanged); **S1 per-codebase freshness pipelining**; **orchestrator-precomputed file universe** handed to all three analysts. |
| **S4/S6/S7 + guardrails** | **Balance-by-reference-surface shard policy** with a fan-in pre-estimate; **S7 mechanical transcription** (movement→REQ / reference→criterion / batch→task-group / approaches verbatim); **S6 thinnest-coverage spot-check sampling**; the **3-adversary floor note**; and a permanent **`## Optimization guardrails`** section fencing four anti-candidates (trust-the-self-check / one-clean-round exit / sonnet adversaries / dropping the logs) with rationale. |

### v3.11.0 — Structure Optimization Pipeline

| Capability | What changed |
|---|---|
| **NEW skill — `structure-optimization`** | Stages S0–S8: maps current via `cartographer-team` (freshness-checked; produced if missing) → ×3 independent `structure-analyst` drafts → ralph-loop convergence gated by a deterministic every-file **partition check** (`git ls-files` = movement table ∪ stays list; zero orphans, zero duplicates) → sharded `reference-tracer` closure (every import / config / CI / docs / string-path / test reference per movement, `file:line` evidence) → ×3 `structure-adversary` refutation rounds until **two consecutive all-clean rounds** → `system-architect` Restructure Plan Audit → `RESTRUCTURE_PLAN.md` (per `superpowers:writing-plans`) + `movements.json` (schema v1.0) → `openspec-propose` authoring + `openspec validate --all --strict --json`. Plan-only: execution belongs to `/architect-team` driving the produced change. |
| **NEW command — `/architect-team:optimize-structure`** | `[codebase-path \| --all] [--objective "<prose>"] [--execute] [--no-commit] [--no-push] [--no-compact]` — dispatch banner first; `--execute` (default off) hands the validated change straight to the implementing pipeline. |
| **3 NEW agents + 1 extended** | `structure-analyst` (opus ×3, full-partition drafts), `reference-tracer` (sonnet ×N shards, mechanical closure + mandatory `search_log`), `structure-adversary` (opus ×3, refutation via modalities the tracers did not run); `system-architect` gains the ninth mode — **Restructure Plan Audit** (re-runs the partition check, spot-checks closure with fresh modalities, walks batch order). |
| **Producer/checker at pipeline scale** | Analysts design, tracers close, adversaries refute, the architect audits, the orchestrator runs the deterministic checks itself — no role verifies its own output (v0.9.13 discipline). |

### v3.10.0 — Second-tier review improvements (R1–R7)

| Capability | What changed |
|---|---|
| **`hooks/vao_tools.py` → the `hooks/vao/` package (R2)** | The 5,209-line / 20-tool monolith split into per-discipline-family modules (each ≤900 lines); `vao_tools.py` is now a ≤400-line **facade** re-exporting the full 125-name public+test-referenced surface (20 `verify_*` functions + 42 UPPER constants + 62 underscore helpers + 1 alias — each identity-checked) + a byte-identical CLI. ZERO behavior change — every fixture + the real-subprocess glue-execution test stay green. NEW `hooks/shared_util.py` unifies `load_json(path, *, missing_ok)` / `_utc_now_iso` / the JSONL reader (eliminating the prior 3–4 duplicate definitions). |
| **NEW capability — `security-hunter` (R6a)** | The 6th `adversarial-reviewer` shape hunts missing/weakened authz, injection-prone construction, secrets in the diff, unsafe deserialization, and unjustified dependency additions. Spawn-brief trigger rules: a backend-dep task spawns BOTH `fake-data-hunter` AND `security-hunter`; an auth/security-path or dependency-add diff makes `security-hunter` mandatory. NEW SR origin kind `security-finding`; the SR origin-kind catalog reconciled to an OPEN canonical catalog. |
| **NEW capability — accessibility axis (R6b)** | `## Accessibility axis (v3.10.0)` for interaction-completeness + the matching audit section for `interaction-reviewer`: keyboard reachability, accessible names, and axe-core-via-Playwright. NEW `a11y-gap` sub-kinds (`keyboard-unreachable` / `missing-accessible-name` / `axe-violation`) + NEW SR origin kind `a11y-gap`; a no-UI n/a rule. |
| **NEW capability — unbounded-run heartbeat (R6c)** | `scripts/notify/notify.py` gains a 6th event type `heartbeat`; `hooks/run_metrics.py` gains `heartbeat_snapshot(...)`; a `### Heartbeat discipline (v3.10.0)` CPC subsection refreshes `.architect-team/in-progress.md` + emits the event during any >30-min phase and at every post-first-hour boundary — never gates, never caps. |
| **Scope-discipline + helper consolidation (R1)** | A canonical `## Scope-fidelity discipline family (v3.10.0)` CPC section names the five scope disciplines (v0.9.36 / v1.4.0 / v2.8.0 / v2.10.0 / v2.14.0) as one family with the shared 3-disposition model + a firing-moment table; the two in-`vao` localhost lists unified; two named override/scope-cut false positives fixed. |
| **Agent hygiene (R4)** | Retired `LS` / `NotebookRead` / `Task` removed from all agent frontmatter (NotebookEdit kept); bounded `Write` granted to `qa-replayer` + `test-completeness-verifier`; git+checkpoint boilerplate re-synced across all 34 (oracle-deriver's `$BASELINE_SHA` restored; the analysis-only checkpoint exemption folded in); colors mapped to the documented palette; `scaffold-agent` documented as an on-demand utility. |
| **`locks.py` concurrency (R5) + registry applicability (R7)** | `acquire_lock` uses `O_CREAT|O_EXCL` + an intersecting-scope re-scan; `globs_intersect` gains the prefix/suffix candidate (`src/**` vs `**/auth.py`). The `discipline_registry` prod-safe + multi-persona detectors gain applicability guards + `{applied, not_applicable, reason}` (this no-UI repo records both `not_applicable`). |
| **Narrative diet (R3)** | `CLAUDE.md` restructured operative-first; CPC narrative compressed with zero rule loss; the four pipeline bodies collapse their duplicated v2.18/v2.19/v2.20/v3.0 bash gate blocks to one-line references + the inline abort stub, with the invocations parameterized in the NEW CPC `## Layer 3 gate invocation table (v3.10.0)`. |

### v3.9.3 — Review-remediation: 30 verified-defect fixes across glue, commands, skill docs, and the docs

| Capability | What changed |
|---|---|
| **Glue executes correctly (A1–A10)** | `hooks/hooks.json` converted to the v2.16.0 detect-once polyglot (no double-execution / no silent exit-127 drop); the three crashing VAO CLIs given bare-module import fallbacks; the in-flight inbox made atomic + path-safe; four hooks switched to UTF-8 stdin + OSError-fails-closed; minimal CLIs added to `teams_mode.py` + `worktree_lifecycle.py` so the command banners + worktree cleanup actually run; `CANONICAL_COMMANDS` regenerated to the real 19 + two matcher fixes. |
| **Command surface honors its conventions (B1–B5)** | `inject.md` sys.path-anchored + quote-safe message passing; `ux-test.md` gains the five missing pipeline-discipline preamble blocks; exit-2-capable / mutating command invocations converted to detect-once; `architect-team-setup.md` allowed-tools repaired; `absorb-phenotype.md` invocation anchored. |
| **Skill docs teach the code as it is (C1–C6)** | the review-evidence schema is taught as **v7** (17 required fields) everywhere; the v3.8.0 unbounded-solving residue reconciled to loop-until-converged; the MemPalace not-on-PATH note authored; the undefined "Phase B3b" reference resolved; the seven over-length skill descriptions trimmed under the 1024-char limit + a cap test added. |
| **Docs reconciled + version bumped (D1–D4)** | `CLAUDE.md` / `CODEBASE_MAP.md` / `README.md` / `INTEGRATION_MAP.md` reconciled — 20 VAO tools, 4 enforcement scripts, schema v7, HOOKS box = 4 scripts / 6 events; version bumped to 3.9.3 + CHANGELOG entry. |
| **Regression coverage (E1–E3)** | a NEW "execute the glue" test family resolves and exercises every command/hook invocation (would have caught A1/A2/A5/A6/B1/C2); per-item regression tests; the suite stays green under cp1252 AND `PYTHONUTF8=1`. |

### v3.9.2 — Deterministic openspec gate at the master-review Stop hook

| Capability | What changed |
|---|---|
| **`_audit_openspec_validation` — independent openspec gate (v3.9.2)** | NEW `hooks/pipeline-completion-audit.py::_audit_openspec_validation(root, at)` — the `Stop` hook **independently re-runs** `openspec validate --all --strict --json` from the repo root once a Phase-7 `master-review/audit-*.json` verdict exists; **any invalid change BLOCKS the commit** (the audit is no longer the orchestrator's self-report). Best-effort no-op when there is no `openspec/` workspace, no `openspec` CLI on `PATH`, or on subprocess error. Wired into `audit()`. Suite green under BOTH cp1252 and `PYTHONUTF8=1` (156 bare `read_text()` calls in tests made encoding-explicit). |

### v3.9.1 — VAO precedence fix + openspec change-folder hygiene

| Capability | What changed |
|---|---|
| **VAO review-evidence precedence fix + 5 orphaned change folders archived (v3.9.1)** | Fixes a latent operator-precedence bug in `hooks/vao_tools.py::_scan_ledger_for_pipeline_elements` — `(A or B) and ".json"` (was `A or (B and C)`). Archives 5 orphaned-but-shipped openspec change folders into `openspec/changes/archive/` so `openspec validate --all --strict` is green; active changes are now just `consolidate-duplicated-rules` + `exploration-pipeline`. |

### v3.9.0 — Uniform plugin usage (predictable regardless of mini or call)

CT6 now invokes its plugin dependencies (superpowers, ralph-loop, cartographer, openspec) **uniformly across every pipeline** — so a run behaves the same regardless of which command launched it — and **superpowers is a hard dependency that is actually exercised at runtime**, not decorative framing.

| Capability | What changed |
|---|---|
| **Superpowers — HARD dependency, actually invoked (v3.9.0)** | `scripts/setup/setup.py` treats a missing required plugin as an **exit-1 hard block** (superpowers called out as a hard dependency); NEW `ensure_openspec_propose_skill()` verifies the vendored `openspec-propose` authoring skill resolves. Every pipeline body (`architect-team` / `bug-fix` / `mini` / `ux-test`) gains a `## Plugin prerequisites (v3.9.0)` **superpowers pre-flight abort gate** plus concrete `superpowers:brainstorming` / `test-driven-development` / `systematic-debugging` / `verification-before-completion` invocations woven into its phases — replacing the prior decorative *"Superpowers-driven"* framing. Precedence preserved: hard-blocking governs plugin **presence** only; user `CLAUDE.md` / `AGENTS.md` instructions still win. |
| **OpenSpec + ralph-loop — uniform gates (v3.9.0)** | Identical openspec gates across implementing pipelines: `mini` gains `openspec validate --all --strict` + `openspec archive` (it previously skipped both); `bug-fix` aligned `--strict` → `--all --strict`. `hooks/vao_tools.py::verify_no_pipeline_bypass` now accepts three openspec-evidence forms (a Bash `openspec ` call / an `openspec-propose` skill invocation / an `openspec/changes/<name>/` artifact) so legitimate `mini` + exploration runs no longer false-trip `openspec-bypassed`. All stale `--max-iterations` scrubbed from live `/ralph-loop` examples; `data-engineering-exploration` + `domain-research-team` converted to the explicit `--completion-promise` form. NEW canonical `## Uniform plugin usage (v3.9.0)` in `common-pipeline-conventions` — the single source of truth all four bodies reference. |

Two owner-directed deliverables on one branch: **the dev loop now runs unbounded** (nothing halts a run — it loops until everything is green), and **a Code & Data Lineage Graph (CDLG) foundation** lands the deterministic, unit-tested core for per-endpoint call-trace + asset-lineage mapping.

| Capability | What changed |
|---|---|
| **Unbounded solving — loop until success (v3.8.0)** | All run / iteration limits removed, per the owner directive *"remove all limits … agents must figure out the problems and cannot stop until success."* Reconciled as: **nothing can BLOCK or HALT a run; the completeness checks become the worklist that keeps the loop running until everything is green.** Removed: the global dev-loop iteration ceiling (was 20); oscillation→abort (now: continue from a *different angle* + surface, never stop); exhaustion→escalate-and-stop; and the bounded sub-loop caps (diagnostic-research 3-cycle, editability / interaction 3-pass, expensive-verification 2-cycle-stop, mapping ralph `--max-iterations N`) → **loop-until-converged**. The `pipeline-completion-audit` Stop hook became a **non-halting worklist** — its other checks still run and still define "not yet success", but they never halt the run. **Kept** (not give-up limits): the shared-state concurrency model, the 3-pass RCA *rigor floor*, the executed-not-described disciplines, and the escalation marker for **required owner input only** (a credential / a design decision only the owner can make). Canonical home: `skills/common-pipeline-conventions/SKILL.md` `## Unbounded solving discipline (v3.8.0)`; the 4 pipeline / ux bodies reference it. |
| **Code & Data Lineage Graph (CDLG) foundation — P0–P6 (v3.8.0)** | NEW `hooks/lineage_graph.py` (stdlib): the deterministic CDLG core — graph schema + validator, `func://` / `asset://` ID nomenclature (rename-stable via content fingerprint — the load-bearing join key for MemPalace dedup + graph diffing), **runtime-witness reconciliation** (edge recall / hallucination + the `witness_gate` trust gate — *reuses* the existing `code-path-witness.json` from v0.9.31/0.9.32 as ground truth, never re-implements execution capture), transitive freshness, and cost-ceiling / truncation. NEW `hooks/run_metrics.py` (stdlib): per-run metric instrumentation (`dev_loop_iterations`, first-pass-fix, oscillation / bug-still-present / fix-regression counts, the FE/API discriminant verdict vs the layer actually fixed, CDLG recall / hallucination) + the frozen-bug-benchmark protocol. NEW skill `endpoint-trace-mapping` + NEW agent `endpoint-tracer` (per-endpoint internal call-trace producing the CDLG; a two-layer extraction contract; witness-verification). NEW skill `data-lineage-mapping` (asset lineage; carries a Reuse Decision vs `data-engineering-exploration`). **P0** reorders `bug-fix-pipeline` isolation: replicate → scope-isolate → an EXECUTED light FE/API discriminant → call-map → diagnose (cheap, evidence-backed checks before deep analysis). **P2** `diagnostic-research-team` consumes the witness-verified CDLG instead of re-tracing. **P4** `hooks/locks.py::cdlg_overlap` flags a shared hot callee (call-graph closure intersection), not just shared files. **P5** `mempalace-integration` adds function-level lineage records keyed by `func://`. **P6** `scripts/setup/worktree_lifecycle.py` gains opt-in squash-merge detection (no false-positive) + a task-aware worktree heuristic; `list_run_branches` now defaults `against=origin/main` (agrees with the v1.3.0 sweep). |
| **Honest boundary (v3.8.0)** | P1's **live polyglot call-graph extraction against arbitrary target repos is the agent's RUNTIME job and is NOT claimed proven** (kill-gated per `docs/LINEAGE_UPGRADE_REQUIREMENTS.md` §7.1). What IS real and unit-tested: the deterministic pieces — schema / ID / witness-reconciliation / freshness / cost. The CDLG foundation ships the machine half; the live extraction is exercised, not yet validated end-to-end. |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  NEW IN v3.7.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
| **Auto-merge-to-main + prune (v3.7.0)** | Autonomous runs are now self-tidying. On a clean Phase 8 / B8 / M7 pass (completion audit green + the commit landed on `architect-team/<change-name>`), the pipeline merges that branch into `main` with `--no-ff`, pushes `main`, deletes the branch (local + remote), and removes the run worktree — but ONLY when the branch merges cleanly. `AUTO_MERGE_MAIN` defaults to `true`. Two new stdlib helpers in `scripts/setup/worktree_lifecycle.py`: `list_run_branches()` (per-branch `merged_into_main` / `cleanly_mergeable` status, excludes non-`architect-team/*` branches) and `merge_branch_to_main_and_prune()` (merge → push → delete-branch → remove-worktree). A merge **conflict** changes nothing (`conflict: true`) and falls back to the feature-branch + PR path; a **rejected push** (branch protection / non-fast-forward) STOPS pruning and leaves the branch + worktree recoverable — `--force` is NEVER added, branch protection always wins. `--no-auto-merge` (or *"keep the branch"* / *"PR only"* / *"don't merge to main"*) restores the v3.6.0 feature-branch + PR behavior. **Startup branch reconciliation:** each `/architect-team` family command enumerates stray (unmerged) `architect-team/*` branches and presents ONE `AskUserQuestion` — merge-all-clean + prune / prune-without-merge / leave. |
| **Worktree end-of-run merge check + hidden container (v3.6.0)** | NEW `finalize_run_worktree()` called at Phase 8 / B8 / M7: when a run's `architect-team/<slug>` branch is already merged into `origin/main`, finalize removes the worktree AND deletes the branch; when NOT yet merged it LEAVES the worktree on disk and returns a persistence warning naming the path + the literal manual cleanup command. **Unmerged work is NEVER auto-deleted.** New worktrees now live in a single hidden per-project container `<parent-of-repo>/.<repo-name>-worktrees/<slug>/` instead of the flat `<parent>/<repo>-<slug>/` layout; cleanup + slug-derivation are dual-layout, so pre-v3.6.0 flat worktrees are still swept. |
| **Data Engineering Exploration Pipeline (v3.5.0)** | NEW skill `data-engineering-exploration` — the data-plane analog of `visual-to-api-design`. A 7-stage pipeline (domain context → conceptual data model → service design → volume + velocity → data security → MANDATORY validation + lineage + observability → OpenSpec authoring) for dbt / Airflow / Snowflake / Databricks / Kafka / data-mesh / feature-store work, dispatched from the new **Phase 0c** of `architect-team-pipeline`. Every transformation MUST carry ≥ 1 blocker-severity validation rule + end-to-end lineage + aggregate + per-endpoint metrics. NEW `## Phenotype convergence rules` codify that `ai-management` implies `user-management` + `config-management`. |
| **Backend-from-frontend modularization (v3.4.0)** | NEW **Phase 0b** backend dispatch check + 3 extracted reusable analysis skills — `cartographer-team` (multi-agent wrapper around the external cartographer call: producer + 3 `codebase-map-reviewer` agents converge to 100% coverage in a ralph-loop), `domain-research-team` (3 `domain-researcher` agents with a MANDATORY outside-research mandate that fires regardless of input completeness), and `api-design-from-frontend` (per-page REST returns → consolidated API design + desk-trace → backend data architecture + phenotype gates + OpenSpec). NEW `domain-researcher` agent (opus, `WebFetch` + `WebSearch`). Frontend-read-only enforcement routes all reference output to `.architect-team/frontend-reference/` — the reference codebase is NEVER modified. |
| **Test-run monitor team (v3.3.0)** | NEW skill `test-run-monitor` + NEW command `/architect-team:monitor-tests` — a strictly passive observer team that watches test runs across 3 adapters (local test command / CI job via `--ci-job` / production QA via `--apm-url` or `--log-tail`) and produces a per-run report. NEW agents `test-run-watcher` (sonnet, captures structured findings) + `monitor-synthesizer` (opus, classifies each finding `flake` / `regression` / `environmental` / `new`, assigns severity, computes a 5-run trend). Log-only — no mid-run interrupts, no auto-SR filing, no pipeline gating. |
| **Visual-to-API dispatch symmetry (v3.3.1) + 7-stage Exploration Pipeline (v3.2.0)** | `visual-to-api-design` extended in place from 4 → 7 stages into a ralph-loop-governed frontend→backend Exploration Pipeline; the 4-stage subset + `/architect-team:visual-to-api` command remain valid. NEW **Phase 0a** makes the Visual-to-API dispatch contract symmetric between `architect-team-pipeline` and `visual-to-api-design`. |
| **Backwards-compatible** | Schema v7 UNCHANGED across v3.2.0–v3.7.0. All new skills / agents / commands are purely additive; `--no-auto-merge` fully restores the pre-v3.7.0 feature-branch + PR behavior; branch naming `architect-team/<slug>` is unchanged; conflicts and protected branches are never forced. |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  CARRIED FROM v3.0.0  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What changed |
|---|---|
| **Unified Unilateral-Override discipline (META)** | Architectural consolidation. v2.10/v2.14/v2.20/v2.21/v2.22 all caught surface manifestations of ONE root pattern: virtue-framed opener + element-of-bypass admission. v3.0.0 ships the meta-discipline that detects it at the source. NEW `hooks/override_markers.py` shared module — 31 `VIRTUE_FRAMED_OPENERS` + 116 `ELEMENT_OF_BYPASS_ADMISSIONS` consolidating all 5 prior surfaces + per-discipline backwards-compat helpers. NEW 21st Layer 3 tool `verify_no_unilateral_override` accepts multi-source dict, fires per-source, single severity. **NEW architectural shift: pre-action runtime guardrail.** `hooks/pretool_unilateral_override_guard.py` fires on `Edit` / `Write` / `NotebookEdit` BEFORE the tool call — when active pipeline + no `Skill(architect-team-pipeline)` invocation + source-file target → exit 2 blocks with disclosure-required error. Catches the bypass at action time, not at Stop time. Registered in `hooks/hooks.json` as `PreToolUse[Edit|Write|NotebookEdit]`. Closes the root cause behind v2.10/v2.14/v2.20/v2.21/v2.22 with one unified detector + one runtime hook. **+94 net tests (3282 → 3376).** |
| **No pipeline-bypass discipline (v2.22.0)** | When the user invokes `/architect-team`, the orchestrator MUST follow the pipeline — not silently apply the methodology by hand because the prior session's mapping seemed sufficient. v2.0.0 Layer 6 detected unmatched Skill-invocation requests; v2.22.0 strengthens it to also detect the FOLLOWED-BUT-NOT-EXECUTED case (Skill called but zero Agent dispatches) AND adds confession-language detection. 20th Layer 3 tool `verify_no_pipeline_bypass` + 5 named severities (`pipeline-bypassed-after-slash-command` / `solo-implementation-instead-of-team-dispatch` / `independent-review-bypassed` / `openspec-bypassed` / `pipeline-confession-language-detected`). Confession marker dictionary covers 31+ verbatim phrases (*"I bypassed all of that and built it solo"*, *"no subagents, no independent review, no OpenSpec, no worktree"*, *"I overrode your explicit choice"*, *"driving directly from the plan"*, *"tokens into code instead of the mapping/spec ceremony"*, etc.). Layer 6 Stop-hook auditor strengthened to fire `solo-implementation-instead-of-team-dispatch` when matched-skill + zero-Agent-dispatches. New SR origin kind `pipeline-bypassed-needs-rerun`. Closes the verbatim user prose *"I bypassed all of that and built it solo... I overrode your explicit choice to use the pipeline."* **+51 net tests (3231 → 3282).** |
| **No proxy-element verification discipline (v2.21.0)** | When a verification step cannot reach the target state OR the target element, the agent MUST escalate — substituting a nearby measurable element (the screen-reader label in the coverage badge instead of the no-patients-monitored empty state) and reporting PASS off that proxy is now a structurally-rejected pattern. 19th Layer 3 tool `verify_target_element_measured` + 3 named severities (`proxy-element-substituted` / `unreachable-state-not-escalated` / `semantic-target-mismatch`). Required verdict fields enforce target/measured selector parity + semantic-label parity + `reachability_status`. Backup detector scans verification text for confession language (*"off that proxy"* / *"did not visually confirm"* / *"measured a different element"* / *"fell back to"*). New SR origin kind `target-state-unreachable-needs-seed-data`. Phase 5 gate + Phase B6 gate wired into both pipelines. Closes the verbatim user prose *"My verification agent couldn't reach the 'no patients monitored' view, so it measured a different element and I wrongly reported item 7 as passing off that proxy."* **+50 net tests (3181 → 3231).** |
| **Deploy mandate discipline (v2.20.0)** | When the user prompt contains a deploy verb + completeness modifier (e.g., *"fully deploy"*, *"100% of all elements active and real and functional"*), the orchestrator now treats the request as a HARD MANDATE with a 5-criterion binding contract: real backend URL + real frontend URL + login verified + every screen on live data + zero mock residue + zero unwired elements. Closes the verbatim user prose *"when I say fully deploy it must have 1 criteria 100% of all elements active and real and functional. anything less is failure."* 18th Layer 3 tool `verify_deploy_mandate_satisfied` + prompt classifier `detect_deploy_mandate_in_prompt` + 4 named severities (`deploy-mandate-not-satisfied` / `plan-only-deliverable-on-deploy-mandate` / `adjacent-dependencies-claimed-as-deployment` / `partial-deploy-passed-off-as-deploy`). Phase −2 detection + Phase 5 cross-layer gate + Phase 8 final gate wired into all 3 pipelines. New SR origin kind `deploy-mandate-not-satisfied`. **+54 net tests (3127 → 3181).** |
| **In-flight clarification injection mechanism (v2.19.0)** | v2.5.0 documented the discipline; v2.19.0 ships the runtime mechanism. Per-run inbox JSONL at `<workspace>/.architect-team/inbox/<run-id>.jsonl` + a new `/architect-team:inject <message>` slash command (works from a separate terminal session) + a phase-boundary check protocol wired into all 3 pipeline bodies (at the start of every numbered phase + after every subagent dispatch returns) + the 17th Layer 3 tool `verify_inflight_clarifications_processed` gating Phase 8 against silently-ignored messages. 3 classifications (`scope-amendment` re-runs upstream phase / `clarification` folds into next phase / `out-of-scope` records-only). New SR origin kind `clarification-requires-rerun`. **+51 net tests (3075 → 3127).** |
| **Codebase discipline registry + Phase 0.1 auto-update (v2.18.0)** | Per-codebase JSON registry at `.architect-team/discipline-registry.json` tracking which CT6 disciplines have been applied to which codebase. New `hooks/discipline_registry.py` module + 4-entry `DISCIPLINE_CATALOG` (prod-safe-test-classification auto-apply-safe / live-data-wiring SR-route / multi-persona-path-coverage SR-route / affordance-coverage SR-route). 16th Layer 3 tool `verify_discipline_registry_current` + new Phase 0.1 wiring in all 3 pipelines (auto-applies safe disciplines, routes the rest as SRs) + 17th slash command `/architect-team:discipline-status [--apply]`. Closes *"so for many of these changes, we need to probably also restructure either docs in a codebase or requirements etc.. so we know if our system is already running / updated or if we need to execute an update."* **+47 net tests (3025 → 3075).** |
| **Prod-safe test classification discipline (v2.17.0)** | Every Playwright / QA test MUST carry `// @prod-safe` (only reads — safe-against-production) or `// @not-prod-safe` (contains mutations) in its first 20 lines. When a run targets a production URL (not matching the 15 dev/staging URL exclusions), the runner filters to `@prod-safe` tests only. 15th Layer 3 tool `verify_test_prod_safety_classification` covering 37 mutation patterns (HTTP POST/PUT/PATCH/DELETE / form submits / file uploads / DB writes via prisma/knex/raw SQL / cloud storage / external sends via SendGrid/Twilio/Stripe) + 17 read-only patterns. 4 severities (`unclassified-test` / `prod-deployment-runs-unsafe-test` / `mutation-in-prod-safe-test` / `classification-mismatch`). NEW skill `test-prod-safety-classifier` (mass-classify + auto-classify modes) + NEW 16th slash command `/architect-team:classify-test-prod-safety`. **+71 net tests (2952 → 3024).** |
| **Backwards-compatible** | Schema v7 UNCHANGED across all three releases. v2.17.0 / v2.18.0 / v2.19.0 each fully no-op when their relevant surface is absent (no test files → classifier passes / no codebase surface → no findings / empty inbox → Layer 3 tool returns valid). All prior fixtures continue to validate. |

### Carried forward from v2.12.0 — cross-discipline gate consistency hotfix

| Capability | What changed |
|---|---|
| **Cross-discipline gate consistency hotfix** | Internal audit ("review our code and make sure that we are optimized and all our gates are logical and not adverse to one another") uncovered two issues. **FINDING 1 (HIGH)**: v2.10.0 `wrap-up-with-known-bugs` fired on legitimate v2.11.0 per-persona success reports because `_ITEM_DISPOSITION_CITATIONS` did not recognize `playwright_test_runs[]` / `per_persona_findings` / `tested green` / `persona_id:` / `entry_point:` as valid disposition channels. **FIXED** — citation list widened with 6 v2.11.0 tokens; detector now also treats non-empty `playwright_test_runs[]` and `per_persona_findings` in the artifact as per-item disposition. **FINDING 2 (MEDIUM)**: `_is_test_path` (v2.6.0) and `_looks_like_test_path` (v2.8.0) diverged on 3 of 8 test paths (one recognized `__mocks__/` / `fixtures/` / `mocks/`, the other recognized `_test.py` / `_spec.rb` suffixes). **FIXED** — unified into one `_is_test_path` with the UNION of all heuristics; `_looks_like_test_path` is preserved as a deprecated alias. |
| **What the audit did NOT find** | Zero overlap across `_STANDING_RED_MARKERS` (v2.8.0) / `_DEFERRAL_CATALOG_MARKERS` / `_FOLLOWUP_QUESTION_MARKERS` (v2.10.0) / `_LOADING_STATE_UI_HINTS` (v2.11.0) / `_MOCK_STATE_SIGNATURES` (v2.6.0). SR `origin.kind` catalog is comprehensive (16 distinct kinds). `vao_tools.py` at 2798 lines is large but proportional. |
| **Backwards-compatible** | The verbatim heirship deferral case (`⏳ Deferred — 7 bugs, 4 work-items … cluster-by-cluster … Want me to continue?`) STILL fires all 3 severities. v2.6.0 mock-state + v2.8.0 standing-red exclusions are unchanged. +12 net tests (2771 → 2783); zero regressions. |

### Carried forward from v2.11.0 — multi-persona path-coverage discipline

| Capability | What it does |
|---|---|
| **Multi-persona path-coverage discipline** | Features serving > 1 user persona (client / attorney / title-agency / family / etc.) MUST have a `persona-inventory.json` artifact AND at least one Playwright test PER PERSONA exercising their `entry_point` URL. Plus: every `cross_persona_dependencies[]` entry asserted by a paired test (writer persona creates data; target persona's view asserts it appears); every `submit_interaction` exercised by a double-click test (two clicks within 500ms with `record_count_after_double_click == 1`); every `backend_call_interaction` exercised by a loading-state test (UI surfaces a canonical hint within 200ms). The verbatim heirship case (*"I entered in with the email link. Filled in information and it did not show on the title side. … two matters were created (I think I hit the create matter twice because it looked frozen). And the attorney view doesn't show anything … this is unacceptable that you would claim a fix and fail to test it."*) is the canonical failure mode. |
| **12th Layer 3 tool — `verify_per_persona_path_coverage`** | NEW deterministic verification function + CLI subcommand in `hooks/vao_tools.py`. `_LOADING_STATE_UI_HINTS` (23 patterns: `spinner`, `Loading...`, `Working...`, `aria-busy`, `skeleton`, `progress-bar`, `Submitting...`, `Saving...`, `Creating...`, `Processing...`, …) + `_DOUBLE_SUBMIT_TIMING_THRESHOLD_MS = 500` + `_LOADING_STATE_MAX_DELAY_MS = 200`. 4 named severities: `persona-path-not-tested` / `cross-persona-sync-not-asserted` / `double-submit-not-tested` / `loading-state-not-asserted`. Trivially passes when `persona_inventory.personas[]` is empty. |
| **4 agent body extensions** | `qa-replayer.md` cannot return `bug-resolved` if a persona gap fires (new `per_persona_findings` block). `frontend.md` enumerates the 6 mandatory per-persona assertions. `interaction-reviewer.md` gains a `persona_path_coverage` axis with 5 classifications. `bug-replicator.md` adds new verdict `needs-persona-inventory`. |
| **Closes the verbatim heirship multi-view-sync failure** | Agent fixed ONE persona's path (client-email-link); the other three (title-agency / attorney / family-member) were silently broken. Plus double-submit from frozen UI created two duplicate matters because no loading state surfaced when the user clicked Create-Matter. v2.11.0's 4 severities catch every aspect verbatim. |
| **Backwards-compatible** | Schema v7 unchanged; 11 existing Layer 3 tools' contracts unchanged; v2.6.0 / v2.7.0 / v2.8.0 / v2.9.0 / v2.10.0 fixtures continue to validate. +49 net tests (2722 → 2771); zero regressions. |

### Carried forward from v2.10.0 — no end-of-run deferral discipline

| Capability | What it does |
|---|---|
| **3 severities** | `deferred-work-catalog` / `followup-decision-question` / `wrap-up-with-known-bugs`. Every in-scope item at run-end has exactly ONE valid disposition: (a) fixed in this change with `commit-sha:` citation, (b) routed via SR with canonical `origin.kind`, OR (c) confirmed-stub with `user_confirmed_at`. The verbatim *"⏳ Deferred — 7 bugs, 4 work-items … cluster-by-cluster (A → B → C → D) … Want me to continue?"* heirship case is the canonical failure. |

### Carried forward from v2.9.0 — MemPalace installer self-heal + polyglot Python in commands

| Capability | What it does |
|---|---|
| **Installer PATH self-heal** | `_locate_pip_user_binary()` + `_bridge_to_path_dir()` symlink macOS `~/Library/Python/*/bin` binaries into `~/.local/bin`; `python -m pip install --user` fallback when no `pip` script is on PATH. `_BRIDGED_BINARIES = ("mempalace", "mempalace-mcp")` is an explicit allowlist. The slash command uses the single polyglot `python3 ... || python ...` invocation pattern; a structural test audits all 14 command files. |

### Carried forward from v2.8.0 — no standing-red discipline

| Capability | What it does |
|---|---|
| **No standing-red discipline** | Agents MUST NOT commit a failing test as documentation of a known bug. When a regression is diagnosed — including cross-layer cases where one layer is correct and the other is broken — the only valid endings are: (a) fix every layer the diagnosis names in this change, (b) route the unfixed layer via a solution requirement so the orchestrator dispatches the right team, OR (c) escalate for an explicit confirmed-stub decision. Committing a failing test that *"will go green when fixed"* ships visible red CI as a substitute for routing the fix — exactly what CI is supposed to forbid. |
| **10th Layer 3 tool — `verify_no_standing_red`** | NEW deterministic verification function + `verify-no-standing-red` CLI subcommand in `hooks/vao_tools.py`. `_STANDING_RED_MARKERS` constant covers 16 patterns including `// standing red` / `// will go green when fixed` / `// known broken` / `// documents the gap` / `test.fixme(` / `it.fixme(` / `test.fail(` / `@pytest.mark.xfail`. 2 named severities: `standing-red-committed` (marker in newly-added test, no confirmed-stub citation) / `cross-layer-fix-not-routed` (cross-layer diagnosis + standing-red + no SR of `cross-layer-backend-required` / `cross-layer-frontend-required` origin kind). Trivially passes when no markers AND no `cross_layer_diagnosis` — fully backwards-compatible. |
| **4 agent body extensions** | `agents/bug-replicator.md` gains new `needs-cross-layer-fix` verdict. `agents/qa-replayer.md` gains new `standing_red_finding` field on `bug-still-present` verdict. `agents/frontend.md` + `agents/backend.md` document cross-layer routing via SR (never standing-red). |
| **Closes the verbatim heirship B23 failure** | Agent correctly proved frontend correct + backend broken (`executeFamilyGraphSync` → Neo4j aggregate misses spouse/child), then committed `live-intake-persist.spec.ts` as a standing-red regression test with `// will go green when it's fixed` instead of routing a `cross-layer-backend-required` SR. v2.8.0's 2 severities catch the verbatim case. |
| **Backwards-compatible** | Schema v7 unchanged; 9 existing Layer 3 tools' contracts unchanged; v2.6.0 + v2.7.0 fixtures continue to validate. +52 net tests (2583 → 2635); zero regressions. |

### Carried forward from v2.7.0 — pattern propagation mandate

| Capability | What it does |
|---|---|
| **6th severity in `verify_live_data_wiring`** | `shared-mock-source-not-swept` fires when a `wiring_mandate.shared_mock_sources[]` entry names N consumer files but the diff modified fewer than N. The 3-step sweep protocol (trace → enumerate → fix) is documented in `common-pipeline-conventions/SKILL.md` + `agents/frontend.md` + `agents/interaction-reviewer.md`. |

### Carried forward from v2.6.0 — live-data wiring discipline

| Capability | What it does |
|---|---|
| **5 severities + 2-pass workflow** | The 9th Layer 3 tool `verify_live_data_wiring` enforces `mock-state-residue` / `live-response-not-rendered` / `mock-fallback-uncovered` / `network-not-intercepted` / `async-status-not-surfaced` via Playwright + tamper test + code-side audit. The 3-reviewer `interaction-completeness` swarm extension audits each slice carrying a `wiring_mandate`. |

### Carried forward from v2.5.0 — in-flight clarification discipline

| Capability | What it does |
|---|---|
| **In-flight clarification** | Mid-run user injections without `/architect-team` invocation MUST be folded into the in-flight pipeline's brief as scope amendments, NOT spawn a sibling workflow. The 3 detection signals (`intake-state.json` phase < 8 / `escalation-pending.md` / unresolved teammate manifests) determine in-flight state; the 4 forbidden anti-patterns (`solve-with-tools-directly` / `answer-conversationally` / `spawn-sibling-invocation` / `silently-ignore`) name what's NOT allowed. |

### Carried forward from v2.4.0 — verified-live discipline

| Capability | What it does |
|---|---|
| **External-state assertion** | For features that touch external systems (email / payment / push / webhook-outbound / oauth / blob-storage), the semantic assertion MUST query the external system's own observable state — NOT a backend response field, NOT a 3rd-party API queue-accept ack (SendGrid 202 ≠ delivered), NOT UI display text. 7th severity `external-state-not-asserted` in `verify_live_verification_claim`. |
| **Evidence-artifact citation** | Every "verified live" claim MUST include `evidence_artifact_path` pointing to a concrete on-disk file (Playwright trace `.zip` / network log / external-API response dump / screenshot). The agent's prose `assertions[]` is no longer accepted as evidence. 8th severity `missing-evidence-artifact`. |
| **Canonical heirship fixtures** | `external-state-not-asserted-email-invite.json` (verbatim "SendGrid logged status=202" case where the user never received the email) + `fabricated-verification-table.json` (verbatim 3-row ✅ "sent" table case where no Playwright run actually captured the results). |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  CARRIED FROM v2.3.0 — PHENOTYPE SUBSYSTEM  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Capability | What it does |
|---|---|
| **Phenotypes** | A library of pre-made, generalized, *deployable* application architectures — each one a blueprint + a parameterized scaffold (starter code + OpenTofu) + metadata — under `phenotypes/`. **Four production seeds ship** in v2.3.0+: `user-management` (async FastAPI + SQLAlchemy-async + Postgres + Redis backend + React/Vite/shadcn frontend + ECS-AWS deploy; dual-credential auth, N-layer RBAC, org hierarchy, audit), `config-management` (multi-service multi-env multi-cloud OpenTofu monorepo with feature-flagged service modules + hierarchical state keys + registry-manifest discovery), `ai-management` (multi-tenant LLM control plane: prompts as versioned inheritable template config with prototype-chain deep_merge + draft/publish/rollback + per-tenant budgets + swappable model gateway + authoring console; deploys via the `config-management` phenotype), `code-wiki` (v3.13.0 — a self-hosted Next.js documentation wiki absorbed from deepwiki-open with the LLM stack stripped: sidebar nav + markdown + client-Mermaid + theming, ingesting a `codebases.json` registry → `docs/*_MAP.md`; deploys locally via docker-compose or to AWS/GCP via the `config-management` phenotype). |
| **`--phenotype <label>`** | Seed a run from a known phenotype (`/architect-team --phenotype user-management "<what you want>"`), OR let the pipeline propose a match reuse-first (a rung above build-new) — surfaced for confirmation, never applied silently. |
| **`absorb`** | `/architect-team:absorb-phenotype <path> --label <name>` — analyze any arbitrary codebase, generalize it (strip names / secrets / account-specifics; parameterize), and ingest it as a new labeled phenotype. Read-only on the source; validated by the engine before it lands under `phenotypes/<label>/`. |
| **Engine** | `scripts/phenotypes/phenotypes.py` (stdlib) exposes 5 CLI subcommands: `list` (show all available phenotypes), `show <label>` (full manifest detail), `match <description>` (reuse-first scoring), `validate <label>` (lint phenotype.json + blueprint.md + scaffold structure), `emit <label> <out-dir>` (render the parameterized scaffold to disk). Backed by two new skills: `phenotypes` (consumption playbook — when to suggest one, how to fill parameters, how it interacts with reuse-first design) + `phenotype-absorption` (capture playbook — how to ingest a reference codebase into a new phenotype). |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  WHAT YOU GET  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
┌─ SKILLS (48) ───────────────────────┬─ AGENTS (39) ─────────────────────────┐
│ ◇ architect-team-pipeline           │ ◆ system-architect (fable)            │
│ ◇ intake-and-mapping                │ ◆ frontend (fable)                    │
│ ◇ reuse-first-design                │ ◆ backend (fable)                     │
│ ◇ frontend-route-mapping            │ ◆ reconciler (fable)                  │
│ ◇ design-fidelity-mapping          *│ ◆ integration (fable)                 │
│ ◇ visual-fidelity-reconciliation   *│ ◆ scaffold-agent (fable)              │
│ ◇ playwright-user-flows             │ ◆ codebase-map-reviewer (fable)       │
│ ◇ dev-api-integration-testing       │ ◆ integration-explorer (fable)        │
│ ◇ coverage-mapping                  │ ◆ master-synthesizer (fable)          │
│ ◇ team-spawning-and-review-gates    │ ◆ route-mapper (fable)                │
│ ◇ root-cause-test-failures          │ ◆ test-completeness-verifier (fable)  │
│ ◇ diagnostic-research-team          │ ◆ diagnostic-researcher (fable)       │
│ ◇ mempalace-integration             │ ◆ editability-reviewer (fable)        │
│ ◇ expensive-verification-debugging  │ ◆ visual-capture (fable)              │
│ ◇ editability-completeness          │ ◆ visual-analyzer (fable)             │
│ ◇ readme-styling                    │ ◆ task-reviewer (fable)               │
│ ◇ visual-verification-team          │ ◆ interaction-reviewer (fable)        │
│ ◇ documentation-currency            │ ◆ bug-replicator (fable)              │
│ ◇ interaction-completeness          │ ◆ qa-replayer (fable)                 │
│ ◇ dynamic-value-discovery           │ ◆ bug-classifier (fable)              │
│ ◇ interaction-intuition             │ ◆ interaction-intuiter (fable)        │
│ ◇ bug-fix-pipeline                  │ ◆ doc-updater (fable)                 │
│ ◇ ux-test-builder                   │ ◆ flow-explorer (fable)               │
│ ◇ proposal-refiner                  │ ◆ flow-executor (fable)               │
│ ◇ email-testing                     │ ◆ fix-sensibility-checker (fable)     │
│ ◇ mini-architect-team-pipeline      │ ◆ prompt-refiner (fable)              │
│ ◇ common-pipeline-conventions       │ ◆ mini-qa (fable)                     │
│ ◇ verified-agent-output (v2.0.0)   *│ ◆ oracle-deriver (fable) ★            │
│ ◇ interactive-mockup-discovery     *│ ◆ adversarial-reviewer (fable) ★      │
│   (v2.1.0)                          │ ◆ interaction-observer (fable) ★      │
│ ◇ phenotypes (v2.3.0)               │ ◆ endpoint-tracer (fable) ★           │
│ ◇ phenotype-absorption (v2.3.0)     │                                       │
│ ◇ visual-to-api-design (v2.13.0)   *│                                       │
│ ◇ test-prod-safety-classifier      *│ ◆ test-run-watcher (fable) ★          │
│   (v2.17.0)                         │ ◆ monitor-synthesizer (fable) ★       │
│ ◇ test-run-monitor (v3.3.0)        *│ ◆ domain-researcher (fable) ★         │
│ ◇ cartographer-team (v3.4.0)       *│ ◆ structure-analyst (fable) ★         │
│ ◇ domain-research-team (v3.4.0)    *│ ◆ reference-tracer (fable) ★          │
│ ◇ api-design-from-frontend         *│ ◆ structure-adversary (fable) ★       │
│   (v3.4.0)                          │                                       │
│ ◇ data-engineering-exploration     *│                                       │
│   (v3.5.0)                          │                                       │
│ ◇ endpoint-trace-mapping            │                                       │
│   (lineage P1 — the CDLG)           │                                       │
│ ◇ data-lineage-mapping              │                                       │
│   (lineage P3 — asset lineage)      │                                       │
│ ◇ structure-optimization           *│                                       │
│   (v3.11.0 — restructure planning)  │                                       │
│ ◇ data-dictionary (v3.17.0)         │ ◆ closeout-agent (fable) ★            │
│ ◇ closeout (v3.18.0)                │ ◆ mcp-design-agent (fable) ★          │
│ ◇ claude-md-efficiency (v3.19.0)    │                                       │
│ ◇ mcp-output-contract-design        │                                       │
│   (v3.20.0 — MCP design)            │                                       │
│ ◇ helpdesk (v3.21.0)                │                                       │
│ ◇ token-compression (v3.22.0)       │                                       │
│ ◇ claude-design-import (v3.33.0)    │                                       │
├─ COMMANDS (23) ─────────────────────┴───────────────────────────────────────┤
│ ▸ /architect-team <path-to-requirements-folder | free-text prompt>          │
│ ▸ /architect-team:architect-team-setup                                      │
│ ▸ /architect-team:visual-qa [<codebase-path>]                               │
│ ▸ /architect-team:visual-to-api <codebase-path>     (v2.15.0 — 4-stage)   * │
│ ▸ /architect-team:mempalace-install                                         │
│ ▸ /architect-team:librarian-install [status|add-topic|run-once|uninstall]   │
│   (v3.29.0 — install the topic-research Librarian background daemon)        │
│ ▸ /architect-team:memory <search|mine|status|wake-up|sweep>                 │
│ ▸ /architect-team:editability-audit [<codebase-path>]                       │
│ ▸ /architect-team:bug-fix <bug-description | requirements-folder>           │
│ ▸ /architect-team:ux-test <persona + objectives + --site or --dev>          │
│ ▸ /architect-team:refine-prompt <free-text prompt>      (standalone refine) │
│ ▸ /architect-team:mini <requirements-folder | free-text prompt>             │
│ ▸ /architect-team:mini-review-sweep [--since <ref>] [--limit <N>]           │
│ ▸ /architect-team:cleanup-worktrees [--dry-run] [--against <ref>]           │
│ ▸ /architect-team:status                          (dispatch / state report) │
│ ▸ /architect-team:absorb-phenotype <path> --label <name>                    │
│ ▸ /architect-team:classify-test-prod-safety [<glob>] [--write-annotations]  │
│   (v2.17.0 — mass-classify @prod-safe / @not-prod-safe annotations)         │
│ ▸ /architect-team:discipline-status [--apply] [--workspace <path>]          │
│   (v2.18.0 — codebase discipline registry: report + auto-apply)             │
│ ▸ /architect-team:inject <message>                                          │
│   (v2.19.0 — in-flight clarification injection into the running pipeline)   │
│ ▸ /architect-team:monitor-tests <test-command-or-source-spec>               │
│   (v3.3.0 — passive observer team: local / CI / production-QA)              │
│ ▸ /architect-team:optimize-structure [<codebase-path> | --all]              │
│   (v3.11.0 — adversarially-verified restructure plan + OpenSpec change)     │
│ ▸ /architect-team:closeout [--check] [--workspace <path>]                   │
│   (v3.18.0 — doc-currency double-check before compact / end-of-work)        │
│ ▸ /architect-team:logit [--privacy <full|summary|off>]                      │
│   (v3.21.0 — manual triage report; consent + privacy)                       │
├─ HOOKS (7 scripts / 8 events) ──────────────────────────────────────────────┤
│ ▸ PreToolUse(*)             skill-invocation hard-gate (v3.15.0/1)          │
│                             + v3.30.0 sticky run arm (active-run marker =>  │
│                             build/dispatch tools need the Skill re-engaged) │
│ ▸ PreToolUse(Edit/Write/    unilateral-override guard                       │
│     NotebookEdit)                                                           │
│ ▸ PostToolUse(TaskUpdate)   review-gate evidence — v7 + independent review  │
│ ▸ TaskCompleted             review-gate evidence re-check                   │
│ ▸ SubagentStop              teammate-idle review-gate re-check              │
│ ▸ TeammateIdle              teammate-idle review-gate re-check              │
│ ▸ Stop                      pipeline-completion audit (terminal gate)       │
│                             + v3.9.2 openspec validate --all --strict gate  │
│                             + v3.30.0 continuation guard (no mid-run stops; │
│                             no-progress bound => auto-escalate)             │
│ ▸ PreCompact                closeout doc-currency reminder (v3.18.0)        │
│ ▸ SessionStart              run-continuity resume directive (v3.30.0)       │
├─ SETUP ─────────────────────────────────────────────────────────────────────┤
│ ▸ scripts/setup/setup.py             openspec CLI, pytest+httpx, Playwright │
│                                      + HARD-gates required plugins +        │
│                                      openspec-propose skill (exit 1)        │
│ ▸ scripts/setup/install_mempalace.py MemPalace CLI + MCP server (uv-first)  │
└─────────────────────────────────────────────────────────────────────────────┘

      * = activates only when design inputs exist (screenshots / Figma /
          tokens / Storybook / brand docs / assets directory)
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  INSTALL  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### ▸ Prerequisites (must be on your machine)

| Requirement | Where to get it |
|---|---|
| **Python 3.10+** as `python3` on `$PATH` | Ubuntu/Debian: `sudo apt install python-is-python3` · macOS: `brew install python` · Windows: re-run the [python.org installer](https://www.python.org/downloads/) with "Add to PATH" checked, or use `py -3` |
| **Node ≥ 20.19** (npm) | [nodejs.org](https://nodejs.org/) or your package manager |
| **Claude Code** | [docs.anthropic.com/claude-code](https://docs.anthropic.com/claude-code) |

### ▸ Install the plugin

```bash
# 1. Register this repo as a marketplace
/plugin marketplace add <git-url-of-this-repo>

# 2. Install the plugin
/plugin install architect-team@architect-team-marketplace
```

### ▸ Install prerequisite Claude plugins (one-time)

```bash
# cartographer ships from a THIRD-PARTY marketplace (kingbootoshi/cartographer);
# add that source FIRST, then install. superpowers + ralph-loop live on the
# built-in claude-plugins-official marketplace (no add step needed).
/plugin install superpowers@claude-plugins-official
/plugin marketplace add kingbootoshi/cartographer
/plugin install cartographer@cartographer-marketplace
/plugin install ralph-loop@claude-plugins-official
```

These three are **HARD (exit-1) prerequisites** (v3.9.0) — `scripts/setup/setup.py` aborts with exit 1 if any is missing; superpowers in particular is a hard dependency, not a warning. The vendored `openspec-propose` authoring skill is a **4th hard-gated prerequisite** (verified by `ensure_openspec_propose_skill()`; a missing skill is also exit 1). The cartographer marketplace source is `kingbootoshi/cartographer` — `architect-team-setup` names it and prints the exact `/plugin marketplace add kingbootoshi/cartographer` + `/plugin install cartographer@cartographer-marketplace` remediation when cartographer is missing.

### ▸ Install CLI / Python / browser deps

```bash
/architect-team:architect-team-setup
```

Idempotent. Flags: `--check-only` (report only), `--no-prompt` (print the suggested settings edit; never writes), `--yes` / `-y` (assume "y" to every consent prompt for non-interactive installs — also enabled by `CT6_SETUP_ASSUME_YES=1`), `--force-reinstall` (reinstall everything managed).

### ▸ Install MemPalace (optional — enables searchable cross-run memory)

```bash
/architect-team:mempalace-install
```

Installs the MemPalace CLI (uv-first, pip fallback) and prints the `claude mcp add` + per-workspace `mempalace init` commands for you to run. The pipeline degrades gracefully without it — every wake-up / mine / search is skipped with a one-line note.

### ▸ Install the Librarian (optional — a background topic-research daemon)

```bash
/architect-team:librarian-install
```

The CT6-6 **Librarian** is also installable (v3.29.0), mirroring the MemPalace install. The stdlib-only installer provisions state under `~/.architect-team/librarian/`, generates the per-OS boot descriptor (launchd / systemd / Task Scheduler), and **prints** the register hint (it never auto-loads it). With an `ANTHROPIC_API_KEY` set it wires the real Anthropic adapter; with no key it installs in an honest **provisioned-but-disabled** state — and (v3.38.0) it ASKS for the key rather than only punting: the command wrapper offers to capture it in-session and apply it via the `--enable` path (an explicit decline is recorded in `key-declines.json` so re-runs never nag; `install --re-ask-keys` clears it), and a direct terminal run prompts with hidden getpass entry on a real TTY (blank to skip). Once enabled it runs as a background daemon on your machine — installable + self-managed, not a deployed/production service.

### ▸ Updating other instances

```bash
/plugin marketplace update architect-team-marketplace
/plugin update architect-team@architect-team-marketplace
/reload-plugins
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  USAGE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
/architect-team <path-to-requirements-folder> [--no-commit] [--no-push] [--no-compact]
```

The requirements folder may contain OpenSpec artifacts (`proposal.md`, `specs/`, `design.md`, `tasks.md`), a Superpowers-formatted brief, or plain markdown. The orchestrator detects and normalizes.

**Default: auto-commit + auto-merge-to-main + push on clean pass (v3.7.0).** At the end of a successful Phase 8, the pipeline stages its working set, commits with a structured message including the requirements implemented + tests added + archive path, then — when the run's `architect-team/<slug>` branch merges cleanly — merges `--no-ff` into `main`, pushes `main`, deletes the branch (local + remote), and removes the run worktree (see Logic Map D). A conflict or protected branch falls back to the feature-branch + PR path and is reported, never forced. To opt out per invocation: pass `--no-auto-merge` (feature branch + recommend a PR, worktree persists), `--no-commit` (skip both commit + merge), `--no-push` (commit locally only), or `--no-compact` (suppress the end-of-run `/compact` prompt). Natural-language opt-outs ("don't commit", "no push", "keep the branch") are honored.

### ▸ Launch a code wiki from your maps (v3.13.0)

The maps every run produces (`CODEBASE_MAP.md` / `ROUTE_MAP.md` / `INTEGRATION_MAP.md` / `DESIGN_MAP.md` / `INTERACTION_INTUITION_MAP.md`) double as wiki content. The `code-wiki` phenotype hosts them — for any number of codebases — in a navigable Next.js wiki (sidebar tree, rendered Mermaid, dark/light theming, absorbed from deepwiki-open with the LLM stack stripped: zero API keys).

```bash
# emit the scaffold, register codebases, run
python scripts/phenotypes/phenotypes.py emit code-wiki ./my-wiki --param "wiki_name=Acme Engineering Docs"
#   -> fill <WIKI_CONTENT_DIR>/codebases.json with [{ "name": ..., "maps_dir": ... }] (one entry per codebase)
cd my-wiki && npm install && npm run build && npm run start     # or: docker compose up --build
```

Hosting is a variation point — `local` (docker-compose, the default), `aws`, or `gcp`; the cloud paths deploy via the `config-management` phenotype (apply its platform layers first, then the emitted `iac/<cloud>/` service layer — both sets `tofu validate`-clean as shipped). Full quick-start: [`phenotypes/README.md`](phenotypes/README.md).

### ▸ Import a Claude Design project (v3.33.0)

Offer a Claude Design project by LINK — no zip download. Paste a `claude.ai/design/p/<id>` link (optionally with a `?file=<screen>` focus and a trailing `Implement: <path>` target), and/or name the `claude_design` MCP. Phase −1 intake detects the offer, fetches the WHOLE project through the MCP, and materializes it to `<workspace>/.architect-team/claude-design/<project-id>/`, then hands it to the existing interactive-mockup oracle path — no special flag needed.

```bash
/architect-team build this dashboard: https://claude.ai/design/p/abc123?file=Finance+Dashboard.html
/architect-team:visual-to-api ./my-app     # a Claude Design link in the requirements is materialized before Stage 1
```

Connect the `claude_design` MCP and run `/design-login` first. When the MCP is unavailable, the run instructs you to connect it and auto-falls-back to the local/zip design-input path, so it never dead-ends. The fetch is an injected runtime adapter — no MCP tokens are persisted. Engine: `scripts/claude_design/claude_design_import.py`; contract: `skills/claude-design-import/SKILL.md`.

### ▸ Constrain appearance changes (v3.14.0)

By default every run is **`strict`** on frontend appearance: the agents change what a user SEES only when the requirement names it, the documented design spec demands it (drift-to-spec restoration), or an explicitly-required capability needs a minimal entry point. Improvement ideas are recorded to `.architect-team/appearance-proposals/<run-id>.json` — never implemented. Backend changes stay unrestricted ("do what you need to on the backend").

```bash
/architect-team improve the export flow                       # strict (default) — no unsolicited visual changes
/architect-team improve the export flow --appearance propose  # ideas batched at a user approval gate; only approved ones land
/architect-team redesign the dashboard --appearance innovate  # free rein — every visual delta logged + DESIGN_MAP-reconciled
```

The review gates enforce it: schema v7's OPTIONAL `appearance_scope_review` evidence field blocks completion when an appearance-affecting delta traces to no mandate, the independent `task-reviewer` traces every visual delta, and the Phase 7 Master Review Audit walks the run diff + the proposals artifact. Canonical rules: `common-pipeline-conventions` `## Appearance-change policy discipline (v3.14.0)`.

### The pipeline at a glance

**Uniform plugin usage (v3.9.0).** Every pipeline body (`architect-team` / `bug-fix` / `mini` / `ux-test`) opens with a **superpowers pre-flight abort gate** and weaves named `superpowers:*` invocations (`brainstorming` / `test-driven-development` / `systematic-debugging` / `verification-before-completion`) through its phases — canonical home `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`. The implementing pipelines (`mini` + `bug-fix` + full) share **identical** `openspec validate --all --strict` + `openspec archive` gates.

```
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE −1      │    │   PHASE 0–1     │    │    PHASE 2      │
       │  Intake & Map   │───▶│  Detect & Plan  │───▶│  Team Spawn     │
       │  · CODEBASE_MAP │    │  · openspec     │    │  · parallel     │
       │  · ROUTE_MAP    │    │  · coverage-map │    │  · non-overlap  │
       │  · DESIGN_MAP * │    │  · reuse-first  │    │  · plan-approval│
       │  · INTEGR_MAP   │    │  100% gate      │    │    triggers     │
       └─────────────────┘    └─────────────────┘    └────────┬────────┘
            3-reviewer            12 conditions               │
            ralph loop            hard gate                   ▼
                                                     ┌─────────────────┐
                                                     │    PHASE 3      │
                                                     │  Review Gate    │
       ┌─────────────────┐    ┌─────────────────┐    │  · hook-enforced│
       │   PHASE 5       │    │   PHASE 4       │    │  · 17 fields    │
       │  Integration    │◀───│  Reconciliation │◀───│  · visual-fid   │
       │  · real backend │    │  · shared bounds│    │  · ui-interactn │
       │  · playwright   │    │  · contract sync│    │  · RCA on fail  │
       │  · visual-fid   │    │  · no feature   │    │  · auto-spawn   │
       │  · ui-interactn │    │    code         │    │    SR on issue  │
       └────────┬────────┘    └─────────────────┘    └─────────────────┘
                │
                ▼
       ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
       │   PHASE 6       │    │   PHASE 7       │    │   PHASE 8       │
       │  Outer Loop     │───▶│  Master Review  │───▶│  Final Report   │
       │  · per-task-grp │    │  · coverage map │    │  · per req →    │
       │  · dep graph    │    │    fully green  │    │    commit →     │
       │  · ledger       │    │  · re-spawn on  │    │    test → demo  │
       │                 │    │    gap          │    │  · openspec     │
       │                 │    │                 │    │    archive      │
       └─────────────────┘    └─────────────────┘    └─────────────────┘

       * DESIGN_MAP only when design inputs exist
```

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LOGIC MAPS — ROUTING & GATES  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The flowchart above shows *what happens next*. These two logic maps show *how flow is decided* — the decision points (`◆`), the gates (`▣`), the verdicts (`✓` allow / `✗` block), and the route-back edges (`◀┄┄`).

### ▌ Logic Map A — the Phase 3 review gate

Every `TaskUpdate(completed)` on a teammate-owned task is gated; the hook exits 2 (block) until the evidence is complete.

```
   teammate calls  TaskUpdate(status = completed)
            │
            ▼
   ◆ is task_id owned by a teammate?          (listed in some manifest's
        │                    │                 expected_review_evidence)
      no│                    │ yes
        ▼                    ▼
   ✓ exit 0             ▣ REVIEW GATE  —  hooks/review-gate-task.py
   not an architect-    reads  .architect-team/reviews/<task_id>.json
   team task; ignored             │
                                  ▼
        ◆ evidence present · valid JSON · all 12 self-review fields valid?
            · spec_review = quality_review = "pass"
            · real_not_stubbed = true · tests added ≥ 1 and == passing
            · reuse_compliance = "ok" · demo_artifact + files_changed non-empty
            · visual_fidelity / test_completeness / integration_testing /
              ui_interaction reviews ≠ "fail"
            · independent_review present · reviewer ≠ teammate ·
              verdict = "pass"   (written by the task-reviewer agent)
            │                                       │
         no │                                       │ yes
            ▼                                       ▼
   ✗ exit 2  —  BLOCK                       ✓ exit 0  —  ALLOW
   stderr names the exact gap               task is marked completed
            ┊
            └┄┄▶ teammate fixes the gap and retries;
                 3 consecutive rejections ⇒ escalation handoff
```

### ▌ Logic Map B — issue → fix routing (Solution Requirements)

Every surfaced issue becomes an SR; test-failure origins route through diagnostic research first, editability + interaction gaps go straight to a fix team; the loop closes when the originating check passes.

```
   an issue surfaces  (failed test · visual drift · editability /
            │           interaction gap — unwired control, placeholder
            │           page, hardcoded dynamic value)
            ▼   the discovering agent writes a Solution Requirement (SR)
   ◆ route by  SR.origin.kind
        │
        ├─ test-failure origin ───────────────────▶ ▣ DIAGNOSTIC RESEARCH
        │  rca-product-bug · playwright-failure ·             3 diagnostic-researcher
        │  integration-test-failure ·                         agents argue in parallel
        │  integration-testing-failure ·                      → system-architect reviews
        │  test-completeness-failure · visual-fidelity-drift  robustness → consolidated
        │                                            diagnostic plan
        │                                                     │
        └─ editability-gap / unwired-control / ───┐            │
           placeholder-page / hardcoded-          │            │
           dynamic-value — the converged map      │            │
           is already the full diagnosis,         │            │
           research is skipped                    │            │
                                                  ▼            ▼
                                       ▣ FIX TEAM  —  spawned in Phase 2,
                                       runs the Phase 2 → 3 → 4 → 5 loop
                                                     │
                                                     ▼
                            ◆ does the originating test / check pass?
                                 │                              │
                              no │                              │ yes
                                 ▼                              ▼
                  ◀┄┄ re-enter the dev loop            ✓ SR → "resolved";
                      (Phase 3 for the slice)             the originating
                                                          teammate unblocks
```

### ▌ Logic Map C — the completion audit (Stop hook)

The orchestrator runs as the main session — no hook can gate its mid-run behaviour, but the `Stop` hook gates its **terminal** state: it blocks the orchestrator from ending a run, or auto-committing, while the run is still incomplete. Since v3.30.0 it is also the **continuation guard**: an active run may not end its turn with *"we've done a lot — want me to continue?"*.

```
   orchestrator session ends ──▶ ▣ Stop HOOK · pipeline-completion-audit.py
            │
            ▼
   ◆ does .architect-team/ hold an INCOMPLETE run?
     · an open / in-progress solution requirement
     · a test-failure SR with no diagnostic plan
     · an unsatisfied editability loop   · a test-completeness debt
     · a master-review audit verdict that is not overall: pass
     · an openspec change that fails `openspec validate --all --strict`
       (v3.9.2, once a master-review verdict exists)
     · a documentation-currency audit verdict that is not overall: pass
     · an ACTIVE active-run.json lifecycle marker — the run has not executed
       `run_continuity.py --mark-complete` yet (v3.30.0; clean worklist or not)
        │                                              │
      no│  (clean — or not an architect-team run)      │ yes
        ▼                                              ▼
   ✓ exit 0 — ALLOW the stop          ◆ escalation-pending.md present, or a
                                        fresh in-progress.md (background wait)?
                                          │                              │
                                      yes │  (legitimately                │ no
                                          ▼   paused / waiting)           ▼
                                 ✓ exit 0 — ALLOW             ✗ exit 2 — BLOCK
                                                              resolve the gaps / keep driving
                                                              the run, OR write the escalation
                                                              marker, then stop again
```

For a session that ENGAGED a pipeline skill, the block persists across stop-chains while the run keeps making progress (the `run_continuity` fingerprint changes) — unbounded, per the Unbounded solving discipline — and after `CT6_MAX_NO_PROGRESS_STOPS` (default 3) consecutive **no-progress** blocks the guard auto-writes `escalation-pending.md` and allows the stop, so a wedged run surfaces to the human instead of looping. Non-engaged sessions get one nudge (with the resume-via-Skill directive) and are never wedged.

The same audit runs as `pipeline-completion-audit.py --check` before the Phase 8 auto-commit — so "clean pass" is a checked fact, not the orchestrator's self-assessment (`--check` deliberately skips the lifecycle marker: Phase 8 runs it while the run is still active).

### ▌ Logic Map D — Phase 8 git behavior (auto-merge-to-main, v3.7.0)

On a clean Phase 8 / B8 / M7 pass the run is **self-tidying by default** — it lands on `main` and cleans up after itself. `--no-auto-merge` restores the feature-branch + PR path; a conflict or a protected branch is always reported, never forced.

```
   Phase 8 GREEN  +  completion audit clean  +  commit on architect-team/<slug>
            │
            ▼
   ◆ AUTO_MERGE_MAIN ?           (--no-auto-merge / "keep the branch" / "PR only"
        │                │        sets it false)
      no│                │ yes
        ▼                ▼
   ✓ feature branch    ▣ MERGE GATE  —  branch cleanly mergeable into main?
   · push branch         (git merge-tree --write-tree · never touches the tree)
   · recommend a PR              │                              │
   · worktree persists        no │  conflict                    │ yes
     (v3.6.0 warning)           ▼                               ▼
            │            ✗ NOTHING CHANGES                merge --no-ff → main
            │            conflict: true                   · push main
            │            ◀┄┄ fall back to feature         · delete branch (local+remote)
            │                branch + PR + persist        · remove worktree
            │                                                    │
            │                                          ◆ push accepted ?
            │                                             │                │
            │                                          no │ protected /    │ yes
            │                                             ▼ non-ff          ▼
            │                                  ✗ STOP pruning        ✓ pruned & tidy
            │                                  reason: push-rejected  main updated;
            │                                  branch + worktree      branch + worktree
            │                                  recoverable; never     gone
            │                                  --force
            ▼                                             │
   startup of the NEXT run reconciles any stray architect-team/* branches:
   ◆ merge-all-clean + prune  /  prune-without-merge  /  leave   (one AskUserQuestion)
```

Branch protection always wins: `--force` is never added. Only `architect-team/*` branches are ever auto-merged, pruned, or reconciled — never the user's own branches.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  THE LOOPS & ACCEPTANCE CRITERIA  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline is a stack of nested loops, each with explicit exit criteria. Listed in execution order; the README enumerates only the contract — skill files are the source of truth.

### ▌ Loop 1 — Per-codebase mapping (Phase −1B)

- **Wrapper:** `/ralph-loop "<review prompt>" --completion-promise "CODEBASE MAP COMPLETE"`. One ralph loop per discovered codebase (loops until the promise; no iteration cap per v3.8.0 unbounded solving).
- **Mechanism:** Cartographer (and `route-mapper` for frontends) produces `<codebase>/docs/CODEBASE_MAP.md` (and `ROUTE_MAP.md` + `DESIGN_MAP.md` if design inputs exist). Then 3 `codebase-map-reviewer` agents are spawned **in parallel**. Each returns `{ "status": "ok" | "deficient", "deficiencies": [...] }`.
- **Iteration body** (if any reviewer returns `deficient`): aggregate + dedupe deficiencies; re-trigger cartographer / route-mapper in update mode; loop.
- **Exit criteria — all of:** all 3 reviewers return `status: "ok"` in the same iteration; the orchestrator emits `CODEBASE MAP COMPLETE`.
- **Freshness short-circuit:** `last_mapped` frontmatter ≥ `git log -1 --format=%cI` ⇒ codebase marked `CURRENT`, loop skipped.
- **Iteration cap:** none — loops until all 3 reviewers agree (v3.8.0 unbounded solving).
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/codebase-map-reviewer.md`](agents/codebase-map-reviewer.md), [`agents/route-mapper.md`](agents/route-mapper.md).

### ▌ Loop 2 — Integration mapping (Phase −1C)

- **Wrapper:** `/ralph-loop "<synthesis prompt>" --completion-promise "INTEGRATION MAP COMPLETE"`. One ralph loop for all codebases (loops until the promise; no iteration cap per v3.8.0 unbounded solving).
- **Mechanism — sequential sub-loops:** (2a) 3 `integration-explorer` agents in parallel, round-robin convergence; (2b) `master-synthesizer` writes `<workspace>/docs/INTEGRATION_MAP.md`; (2c) confirmation pass — each explorer confirms the master doc.
- **Exit criteria — all of:** all 3 explorers confirm; INTEGRATION_MAP.md exists with frontmatter + 6 sections; master-synthesizer emits `INTEGRATION MAP COMPLETE`.
- **Iteration cap:** none — loops until all 3 explorers confirm (v3.8.0 unbounded solving).
- **References:** [`skills/intake-and-mapping/SKILL.md`](skills/intake-and-mapping/SKILL.md), [`agents/integration-explorer.md`](agents/integration-explorer.md), [`agents/master-synthesizer.md`](agents/master-synthesizer.md).

### ▌ Loop 3 — Planning validation (Phase 1, hard gate)

- **Wrapper:** Orchestrator-internal. 100% coverage required; no iteration cap — Phase 2 cannot start until exit.
- **Mechanism per iteration:** `openspec validate --all --strict --json` + `openspec status --json` + refresh `coverage-map.json`, then evaluate the 12-condition exit checklist.
- **Exit criteria — every one must hold:**
  1. `openspec validate` returns `valid: true` with no errors.
  2. Every artifact (`proposal`, `specs`, `design`, `tasks`) has `status: done`.
  3. Every source requirement has ≥ 1 scenario.
  4. Every requirement's acceptance criteria are measurable.
  5. Every front-end requirement has an explicit Playwright user-flow spec.
  6. Every back-end requirement has explicit dev-API integration test criteria.
  7. **Every `both`-layer requirement has an explicit front-to-back integration criterion** (real-backend testing) — or a recorded `mock_testing_authorized` opt-out.
  8. Every new module / file / dependency in `design.md` has a Reuse Decision citing CODEBASE_MAP.md.
  9. Every Reuse Decision cites a file/symbol that **actually exists** in CODEBASE_MAP.md.
  10. No duplicate capabilities (cross-checked via CODEBASE_MAP / INTEGRATION_MAP).
  11. Every new third-party dep has a documented comparison against the existing stack.
  12. `tasks.md` creates a new file only where existing files cannot be extended.
- **References:** [`skills/architect-team-pipeline/SKILL.md`](skills/architect-team-pipeline/SKILL.md), [`skills/coverage-mapping/SKILL.md`](skills/coverage-mapping/SKILL.md), [`skills/reuse-first-design/SKILL.md`](skills/reuse-first-design/SKILL.md).

### ▌ Loop 3b — Solution-Requirement intake (continuous; runs after every subagent idle)

- **Mechanism:** orchestrator walks `<cwd>/.architect-team/solution-requirements/*.json`. For each `open` SR: validates schema; auto-mines it to MemPalace; updates the coverage-map. **Test-failure-origin SRs** (`rca-product-bug`, `playwright-failure`, `integration-test-failure`, `integration-testing-failure`, `test-completeness-failure`, `visual-fidelity-drift`) route through `diagnostic-research-team` (Logic Map B) **before** the fix team spawns. `editability-gap` SRs spawn a fix team directly. The fix team's brief carries `acceptance_criteria` verbatim + (for test-failure SRs) the consolidated diagnostic plan.
- **Exit criteria** (per SR): originating failing test passes; acceptance criteria reflected in passing tests; SR → `resolved`; originating teammate unblocks.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md) §`Solution Requirements`, [`skills/diagnostic-research-team/SKILL.md`](skills/diagnostic-research-team/SKILL.md).

### ▌ Loop 4 — Per-task review gate (Phase 3, hook-enforced)

- **Enforcement layer:** `PostToolUse(TaskUpdate)` → [`hooks/review-gate-task.py`](hooks/review-gate-task.py) + `SubagentStop` → [`hooks/teammate-idle-check.py`](hooks/teammate-idle-check.py). See Logic Map A.
- **Mechanism:** teammate writes its self-review into `<cwd>/.architect-team/reviews/<task-id>.json` (evidence schema v7) BEFORE any `TaskUpdate(status=completed)`; an independent `task-reviewer` agent then reads the diff and writes the `independent_review` block. Exit 0 = allow, exit 2 = block.
- **Acceptance criteria — 17 self-review fields + the `independent_review` block:**

  | Field | Required value |
  |---|---|
  | `task_id` | non-empty, `_safe_id()`-validated |
  | `spec_review` | `"pass"` |
  | `quality_review` | `"pass"` |
  | `real_not_stubbed` | `true` |
  | `tests` | `{ added: int ≥ 1, passing: int == added }` |
  | `demo_artifact` | non-empty string |
  | `files_changed` | non-empty array |
  | `reuse_compliance` | `"ok"` |
  | `visual_fidelity_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `test_completeness_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `integration_testing_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks |
  | `ui_interaction_review` | `"pass"` / `"n/a"` (+ non-empty `_note`) — `"fail"` blocks (added in v0.9.19; every interactive element genuinely user-flow-tested, every page live, every value correctly static/dynamic, or a confirmed stub) |
  | `oracle_match_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `baseline_clean_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `no_fake_data_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `adversarial_review` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO) — `"fail"` blocks |
  | `skill_invocation_audit` | `"pass"` / `"n/a"` / `"fail"` OR `{verdict, verdict_path}` (v2.0.0 VAO, Layer 6) — `"fail"` blocks |
  | `independent_review` | object — `reviewer` (≠ `teammate`), `verdict` = `"pass"`, `spec_review` / `quality_review` = `"pass"`, `real_not_stubbed` = `true`, `reuse_compliance` = `"ok"`, `reviewed_at` non-empty. Written by the `task-reviewer` agent — the gate cannot open on the teammate's self-review alone. |

  Plus 3 OPTIONAL VAO fields (`interactions_honored_review`, `live_verification_review`, `appearance_scope_review`) — present only when applicable (a non-empty oracle `interactions[]`, a "verified live" claim, or a diff touching frontend presentation surface, respectively).

- **Escalation policy:** after 3 consecutive hook rejections on the same `task_id` → teammate stops retrying and writes a `<teammate>-to-orchestrator-stuck-<task_id>` handoff.
- **References:** [`skills/team-spawning-and-review-gates/SKILL.md`](skills/team-spawning-and-review-gates/SKILL.md), [`hooks/review-gate-task.py`](hooks/review-gate-task.py).

### ▌ Loop 4b — Per-test-failure root-cause analysis (Phase 3 & 5)

- **Trigger:** any Playwright or live dev-API test failure. Mandatory; no retry / patch / rationalize.
- **Pre-condition:** `<test-output-dir>/expectations/<test-id>.json` written BEFORE the test runs.
- **3-pass loop:** (1) forward data-flow trace; (2) backward call-flow trace; (3) alternative-hypotheses sweep — including the **multiple-simultaneous-causes** category (a symptom can have several independent root causes; finding one does not mean you found them all).
- **RCA artifact:** `<test-output-dir>/rca/<test-id>-<ts>.json`. `product-bug` → SR + handoff; **others** → fix in-loop.
- **Expensive verify loops:** when verifying a fix needs a deploy / rebuild / slow CI run, apply [`skills/expensive-verification-debugging/SKILL.md`](skills/expensive-verification-debugging/SKILL.md) — audit the whole failure pathway statically, batch every fix, spend the expensive cycle once; STOP and escalate after 2 cycles.
- **References:** [`skills/root-cause-test-failures/SKILL.md`](skills/root-cause-test-failures/SKILL.md).

### ▌ Loop 4c — Visual-fidelity reconciliation (Phase 3 when frontend touched + Phase 5 regression)

- **Trigger:** any frontend file change + DESIGN_MAP.md exists, OR `/architect-team:visual-qa` on-demand audit.
- **Phase 0 — the live app is a hard precondition:** the real running app (real backend) must be started and serving before any analysis. No live app → escalate `blocked`; never substitute static analysis.
- **Phase A.0 — design-baseline check:** if the design Oracle itself moved (a `design_baseline` change — a redesign / Full→V2 migration), every screen is in scope and an unmigrated implementation is drifted *by definition*.
- **Phase B code-first + Phase C live-app render:** resolve every styling layer to its concrete value; render the live app at every viewport; induce every state; capture computed styles + bounding box + per-state + per-viewport screenshots. A verdict with no live screenshot did not happen.
- **Tolerance defaults:** 0px / exact color / exact font / exact spacing / exact shadow. **Phase E remediation — fix to spec by default;** escalation reserved for 4 narrow cases, each writing an SR.
- **Independently verified** by the visual-verification-team — see Loop 4f.
- **References:** [`skills/visual-fidelity-reconciliation/SKILL.md`](skills/visual-fidelity-reconciliation/SKILL.md), [`skills/design-fidelity-mapping/SKILL.md`](skills/design-fidelity-mapping/SKILL.md).

### ▌ Loop 4d — Test-completeness verification (Phase 3 + Phase 5)

- **Trigger:** end of Phase 3 / Phase 5; on-demand when the orchestrator suspects a coverage gap.
- **Mechanism:** `test-completeness-verifier` confirms unit + integration + Playwright tests all ran for the applicable layers; grep-audits Playwright source for forbidden `page.evaluate(() => fetch(...))` / `page.request.*` / `axios.*` direct-API patterns; flags a "user-flow test" that navigates and asserts with no genuine user-interaction call (a vacuous flow); cross-checks the evidence-listed Playwright tests against the interactivity inventory so an uncovered element is flagged; runs the backend-integration audit (real backend vs mock-backed); confirms each acceptance criterion is covered.
- **Verdict JSON:** per-kind `status` + `backend_integration_audit` + `integration_testing_review` + the vacuous-flow + uncovered-element findings.
- **On `overall: fail`:** writes an SR (`test-completeness-failure` or `integration-testing-failure`); orchestrator re-spawns the originating team.
- **References:** [`agents/test-completeness-verifier.md`](agents/test-completeness-verifier.md).

### ▌ Loop 4e — Editability completeness (Phase 5 + on-demand)

- **Trigger:** any feature with a create or edit flow, at Phase 5; or `/architect-team:editability-audit`.
- **Mechanism:** three `editability-reviewer` agents (fable) spawn in parallel. Each independently enumerates every attribute of every entity (union of DB schema + API schemas + design + components), classifies each (`user-editable` / `user-settable-at-create-only` / `system-managed` / `derived` / `dynamic-via-action` / `ambiguous`), and traces every user-controllable attribute end-to-end through 7 stages: create control → edit control → state → request → request schema → handler → database → read-back.
- **Convergence:** the three argue round-robin (evidence-cited) until they hold one identical canonical list of must-be-editable attributes + gaps. Ambiguous attributes escalate to the human.
- **Gaps → SRs:** every gap (`missing-control`, `dead-control`, `orphan-field`, `no-readback`, `schema-mismatch`) becomes an `editability-gap` SR — spawns a fix team directly.
- **Multi-pass:** after the fixes land, the three re-spawn and re-review; the loop runs until all three agree zero gaps remain — no fixed cycle cap (per `## Unbounded solving discipline`); it pauses only for a required owner input that cannot be auto-supplied.
- **References:** [`skills/editability-completeness/SKILL.md`](skills/editability-completeness/SKILL.md), [`agents/editability-reviewer.md`](agents/editability-reviewer.md).

### ▌ Loop 4f — Visual verification team (Phase 5 + on-demand)

- **Trigger:** after the Phase 5 visual-fidelity reconciliation sweep, OR `/architect-team:visual-qa`. Independently verifies that the reconciliation actually rendered the live app — a self-report does not gate the run.
- **Mechanism — three roles:** `visual-capture` agents (×N, by screen-group) start the LIVE app and capture screenshots + computed-style DATA for every DESIGN_MAP screen (countable artifacts); `visual-analyzer` agents run the objective structural analysis — a deterministic data diff vs the spec + a pixel diff vs the design reference image + a code cross-check; the `system-architect` (Visual Gap Synthesis mode) synthesizes the per-screen gap lists holistically, clustering them into root causes.
- **The verdict is DATA, not eyeballed images.** `38px ≠ 26px` is arithmetic; screenshots are the secondary pixel-diff + gross-break channel.
- **Anti-cheat — the artifact boundary:** capture sets are countable (`screens_captured == screens_analyzed == design_map_screen_count` for a `pass`); analysis cannot precede capture; the verdict is reproducible data; synthesis is independent of both.
- **Exit criteria:** the team's consolidated verdict — not the reconciliation self-report — is `overall: pass`. Each gap cluster → an SR; `blocked` (live app won't run) / `incomplete` escalates. The `Stop` hook blocks a run whose reconciliation was never verified by the team.
- **References:** [`skills/visual-verification-team/SKILL.md`](skills/visual-verification-team/SKILL.md), [`agents/visual-capture.md`](agents/visual-capture.md), [`agents/visual-analyzer.md`](agents/visual-analyzer.md).

### ▌ Loop 4g — Interaction completeness (Phase 3 + Phase 5)

- **Trigger:** any slice with UI/UX interactive surface, at the Phase 3 review gate and the Phase 5 cross-layer pass. The independent VERIFICATION gate that the `playwright-user-flows` authoring discipline was followed — the sibling of Loop 4e (editability), at the granularity of controls and pages instead of attributes.
- **Mechanism:** three `interaction-reviewer` agents (fable, analysis-only) spawn in parallel. Each independently re-enumerates every interactive element (the union of the design / `DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code) AND every page / screen / route; classifies each element `endpoint-backed` / `client-only` / `confirmed-stub` / `ambiguous` and each page `live` / `placeholder` / `confirmed-stub`; verifies every non-stub element has a genuine user-driven Playwright test (real `page.click` / `page.fill` — not a `page.request.*` direct call, not a vacuous navigate-and-assert); traces each element to its endpoint or client behavior; and applies `dynamic-value-discovery` to flag a hardcoded value the context shows should be dynamic.
- **Convergence:** the three argue round-robin (evidence-cited) to one identical converged interaction map; a `system-architect` Round-3 robustness review checks for a shared blind spot; bounded multi-pass until all three agree the interactive surface is genuine.
- **Confirmed-stub mechanism:** an intentionally-inert control or a placeholder page is `confirmed-stub` ONLY with explicit user confirmation — the reviewer escalates a structured question, never guesses. A confirmed stub is recorded in the converged map and in `coverage-map.json` `confirmed_stubs[]`; it needs no user-flow test but is tracked.
- **Gaps → SRs:** every gap (`unwired-control`, `placeholder-page`, `hardcoded-dynamic-value`) becomes an SR — spawns a fix team directly; surfaces through the `ui_interaction_review` evidence field.
- **References:** [`skills/interaction-completeness/SKILL.md`](skills/interaction-completeness/SKILL.md), [`agents/interaction-reviewer.md`](agents/interaction-reviewer.md), [`skills/dynamic-value-discovery/SKILL.md`](skills/dynamic-value-discovery/SKILL.md).

### ▌ Loop 5 — Cross-layer integration (Phase 5)

- **Wrapper:** Orchestrator-internal. Begins after both layer-teams pass Loop 4 + Phase 4 merges cleanly.
- **Mechanism:** integration agent runs the full suite locally then against the **live dev API with real dev data** (never mocks). For frontend: Playwright user-flow tests against the **real running dev environment** — and for `both`-layer features the run exercises the **real backend** (no `page.route` happy-path stubs, no MSW, no fake API server). Visual-fidelity regression sweep (Loop 4c), its independent verification by the visual-verification-team (Loop 4f), the editability-completeness review (Loop 4e), and the interaction-completeness review (Loop 4g) all run here.
- **Exit criteria:** every Phase 1 acceptance criterion passes; every documented error response exercised; every interactive element covered by a genuine user-flow test and every page verified live (the interaction-completeness team agrees the interactive surface is genuine); the editability team reaches `satisfied`.
- **On failure:** SR auto-spawn → Logic Map B.
- **References:** [`skills/dev-api-integration-testing/SKILL.md`](skills/dev-api-integration-testing/SKILL.md), [`skills/playwright-user-flows/SKILL.md`](skills/playwright-user-flows/SKILL.md), [`agents/integration.md`](agents/integration.md).

### ▌ Loop 6 — Outer task-group loop (Phase 6)

- **Mechanism:** repeat Phase 2 → Phase 5 for each parallel task group, respecting the dependency graph. Maintain a running ledger.
- **Exit criteria:** every task group complete + ledger fully populated.

### ▌ Loop 7 — Master review meta-loop (Phase 7)

- **Mechanism per iteration:** walk every commit; attribute to ≥ 1 requirement via the coverage map; re-run `openspec validate`; walk every coverage-map entry. Then dispatch the `system-architect` in **Master Review Audit mode** — an independent re-verification of every entry + every SR (the orchestrator's own walk is a producer-is-own-checker step; the audit is the independent checker).
- **Exit criteria — every entry must have:** ≥ 1 commit SHA; passing unit/integration tests; passing Playwright flow(s) where applicable; non-empty `demo_artifact`; the editability team `satisfied` for entity-bearing features. Plus `openspec validate` reports `valid: true`, AND the independent master-review audit verdict is `overall: pass` (it gates the Phase 8 commit; the `Stop` hook checks it). Per v3.9.2, once a master-review verdict exists the `Stop` hook ALSO independently re-runs `openspec validate --all --strict` — an openspec change that fails this gate BLOCKS the commit.
- **On any gap:** re-spawn the appropriate team(s); meta-loop continues until the coverage map is fully green.
- **Terminal action:** `openspec archive <change-name>`. Phase 8 then runs the **documentation-currency gate** — every doc the change touched (the maps, `README.md`, `CHANGELOG.md`, `CLAUDE.md`) is updated and then independently audited by the `system-architect` (Documentation Currency Audit mode) — emits the final report (persisted + mined to MemPalace), and auto-commits + pushes.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  ON-DEMAND COMMANDS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

### `/architect-team <path>`

Run the full Phase −1 → 8 pipeline against a requirements folder. See "Usage" above.

### `/architect-team:architect-team-setup [--check-only] [--no-prompt] [--yes] [--force-reinstall] [--codex|--no-codex] [--external-llm|--no-external-llm] [--secondary <openai|zai>]`

Cross-platform installer for prerequisites: openspec CLI, pytest+httpx, Playwright + chromium. Idempotent. Also **HARD-checks (exit 1)** that the required plugins (superpowers, cartographer, ralph-loop) are installed and verifies the vendored `openspec-propose` skill resolves via `ensure_openspec_propose_skill()`. Manages the v3.35.0 role split (`--codex`/`--no-codex`) and the v3.36.0 external-LLM gateway (`--external-llm`/`--no-external-llm`) — both never-gates. **v3.40.0 — choose the secondary API:** `--secondary <openai|zai>` (or `CT6_SECONDARY_PROVIDER`) selects which provider backs the split's provider-neutral `ct6-secondary` alias — OpenAI Codex (`gpt-5.6-sol`) or Z.ai GLM 5.2 (`glm-5.2`, keyed by `ZAI_API_KEY` with full v3.38.0 decline parity via `--zai-key`); the choice is asked once (the wrapper's "Choose the secondary API" gate / the installer's TTY prompt), remembered in `gateway.json`, grandfathered as openai for a pre-v3.40 install, and re-opened only by `--re-ask-provider`. **v3.38.0 — ask for missing keys, never punt:** on an absent-key state from the external-LLM path (`ANTHROPIC_API_KEY` absent in subscription mode / the chosen secondary provider's key — `OPENAI_API_KEY` or `ZAI_API_KEY` — absent in provisioned-but-NOT-enabled), the wrapper ASKS for the key in-session (capture-and-apply, with a prior `--yes` carrying over as `--activate` consent) or records an explicit decline via the installer's `decline` subcommand — never the bare script remediation as the only path; an interactive terminal run of the installer prompts itself (hidden entry, blank-to-skip).

### `/architect-team:visual-qa [<codebase-path>]`

On-demand pixel-perfect audit against `DESIGN_MAP.md`. Refreshes the design map if stale, runs code-first + Playwright reconciliation with zero-tolerance defaults, fixes drift to spec. Emits structured `PASS` / `DRIFT_DETECTED` / `GAPS_DETECTED`.

### `/architect-team:mempalace-install [--check-only] [--workspace <path>]`

One-time installer for the MemPalace CLI + MCP server. uv-first, pip fallback. Prints (does not auto-run) the `claude mcp add` + per-workspace `mempalace init` commands.

### `/architect-team:librarian-install [install|status|add-topic|list-topics|remove-topic|run-once|uninstall|decline] [--enable] [--check-only] [--json] [--purge] [--re-ask-keys]`

Full-lifecycle installer (v3.29.0) for the CT6-6 **Librarian** background topic-research daemon, mirroring `mempalace-install`. Stdlib-only installer + CLI (`scripts/setup/install_librarian.py`); provisions state under `~/.architect-team/librarian/` and generates the per-OS boot descriptor (launchd / systemd / Task Scheduler) — printing the register hint, never auto-loading. With `ANTHROPIC_API_KEY` resolvable it wires the real Anthropic LLM adapter; with no key it provisions in an honest **disabled** state — and (v3.38.0) asks for the key instead of only punting: the wrapper captures it in-session (or records an explicit decline via the `decline` subcommand; `key-declines.json` auto-resets when a key resolves, `install --re-ask-keys` re-asks), and a direct TTY run prompts with hidden getpass entry. Once installed and enabled it runs as a background daemon on the local machine (the daemon entry point + the stdlib `UrlSource` fetcher live in `services/librarian/daemon.py`) — installable + self-managed, NOT a deployed/production service.

### `/architect-team:memory <search|mine|status|wake-up|sweep> [args]`

Ad-hoc interaction with the per-workspace MemPalace store at `<workspace>/.mempalace/palace` — semantic search, manual mining, status, wake-up context, transcript sweep.

### `/architect-team:editability-audit [<codebase-path>] [--feature <name>]`

On-demand editability-completeness audit. Spawns the three-reviewer team (Loop 4e), reports the converged editable-surface map + gaps + escalations, and writes the `editability-gap` SRs.

### `/architect-team:mini <requirements-folder | free-text prompt>`

Faster sibling pipeline (`mini-architect-team-pipeline` skill — phases **M0 → M8**) for ≤5-AC changes against a familiar codebase. Single architect drafts proposal + spec + tasks + coverage in one pass (M2) and self-confirms against the prompt (M3, cap 3); frontend + backend work parallel non-overlapping slices and cross-review each other's evidence (M4); the `mini-qa` agent runs unit + integration + ≤ 3 Playwright user-flows against the live dev environment (M5); a `green` verdict (M6) auto-merges to `main` with a structured **`Mini-Run: <slug>`** commit trailer (M7); the architect re-evaluates against the merged state (M8, cap 3) and escalates if gaps remain. Use when the change is small and the maps are fresh — falls back to the full `/architect-team` flow for larger scope. Accepts the same two input forms as `/architect-team` — folder OR plain-language prose.

### `/architect-team:mini-review-sweep [--since <ref>] [--limit <N>]`

On-demand replay of the heavyweight gates against a batch of recent mini-runs — finds commits with the **`Mini-Run: <slug>`** trailer since `<ref>` (default: last release tag) up to `<N>` (default: 10), and runs the visual-fidelity reconciliation, editability completeness, master-review audit, and doc-currency audit against the merged set. Use when you have shipped several mini changes and want the deeper gates applied as a batch.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DOCUMENT CONVENTIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

| Path | Purpose | Frontmatter |
|---|---|---|
| `<codebase>/docs/CODEBASE_MAP.md` | Cartographer's output | `last_mapped` |
| `<codebase>/docs/ROUTE_MAP.md` | Route-mapper's output for frontends | `last_routed` |
| `<codebase>/docs/DESIGN_MAP.md` | Design-fidelity output (conditional) — tokens, asset registry, per-screen specs, link inference | `last_designed` |
| `<workspace>/docs/INTEGRATION_MAP.md` | Master-synthesizer's cross-codebase synthesis | `last_synthesized` |
| `<workspace>/.architect-team/intake-state.json` | Re-entry short-circuit state | — |
| `<workspace>/.architect-team/reviews/<task-id>.json` | Per-task review-gate evidence (v7 schema — 17 self-review fields + the independent `task-reviewer` verdict) | — |
| `<workspace>/.architect-team/teammates/<name>.json` | Teammate manifests | — |
| `<workspace>/.architect-team/handoffs/<from>-to-<to>-<ts>.md` | Inter-agent coordination | — |
| `<workspace>/.architect-team/solution-requirements/SR-<id>-<ts>.json` | Auto-spawn fix-team requirements | — |
| `<workspace>/.architect-team/diagnostic-research/<test-id>/` | Researcher drafts + consolidated diagnostic plan | — |
| `<workspace>/.architect-team/editability/<feature>/converged-map-*.json` | Converged editable-surface maps | — |
| `<workspace>/.architect-team/failure-pathway/<symptom>-<ts>.json` | Pathway-audit artifacts (expensive-verification debugging) | — |
| `<workspace>/.architect-team/test-completeness/<task-id>-<ts>.json` | Test-completeness verdicts | — |
| `<workspace>/.architect-team/master-review/audit-<ts>.json` | Phase 7 independent master-review audit verdict (system-architect Master Review Audit mode) | — |
| `<workspace>/.architect-team/visual-fidelity/` | visual-verification-team artifacts — `capture/` (screenshots + computed-style data), `analysis/` (per-screen gap lists), `verification-verdict-*.json` (consolidated verdict) | — |
| `<workspace>/.architect-team/escalation-pending.md` | Escalation marker — present while the run is paused for a human (the Stop hook stands down) | — |
| `<workspace>/.architect-team/runs/<change>-<ts>.md` | Phase 8 final reports | — |
| `<workspace>/.mempalace/palace` | MemPalace local-first searchable memory store | — |
| `<test-output-dir>/expectations/<test-id>.json` | Per-test predictions (RCA pre-condition) | — |
| `<test-output-dir>/rca/<test-id>-<ts>.json` | 3-pass RCA artifact for failed tests | — |
| `openspec/changes/<change>/coverage-map.json` | Coverage map (Phase 1 → 8 spine) | — |

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  PROJECT EMAIL NOTIFICATIONS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

A pipeline run is long and mostly unattended. The **project email-notification
system** (v0.9.18; overhauled in v3.34.0) keeps a configured list of
stakeholders informed as a run progresses — opt-in, per-project, strictly
best-effort, and (since v3.34.0) **informative, not just status-updating**.

### ▸ How it works

The feature is **entirely opt-in**: a project enables it by committing a
`.architect-team-notify.json` file at its repository root. If that file is
absent the notifier is a **silent no-op** and the pipeline behaves exactly as
before. When the file is present, every pipeline — `/architect-team`,
`/architect-team:bug-fix`, `/architect-team:mini`, AND `/architect-team:ux-test`
(newly wired in v3.34.0) — invokes the notifier CLI
(`scripts/notify/notify.py`) at its canonical event points; each invocation is
**best-effort** — the notifier always exits 0, and a notification failure never
blocks, fails, or alters a run.

### ▸ Informative, not just status (v3.34.0)

Every email carries meaningful content — the goal is that a stakeholder
reading only the emails can follow the run:

- **What is about to start** — every `phase_start` includes `--details` (what
  the phase will do *for this run*), plus `--progress` (where the run stands,
  e.g. *"4 of 12 phases complete"*) and `--next-step`.
- **What was completed** — every `phase_complete` describes what the phase
  actually accomplished (artifacts, verdicts, counts).
- **The kickoff email carries the plan itself** — `run_start` fires once, the
  moment the architecture + solution plan exists, and **embeds the plan
  artifacts** (proposal / design / tasks) in that ONE email via repeatable
  `--plan-file` (per-file size cap; missing files degrade to a note).
- **You know when it's waiting — and when the wait ends** —
  `waiting_on_agents` fires at every agent dispatch (naming each agent and its
  mission), `agents_complete` when the dispatch fully returns (with outcomes).
- **You know when it finishes** — `run_complete` is the run's final email:
  what shipped, the final commit, elapsed time.

### ▸ The ten event types

| Event | Emitted when | Context in the email |
|---|---|---|
| `run_start` | once, when the architecture + solution plan first exists (Phase 1 / B3 / M3 / U4) | the requirement summary + **the embedded plan artifacts** |
| `phase_start` | at the start of each pipeline phase | the phase name + what it will do + run progress |
| `phase_complete` | at the end of each pipeline phase | the phase name + what it accomplished + run progress |
| `waiting_on_agents` | when agents are dispatched and the run enters a wait | the agent roster with per-agent missions |
| `agents_complete` | when every agent in that dispatch has returned | the roster with per-agent outcomes |
| `issue_discovered` | a new solution requirement is picked up (Phase 3b / B6 / M8 / U8) | the issue summary |
| `git_commit` | immediately after a pipeline-produced git commit | the commit SHA + what it ships |
| `deploy` | when a live dev instance is brought up | the deploy layer |
| `run_complete` | once, as the run's final notification | what shipped + final commit + elapsed |
| `heartbeat` | tick-driven during long phases (v3.10.0 liveness signal) | run id, phase, elapsed, QA cycles, agents dispatched |

Each recipient subscribes to whichever events they want — or to the `"all"`
shorthand for every event.

### ▸ The `.architect-team-notify.json` schema

A committed JSON file at the **target project's** repository root. Copy
[`.architect-team-notify.example.json`](.architect-team-notify.example.json)
and edit it:

```jsonc
{
  "provider": "gmail",                       // "gmail" or "sendgrid"
  "from_address": "ci-bot@your-domain.example",
  "from_name": "Architect Team CI",          // optional display name

  "gmail": {                                  // settings for the gmail provider
    "username": "ci-bot@your-domain.example", // SMTP login (defaults to from_address)
    "app_password_env": "ARCHITECT_GMAIL_APP_PASSWORD"   // env-var NAME, not the secret
  },
  "sendgrid": {                               // settings for the sendgrid provider
    "api_key_env": "ARCHITECT_SENDGRID_API_KEY"          // env-var NAME, not the secret
  },

  "recipients": [
    { "email": "tech-lead@your-domain.example", "events": ["all"] },
    { "email": "qa@your-domain.example",
      "events": ["run_start", "phase_complete", "issue_discovered", "deploy", "run_complete"] }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `provider` | yes | `"gmail"` or `"sendgrid"` — selects the send transport |
| `from_address` | yes | the sender email address |
| `from_name` | no | optional sender display name |
| `gmail.username` | no | SMTP login; defaults to `from_address` |
| `gmail.app_password_env` | for gmail | **name** of the env var holding the Gmail app password |
| `sendgrid.api_key_env` | for sendgrid | **name** of the env var holding the SendGrid API key |
| `recipients[]` | yes (non-empty) | one entry per recipient |
| `recipients[].email` | yes | the recipient address |
| `recipients[].events[]` | yes (non-empty) | the event types this recipient receives, or `["all"]` |

The config file is `.json` (parsed with the standard-library `json` module) and
holds **only** the *name* of an environment variable for each provider secret —
never the secret value itself.

### ▸ Secret handling — environment variables only

Provider secrets are **never committed and never logged**. The config names an
environment variable (`gmail.app_password_env` / `sendgrid.api_key_env`); the
notifier reads `os.environ[<that name>]` at send time. If the variable is unset,
the send is skipped with a one-line stderr warning that names the variable but
never echoes a secret — and the process still exits 0. The recipient email
addresses themselves do live in the committed config (the project's explicit
choice — ordinary practice, as with `CODEOWNERS`).

### ▸ Provider setup

**Gmail** — transmits via `smtp.gmail.com:587` over STARTTLS (standard-library
`smtplib`). Gmail requires an **app password**, not your account password:
enable 2-Step Verification on the sending Google account, then create an app
password at <https://myaccount.google.com/apppasswords>. Export it under the
name your config gives in `gmail.app_password_env`:

```bash
export ARCHITECT_GMAIL_APP_PASSWORD="<the 16-character app password>"
```

**SendGrid** — POSTs to the SendGrid v3 mail-send API
(`https://api.sendgrid.com/v3/mail/send`) with the API key as a Bearer header
(standard-library `urllib.request`). Create an API key in the SendGrid console
(Settings → API Keys, Mail Send permission) and export it under the name your
config gives in `sendgrid.api_key_env`:

```bash
export ARCHITECT_SENDGRID_API_KEY="<the SendGrid API key>"
```

The notifier uses **only the Python standard library** for both providers —
zero new third-party dependencies.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  UI INTERACTION FIDELITY  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The pipeline kept shipping frontend work that was not what it claimed to be —
and the verification did not catch it. v0.9.19 makes the genuineness of a
shipped UI a **structural, hook-enforced gate** rather than trust-based
Markdown. Three failure modes, one enforcement layer.

### ▸ The three failure modes it closes

| Failure mode | What shipped | How v0.9.19 catches it |
|---|---|---|
| **Fake user-flow test** | A Playwright "user-flow" test passes without driving the UI — a direct `page.request.post('/api/...')` call, or a navigate-and-assert with zero `page.click`. `integration_testing_review` gates real-backend-vs-mock, a different axis; a grep finds *present* bad patterns, not an *absent* genuine interaction. | The interaction-completeness team audits every Playwright test for genuine user-driven interaction; the strengthened `test-completeness-verifier` flags a vacuous flow mechanically. |
| **Placeholder page** | A route is wired to a `ComingSoon` / skeleton / mock page where the design specifies a real live page — and a Playwright test clicks happily through it. | Every page / screen / route is enumerated and classified `live` / `placeholder` / `confirmed-stub`, cross-checked against the design / requirements / `ROUTE_MAP.md`. |
| **Hardcoded dynamic value** | The design mockup's sample data — `"John Smith"`, `"$1,234.00"`, `"Welcome back, Sarah"` — is copied literally into the code, so one person's sample data ships to everyone. | `dynamic-value-discovery` classifies every displayed value `static` vs. `dynamic` FROM CONTEXT; a hardcoded value the context shows should be bound is a `hardcoded-dynamic-value` gap. |

### ▸ The `interaction-completeness` verification gate

A new judgment-heavy verification discipline — the `interaction-completeness`
skill — modeled on the proven `editability-completeness` pattern. For any slice
with UI/UX surface it runs at the **Phase 3** review gate and the **Phase 5**
cross-layer pass: three `interaction-reviewer` agents (fable, analysis-only)
spawn **in parallel** and each independently re-enumerates **every interactive
element** (buttons, links, inputs, selects, toggles, menus, drag handles,
file-uploads) AND **every page / screen / route** — the union of the design /
`DESIGN_MAP`, the `ROUTE_MAP.md`, the route table, and the component code.
Each reviewer classifies how each element is wired, classifies each page, and
audits whether each non-stub element has a genuine user-driven Playwright test.
The three then **argue round-robin to a converged interaction map**; the
`system-architect` performs a Round-3 robustness review; a bounded multi-pass
outer loop re-reviews after fixes land — the exact relationship
`editability-completeness` has to `playwright-user-flows`, applied to controls
and pages instead of attributes.

### ▸ The classification rubrics

Each **interactive element** is classified — from THIS feature's requirements
and design, never from a name alone:

- `endpoint-backed` — drives an API call (control → handler → HTTP client → endpoint).
- `client-only` — pure client behavior (navigation / state change / overlay).
- `confirmed-stub` — intentionally inert, **user-confirmed** (see below).
- `ambiguous` — the requirements do not determine it → **escalate to the human**.

Each **page / screen / route** is classified `live`, `placeholder`, or
`confirmed-stub`. The skill carries a **placeholder-signal rubric** — component
/ file naming (`Placeholder`, `ComingSoon`, `Stub`, `Mock`, `Demo`, `WIP`),
"coming soon" / "under construction" / lorem-ipsum content, a data-driven page
that makes no API calls, a near-empty route shell, a route-table entry pointing
at a placeholder while the real component is specified-but-unwired.

### ▸ The confirmed-stub mechanism

An interactive element OR a page that is **intentionally inert** is classified
`confirmed-stub` **ONLY with explicit user confirmation**. A reviewer that finds
an inert control or a placeholder page does **not guess** — it escalates a
structured question to the human via the orchestrator. Once confirmed, the stub
is recorded durably in the converged interaction map AND in the change's
`coverage-map.json` `confirmed_stubs[]` list; it does not require a user-flow
test (testing an intentionally-inert control is meaningless) but it **is
tracked**, never silently ignored. An **unconfirmed** inert control is an
`unwired-control` gap; an **unconfirmed** placeholder page is a
`placeholder-page` gap — each routed as a solution requirement.

### ▸ The `ui_interaction_review` review-gate field (added at evidence schema v6; current schema is v7)

The shared review-gate evidence schema was bumped **v5 → v6** (in v0.9.19) to add a new
hook-enforced field — `ui_interaction_review`, taking `pass` / `n/a` / `fail`. (The
schema has since advanced to **v7**, which added the 5 Verified Agent Output fields;
`ui_interaction_review` remains a required field throughout.):

- `pass` — every interactive element in the slice is genuinely UI-tested, every page is live, every displayed value is correctly static or dynamically bound, or a confirmed stub.
- `n/a` — the slice has no UI/frontend interactive surface; **requires** a non-empty `ui_interaction_review_note`.
- `fail` — **blocked by the hook**; an `unwired-control` / `placeholder-page` / `hardcoded-dynamic-value` gap must be escalated via a solution requirement, not marked complete.

It is a **separate** field from `integration_testing_review` because it gates a
genuinely orthogonal axis — a test can be real-backend + fake-interaction, or
mock-backend + real-interaction. The field is defined once in
`hooks/review_evidence_schema.py`; both evidence hooks import that module, so
the bump flows through with no per-hook drift — exactly as
`visual_fidelity_review` (v0.5.0), `test_completeness_review` (v0.9.0), and
`integration_testing_review` (v0.9.5) were each added.

### ▸ Dynamic-value discovery — a cross-role discipline

A hardcoded value that should be dynamic cannot be caught by a single gate — it
has to be *prevented* at planning, *avoided* at implementation, and *caught* at
review. So v0.9.19 adds the `dynamic-value-discovery` skill — a cross-role
discipline, modeled on `reuse-first-design`, wired into all three roles:

- **Architect** — `system-architect` and `design-fidelity-mapping` consult it: the `DESIGN_MAP`'s per-screen specs classify each value `static` / `dynamic` and name the data source for each dynamic value.
- **Developer** — `frontend` and `backend` consult it: bind every dynamic value to its data source; never hardcode design sample data.
- **Evaluator** — the `interaction-reviewer`, guided by it, flags a hardcoded value the context shows should be dynamic.

The core rule: **classify FROM CONTEXT, never from the literal** — the same
string is `dynamic` beside an avatar and `static` in a nav bar; the value alone
never decides. Person names, dates, currency amounts, counts, statuses, a value
in a record-detail view or a repeating list row, a greeting with a name are
`dynamic` signals; nav labels, button text, section headings, fixed helper
text, brand strings are `static` signals. Every value classified `dynamic` is
bound to a **named data source**; a genuinely ambiguous classification
escalates to the human.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  DEVELOPMENT  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```bash
# Run the plugin's self-tests
python -m pytest -v
```

Tests validate: plugin/marketplace JSON; all 48 skill frontmatters; all 39 agent frontmatters (tool + model names); all 23 commands; the v3.31.0 instruction-compliance lint (`tests/test_instruction_compliance.py` — the deterministic engine's enforced zero-findings gate across all 113 in-scope instruction files, plus the uniform 1024-char raw-description cap for agents + commands); hooks.json wiring for all six trigger events (PreToolUse + PostToolUse + SubagentStop + Stop + the v1.0.0 TaskCompleted + TeammateIdle); hook script logic (review-gate + teammate-idle share one `review_evidence_schema` module — evidence schema v7: 17 self-review fields + the independent `task-reviewer` verdict; the `pretool_unilateral_override_guard` PreToolUse hook; the `pipeline-completion-audit` Stop hook incl. the master-review audit check; path-traversal sanitization); cross-component consistency (the two evidence hooks cannot drift; the Stop hook's origin set matches the pipeline; no unregistered skills/agents/commands); the setup + MemPalace install scripts; the `scripts/notify/notify.py` notifier (config load/validate, Gmail + SendGrid message construction with mocked transport, event dispatch, secret resolution, CLI + failure isolation) and its pipeline wiring; the v1.0.0 teams-mode detection helper (`scripts/setup/teams_mode.py`) + the cross-session lock layer (`hooks/locks.py`); the v1.1.0 worktree-aware state-resolution helper (`scripts/setup/worktree_paths.py`) including the cross-worktree lock-coordination integration test (acquire from a real `git worktree add`-created worktree blocks an intersecting acquire from main with the default `locks_dir`); the v1.2.0+v1.3.0+v3.6.0 worktree-lifecycle helper (`scripts/setup/worktree_lifecycle.py`) including `create_run_worktree` (now at the v3.6.0 hidden per-project container layout `<parent>/.<repo>-worktrees/<slug>/`) + collision handling, `current_worktree_is_run` True / False detection, `current_run_slug` extraction, `cleanup_run_worktree` with + without branch removal, the v1.3.0 auto-cleanup helpers (`list_merged_architect_team_worktrees` with `exclude_current` safeguard; `cleanup_merged_worktrees` with `dry_run` preview; end-to-end cleanup-only-removes-merged), and the v3.6.0 `finalize_run_worktree` end-of-run merge check (remove-when-merged / warn-when-unmerged / no-op-on-non-run-branch) + dual-layout (old-flat + new-container) slug derivation & sweep, and the v3.7.0 auto-merge-to-main helpers (`list_run_branches` per-branch merged / cleanly-mergeable status excluding non-architect-team branches; `merge_branch_to_main_and_prune` clean-merge→push→delete-branch→remove-worktree with conflict-abort-changes-nothing and never-`--force` safety)) — all exercising real `git init` + `git worktree add` fixtures with no git mocks; and the no-arbitrary-timers, diagnostic-research, MemPalace-integration, integration-testing, expensive-verification, editability-completeness, readme-styling, design-baseline-migration, visual-verification-team, producer-checker-enforcement, mempalace-mine-syntax, documentation-currency, project-email-notifications, ui-interaction-fidelity, email-testing, proposal-refiner, ux-test-builder, bug-fix-pipeline, code-path-witness, mini-architect-team-pipeline, agent-teams-mode, and scope-discipline (v1.4.0 — `tests/test_scope_discipline.py` audits the canonical `## Scope discipline` section in `common-pipeline-conventions/SKILL.md`, the 6 parity-implying verbs documented in the section + the bug-classifier action-verb section, the 3 pipeline body references, the prompt-refiner 6th `scope-fidelity` axis + grade-schema, the proposal-refiner Phase R2 documentation of the axis + new weights, and the system-architect Master Review Audit + Phase 2 architect brief scope-narrowing checks) disciplines. **5689 tests pass (+ 4 skipped, across 202 test files).**

### Bumping versions

1. Update `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` version.
2. Add a `## [x.y.z] — YYYY-MM-DD` entry to `CHANGELOG.md`.
3. Commit with explicit author override:
   ```bash
   git -c user.name="Paul Ingram" -c user.email="paulingram@users.noreply.github.com" commit -m "..."
   ```
4. Refresh this README per [`skills/readme-styling/SKILL.md`](skills/readme-styling/SKILL.md) — banner version, badges, inventory counts, NEW IN, the timeline.

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  STATUS  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

```
   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰

           v0.1.0 ─ initial release
           v0.2.0 ─ orchestrator skill rename (command/skill collision)
           v0.2.3 ─ path-traversal hardening + escalation policy
           v0.2.4 ─ python3 portability
           v0.3.0 ─ root-cause-test-failures + playwright hardening
           v0.4.0 ─ design-fidelity-mapping + visual-fidelity tests
           v0.5.0 ─ visual-fidelity-reconciliation + /visual-qa command
           v0.6.0 ─ link inference for un-annotated UI
           v0.7.0 ─ solution-requirement auto-spawn
           v0.8.0 ─ auto-commit + push on clean pass
           v0.8.1 ─ frontend + backend implementers on opus
           v0.9.0 ─ test-completeness verification
           v0.9.1 ─ auto-compact prompt at end of pipeline
           v0.9.2 ─ forbid arbitrary wall-clock wakeups / timers
           v0.9.3 ─ diagnostic-research-team (3 researchers + architect)
           v0.9.4 ─ MemPalace integration — searchable pipeline memory
           v0.9.5 ─ real backend by default for full-stack tests
           v0.9.6 ─ expensive-verification-debugging
           v0.9.7 ─ editability-completeness review
           v0.9.8 ─ readme-styling skill + README refresh
           v0.9.9 ─ logic-implementation review — Tier 1/2/3 hole fixes
           v0.9.10 ─ design-baseline-migration awareness
           v0.9.11 ─ live-app visual verification (single verifier)
           v0.9.12 ─ visual verification team — capture / analyze / synthesize
           v0.9.13 ─ independent review — task-reviewer + master-review audit
           v0.9.14 ─ MemPalace `mine` syntax fix — drop the invalid `--room` flag
           v0.9.15 ─ documentation-currency gate
           v0.9.16 ─ readme-styling: centering + color + themes
           v0.9.17 ─ plain-language requirements are a first-class input
           v0.9.18 ─ project email notifications — Gmail / SendGrid, five events
           v0.9.19 ─ UI interaction fidelity — genuine controls, live pages, dynamic values
           v0.9.20 ─ gates are opt-in — orchestrator drives end-to-end without asking obvious questions
           v0.9.21 ─ interaction intuition at Phase −1 — every control mapped before code is written
           v0.9.22 ─ bug-fix pipeline — replicate, propose, fix, QA-replay against live dev
           v0.9.23 ─ automatic documentation currency via a dedicated doc-updater agent
           v0.9.24 ─ MemPalace wake-up runs at the earliest phase, before any subagent dispatch
           v0.9.25 ─ bug-fix-pipeline gets its own planning-validation gate at Phase B3
           v0.9.26 ─ system-architect agent gets bounded Write for its 7 audit verdicts
           v0.9.27 ─ bug-fix-pipeline gets full notification wiring
           v0.9.28 ─ cohesion-review close-out: confirmed-stubs cross-reference + polish
           v0.9.29 ─ UX test builder + bug-fix Phase B6b post-deploy sensibility check
           v0.9.30 ─ cross-platform Python hook invocation — Windows Store-shim fix
           v0.9.31 ─ Phase B6 code-path execution witness — qa-replayer catches tests that pass via wrong path
           v0.9.32 ─ wrong-code-path witness generalized across all 3 Playwright sites: B2 selector / Phase 5 feature / U6 flow-effect
           v0.9.33 ─ proposal-refiner — conversational pre-pipeline prompt refinement with codebase-grounded clarity grading
           v0.9.34 ─ email-testing — automatic Mailpit-based email flow verification across all QA agents
           v0.9.35 ─ email-testing audit — Mailpit search API, pre-test cleanup, container collision fix, redirect chain docs, language indicators, 38 new tests, doc-currency refresh
           v0.9.36 ─ bug-fix testing enforcement (verdict file mandates + completion-audit hook) + anti-deferral discipline (both pipelines)
           v0.10.0 ─ mini pipeline — rapid feature changes (≤5 ACs, familiar codebase) with single-architect drive + auto-merge to main on green QA
           v1.0.0  ─ Agent Teams as default dispatch mode — long-lived 1M-context teammates + shared task list; `.architect-team/locks/` cross-session lock layer; hook triggers split TaskCompleted/TeammateIdle; agent bodies framed as teammates; subagents-mode fallback via `--no-teams`
           v1.1.0  ─ worktree-aware state resolution — 3-layer model (filesystem isolation = worktrees / architectural coordination = locks resolved to main worktree / context sharing = MemPalace resolved to main worktree); shared vs per-run state split via `scripts/setup/worktree_paths.py`; cross-worktree lock coordination via `hooks/locks.py` shared default; backwards-compatible for single-session users
           v1.2.0  ─ auto-worktree lifecycle — every `/architect-team` family invocation creates a fresh worktree by default (`<parent-of-repo>/<repo-name>-<slug>/` on branch `architect-team/<slug>`); re-entry detection via `current_worktree_is_run()` skips nested creation; `--no-worktree` reverts to v1.1.0 single-tree behavior; collision handling appends `-2`, `-3`, ...; cleanup recommended at Phase 8 / B8 / M7 success (made automatic in v1.3.0)
           v1.3.0  ─ auto-cleanup of merged worktrees — every `/architect-team` family invocation sweeps merged `architect-team/*` worktrees first (best-effort, excludes current); mini Phase M7 cleans its own worktree after green merge; new `/architect-team:cleanup-worktrees [--dry-run] [--against <ref>]` for on-demand cleanup; merged-branch detection via `git merge-base --is-ancestor` (squash-merges not detected — false-negative is safer than false-positive auto-delete); 2 new helpers (`list_merged_architect_team_worktrees`, `cleanup_merged_worktrees`) in `scripts/setup/worktree_lifecycle.py`; 6 new tests; cleanup failures NEVER block the new run
           v1.4.0  ─ scope discipline — agents using this package must NOT silently narrow the user's prompt at intake; the v0.9.36 anti-deferral discipline forbade the MID-RUN version, v1.4.0 extends it to INTAKE; new `## Scope discipline` section in `common-pipeline-conventions/SKILL.md` (the canonical home) naming the anti-pattern, listing the 6 parity-implying verbs (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) each implying visual + structural + behavioral parity, classifying scope-narrowing as a DOMAIN gate, requiring `AskUserQuestion` surfacing BEFORE starting work; `prompt-refiner` gains a 6th `scope-fidelity` grading axis (weight 0.17); `bug-classifier` gains an action-verb interpretation section; `system-architect` Master Review Audit + Phase 2 architect brief gain scope-narrowing detection (verdict JSON gains `scope_fidelity_finding` block); 3 pipeline body anti-pattern entries; 35 new tests; backwards-compatible discipline change
           v1.5.0  ─ dispatch-mode observability — the user's direct question *"how do I know if a team is deployed via agent teams vs subagents, can we show an indicator"* exposed a real gap (v1.0.0 made the decision silent). New `format_dispatch_banner()` helper in `scripts/setup/teams_mode.py` renders a one-block banner naming **AGENT TEAMS** or **SUBAGENTS (fallback)** + (in the fallback case) the diagnosed `Reason:`. Each of the 3 pipeline-driving slash commands prints the banner as its FIRST user-visible action (before v1.3.0 auto-cleanup, before argument parsing). New `/architect-team:status` command (13th) reports dispatch mode + active worktrees + open SRs + last completed run. Phase 8 / B8 / M7 commit-message templates gain a `Dispatch-Mode: <teams|subagents>` trailer above the existing `Co-Authored-By` trailer, derived from `intake-state.json`. Banner is informational, never gating — subprocess failure surfaces a one-line note and the run continues. 20 new tests in `tests/test_dispatch_banner.py`; backwards-compatible observability addition
           v1.6.0  ─ teammate git discipline — a real-world failure surfaced in a separate user session exposed a discipline gap: four teammates dispatched in parallel against the same working tree each ran `git stash` to verify their work against baseline; concurrent stash + pop interleaved catastrophically; the reflog showed 10+ consecutive `reset: moving to HEAD` entries; three of four teammates' work was lost (only the last writer survived). The plugin had no rule forbidding teammates from running destructive git operations, so the teammates did. v1.6.0 ships the discipline at 4 enforcement points (same shape as v1.4.0 scope-discipline): (1) new `## Teammate git discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 6 forbidden destructive operations (`git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f`), documents the heirship-app-v2 worked example with the smoking-gun reflog signature, names the right pattern (orchestrator captures `BASELINE_SHA=$(git rev-parse HEAD)` at run start; teammates run `git diff $BASELINE_SHA -- <my-files>`); (2) 3 pipeline body anti-pattern entries; (3) all 27 `agents/*.md` files gain a `## Forbidden git operations` section as a uniform 5-line block; (4) new `## Baseline SHA capture` sub-section in `team-spawning-and-review-gates/SKILL.md` documents the orchestrator-side mechanics — SHA persisted to `intake-state.json` as `baseline_sha`, carried in every teammate's spawn brief (extending the v0.9.13 manifest schema). 265 new tests in `tests/test_teammate_git_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the orchestrator-provided alternative)
           v1.7.0  ─ frontend missing-API discipline — orthogonal to v1.6.0. When a frontend agent encounters a UI element that needs a backend API which does NOT yet exist, the previous discipline didn't tell the agent what to do — the predictable failure modes were the four downstream defects each existing gate catches AFTER the round trip is wasted (fake the data → caught by `dynamic-value-discovery`; mock the endpoint → caught by `playwright-user-flows`; hardcode the response → caught by `dynamic-value-discovery`; silently stub the UI → caught by `interaction-completeness`). v1.7.0 ships the explicit alternative at 4 enforcement points: (1) new `## Frontend missing-API discipline` section in `common-pipeline-conventions/SKILL.md` is the canonical home — names the 4 anti-patterns + the right pattern (write SR with `origin.kind: "missing-api-for-frontend-element"`, pause that element's work, continue on the rest of the slice, return to wire when the orchestrator re-dispatches with the SR resolved); (2) `## Missing-API discipline` section in `agents/frontend.md` (authoring side; worked example: `<UserAvatar>` component needing `GET /api/users/me`) + `## Missing-API SR intake` section in `agents/backend.md` (resolver side; surfaces actual endpoint shape in dispatch report so frontend can confirm before wiring); (3) `agents/system-architect.md` Phase 2 architect brief — new ordering-dependency check for every `both`-layer requirement (decide between sequencing backend-first or authorizing the frontend to surface missing-API SRs — the default); (4) new `pending-backend` element classification in `skills/interaction-completeness/SKILL.md` (the 5th classification; SR-linkage rule: reviewer accepts only with matching open SR; without the SR it's an `unwired-control` gap) + new `missing-api-for-frontend-element` SR origin-kind in `skills/team-spawning-and-review-gates/SKILL.md` with documented routing (orchestrator dispatches BACKEND agent FIRST, NOT through `diagnostic-research-team` — this is not a test failure; on backend completion the orchestrator re-dispatches the FRONTEND to wire up). 26 new tests in `tests/test_frontend_missing_api_discipline.py`; backwards-compatible discipline addition; no runtime detector, no enforcement hook (discipline lives in agent bodies + structural tests + the SR auto-spawn)
           v1.8.0  ─ agent-resume discipline — a reliability gap distinct from v2.0.0's verified-agent-output framework. A real-world background `dv-attorney` agent ran 68 tool-calls of real work; the final report message was lost to a harness-level stream timeout (rate-limit cutoff); the orchestrator saw an empty result and treated the agent as failed; the work was on disk the whole time; the user had to manually `redispatch and continue` so the agent could re-emit its verdict from already-loaded context. v1.8.0 automates the recovery and adds a checkpoint discipline so the resumed agent doesn't re-do the 68 tool calls. 4 enforcement points (same shape as v1.6.0 + v1.7.0): (1) new `scripts/setup/agent_resume.py` helper exposes `is_truncated(result)` (3 heuristics — empty / sub-50-char output, rate-limit / stream-timeout markers, missing `Status:` / `DONE` / `BLOCKED` / `NEEDS_CONTEXT` report markers), `wrap_agent_result(result, agent_id, send_message, max_attempts=2)` (dependency-injected `SendMessage`; merges resumed output with original via `[resumed via wrap_agent_result]` marker; caps at 2 attempts; surfaces `resumed_failed=True` + `resume_error` on cap-exhaustion without raising), `read_checkpoint(agent_id, checkpoints_dir=None)` (defaults to `shared_state_dir() / 'agent-checkpoints'` via the v1.1.0 lazy-import pattern; returns None for absent / malformed); (2) two new canonical sections in `skills/common-pipeline-conventions/SKILL.md` — `## Background-agent resume discipline` (wrap-call rule + 3 truncation heuristics + 2-attempt cap + user-surfacing) and `## Agent checkpoint discipline` (path + schema + cadence + resume-reads-checkpoint pattern); (3) one-paragraph reference in each of the 3 pipeline SKILL.md bodies enumerating the dispatch phases; (4) uniform `## Checkpoint discipline` section in all 27 `agents/*.md` files inserted AFTER `## Forbidden git operations`. 42 new tests in `tests/test_agent_resume_discipline.py`; backwards-compatible (purely additive); orthogonal to v2.0.0 (the VAO branch is unaffected; the helper layers cleanly underneath if v2.0.0 is later approved); no runtime detector, no enforcement hook (discipline lives in the helper + canonical sections + 27-agent fan-out)
           v2.0.0  ─ verified-agent-output (VAO) framework — derive a frozen oracle spec, adversarially review it, then deterministically verify the build against it (6 layers); new oracle-deriver + adversarial-reviewer agents + skill-invocation audit hook
           v2.1.0  ─ interactive-mockup discovery — two-pass (interaction-observer runs the mockup; interaction-intuiter infers intent) so a mockup's broken literal behaviour never becomes the contract; verify-interactions-honored Layer-3 tool
           v2.2.0  ─ verified-live discipline — rejects invalid verification CLAIMS (gesture-substitution / self-verification-loop / prefill-masking); verify-live-verification-claim Layer-3 tool + qa-replayer audit
           v2.3.0  ─ phenotype subsystem — pre-made generalized deployable architectures (blueprint + parameterized scaffold + metadata); 3 seeds (user-management, config-management, ai-management); `--phenotype` trigger + reuse-first auto-suggest; `absorb` any codebase into a new phenotype
           v2.4.0  ─ external-state assertion + evidence-artifact citation — closes the verbatim heirship-app-v3 "SendGrid 202 ≠ delivered" case + the fabricated 3-row ✅ table case; 6 canonical external-system kinds (email / payment / push / webhook-outbound / oauth / blob-storage); 2 new severities (`external-state-not-asserted` / `missing-evidence-artifact`); on-disk artifact required for every verified-live claim
           v2.5.0  ─ in-flight clarification discipline — when a pipeline is mid-execution and the user injects a message without `/architect-team`, fold it into the in-flight brief as a scope amendment rather than spawning a sibling workflow; 3 detection signals + 4 forbidden anti-patterns; symmetric counterpart to v2.0.0 Layer 6
           v2.6.0  ─ live-data wiring discipline — when the requirement mandates live data, agents must remove pre-existing mock state (not just refrain from adding new mock state); 9th Layer-3 tool `verify_live_data_wiring` with 5 severities (mock-state-residue / live-response-not-rendered / mock-fallback-uncovered / network-not-intercepted / async-status-not-surfaced); 2-pass workflow (Playwright + tamper test, then code-side audit); extends the 3-reviewer Phase 5 swarm
           v2.7.0  ─ pattern propagation mandate — when an agent fixes one mock-state instance under a `wiring_mandate`, it MUST sweep the codebase for the same shared source and fix ALL consumers in the same change (no follow-up offers); 6th severity `shared-mock-source-not-swept`; 3-step sweep protocol; closes the verbatim WtData walkthrough case
           v2.8.0  ─ no standing-red discipline — agents MUST NOT commit a failing test as documentation of a known bug; cross-layer bugs route via SR (origin kinds `cross-layer-backend-required` / `cross-layer-frontend-required`), never via a committed `// will go green when fixed` test; 10th Layer-3 tool `verify_no_standing_red` with 2 severities (`standing-red-committed` / `cross-layer-fix-not-routed`); closes the verbatim heirship B23 case
           v2.9.0  ─ MemPalace installer self-heal + polyglot Python in commands — `_locate_pip_user_binary()` + `_bridge_to_path_dir()` symlink macOS `~/Library/Python/*/bin` binaries into `~/.local/bin`; `python -m pip install --user` fallback when no `pip` script is on PATH; `_BRIDGED_BINARIES` allowlist; single polyglot `python3 ... || python ...` block in `commands/mempalace-install.md`; structural test audits all 14 command files
           v2.10.0 ─ no end-of-run deferral discipline — agents MUST NOT end a run by cataloguing in-scope work as "Deferred" with a "Want me to continue?" follow-up offer; every item has one of 3 valid dispositions (fixed in this change / SR routed / confirmed-stub); 11th Layer-3 tool `verify_no_end_of_run_deferral` with 3 severities (`deferred-work-catalog` / `followup-decision-question` / `wrap-up-with-known-bugs`); closes the verbatim heirship 7-bugs-4-work-items A→B→C→D cluster-list case
           v2.11.0 ─ multi-persona path-coverage discipline — features serving > 1 user persona MUST have a `persona-inventory.json` artifact AND a Playwright test per persona exercising their `entry_point` URL, plus assertions for every cross_persona_dependency, every submit_interaction (double-click idempotency), every backend_call_interaction (loading-state UI within 200ms); 12th Layer-3 tool `verify_per_persona_path_coverage` with 4 severities (`persona-path-not-tested` / `cross-persona-sync-not-asserted` / `double-submit-not-tested` / `loading-state-not-asserted`); closes the verbatim heirship multi-view-sync failure
           v2.12.0 ─ cross-discipline gate consistency hotfix — internal audit uncovered v2.10.0 wrap-up-with-known-bugs falsely firing on legitimate v2.11.0 per-persona success reports (citation list widened with 6 v2.11.0 tokens) + two duplicate test-path detectors (`_is_test_path` and `_looks_like_test_path`) diverging on 3 of 8 paths (unified into one); the verbatim heirship deferral case STILL fires
           v2.13.0 ─ dynamic affordance discovery + UX env-sequencing + visual-to-api-design skill (3 disciplines in one release)
           v2.14.0 ─ no implementation-time scope cut discipline — "⚠️ Honest scope statement" M0-foundation virtue-framing rejected
           v2.15.0 ─ dedicated `/architect-team:visual-to-api <codebase-path>` slash command (4-stage subset entry point)
           v2.16.0 ─ Stop-hook duplicate-output fix + `.architect-team/in-progress.md` 4th disposition
           v2.17.0 ─ prod-safe test classification — every Playwright/QA test carries `@prod-safe` / `@not-prod-safe`; prod URLs run reads only
           v2.18.0 ─ codebase discipline registry + Phase 0.1 auto-update — track which CT6 disciplines are applied per codebase
           v2.19.0 ─ in-flight clarification injection mechanism — per-run inbox JSONL + `/architect-team:inject` + phase-boundary check
           v2.20.0 ─ deploy mandate discipline — "fully deploy / 100% of all elements active and real" is a 5-criterion hard mandate
           v2.21.0 ─ no proxy-element verification — substituting a nearby measurable element and reporting PASS off the proxy is rejected
           v2.22.0 ─ no pipeline-bypass discipline — Skill-called-but-zero-Agent-dispatches + confession-language detection
           v3.0.0  ─ unified Unilateral-Override discipline (META) + PreToolUse runtime guardrail — one detector + one pre-action hook behind v2.10/v2.14/v2.20/v2.21/v2.22
           v3.1.0  ─ rule-source consolidation (single source of truth + drift guards) + Windows test portability
           v3.2.0  ─ Exploration Pipeline — extend visual-to-api-design 4→7 stages, ralph-loop per stage
           v3.3.0  ─ test-run monitor team — passive observer across local / CI / production-QA; `/architect-team:monitor-tests`
           v3.3.1  ─ visual-to-API dispatch symmetry (Phase 0a) — explicit dispatch contract on both pipeline sides
           v3.4.0  ─ backend-from-frontend modularization (Phase 0b) — cartographer-team + domain-research-team + api-design-from-frontend + domain-researcher agent
           v3.5.0  ─ data engineering exploration pipeline (Phase 0c) — 7-stage data-plane analog + phenotype convergence rules
           v3.6.0  ─ worktree end-of-run merge check (`finalize_run_worktree`) + hidden per-project container layout `<parent>/.<repo>-worktrees/<slug>/`
           v3.7.0  ─ auto-merge-to-main + prune by default — clean Phase 8 lands on `main` and tidies up (`AUTO_MERGE_MAIN`; `list_run_branches` / `merge_branch_to_main_and_prune`); `--no-auto-merge` opt-out; startup branch reconciliation; never `--force`, branch protection always wins
           v3.8.0  ─ unbounded solving (all run/iteration limits removed; completion-audit becomes a non-halting worklist) + Code & Data Lineage Graph (CDLG) foundation (`lineage_graph.py` / `run_metrics.py` + `endpoint-trace-mapping` / `data-lineage-mapping` skills + `endpoint-tracer` agent)
           v3.9.0  ─ uniform plugin usage — superpowers a HARD (exit-1) dependency, actually invoked; `ensure_openspec_propose_skill()`; per-pipeline superpowers pre-flight abort gate + named `superpowers:*` invocations; identical openspec gates across mini/bug-fix/full
           v3.9.1  ─ VAO review-evidence precedence fix (`(A or B) and ".json"`) + 5 orphaned openspec change folders archived into `openspec/changes/archive/`
           v3.9.2  ─ deterministic openspec gate at the master-review Stop hook (`_audit_openspec_validation` re-runs `openspec validate --all --strict`, blocks the commit on any invalid change); suite green under both cp1252 and `PYTHONUTF8=1`
           v3.9.3  ─ review-remediation — 30 verified-defect fixes across the enforcement glue (detect-once `hooks.json`, bare-module VAO CLI fallbacks, atomic in-flight inbox, UTF-8 stdin + OSError-fails-closed, `teams_mode` / `worktree_lifecycle` CLIs), the command surface, the skill docs (schema taught as v7, unbounded-solving residue swept), and the docs; a NEW "execute the glue" test family
           v3.10.0 ─ second-tier review improvements (R1–R7) — `hooks/vao_tools.py` split into the `hooks/vao/` package behind a 125-name identity-checked facade + NEW `hooks/shared_util.py`; NEW `security-hunter` adversarial shape (+ `security-finding` SR) / interaction-completeness accessibility axis (`a11y-gap`) / unbounded-run `heartbeat` notify event; scope-fidelity discipline family + helper/localhost consolidation; agent hygiene sweep; `locks.py` `O_CREAT|O_EXCL` + `globs_intersect` prefix/suffix; registry applicability guards; narrative diet
           v3.11.0 ─ structure-optimization pipeline — adversarially-verified codebase-restructure planning: `structure-optimization` skill (S0–S8) + `/architect-team:optimize-structure` + `structure-analyst` / `reference-tracer` / `structure-adversary` agents + the system-architect Restructure Plan Audit mode; deterministic partition check; two-consecutive-clean adversarial exit; plan ships as RESTRUCTURE_PLAN.md + movements.json + a strict-validated OpenSpec change
           v3.12.0 ─ structure-optimization performance + review remediation — 3-lens panel: 10 in-place correctness fixes (partition `.splitlines()` + `normcase`; `phase_complete`; `"to": []`; shard assembly; S6 routing table; arg precedence) + S5/S3 cost optimizations (adversary-round warm-start, per-round partition-recompute dedup → published `partition-check.json`, structured agree/dispute convergence, front-loading, precomputed file universe, shard policy, mechanical S7 transcription, thinnest-coverage sampling) + a permanent `## Optimization guardrails` section — every accuracy invariant preserved
           v3.13.0 ─ code-wiki phenotype — a fourth seeded phenotype absorbed (READ-ONLY) from deepwiki-open (MIT) via `phenotype-absorption`: the sidebar-nav + markdown + client-Mermaid + theming presentation pattern re-expressed as a lean Next.js scaffold (`kind: singleton`, plain CSS, `lib/maps-loader` ingesting `codebases.json` → `docs/*_MAP.md`), the entire LLM stack stripped; `deploy.via = config-management phenotype` (`iac/aws` + `iac/gcp` service-layer plug-ins, both `tofu validate`-clean); proven by an executed local demo (HTTP 200 + a Playwright screenshot of 2 rendered Mermaid diagrams + the nav tree)
           v3.14.0 ─ appearance-change policy — three modes governing unsolicited frontend-appearance changes (`strict` DEFAULT: no appearance-affecting change beyond the explicit mandate, improvement ideas recorded as proposals and never implemented; `propose`: proposals batched at a user approval gate; `innovate`: authorized + every delta logged + DESIGN_MAP-reconciled); `--appearance` flag on `/architect-team` + `:bug-fix` + `:mini`; `appearance_mode` bound at intake + carried in every spawn brief; `.architect-team/appearance-proposals/<run-id>.json` artifact; schema v7 gains the OPTIONAL `appearance_scope_review` field (hook-blocked on fail); task-reviewer per-delta trace + Master Review Audit run-diff walk
           v3.15.0 ─ skill-invocation hard-gate — a new `PreToolUse[*]` hook (`hooks/pretool_skill_gate.py`) converting Layer-6 skill-invocation DETECTION into real-time PREVENTION: when the latest genuine user prompt is an unsatisfied pipeline-command request it BLOCKS (exit 2) the first non-`Skill` tool call until a pipeline skill is engaged; universal (keyed off the plugin's own command set + Skill ledger, reusing `skill_invocation_audit`); scoped to the 5 pipeline-driving commands; false-block-safe (excludes `isMeta`/`system`/`isSidechain` records, fail-open, Skill always allowed); adversarially verified on 9 real transcripts — 0 spurious blocks, 402 genuine bypasses caught
           v3.15.1 ─ skill-gate narrowing fix — the v3.15.0 `*`-matcher over-fired on the command wrapper's own pre-Skill setup (dispatch banner / cleanup / worktree = Bash, + ToolSearch), seen on a server blocking the banner; narrowed to block ONLY build/dispatch tools (`Edit`/`Write`/`NotebookEdit`/`Agent`/`Task*`) — read-only investigation + the wrapper's Bash are always allowed, so a well-behaved run never trips it; re-verified 9 transcripts / 3939 calls — blocks only build/dispatch (204 catches), 0 non-build/dispatch blocked
           v3.16.0 ─ responsive + parallel `/architect-team:inject` — a new `parallel-problem` inbox classification + `lane_id` opens a sanctioned concurrent in-run LANE (a background team with a disjoint `hooks/locks.py` file-scope lock, converging via Phase 4) instead of folding; the inbox is polled on every phase boundary AND every background-dispatch return/wake; the forbidden `spawn-sibling-invocation` rule is amended to allow in-run lanes. Honest: polling-not-push, lock isolation is file-glob/advisory (`cdlg_overlap` not wired into `acquire_lock`), lanes degrade to sequential in subagents-mode, a failed lane downgrades rather than wedging Phase 8. New `tests/test_parallel_lane_inject.py` (13 cases incl. the end-to-end dogfood)
           v3.32.0 ─ Fable 5 default + first-install setup hardening — Fable 5 (`claude-fable-5`) is the default agent + service model with an implemented Opus 4.8 (`claude-opus-4-8`) fallback (`resolve_model` / the `scripts/setup/set_default_model.py` lever); `setup.py` hardened for a real first install (cartographer marketplace provenance `kingbootoshi/cartographer`, npm EACCES `--prefix ~/.local` retry, PEP-668 uv→pip-`--user`→`--break-system-packages` ladder + `tiktoken`, `--yes`/`CT6_SETUP_ASSUME_YES` non-interactive consent); two SR fixes folded in (skill-gate teammate/peer-message false-block; atomic `os.link` lock publish closing the ~20% multi-winner race); README bare `/architect-team-setup` command forms fixed
           v3.33.0 ─ claude-design-import — native ingestion of a Claude Design project offered via a `claude.ai/design/p` link (and/or the `claude_design` MCP): a new stdlib engine (`scripts/claude_design/claude_design_import.py`) detects the offer, materializes the WHOLE project locally path-safely, and hands it to the EXISTING interactive-mockup oracle path (`oracle-deriver` → `interactive-mockup-discovery` → `visual-to-api-design`) — no new downstream consumer; the real MCP fetch is an injected runtime adapter (ToolSearch, no tokens persisted) with an instruct-then-fallback to the zip/local path so a run never dead-ends; 48th skill (`claude-design-import`); NEW `tests/test_claude_design_import.py` (47 offline tests); folds in the stale dispatch-banner version pin (→ 3.33.0); suite → 5263 passing + 5 skipped
           v3.34.0 ─ informative run notifications — the email notifier's vocabulary goes 6 → 10 events, wired into ALL FOUR pipelines (ux-test previously had ZERO wiring): `run_start` (fires when the plan first exists and EMBEDS the architecture + solution plan itself via repeatable `--plan-file`, one email), the `waiting_on_agents` / `agents_complete` dispatch-wait pair (roster + missions when dispatched, outcomes when returned), `run_complete` (the final what-shipped email), + universal informative flags `--details` / `--progress` / `--next-step` on every event under the canonical "Informative, not just status" content contract (a bare status-only invocation is non-compliant wiring; the first phase_start is the engagement email); opt-in / best-effort / stdlib-only / secrets-via-env preserved verbatim
           v3.35.0 ─ Codex 5.6 model role split — availability-gated: with Codex 5.6 in the harness, `fable` keeps all architecture/control/design agents (18) and `codex-5.6-sol` takes all development/code-checking/testing agents (21, per a 3-classifier adversarially-re-derived `AGENT_ROLES`); without it the current operating model stays (uniform fable + the Opus fallback lever). Managed by `/architect-team:architect-team-setup` — deploy is ONE flag (`--codex`, or `CT6_CODEX_56_AVAILABLE=1`; `--no-codex` restores; no signal touches nothing); the `set_default_model.py` lever gains `--split codex` / the tri-state `--auto` (absent env = no-op, never clobbering a manual Opus state) / policy-state `--check` / `--codex-model`; unclassified agents fail safe to fable; availability is an INPUT, never probed; review-confirmed test-hermeticity fix (an ambient deploy var can no longer make the suite rewrite tracked agents/*.md)
           v3.35.1 ─ doc-currency + code/test-hygiene sweep — a 3-lens review-driven PATCH, no behavior change: stale prose test-counts + the README badge brought current; the newline-rewrite trio + truthy-env parsing consolidated (agent_boilerplate_blocks / teams_mode); vao_tools delegates to shared_util.load_json; 6 dead imports removed; the permanently-skipping mini-run-trailer test stub deleted (199 → 198 test files, skips 5 → 4); tests/helpers gains the shared module_loader (67 boilerplate sites / 55 files migrated) + pins (magic-number tripwires single-sourced); the three >900-line modules deliberately deferred (locks.py is freshly race-fixed concurrency code)
           v3.36.0 ─ external-LLM gateway — one setup flag (`--external-llm` / `CT6_EXTERNAL_LLM=1`) installs + configures the MIT-licensed LiteLLM proxy (`scripts/setup/install_gateway.py`, stdlib-only, mirrors the librarian installer), giving the v3.35.0 codex split a real backend: `codex-5.6-sol` → `openai/gpt-5.6-sol` behind a generated master key; TWO auth modes resolved from key presence — api-key (the gateway fronts both providers; consent-gated `--activate` writes `ANTHROPIC_BASE_URL` into settings.json AND applies the codex split) vs subscription (no Anthropic key: fable keeps Claude sign-in auth, the split stays OFF, the gateway serves OpenAI to direct callers); raw keys ONLY in 0600 `gateway.env`; never gates setup; symmetric uninstall
           v3.37.0 ─ gateway auto-registration — the installer registers + starts the gateway itself, user-level on every OS (`schtasks onlogon` + a Startup-folder-shim fallback + a detached start-now spawner / `systemctl --user` with a `default.target` unit / a LaunchAgents plist), never sudo; `--no-register` opts back to the printed hint; a failure degrades to the hint (never gates); uninstall stops + unregisters symmetrically; `status` gains `registered=` (v3.37.1 PATCH: setup's gateway loader registers the module in `sys.modules` before exec, so the `--external-llm` setup row actually loads)
           v3.38.0 ─ setup asks for missing keys — ask-then-apply, never punt-to-script: the setup + librarian-install wrappers ask in-session on an absent-key state (AskUserQuestion — capture-and-apply with the `--yes`→`--activate` carry-over, or an explicit decline recorded via the new `decline` subcommand); the gateway + librarian installers prompt themselves on a real interactive TTY (hidden getpass entry, blank-to-skip, interrupt-skips); a per-key `key-declines.json` record auto-resets on key resolution (`--re-ask-keys` clears; `status` reports `declined=`; `uninstall --purge` symmetric); all 11 `scripts/setup/*.py` dispositioned (REQ-005) — non-user-holdable remediations stay printed; +56 hermetic tests; suite → 5465 passing + 5 skipped
           v3.39.1 ─ living-docs current-state refresh — docs-only PATCH on v3.39.0: 12 stale README/map assertions corrected; the class-general derive-and-compare detector retained as a standalone regression artifact; counts unchanged at 48 skills / 39 agents / 23 commands; suite totals unchanged (docs-only, no delta; 199 test files)
           v3.40.0 ─ secondary-provider registry — the gateway's secondary model slot becomes selectable (OpenAI Codex gpt-5.6-sol or Z.ai GLM 5.2 glm-5.2) via the SECONDARY_PROVIDERS registry single-sourced in set_default_model.py (one dict entry per future provider, extensibility test-pinned); the split's written id becomes the provider-neutral ct6-secondary under policy secondary-split (legacy codex-5.6-sol/codex-split still read, never written; --split secondary canonical); the choice is asked once (wrapper AskUserQuestion / TTY prompt / --secondary / CT6_SECONDARY_PROVIDER), remembered in gateway.json, grandfathered as openai for pre-v3.40 installs, re-opened by --re-ask-provider; --zai-key joins the key machinery with full decline parity; 3-round adversarial migration hardening (heal-to-recorded-alias; migration on every config-regenerating install with prior-state carry-forward; provider-switch key retention); suite → 5542 passing + 4 skipped
           v3.40.1 ─ context-token-optimization — instruction-surface token-efficiency PATCH (docs/instruction files only, zero behavior change): CLAUDE.md 95,221 → 25,331 B (Recent releases bounded to the 3 most recent entries + the CHANGELOG pointer; What-this-repo-is + Stack rewritten as-shipped; the .mempalace location corrected to disk truth); the three pipeline dispatch-mode residual digests trimmed to their common-pipeline-conventions citations; two consistency fixes; new living spec context-surface-efficiency (59 → 60); counts unchanged 48/39/23; suite 5542 passing + 4 skipped
           v3.41.0 ─ glm-secondary-route-fix — the GLM secondary made real: SECONDARY_PROVIDERS entries carry route_dialect and the gateway route is derived <route_dialect>/<model> (zai → hosted_vllm/glm-5.2; the hard-coded openai/ prefix 404'd every call), the role split writes the spawn-compatible DISCLOSED impersonation alias claude-haiku-4-5 (Claude Code validates teammate ids client-side), CONFIRMED-live requires a spawn-alias-mandatory /v1/messages completion with upstream-deployment identity + an auth-enforcement rung, plus served-state route-contradiction staleness, exactly-one tree-aware instances, the port-holder-stopping bind-verified restart, the never-dark verify-then-swap deploy and the launcher port guard; suite 5646 passing + 4 skipped
   ◆       v3.41.1 ─ gateway-activation-drift — a recorded-consent flag is never ground truth: status names activation drift loudly (summary + a dedicated activation-drift row + a drifted footer + a first-class --json field; a clean machine's output stays byte-identical), the install carry-forward VERIFIES against the served port before trusting the flag and HEALS from the persisted master key (corrupt settings.json aborts first; unhealable is a FAIL row, never a green carried-forward), and the new maybe_heal_activation() self-heals at SessionStart behind a TCP liveness guard without ever clobbering a user-customized ANTHROPIC_BASE_URL; REQ-004 — the root clobberer was this repo's OWN test suite (a real uninstall with no --settings-path stripped the env block from the developer's real ~/.claude/settings.json on every full pytest run, a silent no-op on CI which is why it survived) — closed by an explicit --settings-path, a module-wide autouse sentinel redirect, and a session-scoped SHA-256 tripwire that fails the suite loudly on any real-state mutation (verified to actually fire); suite 5689 passing + 4 skipped (current)

   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰
```

Full design history: [`docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md`](docs/superpowers/specs/2026-05-16-architect-team-plugin-design.md). Full changelog: [`CHANGELOG.md`](CHANGELOG.md).

```
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
█▓▒░  ◆  LICENSE  ◆  ░▒▓█
░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

MIT — see [`LICENSE`](LICENSE).

```
                  ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
                  █  Built with Claude Code · Opus 4.8  █
                  ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```
