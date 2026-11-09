# opus-5-model-upgrade — the plugin's current Opus generation becomes Claude Opus 5

## Why

Claude Opus 5 shipped. CT6's shipped model policy (v3.43.0's delivery-adversarial split) runs 12 delivery + adversarial agents on Opus and 27 planning / validation / review agents on Fable — but every version-bearing Opus reference in the plugin still names **Opus 4.8** or **Opus 4.7**, two generations behind. Concretely:

1. `services/common/service_config.py` hard-codes `FALLBACK_MODEL = "claude-opus-4-8"` — a dated id that is now a documented **Legacy** model — and its own `resolve_model` docstring repeats "Opus 4.8 by default" in prose, so the constant and the docstring will drift apart the moment either moves.
2. `scripts/setup/install_gateway.py`'s `ANTHROPIC_EXPLICIT_MODELS` tuple has no `claude-opus-5` route. The `*` catch-all was observed **non-functional** on a real LiteLLM install (SR-gateway-wildcard-route), which is why explicit per-model routes exist at all — so an id absent from that tuple has no working gateway route. The tuple's own comment says *"Extend here when Anthropic ships new ids."*
3. Four `commands/*.md` and three `skills/*/SKILL.md` emit `Co-Authored-By: Claude Opus 4.7 (1M context)` into every commit the pipelines author, so the plugin mis-attributes its own work.
4. Six current-state assertions across `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, and `README.md` tell a reader the plugin ships on Opus 4.8. `docs/INTEGRATION_MAP.md:20` is doubly stale — it still describes uniform `model: fable` "As of v3.32.0" and predates the v3.43.0 split entirely.
5. A **living** (non-archived) OpenSpec requirement — `openspec/specs/fable-default-setup-fixes/spec.md` — normatively `SHALL`s `FALLBACK_MODEL = "claude-opus-4-8"` in its requirement text plus one scenario THEN clause. Because `hooks/pipeline-completion-audit.py:367` runs `openspec validate --all --strict` as a Stop-hook gate, code and spec cannot diverge silently: the spec must move in lockstep or the commit is blocked.

## What the research settled

The real Claude API id **and** alias is **`claude-opus-5`** — the 4.6-generation-and-later dateless scheme `claude-{name}-{major}[-{minor}]`, with major releases omitting the minor segment. There is no `claude-opus-5-0`, no dated `claude-opus-5-YYYYMMDD`, no `-v1` suffix. Bedrock: `anthropic.claude-opus-5`; Google Cloud: `claude-opus-5`.

Two facts from the docs are decision-relevant rather than incidental:

- **A dateless id is a pinned snapshot, not an evergreen pointer.** `claude-opus-5` maps to one fixed snapshot forever; Anthropic ships updated weights under new ids. This is the *opposite* of pre-4.6 aliases such as `claude-sonnet-4-5`, which do resolve to the newest dated snapshot. It is why this change deliberately does NOT pin `claude-opus-5` into agent frontmatter — the bare harness alias `model: opus` floats to the current Opus, and pinning would trade that auto-follow for reproducibility nobody asked for.
- **`claude-fable-5` remains "Anthropic's most capable widely released model."** Opus 5 is positioned "for complex agentic coding and enterprise work." Opus 5's arrival therefore does not argue for dissolving the v3.43.0 Fable-plans / Opus-delivers partition, and this change does not touch it.

## What Changes

- **Service-tier fallback**: `FALLBACK_MODEL` → `claude-opus-5`, with the `resolve_model` docstring prose moved in the same edit, and the living `fable-default-setup-fixes` requirement + scenario amended in lockstep.
- **Gateway routing**: `claude-opus-5` added to `ANTHROPIC_EXPLICIT_MODELS`, every legacy id retained (the tuple is an allow-list of routable ids, not a currency statement), and the ordering comment refreshed.
- **Lever narrative**: the two version-bearing lines in `scripts/setup/set_default_model.py` (module docstring line 6; the delivery-split header comment line 199) name Opus 5. `OPUS_MODEL = "opus"` and `VALID_MODELS` are untouched.
- **Commit trailers**: the 7 live `Claude Opus 4.7 (1M context)` trailers become `Claude Opus 5 (1M context)`.
- **Current-state docs**: 6 lines corrected; 6 historical per-release lines deliberately frozen.
- **Agent frontmatter**: unchanged — 12 `model: opus`, 27 `model: fable`, byte-identical.
- **Release**: MINOR bump to 3.45.0 (`plugin.json` + `marketplace.json` + `CHANGELOG.md`), matching how v3.43.0 shipped its model-policy change.

## Non-goals

- **Repartitioning roles.** Which agents run Opus is unchanged; only which Opus they run.
- **Pinning `claude-opus-5` in agent frontmatter.** Explicitly rejected (see above).
- **Rewriting release history.** `CHANGELOG.md` entries and the per-release sections of `README.md` / `CLAUDE.md` / `docs/CODEBASE_MAP.md` stay byte-identical: past releases genuinely shipped on Opus 4.8, and rewriting them would falsify the record.
- **Changing `DEFAULT_MODEL`.** Fable 5 stays the service-tier preferred model.
- **New skills / agents / commands / hooks / Layer-3 tools.** Counts hold at 48 / 39 / 23 / 7 / 20.

## A recorded decision that was made against advice

Bumping `FALLBACK_MODEL` to `claude-opus-5` is the owner's explicit call, taken after the refiner raised this objection: `FALLBACK_MODEL` exists for a harness too old to resolve the `fable` alias, and Opus 5 (July 2026) is **newer** than Fable 5 (GA 2026-06-09) — so the new fallback is strictly *less* likely to resolve on such a harness than the primary it backs. The objection was surfaced; the owner reaffirmed the bump. It ships as specified, with the trade-off recorded in a code comment. Substituting a "safer" laddered or unchanged value here would be **invented caution** per `docs/ETHOS.md` `## Fidelity to human-configured policy`.
