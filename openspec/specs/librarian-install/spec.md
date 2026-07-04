# librarian-install Specification

## Purpose
TBD - created by archiving change librarian-installable. Update Purpose after archive.
## Requirements
### Requirement: Slash command entry point

The plugin SHALL provide a `/architect-team:librarian-install` slash command at `commands/librarian-install.md` that invokes `scripts/setup/install_librarian.py` via the polyglot `python3 … || python …` pattern and forwards its arguments, mirroring `commands/mempalace-install.md`.

#### Scenario: command file invokes the installer polyglot

- **WHEN** `commands/librarian-install.md` is read
- **THEN** it contains a single fenced invocation block running `scripts/setup/install_librarian.py` under both `python3` and `python` with `||` fallback
- **AND** it carries the same structural sections as the mempalace-install command (description frontmatter, "After the script runs, summarize", "Safety rules")

### Requirement: Full-lifecycle installer CLI

`scripts/setup/install_librarian.py` SHALL be a stdlib-only script exposing the subcommands `install` (default), `status`, `add-topic`, `list-topics`, `remove-topic`, `run-once`, and `uninstall`, plus the flags `--enable`, `--check-only`, and `--json`.

#### Scenario: every documented subcommand is dispatchable

- **WHEN** the installer is invoked with any of the seven subcommands
- **THEN** the script dispatches to the corresponding handler and exits 0 on success
- **AND** `--json` produces a machine-readable status report

#### Scenario: installer imports only the standard library at module load

- **WHEN** `install_librarian.py` is imported in a stdlib-only environment with no third-party packages
- **THEN** the import succeeds (the `anthropic` SDK is referenced only lazily, behind the existing `service_config` boundary)

### Requirement: Daemon entry point

The change SHALL provide a runnable daemon entry point that constructs the `LibraryIndex`, the LLM client, and the `Source`, builds a `Librarian`, registers one scheduler task per topic on a `bg_runtime.Scheduler`, and calls `run_forever()`.

#### Scenario: the daemon module is runnable and wires the scheduler

- **WHEN** the daemon entry point is invoked with a bounded tick count (test mode)
- **THEN** it loads the persisted config + topic registry, builds a `Librarian`, registers a `ServiceTask` per registered topic, and runs the scheduler loop
- **AND** the module is the target named in the generated boot descriptor's program arguments

### Requirement: Real urllib data source

The change SHALL provide a `Source` implementation that fetches each registered topic's URLs over stdlib `urllib`, returning `{doc_id, text, source}` records, with network/HTTP failures logged and skipped rather than raising.

#### Scenario: fetch failures degrade gracefully

- **WHEN** a topic URL is unreachable or returns an error
- **THEN** the source logs the failure and returns the successfully-fetched documents (an empty list if none), and the scheduler tick does not crash

### Requirement: Configurable LLM with honest degraded fallback

The installer and daemon SHALL use the real Anthropic LLM adapter (`service_config.anthropic_client`) when `ANTHROPIC_API_KEY` is resolvable, and fall back to `FakeLLMClient` otherwise, NEVER silently — the active mode is surfaced to the user.

#### Scenario: the active LLM mode is reported

- **WHEN** `install` or `status` runs
- **THEN** the output names whether the real Anthropic adapter or the degraded `FakeLLMClient` is in effect, based on key presence

### Requirement: No-key install is provisioned-but-disabled

When `ANTHROPIC_API_KEY` is absent at install time, `install` SHALL provision all state + write the boot descriptor but SHALL NOT enable/load the daemon, and SHALL print the degraded notice plus the exact remediation to set a key and run `--enable`.

#### Scenario: missing key blocks enable and prints remediation

- **WHEN** `install` runs with no resolvable Anthropic key
- **THEN** state dirs, config, and the boot descriptor are created
- **AND** the daemon is NOT enabled, and the output prints the `--enable` remediation naming `ANTHROPIC_API_KEY`
- **AND** nothing in the output describes the librarian as "running" or "deployed"

### Requirement: Per-user state layout

The librarian's state SHALL persist under `~/.architect-team/librarian/` with `config.json`, `topics.json`, `index.sqlite`, a `bodies/` directory, a `metadata/` directory, and a `librarian.log.jsonl` log sink.

#### Scenario: install creates the state layout

- **WHEN** `install` runs
- **THEN** `~/.architect-team/librarian/` exists containing `config.json` and `topics.json`, with `bodies/` and `metadata/` directories created
- **AND** the base directory is overridable for tests via an explicit parameter / env var (no hardcoded home in the testable core)

### Requirement: Per-OS boot descriptor with printed register hint

`install` (when enabling) SHALL generate the per-OS boot/restart descriptor via `bg_runtime.install_descriptor` (launchd plist on macOS, systemd unit on Linux, schtasks XML on Windows) pointing its program arguments at the daemon entry point, write it to the conventional location, and PRINT the register hint rather than auto-executing it.

#### Scenario: descriptor is written and the register hint is printed not run

- **WHEN** `install --enable` runs on a given platform with a key present
- **THEN** the matching descriptor (`.plist` / `.service` / `.xml`) is generated naming the daemon entry point and written to disk
- **AND** the register command (`launchctl load …` / `systemctl enable …` / `schtasks …`) is PRINTED for the user to run, never executed by the installer

### Requirement: Topic registry management

The installer SHALL manage the topic→URL registry in `topics.json` via `add-topic <name> <url...>`, `remove-topic <name>`, and `list-topics`, and the daemon SHALL build one scheduler task per registered topic.

#### Scenario: topics round-trip through the registry

- **WHEN** `add-topic "rust async" https://example.com/feed` then `list-topics` runs
- **THEN** `list-topics` reports the topic with its URL(s)
- **AND** `remove-topic "rust async"` removes it from `topics.json`

### Requirement: run-once and status and uninstall

The installer SHALL provide `run-once` (one synchronous fetch→extract→index→metadata cycle over all topics, foreground, no daemon), `status` (descriptor-installed / key-present / enabled-or-degraded / per-topic last-run), and `uninstall` (remove the boot descriptor; `--purge` also removes the state dir).

#### Scenario: run-once executes a full cycle offline in tests

- **WHEN** `run-once` runs with an injected `StaticSource` + `FakeLLMClient`
- **THEN** it performs fetch→extract→index→metadata over the registered topics and reports per-topic `{fetched, indexed, skipped}` with zero network access

#### Scenario: uninstall removes the descriptor and optionally purges state

- **WHEN** `uninstall` runs
- **THEN** the boot descriptor is removed (and its unregister hint printed)
- **AND** with `--purge` the `~/.architect-team/librarian/` state directory is also removed

### Requirement: Honest-boundary and stdlib-only discipline

The change SHALL keep the plugin core stdlib-only (no hard third-party import at module load), preserve the `services/separation.py::check_separation()` import-clean invariant, and never describe the librarian as deployed/running beyond what is actually stood up.

#### Scenario: separation invariant still holds

- **WHEN** `services/separation.py::check_separation()` runs after the change
- **THEN** every `services/**/*.py` (including the new `daemon.py`) is import-clean (stdlib + in-repo only at module load)

### Requirement: Tests and release artifacts

The change SHALL add full pytest coverage for the installer, daemon, and source (offline), add a `CHANGELOG.md` entry, and bump the version in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.

#### Scenario: the suite is green and the version is bumped

- **WHEN** `python -m pytest` runs after the change
- **THEN** the new tests pass and the existing `services/librarian` + `services/common` tests remain green
- **AND** `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the new version, and `CHANGELOG.md` has the matching entry

