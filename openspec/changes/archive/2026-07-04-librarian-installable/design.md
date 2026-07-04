# Design — librarian-installable

## Context

The librarian's deterministic core exists; only the runnable glue + installer + command are missing. This change adds exactly that glue, mirroring the mempalace-install installable pattern, and nothing more. Plugin core stays stdlib-only; the `anthropic` SDK remains an optional, lazily-imported boundary.

## Reuse Decision Log

Per `reuse-first-design` (extend > compose > reuse > build-new). Anchored in `docs/CODEBASE_MAP.md` + `services/`.

| Need | Decision | Reuse target (exists in map) | New code justification |
|---|---|---|---|
| Daemon loop / scheduling | **REUSE** | `services/common/bg_runtime.py` — `Scheduler`, `run_forever`, `ServiceTask` | none — used as-is |
| Boot/restart descriptor | **REUSE** | `services/common/bg_runtime.py::install_descriptor` (launchd/systemd/schtasks) | none — used as-is |
| Off-machine log sink | **REUSE** | `services/common/bg_runtime.py::FileLogShipper` | none — used as-is |
| Fetch→extract→index→metadata flow | **REUSE** | `services/librarian/librarian.py::Librarian` (`research_topic`, `build_scheduler_tasks`, `install_descriptor`) | none — used as-is |
| Document extraction | **REUSE** | `services/librarian/extract.py::extract_record` | none |
| Reference index | **REUSE** | `services/librarian/library_index.py::LibraryIndex` (sqlite) | none |
| LLM adapter | **REUSE** | `services/common/service_config.py::anthropic_client` / `FakeLLMClient` / `load_config` | none |
| Data source interface | **EXTEND** | `services/librarian/librarian.py::Source` (only `StaticSource` exists) | `UrlSource` — the missing concrete stdlib `urllib` implementation of the existing interface |
| Daemon entry point | **BUILD-NEW** | none exists (`services/` has no `__main__`) | `services/librarian/daemon.py` — the missing runner the boot descriptor targets; smallest module that wires the reused pieces + `run_forever` |
| Installer + CLI | **BUILD-NEW** (pattern-mirror) | `scripts/setup/install_mempalace.py` is the sibling pattern (not importable for reuse — different tool) | `scripts/setup/install_librarian.py` — provisioning + lifecycle CLI, structurally parallel to install_mempalace.py |
| Slash command | **BUILD-NEW** (pattern-mirror) | `commands/mempalace-install.md` is the template | `commands/librarian-install.md` |

## Key decisions

- **State location** `~/.architect-team/librarian/` — consistent with the plugin's `~/.architect-team` user-home convention; per-user (one daemon), base-dir injectable for tests.
- **Topic management** via CLI subcommands writing `topics.json` (not hand-edited) — guard-railed + testable.
- **No-key ⇒ install-but-disabled** — a `FakeLLMClient` daemon would index non-real extractions, so enabling it without a key would violate the honest-boundary discipline. Install provisions everything and prints an explicit `--enable` path; `status` shows degraded.
- **Register hint printed, not executed** — same safety posture as `mempalace-install` never auto-registering the MCP server; descriptor generation is mechanical, loading is the user's explicit action.
- **Daemon module placement** `services/librarian/daemon.py`, run as `python -m services.librarian.daemon` — keeps the entry point inside the separable service dir so `check_separation()` still holds and the service stays liftable (REPO-4).

## Risks / boundaries

- `UrlSource` does real network I/O at runtime, but tests inject `StaticSource` + `FakeLLMClient` + a fake env so the suite stays offline + stdlib-only.
- The installer must not `pip install anthropic` — the SDK stays an optional boundary; degraded mode is the honest fallback.
- Honest-boundary wording: the installer output never claims "deployed/running in production" beyond what is actually enabled.
