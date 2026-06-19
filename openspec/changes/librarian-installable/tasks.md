# Tasks

## 1. Daemon entry point + real source
- [ ] 1.1 Add `services/librarian/daemon.py` with `UrlSource(Source)` (stdlib `urllib`; graceful failure) (REQ-004)
- [ ] 1.2 Add the daemon runner: load config + registry → build `LibraryIndex` + LLM + `Source` → `Librarian` → register `ServiceTask` per topic on a `Scheduler` → `run_forever()`; runnable as `python -m services.librarian.daemon` with a bounded-tick test hook (REQ-003)
- [ ] 1.3 Confirm `services/separation.py::check_separation()` still passes with the new module (REQ-011)

## 2. Installer + CLI
- [ ] 2.1 Add `scripts/setup/install_librarian.py` (stdlib-only) with an argparse CLI: `install` (default), `status`, `add-topic`, `list-topics`, `remove-topic`, `run-once`, `uninstall` + `--enable` / `--check-only` / `--json` (REQ-002)
- [ ] 2.2 State layout under `~/.architect-team/librarian/` (config/topics/index/bodies/metadata/log), base-dir overridable for tests (REQ-007)
- [ ] 2.3 LLM mode resolution (Anthropic when key present, else `FakeLLMClient`) surfaced in output (REQ-005)
- [ ] 2.4 No-key path: provision + descriptor but daemon NOT enabled; print `--enable` remediation; honest wording (REQ-006)
- [ ] 2.5 Boot descriptor via `bg_runtime.install_descriptor`; write file; PRINT (never run) the register hint (REQ-008)
- [ ] 2.6 Topic registry subcommands round-trip `topics.json` (REQ-009)
- [ ] 2.7 `run-once` (injectable source/llm), `status`, `uninstall` (+ `--purge`) (REQ-010)

## 3. Command + tests + release
- [ ] 3.1 Add `commands/librarian-install.md` mirroring `commands/mempalace-install.md` (polyglot block, summary + safety sections) (REQ-001)
- [ ] 3.2 Add `tests/test_install_librarian.py` — installer subcommands, no-key path, descriptor generation, topic round-trip, run-once offline, daemon bounded-tick, UrlSource graceful failure, stdlib-only import (REQ-012)
- [ ] 3.3 Bump version in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`; add `CHANGELOG.md` entry (REQ-012)
- [ ] 3.4 Documentation currency: `services/README.md` (librarian now installable), `CLAUDE.md`, `docs/CODEBASE_MAP.md` (REQ-011, REQ-012)
