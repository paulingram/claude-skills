## Why

The CT6 Librarian (`services/librarian/`) ships today as design + a stdlib-only deterministic core + tests — `Librarian` (fetch→extract→index→metadata), `extract.py`, `library_index.py`, on the shared `bg_runtime` (`Scheduler` + `run_forever` + per-OS install descriptors) and `service_config` (LLM adapter). Per `services/README.md` it is explicitly NOT live-deployed: there is **no CLI / `__main__` / daemon entry point anywhere in `services/`**, the real data **Source** (web scrape / API) is not built (only `StaticSource`), and the Anthropic LLM adapter needs the `anthropic` SDK + `ANTHROPIC_API_KEY`. So a user cannot actually turn the librarian on. MemPalace, by contrast, IS installable — `/architect-team:mempalace-install` + `scripts/setup/install_mempalace.py` provision it end-to-end. This change gives the librarian the same first-class installable treatment.

A reuse-first sweep found that the daemon loop, the scheduler, the per-OS boot/restart descriptors, the sqlite index, the extraction flow, the `Source` interface, the LLM adapter, and the log shipper ALL already exist. What is genuinely missing is the **glue**: a daemon entry point that wires them and calls `run_forever`, a concrete `urllib` `Source` over a topic→URL registry, an installer that provisions state + generates/installs the boot descriptor, and a slash command — exactly mirroring the mempalace-install installable pattern.

## What Changes

- **NEW** `commands/librarian-install.md` → `/architect-team:librarian-install`, mirroring `commands/mempalace-install.md` (frontmatter, polyglot `python3 … || python …` invocation, "After the script runs, summarize" + "Safety rules" sections). Slash-command count increments by 1. (REQ-001)
- **NEW** `scripts/setup/install_librarian.py` — stdlib-only installer exposing the full-lifecycle CLI: `install` (default) / `status` / `add-topic` / `list-topics` / `remove-topic` / `run-once` / `uninstall`, plus `--enable`, `--check-only`, `--json`. (REQ-002, REQ-009, REQ-010)
- **NEW** daemon entry point `services/librarian/daemon.py` (runnable as `python -m services.librarian.daemon`) — loads config + registry, constructs `LibraryIndex` + LLM client + `Source`, builds a `Librarian`, registers its scheduler tasks on a `bg_runtime.Scheduler`, calls `run_forever()`. This is the `ProgramArguments`/`ExecStart` target. (REQ-003)
- **NEW** `UrlSource` — a stdlib `urllib`-based `Source` implementation over the topic→URL registry; network failures degrade gracefully (logged + skipped, never crash a tick). No new hard dependency in the plugin core. (REQ-004)
- **LLM wiring** — `service_config.anthropic_client()` when `ANTHROPIC_API_KEY` resolves; else `FakeLLMClient`. Never silently fake — the mode is surfaced. (REQ-005)
- **No-key behavior** — with no key, `install` provisions all plumbing + writes the boot descriptor but does NOT enable the daemon; it prints the degraded notice + the exact `ANTHROPIC_API_KEY=… ; librarian-install --enable` remediation. (REQ-006)
- **State** under `~/.architect-team/librarian/`: `config.json`, `topics.json`, `index.sqlite`, `bodies/`, `metadata/`, `librarian.log.jsonl`. (REQ-007)
- **Per-OS boot descriptor** generated via `bg_runtime.install_descriptor` (launchd on macOS / systemd / schtasks) and written to the right location; the register hint is PRINTED, never auto-executed. (REQ-008)
- **Honest-boundary discipline** — nothing described as "deployed / running in production" beyond what is stood up; degraded mode surfaced plainly; the plugin core stays stdlib-only and the `services/separation.py::check_separation()` import-clean invariant still passes. (REQ-011)
- **Tests + release** — full pytest coverage for the installer + daemon + `UrlSource` (offline, via `StaticSource`/`FakeLLMClient`/fake env); the all-commands polyglot audit covers the new command; `CHANGELOG.md` entry; version bump in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`. (REQ-012)

This produces a real installable; it does NOT build LIB-4's centralized curation endpoint, LIB-7, the LIB-9 MemPalace vector store, or any other CT6-6 service.

## Capabilities

### New Capabilities

- `librarian-install`: a first-class installable for the CT6 Librarian — a slash command + a stdlib-only full-lifecycle installer that provisions the librarian's state, wires a real `urllib` data source and the configurable LLM, generates + installs the per-OS boot/restart descriptor (printing the register hint), and enables the background daemon only when an Anthropic key is present (otherwise installs-disabled with an explicit `--enable` path), under the honest-boundary discipline.

### Modified Capabilities

None. The existing `services/librarian/*.py` and `services/common/*.py` contracts are extended only additively (a new `daemon.py` + `UrlSource`); their tests stay green.

## Impact

**Affected files:**
- `commands/librarian-install.md` — NEW (slash command).
- `scripts/setup/install_librarian.py` — NEW (installer + CLI).
- `services/librarian/daemon.py` — NEW (daemon entry point + `UrlSource`).
- `tests/test_install_librarian.py` — NEW (installer + daemon + source coverage).
- `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` — MODIFIED (version bump).
- `CHANGELOG.md` — MODIFIED (release entry).
- `services/README.md` / `CLAUDE.md` / `docs/CODEBASE_MAP.md` — MODIFIED (documentation currency).
