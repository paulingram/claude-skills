# Tasks — setup-auto-key-prompts (v3.38.0)

## 1. Gateway installer — prompt seam + decline record (backend-A)

- [ ] 1.1 `install_gateway.py`: add `key-declines.json` helpers (`_read_declines`/`_write_declines`/`_record_decline`/`_clear_declines`), the `_prompt_for_key` seam (interactive + TTY + unresolved + not-declined; getpass-hidden with unachievable→visible-warning fallback; blank→None), and the `--interactive-prompts` + `--re-ask-keys` flags on the shared parser. (REQ-002, REQ-003)
- [ ] 1.2 Wire the seam into `_cmd_install` (after `resolve_keys`, per slot openai→anthropic; captured key folds into `keys` before `write_env_file`; blank records decline; auto-reset a slot's decline whenever that slot resolves); add the `decline <slot> [--clear]` subcommand; `status` appends `declined=<slots>`; `uninstall --purge` removes the record. (REQ-002, REQ-003, REQ-006)
- [ ] 1.3 `setup.py`: `apply_external_llm_policy`/`setup_entry` pass interactivity through (`--interactive-prompts` only when NOT assume_yes/check_only and stdin is a TTY); prompt-seam exceptions stay inside the warn-degrade posture. (REQ-002, REQ-006)
- [ ] 1.4 Tests (`tests/test_install_gateway.py` + `tests/test_setup_install_fallbacks.py`): prompt fires on interactive TTY + absent key (injected seams); hidden entry used; captured key lands only in gateway.env and masks in reports; blank skips + records; decline suppresses re-prompt; auto-reset on key resolution; `--re-ask-keys` re-prompts; `--yes`/non-TTY/check-only/json never prompt; `decline` subcommand records/clears; purge removes record; setup interactivity pass-through + warn-degrade. (REQ-002, REQ-003, REQ-006, REQ-007)

## 2. Librarian installer parity (backend-B)

- [ ] 2.1 `install_librarian.py`: same decline helpers + `_prompt_for_key` seam (single anthropic slot) + `--interactive-prompts`/`--re-ask-keys` + `decline [--clear]` subcommand; captured key routes through the existing enable path; blank keeps provisioned-but-NOT-enabled + records; status honesty; purge symmetry. (REQ-004)
- [ ] 2.2 Tests (`tests/test_install_librarian.py`): the same matrix as 1.4 scoped to the single slot. (REQ-004, REQ-007)

## 3. Command wrappers — the ask directions (backend-B)

- [ ] 3.1 `commands/architect-team-setup.md`: `### Ask for missing keys — never punt (v3.38.0)` — absent-key detection, `status` declined-consult, AskUserQuestion capture/decline dispositions, agent-run apply with the D4 `--yes`→`--activate` carry-over, `decline` record channel, never-bare-remediation rule. (REQ-001)
- [ ] 3.2 `commands/librarian-install.md`: the equivalent section for the librarian key. (REQ-004)
- [ ] 3.3 Wrapper-text pins in `tests/test_commands.py` (section presence + the never-punt sentence + the carry-over rule); instruction-compliance lint stays zero-findings. (REQ-001, REQ-004, REQ-007)

## 4. Ship rituals (orchestrator + doc-updater)

- [ ] 4.1 Version bump: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` → 3.38.0; dispatch-banner pin (`tests/test_dispatch_banner.py`) → 3.38.0. (REQ-007)
- [ ] 4.2 CHANGELOG entry (incl. the REQ-005 sweep summary); documentation-currency inventory (README / CLAUDE.md / maps note ledgers). (REQ-005, REQ-007)
- [ ] 4.3 Full suite green under both Windows cp1252 and PYTHONUTF8=1. (REQ-007)
