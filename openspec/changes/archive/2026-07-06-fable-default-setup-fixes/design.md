# Design — fable-default-setup-fixes

## Context

Two independent halves sharing a file surface: (A) harden the first-install path that demonstrably broke on a real VM; (B) move the plugin's model defaults to Fable 5 with an honest, implemented Opus 4.8 fallback. Both are backend/infra-shaped; no frontend, no Playwright, no dev API.

## Reuse Decision Log

Per `reuse-first-design` (extend > compose > reuse > build-new).

| Need | Decision | Reuse target | New justification |
|---|---|---|---|
| Setup install/consent logic | **EXTEND** | `scripts/setup/setup.py` (existing npm/uv/consent sites at 159–167 / 195–203 / 578–581) | none — in-place hardening |
| Setup behavior tests | **EXTEND** | `tests/test_setup_teams_checks.py` (existing setup.py test home) + a new focused file if the module-import fixture doesn't fit install-ladder mocking | new file only if fixture-shape forces it; justify in evidence |
| Uniform frontmatter rewrite lever | **BUILD-NEW** | none — `sync_agent_boilerplate.py` re-syncs boilerplate SECTIONS, not frontmatter scalar fields | `scripts/setup/set_default_model.py` — stdlib, mirrors the sync-script pattern (walk agents/*.md, targeted field rewrite, --check mode); needed as the deterministic fable→opus fallback lever |
| Service model default + fallback | **EXTEND** | `services/common/service_config.py` (`DEFAULT_MODEL` already exists = claude-opus-4-8) | `resolve_model()` is a small pure function in the same module — not a new module |
| Model validity pins | **EXTEND** | `tests/test_agents.py` `VALID_MODELS` | none |
| Command docs | **EXTEND** | `commands/architect-team-setup.md`, `README.md` | none |

## Key decisions

- **All 39 agents → `model: fable`, uniformly.** The user directive is "the default for all models… we need fable running". The prior opus/sonnet split was a cost heuristic; the directive overrides it. The uniform state is itself pinned by a new test so drift is caught; `set_default_model.py --model opus` restores the fallback state in one command.
- **Frontmatter fallback is a LEVER + a CHECK, not magic.** Claude Code agent frontmatter has no fallback-list syntax, and model availability cannot be reliably probed from a hook. So: (1) the frontmatter says `fable`; (2) `architect-team-setup` gains a heuristic availability check (Claude Code version gate — the fable alias ships with Fable-5-aware releases; the check is documented as heuristic) that PRINTS `python3 scripts/setup/set_default_model.py --model opus` as remediation when fable looks unavailable; (3) the lever is deterministic, idempotent, and tested. Never auto-applied silently.
- **Service-tier fallback is injected, not hard-wired.** `resolve_model(preferred="claude-fable-5", fallback="claude-opus-4-8", availability_checker=None)` — a checker (callable model-id → bool) is an adapter the operator/tests inject; the live-API probe stays an adapter boundary per the services honest-boundary convention (REPO-4: no new imports). With no checker, preferred wins (the API itself errors informatively if genuinely absent). `build_llm_client` routes through it.
- **npm EACCES retry is non-persistent.** Retry with `npm install -g --prefix ~/.local` rather than mutating the user's npm config; print the persistent fix (`npm config set prefix ~/.local`) + the PATH note as remediation text. Never silently change user config.
- **PEP-668 ladder order:** `uv pip --system` (existing) → plain `pip install --user` → on the `externally-managed-environment` error string, `pip install --user --break-system-packages`; if no pip module at all, actionable hint (`apt install python3-pip` on Debian-family) — setup REPORTS, it does not sudo. `tiktoken` joins the dep list (cartographer dependency observed missing on the VM).
- **`--yes` + `CT6_SETUP_ASSUME_YES` short-circuit every consent prompt** by making the prompt function return "y" without reading stdin; both spellings honored (flag wins). The env var follows the existing truthy set {"1","true","yes"} (setup.py:462).
- **Scope-out:** no hooks changes; no skills-body changes; the maps' agent-table model column is Phase 8 doc-currency work (doc-updater), not team work.

## Parallelization (disjoint file scopes)

- **Team A `setup-hardening`** — owns `scripts/setup/setup.py`, `tests/test_setup_teams_checks.py` (+ optional new focused test file), `commands/architect-team-setup.md`, `README.md`. REQ-001…005.
- **Team B `model-default`** — owns `agents/*.md` (frontmatter model field ONLY), `scripts/setup/set_default_model.py` (new), `services/common/service_config.py`, `tests/test_agents.py`, `tests/test_services_common.py` (+ new `tests/test_set_default_model.py`). REQ-006…007.
- Zero file overlap. Phase 4 reconciliation: only needed if Team A's setup fable-check touches set_default_model interplay — Team A prints the remediation STRING only (no import of Team B's module at runtime; the string is stable), so no shared-boundary conflict is expected.
- REQ-008 (version bump + CHANGELOG + inventory docs) is orchestrator + doc-updater work at Phase 8 per the pipeline's documentation-currency gate.

## Risks / boundaries

- **Fable alias unavailable in some harnesses** → agents fail to spawn there. Mitigated by the check + lever + docs; residual risk accepted per the explicit user directive ("we need fable running").
- **Uniform fable raises cost** for previously-sonnet mechanical agents — accepted per directive; the lever supports `--model sonnet` restoration per-need (future per-agent tuning is out of scope).
- **Setup tests must not hit the network/npm/pip for real** — install functions get injectable runners (the existing pattern in setup.py uses subprocess wrappers; tests monkeypatch).
- **PEP-668 detection is string-based** (`externally managed`) — pinned to the canonical pip error marker; documented as heuristic.
