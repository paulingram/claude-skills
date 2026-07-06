## Why

A real first install of CT6 on a Linux VM (2026-07-05) hit five distinct failures, each costing live debugging; and the plugin's model defaults predate Fable 5. The five friction findings: (1) `architect-team-setup` requires `cartographer@cartographer-marketplace` (setup.py:65) but NO CT6 doc says where that marketplace lives — the installer had to GitHub-search to `kingbootoshi/cartographer`; (2) the setup's `npm install -g @fission-ai/openspec` (setup.py:159–167) has no fallback when the npm global prefix is unwritable (EACCES on `/usr`); (3) the Python-deps step `uv pip install --system` (setup.py:195–203) breaks on PEP-668 externally-managed environments (Debian-family), there is no handling for python3-shipping-without-pip, and `tiktoken` (a cartographer dependency) is not in the dep list; (4) the teams-mode consent prompt (setup.py:578–581, `input()` y/N) cannot be answered in a non-interactive run; (5) README carries five bare command forms (`/architect-team-setup` at lines 59/60/528/622/1051) that do not resolve — plugin commands are namespaced-only.

Secondarily, the user directive: make **Fable 5** (`claude-fable-5`) the default model across the plugin — we need fable running wherever it is available — with an implemented fallback to **Opus 4.8** (`claude-opus-4-8`) where it is not. Current state: agent frontmatter is 31 × `model: opus` + 8 × `model: sonnet`; `services/common/service_config.py` `DEFAULT_MODEL = "claude-opus-4-8"`; `tests/test_agents.py` `VALID_MODELS = {"opus", "sonnet", "haiku", "inherit"}` (no `fable`).

## What Changes

- **Setup hardening (`scripts/setup/setup.py`)** — (a) when cartographer is missing, the check output names the marketplace source and prints the exact remediation (`/plugin marketplace add kingbootoshi/cartographer` then `/plugin install cartographer@cartographer-marketplace`); (b) npm EACCES → retry the install with `--prefix ~/.local` (non-persistent) and print the PATH + `npm config set prefix` remediation; (c) Python deps ladder `uv pip --system` → `pip install --user` → `pip install --user --break-system-packages` (on the externally-managed error), with an actionable python3-pip hint when no pip exists, and `tiktoken` added to the dep list; (d) a `--yes` CLI flag AND a `CT6_SETUP_ASSUME_YES` env var that short-circuit every consent prompt (answering yes) for non-interactive runs. (REQ-001…004)
- **Docs command-form sweep** — the five README bare `/architect-team-setup` sites become `/architect-team:architect-team-setup`; the README setup section documents the cartographer marketplace source; `commands/architect-team-setup.md` documents `--yes` + the env var + the marketplace source. (REQ-001, REQ-004, REQ-005)
- **Fable 5 agent default** — all 39 `agents/*.md` frontmatter `model:` fields → `fable`; `tests/test_agents.py` `VALID_MODELS` gains `"fable"` and a new pin asserts every agent is `fable` (the deliberate uniform default); NEW stdlib lever `scripts/setup/set_default_model.py` (`--model fable|opus|sonnet|haiku [--check]`) rewrites/reports the frontmatter uniformly — the implemented fallback for harnesses without the fable alias, wired into `architect-team-setup`'s check output (version-gated heuristic + printed remediation, never auto-applied silently). (REQ-006)
- **Fable 5 service default with fallback** — `services/common/service_config.py`: `DEFAULT_MODEL = "claude-fable-5"`, `FALLBACK_MODEL = "claude-opus-4-8"`, new `resolve_model(preferred, fallback, availability_checker=None)` (checker injected — the live-API probe is an adapter boundary; no checker ⇒ preferred) used by `build_llm_client`; `install_librarian.py` inherits via ServiceConfig. (REQ-007)
- **Version + docs** — plugin.json + marketplace.json → **v3.32.0**; CHANGELOG entry; README/CLAUDE.md/maps model-pattern + count lines refreshed at the Phase 8 doc-currency gate. (REQ-008)

- **Skill-gate exclusions fix (mid-run SR fold)** — `hooks/pretool_skill_gate.py` arm 1 false-blocks teammates (no CT6-TEAMMATE/sidechain standdown, unlike arm 2) and is re-armed in Lead sessions by inbound teammate-message records; observed live 4x across two runs this session. Fix arm 1's exclusions + regression tests for both manifestations. (REQ-009, SR-gate-teammate-false-block)

## Capabilities

### New Capabilities

- `fable-default-setup-fixes`: first-install setup hardening (marketplace provenance, npm EACCES fallback, PEP-668 install ladder + tiktoken, non-interactive consent) + the Fable-5-preferred / Opus-4.8-fallback model default across agent frontmatter and the service tier, with a deterministic model-switch lever and updated test pins.

### Modified Capabilities

None (no existing living spec governs setup install fallbacks or model defaults).

## Impact

- `scripts/setup/setup.py` — hardened (4 behaviors), backward-compatible flags.
- `scripts/setup/set_default_model.py` — NEW (stdlib CLI lever).
- `agents/*.md` (39) — frontmatter `model:` → `fable` (one-line change each; bodies untouched).
- `services/common/service_config.py` — model defaults + `resolve_model`.
- `tests/` — `test_agents.py` pin updated; new/extended tests for the setup ladder, `--yes`/env short-circuit, `set_default_model`, `resolve_model`.
- `README.md` + `commands/architect-team-setup.md` — command forms + marketplace + `--yes` docs.
- `.claude-plugin/plugin.json` + `marketplace.json` + `CHANGELOG.md` + `CLAUDE.md` + maps — v3.32.0 currency (Phase 8).
- `hooks/pretool_skill_gate.py` + `tests/test_pretool_skill_gate.py` — arm-1 exclusions fix (REQ-009 mid-run SR fold).
- NOT touched: other hooks/, services/ beyond service_config.py, skills/ bodies, phenotypes/.
