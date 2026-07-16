# Setup asks for missing keys (ask-then-apply, never punt-to-script)

## Why

The owner directive (2026-07-15, refined to an A-grade brief through two proposal-refiner iterations): everything the setup flow runs must be automatic — when setup needs input only the user holds (an API key), it must PROMPT for it in the flow and apply it itself; it must never print a "run this outside script yourself" remediation as the only path. The observed gap is live: `/architect-team:architect-team-setup --external-llm --yes` on a machine with no `ANTHROPIC_API_KEY` lands the gateway in subscription mode and the report/command text punts to "add an ANTHROPIC_API_KEY and re-run `python scripts/setup/install_gateway.py install --activate`"; a missing `OPENAI_API_KEY` likewise lands provisioned-but-NOT-enabled with a printed remediation; `install_librarian.py` has the same absent-key punt (`export ANTHROPIC_API_KEY=… ; librarian-install --enable`). The v3.36.0/v3.37.0 printed-remediation behavior was working as designed; this change adds the missing interaction capability on top of it.

## What Changes

- **`scripts/setup/install_gateway.py`** — an interactive stdin key prompt for direct-terminal use (interactive TTY + key absent → hidden getpass-style entry with blank-to-skip; `--yes`/non-interactive/non-TTY never prompts, never blocks, never invents a key), a per-key decline record (`key-declines.json` in the state dir: wrapper decline and blank-to-skip both record; auto-reset when the slot's key resolves or `--re-ask-keys` is passed; a new `decline` subcommand gives the wrapper a deterministic record/clear channel), `status` reporting of declined slots, and uninstall symmetry (`--purge` removes the decline record with the state dir). (REQ-002, REQ-003, REQ-006)
- **`scripts/setup/setup.py`** — the `--external-llm` path passes interactivity through to the installer prompt seam (interactive setup runs may prompt; `--yes`/`--no-prompt`/`--check-only` stay prompt-free), mirroring the existing Agent-Teams `settings.json` consent-prompt house pattern. (REQ-002, REQ-006)
- **`commands/architect-team-setup.md`** — a wrapper-level "ask for missing keys" direction: on an absent-key state in the setup report (Anthropic absent in subscription mode, OpenAI absent in provisioned-but-NOT-enabled) and no recorded decline, the executing agent MUST AskUserQuestion — capture the key now (then itself run the installer with `--anthropic-key`/`--openai-key`, with a prior `--yes` carrying over as `--activate` consent) or take an explicit decline (recorded via the `decline` subcommand); never print the bare script remediation as the only path. (REQ-001, REQ-006)
- **`scripts/setup/install_librarian.py` + `commands/librarian-install.md`** — the same three behaviors for the librarian's Anthropic key: wrapper-level ask, installer-level hidden stdin prompt with blank-to-skip, per-key decline record in `~/.architect-team/librarian/` with the same auto-reset + `--re-ask-keys` + status honesty. (REQ-004)
- **Setup-surface sweep** — every installer under `scripts/setup/` dispositioned qualifies vs examined-and-excluded (the table lives in `design.md` and the CHANGELOG entry); non-user-holdable remediations (plugin installs, npm/PEP-668 environment fixes) explicitly STAY printed. (REQ-005)
- **Tests + version + docs** — hermetic prompt/decline tests via injectable input/isatty/getpass seams across `tests/test_install_gateway.py` / `tests/test_install_librarian.py` / `tests/test_setup_install_fallbacks.py`, wrapper-text pins in `tests/test_commands.py`, the dispatch-banner pin → 3.38.0; plugin.json + marketplace.json → v3.38.0 (MINOR); CHANGELOG; documentation-currency inventory. (REQ-007)

## Capabilities

### New Capabilities

- `setup-key-prompting`: the setup flow asks for user-holdable inputs (API keys) itself and applies them — a wrapper-level AskUserQuestion direction for the slash-command flow (where stdin is unavailable), an installer-level hidden stdin prompt for direct terminal use, and a per-key decline record with auto-reset so re-runs never nag — while every existing posture (never-gates-setup, raw keys only in 0600 env files, last-4 masking, consent-gated activation, uninstall symmetry) holds verbatim.

### Modified Capabilities

None. The v3.36.0 `external-llm-gateway` and v3.37.0 `gateway-auto-registration` capabilities are untouched in behavior when no prompt fires — the prompt seam composes in front of the existing key resolution; subscription mode remains a first-class deliberate outcome.

## Impact

- `scripts/setup/install_gateway.py`, `scripts/setup/install_librarian.py`, `scripts/setup/setup.py` — extended (no behavior change under `--yes`/non-interactive/non-TTY beyond decline-record bookkeeping).
- `commands/architect-team-setup.md`, `commands/librarian-install.md` — new ask-for-keys sections.
- `tests/test_install_gateway.py`, `tests/test_install_librarian.py`, `tests/test_setup_install_fallbacks.py`, `tests/test_commands.py`, `tests/test_dispatch_banner.py` — extended/pinned.
- Skill / agent / command counts UNCHANGED (48/39/23); NO new skill / agent / command / hook / Layer-3 tool; stdlib-only posture holds (`getpass` is stdlib).
