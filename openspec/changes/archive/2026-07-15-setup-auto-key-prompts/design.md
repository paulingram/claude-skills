# Design — setup-key-prompting (v3.38.0)

## Context

v3.36.0 shipped the external-LLM gateway with key resolution `args > process env > gateway.env` (`install_gateway.py::resolve_keys`, line ~197) and honest absent-key outcomes: subscription mode (no Anthropic key; `SUBSCRIPTION_MODE_NOTE` remediation) and provisioned-but-NOT-enabled (no OpenAI key; `report.remediation`, line ~729). v3.29.0's `install_librarian.py` has the same shape for its Anthropic key (`_cmd_install` no-key path, lines ~302-308). Both punt remediation to a manual script run; the owner directs an ask-then-apply capability instead. The two consumption contexts differ structurally: the slash-command flow runs the installer through Bash with no usable stdin (the agent must ask via AskUserQuestion and re-invoke the installer with flags), while direct terminal use has a real TTY (the installer itself can prompt). Both channels need the same decline memory so re-runs don't nag.

## Goals / Non-Goals

**Goals:** the wrapper-level ask (agent-run apply), the installer-level hidden stdin prompt, the per-key decline record with auto-reset, librarian parity, the setup-surface sweep, posture preservation, hermetic tests.

**Non-Goals:** no auth-mode semantic changes (subscription stays first-class); no live-API probing; no new hook / Layer-3 tool / skill / agent / command; no service-tier changes; no centralized cross-installer secret store.

## Decisions

### D1 — Injectable prompt seam in each installer (chosen over setup.py-only prompting)

`install_gateway.py` gains `_prompt_for_key(slot, *, prompt_fn=None, isatty_fn=None)`:

