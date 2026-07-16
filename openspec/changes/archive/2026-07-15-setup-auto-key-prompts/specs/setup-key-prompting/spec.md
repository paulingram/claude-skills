## ADDED Requirements

### Requirement: Wrapper-level ask on absent-key states

`commands/architect-team-setup.md` SHALL direct the executing agent, whenever the setup report or gateway status shows an absent-key state (`ANTHROPIC_API_KEY` absent in subscription mode, or `OPENAI_API_KEY` absent in provisioned-but-NOT-enabled) with no recorded decline for that slot, to ask the user in-session via AskUserQuestion with exactly two dispositions: capture the key now (the agent then itself runs `install_gateway.py install --anthropic-key/--openai-key …`), or an explicit decline (the agent records it via the `decline` subcommand). The wrapper SHALL NOT present the bare run-this-script remediation as the only path. A `--yes` (or `CT6_SETUP_ASSUME_YES`) present on the original setup invocation SHALL carry over as `--activate` consent when a key is captured; with no prior consent signal, activation stays consent-gated. Subscription mode SHALL remain a first-class deliberate outcome on decline.

#### Scenario: absent Anthropic key directs an in-session ask

- **WHEN** the wrapper text is inspected for the subscription-mode absent-key state
- **THEN** it directs an AskUserQuestion with capture-and-apply and explicit-decline dispositions, names the `--anthropic-key` apply path with the `--yes` → `--activate` carry-over, and names the `decline` subcommand for the decline path

#### Scenario: recorded decline suppresses the ask

- **WHEN** the wrapper text is inspected for its decline handling
- **THEN** it directs the agent to consult the recorded declines (via `status`) and NOT re-ask a declined slot absent an explicit re-ask signal

### Requirement: Installer-level interactive key prompt

`install_gateway.py` SHALL prompt for a missing key during `install` ONLY when all of: the run is interactive (no `--yes`-equivalent non-interactive signal), stdin is a TTY, and the slot's key did not resolve (args > env > env file). The prompt SHALL use hidden (getpass-style) entry, falling back to visible input only where hidden entry is unachievable (non-console stdin), and blank entry SHALL skip without error. Non-interactive, non-TTY, `--check-only`, and `--json` runs SHALL never prompt, never block, and never invent a key. The `setup.py --external-llm` path SHALL pass interactivity through (interactive setup may prompt; `--yes`/`--no-prompt`/`--check-only` stay prompt-free).

#### Scenario: interactive TTY with absent key prompts hidden

- **WHEN** `install` runs with an injected interactive TTY, no resolvable OpenAI or Anthropic key, and an injected getpass seam
- **THEN** the getpass seam is invoked for the absent slot(s), the entered key lands in `gateway.env` only, and every report line masks it to its last 4 characters

#### Scenario: blank entry skips

- **WHEN** the prompt seam returns an empty string for a slot
- **THEN** the install proceeds exactly as the absent-key path does today (honest provisioned-but-NOT-enabled / subscription outcome) and the slot's decline is recorded

#### Scenario: non-interactive never prompts

- **WHEN** `install` runs with `--yes`-equivalent non-interactive signal or a non-TTY stdin
- **THEN** no prompt seam is invoked and the behavior is byte-equivalent to the pre-change absent-key path aside from decline-record bookkeeping

### Requirement: Per-key decline record with auto-reset

The gateway state dir SHALL carry a `key-declines.json` mapping slot (`anthropic` | `openai`) → decline metadata. Both an explicit wrapper-level decline (the `decline` subcommand) and a blank-to-skip at the installer prompt SHALL record the slot. A recorded decline SHALL suppress that slot's prompt on re-runs. The record SHALL auto-reset for a slot when that slot's key later resolves (args, env, or env file), and `--re-ask-keys` SHALL clear the record so prompts fire again. `status` SHALL continue to report the absent/declined state honestly — the decline suppresses the PROMPT, never the truth. `uninstall --purge` SHALL remove the record with the state dir.

#### Scenario: decline suppresses the next prompt

- **WHEN** a slot is declined and `install` re-runs interactively with the key still absent
- **THEN** no prompt fires for that slot and the report notes the recorded decline

#### Scenario: key resolution auto-resets

- **WHEN** a declined slot's key later resolves on any resolution path
- **THEN** the decline entry for that slot is cleared and the key is used normally

#### Scenario: re-ask clears the record

- **WHEN** `install --re-ask-keys` runs interactively with keys still absent
- **THEN** previously-declined slots prompt again

### Requirement: Librarian key-prompt parity

`install_librarian.py` and `commands/librarian-install.md` SHALL exhibit the same three behaviors for the librarian's Anthropic key: the wrapper-level AskUserQuestion direction on the provisioned-but-NOT-enabled state, the installer-level hidden stdin prompt (same interactivity + TTY + blank-to-skip + never-under-non-interactive rules), and the per-key decline record in the librarian state dir with the same auto-reset, `--re-ask-keys`, status honesty, and purge symmetry.

#### Scenario: librarian installer prompts on interactive TTY

- **WHEN** librarian `install` runs with an injected interactive TTY, no resolvable Anthropic key, and an injected getpass seam
- **THEN** the seam is invoked once, a captured key enables the daemon path exactly as `--enable` with a key does, and a blank entry records the decline and keeps the honest provisioned-but-NOT-enabled outcome

#### Scenario: librarian wrapper directs the ask

- **WHEN** the librarian command wrapper text is inspected
- **THEN** it directs an AskUserQuestion with capture-and-apply and recorded-decline dispositions instead of only the printed `--enable` remediation

### Requirement: Setup-surface sweep record

The change SHALL record a disposition for every installer under `scripts/setup/` — `qualifies` (punts on user-holdable input; converted to ask-then-apply) or `examined-and-excluded` (with the reason) — in `design.md`, and non-user-holdable remediations (plugin installs, npm EACCES / PEP-668 environment fixes, version upgrades) SHALL remain printed remediations.

#### Scenario: every installer is dispositioned

- **WHEN** the sweep table in `design.md` is compared against the `scripts/setup/*.py` inventory
- **THEN** every installer file appears with an explicit qualifies or examined-and-excluded disposition and no installer is silently skipped

### Requirement: Posture preservation

The change SHALL preserve verbatim: key/remediation failures never gate setup (the `setup_entry` warn-degrade posture); raw keys ONLY in the installer env files (0600 best-effort), masked to last-4 in every report line and never echoed to the terminal by the scripts (the prompt itself uses hidden entry); activation consent-gated (with the `--yes` carry-over); uninstall symmetry (deactivate + stop + unregister + restore-fable, now including decline-record removal under `--purge`).

#### Scenario: prompt failure never gates setup

- **WHEN** the prompt seam raises (e.g. interrupted stdin) during a setup-driven install
- **THEN** `setup_entry` degrades to its existing warn-row posture and setup completes

#### Scenario: captured key never appears raw outside the env file

- **WHEN** a key is captured via the prompt seam and the report is rendered
- **THEN** the raw value exists only in the env file and every report/status line shows the last-4 mask
