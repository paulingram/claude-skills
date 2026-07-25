# design — opus-5-model-upgrade

## Reuse Decision Log

This change creates **zero new files** outside the OpenSpec bundle itself. Every edit lands in an existing module, doc, or test. The reuse-first ladder therefore terminates at **reuse** for every touchpoint — there is nothing to extend, compose, or build. The log below accounts for **every file in the diff**, including the two pulled in by the scope extensions recorded in `coverage-map.json` `scope_extensions`. The invariant is stated as a property rather than a hard count deliberately: a mismatch between this log and the diff was NF5 from the adversarial re-verification, and the count was then invalidated *twice* by in-run scope growth (20 → 22 → 23). Same lesson as NF1 — pin the property, not the number.

| Proposed change | Ladder rung | Existing artifact reused (per `docs/CODEBASE_MAP.md`) | Why not build new |
|---|---|---|---|
| Service fallback id | reuse | `services/common/service_config.py:21` `FALLBACK_MODEL` + `:25-53` `resolve_model` | The constant and the pure resolver already exist and are already the single source; only the literal moves. |
| Gateway route for Opus 5 | reuse | `scripts/setup/install_gateway.py:308-317` `ANTHROPIC_EXPLICIT_MODELS` | The tuple is the designed extension point; its comment says so verbatim. |
| Lever narrative | reuse | `scripts/setup/set_default_model.py:6,199` | Docstring/comment prose only; no code path changes. |
| Commit trailers | reuse | 4 `commands/*.md` + 3 `skills/*/SKILL.md` | The trailer template already exists in each pipeline body. |
| Current-state docs | reuse | `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`, `README.md` | The documentation-currency inventory already covers these files. |
| Living spec pin | reuse | `openspec/specs/fable-default-setup-fixes/spec.md:88,98` | An OpenSpec `MODIFIED Requirements` delta is the sanctioned mechanism. |
| Tests | reuse | 6 existing test files | Every assertion already exists; only expected literals move. One assertion is *added* to an existing test in `tests/test_install_gateway.py`; two test functions are *renamed* (no assertion touched) where their names asserted the claim their rewritten docstrings retract. |
| Setup-surface ship-state prose *(scope extension 2)* | reuse | `scripts/setup/setup.py:40,789,880` | Docstring / argparse-help / runtime-detail prose only; no code path changes. Added because four sibling instances live in `set_default_model.py`, which this change already edits — see `## Scope extensions` below. |
| Setup-command model-policy doc *(scope extension 1)* | reuse | `commands/architect-team-setup.md:41` | The bullet already exists; only its ship-state claim and its `--no-codex` verb change. This is the user-facing instance of the same defect. |

No new third-party dependency. The repo is stdlib-only by constitution (`services/separation.py::check_separation()` enforces import-cleanliness); nothing here approaches that boundary.

## The central design decision: alias vs. pin

`agents/*.md` frontmatter carries the bare harness alias `model: opus` on the 12 delivery/adversarial agents. Two options existed:

| | Bare alias `opus` (CHOSEN) | Pin `claude-opus-5` |
|---|---|---|
| Agents pick up Opus 5 | Yes, with **zero file edits** — the harness resolves `opus` to the current Opus | Yes, explicitly |
| Follows future Opus releases | Automatically | No — a dateless id is a **pinned snapshot**, so every future Opus needs a new edit |
| Blast radius | None | `tests/test_agents.py:65-68` `VALID_MODELS` admits no `claude-opus-*` id, so the allow-list, the `set_default_model.py` lever (`OPUS_MODEL`), `apply_delivery_split`, and its 10 lever tests all move |
| Reproducibility | Weaker (the alias can shift under you) | Stronger |

The owner chose the alias. The reasoning that makes this more than a preference: the platform docs are explicit that for the 4.6 generation onward a dateless id is *not* an evergreen pointer, so pinning `claude-opus-5` would convert a self-maintaining alias into a recurring maintenance obligation, in exchange for reproducibility this plugin does not need (it is an instruction surface, not a reproducible inference pipeline).

**Consequence for verification:** `agents/*.md` and `tests/test_agents.py` are the run's **negative control**. If either changes, the run violated its own contract.

## The current-state vs. frozen-narrative discipline

This is the run's only genuinely error-prone dimension. Three files are *partly* in scope and *partly* frozen, at line granularity:

| File | UPDATE (current-state claim) | FREEZE (historical per-release narrative) |
|---|---|---|
| `CLAUDE.md` | `:9` (v3.44.0 "Current shape"), `:33` (`service_config` digest) | `:60` (the v3.43.0 CHANGELOG digest) |
| `docs/CODEBASE_MAP.md` | `:293` (the Model note's parenthetical), `:360` (the lever's present-tense "IMPLEMENTED Opus 4.8 fallback") | `:36` (the per-release version ledger) |
| `README.md` | `:1729` (the "Built with Claude Code" badge) | `:132` (v3.43.0 section), `:251`, `:256`, `:1698` (v3.32.0 section + version cascade) |
| `docs/INTEGRATION_MAP.md` | `:20` | — |

The test is **tense and function, not proximity**: a line asserting what the plugin *is* gets updated; a line recording what a release *did* is frozen. `docs/CODEBASE_MAP.md:360` is the subtle one — it is version-tagged `**(v3.32.0)**` yet its clause ("the IMPLEMENTED Opus 4.8 fallback for a harness predating the `fable` alias") describes what the lever presently *is*, and it is the direct mirror of `scripts/setup/set_default_model.py:6`. Updating the module while freezing its map entry would leave the map contradicting the module — precisely the drift the Phase 8 documentation-currency audit exists to catch. The two move together.