- Fires only when `interactive and isatty_fn() and slot key unresolved and slot not declined`.
- `prompt_fn` defaults to `getpass.getpass` (hidden entry — satisfies never-echoed); when hidden entry is unachievable (getpass's non-console fallback path raises/warns), degrade to `input()` with a one-line visible-entry warning. The condition is "hidden entry unachievable", NOT an import check (`getpass` always imports).
- Blank → return `None` → the existing absent-key path runs verbatim + the decline is recorded.
- `_cmd_install` calls it for `openai` then `anthropic` after `resolve_keys` leaves a slot empty. A captured key is folded into `keys` before `write_env_file`, so masking/0600/`config.yaml`-reference behavior is inherited unchanged.
- Interactivity plumbed as a new parser flag `--interactive-prompts` set ONLY by `setup_entry(assume_yes=False, check_only=False)` and by `main()` when invoked directly on a TTY without `--json`/`--check-only`. `--yes`-equivalent non-interactive runs never set it. Rejected alternative (Approach C — prompting only in setup.py): fails requirement 2, direct `install_gateway.py install` runs would stay punt-only.

### D2 — Per-installer `key-declines.json` (chosen over a centralized store)

`<state>/key-declines.json`: `{"anthropic": {"declined_at": "<ISO>", "via": "wrapper|prompt-skip"}, "openai": {...}}`. Owned by the installer whose state dir it lives in (gateway: `~/.architect-team/gateway/`; librarian: `~/.architect-team/librarian/`). Auto-reset: any resolution of that slot's key deletes the entry (checked in `resolve_keys` callers, not `resolve_keys` itself — resolution stays pure); `--re-ask-keys` clears the file; `uninstall --purge` removes it with the state dir (symmetry). `status` appends `declined=<slots>` when entries exist. Rejected alternative (Approach B — one `~/.architect-team/setup-declines.json`): crosses installer state boundaries and breaks per-installer purge symmetry.

### D3 — `decline` subcommand as the wrapper's record channel

The wrapper flow cannot type into a prompt; it needs a deterministic way to record the user's AskUserQuestion decline. New subcommand: `install_gateway.py decline <anthropic|openai>` (and `decline <slot> --clear`); librarian: `install_librarian.py decline` (its only slot) / `--clear`. Kept out of `install` flags so a decline is an explicit, auditable action.

### D4 — `--yes` carry-over as activation consent

Already the house convention: `setup_entry` appends `--activate` when `assume_yes` (install_gateway.py lines ~936-939). The wrapper direction reuses it verbatim: key captured after a `--yes` setup run ⇒ the agent's re-invocation includes `--activate`; no prior consent signal ⇒ no `--activate`, remediation line unchanged. No new consent state is invented.

### D5 — Wrapper ask sections (the slash-command half)

`commands/architect-team-setup.md` gains `### Ask for missing keys — never punt (v3.38.0)` under the External-LLM section; `commands/librarian-install.md` gains the equivalent. Both direct: parse the absent-key state, consult `status` for `declined=`, AskUserQuestion (capture → agent runs the installer with the key flag [+ `--activate` per D4]; decline → agent runs `decline <slot>`), and never present the bare script remediation as the only path. Instruction-compliance rubric shapes (frontmatter untouched, section structure, resolvable cross-references) hold.

## Reuse Decisions (reuse-first ladder)

| New surface | Decision | Justification (CODEBASE_MAP anchor) |
|---|---|---|
| Prompt seam in `install_gateway.py` | EXTEND existing installer | The installer already owns key resolution + masking + env-file write (`resolve_keys`/`_mask`/`write_env_file`); a new module would split the secret path. Mirrors `setup.py::_prompt_user_consent` house pattern. |
| Prompt seam in `install_librarian.py` | EXTEND existing installer | Same rationale; its `_resolve_config_and_mode`/`--enable` path already owns the key decision. |
| `key-declines.json` read/write helpers | BUILD-NEW (2 small functions per installer) | No existing state helper is shared between the two installers (deliberate REPO-boundary separation); each installer already has its own `_read_state`/`_write_state` idiom to mirror. |
| `decline` subcommand | EXTEND existing argparse surface | `_build_parser` already carries install/status/uninstall; a 4th verb reuses `_add_shared_flags`. |
| Wrapper sections | EXTEND existing command docs | The External-LLM section (architect-team-setup.md) and the lifecycle section (librarian-install.md) already exist; no new command file. |
| `getpass` | REUSE stdlib | No third-party dependency; stdlib-only posture holds. |

## Setup-surface sweep (REQ-005 record)

| Installer (`scripts/setup/`) | Disposition | Reason |
|---|---|---|
| `install_gateway.py` | **qualifies** | OPENAI/ANTHROPIC keys are user-holdable → ask-then-apply (this change) |
| `install_librarian.py` | **qualifies** | ANTHROPIC key is user-holdable → ask-then-apply (this change) |
| `setup.py` | examined-and-excluded (its own punts) | Remaining remediations are plugin installs (`/plugin install …` — the script cannot run them), npm EACCES / PEP-668 environment fixes, and python/node version upgrades — none user-holdable input; its Agent-Teams settings.json consent prompt ALREADY asks (the house pattern this change mirrors); the `--external-llm` path now passes interactivity through (this change) |
| `install_mempalace.py` | examined-and-excluded | Its remediations are tool/plugin availability (uv/pip install ladder, MCP registration hint) — no user-holdable secret input |
| `set_default_model.py` | examined-and-excluded | A policy lever; consumes flags/env signals, no user-holdable secret |
| `teams_mode.py`, `worktree_paths.py`, `worktree_lifecycle.py`, `agent_resume.py`, `sync_agent_boilerplate.py` | examined-and-excluded | Not installers; no remediation printing of the punt class |
| `agent_boilerplate_blocks.py` | examined-and-excluded | Not an installer — the v3.20.0 boilerplate data helper consumed by `sync_agent_boilerplate.py`; prints no remediation, consumes no user-holdable input (row added at Phase 5 on the test-completeness verifier's advisory — the sweep claims every `scripts/setup/*.py`, so the 11th file is dispositioned explicitly) |

## Risks / Trade-offs

- **A captured wrapper key appears once, raw, in the session transcript** — owner-accepted (refiner iteration 1); scripts still mask everywhere and store raw only in the env file.
- **Blank-to-skip records a decline** — an accidental Enter suppresses future prompts; mitigated by `status` honesty (`declined=` visible), the auto-reset on key resolution, and `--re-ask-keys`.
- **getpass fallback visibility** — on non-console stdin hidden entry may be unachievable; we degrade with an explicit visible-entry warning rather than failing (never-gates posture).

## Migration

None. Absent `key-declines.json` behaves exactly as today (no declines recorded). No state-format change to `gateway.json`/`gateway.env`/librarian config.