Because whole-file byte checks are impossible under this split, the acceptance criterion is stated at line granularity: `git diff -U0` must not touch any of the 6 frozen lines.

## Coverage as a countable contract

The change is bounded by a mechanically-reproducible sweep rather than by judgment:

```
grep -rniE "opus[- ]?4[.-][78]" --include=*.py --include=*.md --include=*.json .
  (excluding CHANGELOG.md, openspec/changes/archive/**, docs/superpowers/**, __pycache__, .architect-team/)
```

Pre-change this returns **36** lines. The exhaustive partition of those 36 is **three** classes, not two — an earlier draft of this document and of the coverage map claimed "30 to update, 6 to freeze", which is arithmetically false and was caught by the adversarial pass:

| Class | Count | What it is |
|---|---|---|
| **Updated** | 27 | Every line whose text changes to name Opus 5 |
| **Retained unchanged** | 3 | Deliberately left as-is and NOT frozen-for-history: the 2 legacy ids in `ANTHROPIC_EXPLICIT_MODELS` (`claude-opus-4-8`, `claude-opus-4-7`) and the pre-existing `tests/test_install_gateway.py` assertion on the first of them. These are live, working routes — a third class the two-way partition had no slot for. |
| **Frozen** | 6 | Historical per-release narrative, byte-identical |

Two lines are additionally **introduced** by this change: `openspec/specs/fable-default-setup-fixes/spec.md:103` (the new scenario quoting the forbidden strings as its subject) and the new `tests/test_install_gateway.py` assertion comment/line pair's matching line.

Post-change the sweep must therefore return exactly **11**, and the arithmetic is checkable: `36 pre − 27 updated + 2 introduced = 11`. The 11 are the 6 frozen lines, the 3 retained-unchanged lines, and the 2 introduced lines. Exclusions must additionally include **`openspec/changes/opus-5-model-upgrade/**`** — the run's own live bundle, which quotes the superseded ids ~35 times by construction because it is the document describing their removal; without that exclusion the documented sweep returns 46, not 11.

The pattern's two non-obvious requirements are load-bearing. It must be **case-insensitive** (`Opus 4.8` in prose is invisible to an `opus|OPUS` pattern) and it must admit the **hyphenated** form (`Opus-4.8`). A case-sensitive sweep missed `services/common/service_config.py:31` and `tests/test_set_default_model.py:6` twice during refinement — both were caught only by the adversarial re-grade. Any implementer or reviewer using a narrower pattern will reproduce that miss.

## Lockstep pairs — edits that cannot land alone

Three pairs must move atomically, or a gate fails:

1. `services/common/service_config.py:21` ⟷ `openspec/specs/fable-default-setup-fixes/spec.md:88,98`. The Stop-hook gate at `hooks/pipeline-completion-audit.py:367` runs `openspec validate --all --strict`; a spec whose `SHALL` contradicts the code blocks the commit.
2. `services/common/service_config.py:21` ⟷ `:31`. Constant and docstring, same file.
3. `scripts/setup/set_default_model.py:6` ⟷ `docs/CODEBASE_MAP.md:360`. Module and its map entry (see above).

## Test-pin constraints

| Constraint | Where | Effect |
|---|---|---|
| `text.find("Co-Authored-By: Claude Opus")` | `tests/test_dispatch_banner.py:372,392,405` | The replacement must retain the literal `Claude Opus ` prefix. `Claude Opus 5 (1M context)` satisfies it; `Claude Fable 5` would not. |
| `VALID_MODELS` admits no `claude-opus-*` | `tests/test_agents.py:65-68` | Reinforces the alias decision; untouched by design. |
| On-disk `opus` set == `DELIVERY_ADVERSARIAL_AGENTS` | `tests/test_agents.py:218-246` | The negative control; must pass unmodified. |
| `claude-opus-4-8 in ANTHROPIC_EXPLICIT_MODELS` | `tests/test_install_gateway.py:441` | Kept, and joined by a `claude-opus-5` assertion — the legacy route is deliberately retained. |
| Top CHANGELOG version == `plugin.json`; suite-total line present | `scripts/docs_tooling/changelog_check.py` | Gates the release entry's shape. |

## Verification posture (honest boundary)

- **Layer**: `infra` throughout. No frontend surface, no API surface, no runtime behavior change beyond one resolved model id.
- **Playwright**: N/A — nothing renders.
- **Dev-API integration**: N/A — no service is stood up. `resolve_model` is a pure function verified by unit assertions; the live availability probe is an injected adapter boundary by design (REPO-4), so no network call is made or claimed.
- **What is genuinely verified**: the constant's value, the tuple's membership, the sweep's post-change count, `openspec validate --all --strict`, the instruction-compliance lint, capability-index freshness, and no-new-failures against the measured baseline.
- **What is NOT verified and is not claimed**: that a live Anthropic endpoint answers to `claude-opus-5` from this machine, and that the gateway's Opus 5 route works against a real LiteLLM install. Both need a live gateway with keys, which this run does not stand up. The id itself is confirmed from the platform docs, not from a live call.

## Baseline

Measured on this Windows checkout **before any edit**: `5948 passed, 2 failed, 5 skipped` (170.65s). The 2 failures are pre-existing line-ending artifacts (`tests/test_installer_guidance_blocks.py::test_remove_deletes_exactly_and_byte_preserves`, `tests/test_skill_references.py::test_target_skill_byte_count_reduced_vs_baseline[common-pipeline-conventions]`) and are out of scope. They cross-check exactly against the CHANGELOG's macOS basis: 5948 + 5 + 2 = 5955 = 5939 + 16, the difference being PyYAML present here (14 gated tests run rather than skip) plus 2 Unix-symlink skips. They may not be "fixed" by editing recorded byte counts, and the run may not claim a fully green suite.
