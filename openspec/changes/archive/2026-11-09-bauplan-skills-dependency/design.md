## Context

CT6 depends on three plugins today (`superpowers`, `cartographer`, `ralph-loop`), all hard: `REQUIRED_PLUGINS` at `scripts/setup/setup.py:74`, enforced by `if missing: return 1` at `setup.py:1141`. There is no second tier. Bauplan Labs' `bauplan` plugin (MIT, six data-lakehouse skills) is the first dependency CT6 wants *conditionally* — valuable on a Bauplan project, pure cost everywhere else.

Two facts from the existing codebase shape every decision below:

1. **The marketplace-provenance mechanism already exists.** `_PLUGIN_MARKETPLACE_SOURCES` (`setup.py:132`) maps a plugin id to a third-party GitHub source, and `plugin_remediation_lines()` emits `/plugin marketplace add <source>` followed by `/plugin install <name>@<market>`. It was built for cartographer. Bauplan needs exactly this shape.
2. **Agent boilerplate is unconditional by construction.** `scripts/setup/sync_agent_boilerplate.py` compiles `agent_boilerplate_blocks.BLOCKS` into every `agents/*.md` by heading match; all 39 agents carry the result. There is no per-agent or per-run conditionality in that compiler.

The user's question — *"determine where to inject these, whether the architect agents or in the development process"* — is answered in Decision 4.

## Goals / Non-Goals

**Goals:**

- A conditional dependency tier that reports and recommends but never gates setup or a run.
- Deterministic per-project arming, recursive so a monorepo subdirectory marker counts.
- The greenfield case (`bauplan-data-pipeline`'s primary use) stays reachable.
- Bauplan's lakehouse safety rules reach a target project even when the plugin does not.
- Zero cost — no added context, no added checks — on a non-Bauplan run.

**Non-Goals:**

- Changing the hardness of the three existing prerequisites.
- Modifying `hooks/skill_invocation_audit.py` or any Layer-6 enforcement hook.
- Vendoring or forking the six bauplan skills.
- Handling Bauplan credentials in any form.
- Building CT6-native lakehouse capability. This is integration, not reimplementation.
- Live-Bauplan-account end-to-end testing as a merge gate.

## Decisions

### D1 — A separate conditional registry, not an extension of `REQUIRED_PLUGINS`

`REQUIRED_PLUGINS` is a `set[str]` consumed by `check_plugin_presence()` whose result feeds the exit-1 branch. Adding a "soft" member to that set would require every consumer to learn a per-member hardness rule, and one missed consumer silently turns Bauplan into a hard dependency.

Instead: a sibling `CONDITIONAL_PLUGINS` registry, its own presence check, its own report rows, and no path into the exit-code computation. The spec pins the two sets disjoint.

*Alternatives considered.* (a) A dict `{plugin_id: hardness}` replacing both — a larger blast radius across existing call sites and tests for no benefit here. (b) Reusing `REQUIRED_PLUGINS` with a filter at the exit-code site — one filter, one place to forget; the disjoint-sets invariant is cheaper to test.

### D2 — Marker detection reuses the existing trait-detector pattern

`hooks/discipline_registry.py:204` (`_has_frontend_markers`) is the house pattern: glob `**/` over the workspace, skip `_SKIP_DIR_PARTS`, return `(bool, evidence_dict)`. A `_has_bauplan_markers` follows it exactly — `**/bauplan_project.yml`, same skip list, same evidence shape.

Verified: the existing globs are recursive, so a monorepo subdirectory marker arms correctly with no new traversal code.

*Alternatives considered.* (a) A new detection module — rejected under reuse-first; the pattern, the skip list, and the evidence contract all already exist. (b) Environment-level detection (`bauplan` CLI on PATH, `~/.bauplan/config.yml`) — rejected as the primary signal: it is per-machine, so it would arm on every repo touched from a Bauplan-configured laptop, including non-Bauplan ones. It remains available as corroboration, never as the trigger.

### D3 — The precedence rule lives in `common-pipeline-conventions`, referenced not duplicated

`skills/common-pipeline-conventions/SKILL.md` holds 50 canonical sections and is referenced by 24 skills. That is CT6's established mechanism for a cross-cutting rule: one canonical home, pointers everywhere else.

The augment-never-replace rule is exactly such a rule — it must hold in the data-eng lane, the bug-fix lane, and anywhere a future bauplan skill is reached. It gets one canonical section; the lanes cite it in a sentence.

*Alternatives considered.* Restating the rule in each lane — rejected; duplicated normative text drifts, and the instruction-compliance lint already treats cross-reference integrity as the house standard.

### D4 — Inject at the LANE level, not into the architect agents

**This is the answer to the delegated question: the development process, specifically the lane bodies — not the agents.**

Against the agents: the boilerplate compiler is unconditional (Context fact 2). A Bauplan block added there ships lakehouse instructions into all 39 agents — `frontend`, `visual-analyzer`, `route-mapper`, `closeout-agent` included — on every run, Bauplan or not. That directly contradicts the premise that Bauplan costs nothing when absent, and it is context pollution in ~99% of runs. The agent tier is the wrong altitude: agents are role definitions, and "how to work with a particular data platform" is not a property of the backend role.

For the lanes: `skills/data-eng-pipeline/SKILL.md` and `skills/bug-fix-pipeline/SKILL.md` are loaded only when their lane runs, so a pointer there is already conditional at the coarse level, and the arming check makes it conditional at the fine level. The phase structure is also what carries the *mapping* — a bauplan skill is right at a specific phase, not in general.

The binding:

| bauplan skill | CT6 phase | Why here |
|---|---|---|
| `bauplan-explore-data` | data-eng D−1/D0 (intake, exploration) | Read-only lakehouse inspection is what exploration needs; it replaces guessing at schemas |
| `bauplan-data-assessment` | data-eng D0 (exploration), D1 (planning validation) | "Can this question be answered with available data" is a feasibility input to the plan, before commitments are made |
| `bauplan-data-pipeline` | data-eng D2–D6 (implement) | Project scaffolding and model authoring is implementation work |
| `bauplan-safe-ingestion` | data-eng D2–D6 (implement) | Ingestion is a transformation; WAP is how it lands safely |
| `bauplan-data-quality-checks` | data-eng D0 Stage 6, D2–D6 | Stage 6 mandates ≥1 blocker validation rule per transformation; this skill emits exactly that as `expectations.py`. The strongest single fit in the whole surface |
| `bauplan-debug-and-fix-pipeline` | bug-fix lane B1–B6 | Its own contract is evidence-first: pin data state, collect evidence, minimal fix, rerun — the bug-fix lane's shape already |

*Alternatives considered.* (a) Agents only — rejected above. (b) Both agents and lanes — inherits the agent objection for no gain. (c) Neither; rely purely on Claude Code's skill autodiscovery from the bauplan `description` fields — rejected as insufficient alone: autodiscovery can surface a skill, but it cannot tell CT6 that a run is Bauplan-shaped, cannot enforce the augment-never-replace precedence, and cannot carry the safety context. Autodiscovery does the *selection*; CT6 supplies the *arming, precedence, and context* it cannot know on its own. That division is why this design adds no re-description of the bauplan skills themselves.

### D5 — The guidance block keys on the marker, not on plugin presence

CT6's three existing installers gate their guidance blocks on installed-capability presence. Doing that here inverts the safety intent: the block carries "never write directly to `main`; branch and merge to publish", and the moment those rules matter most is when the plugin that would otherwise enforce them is missing.

So the Bauplan block's capability check is the project trait. Trait present → block present, plugin or no plugin. Trait absent → block removed, byte-preserving the rest of the file. The opt-in `--claude-md` flag still governs; nothing is written without it.

### D6 — Dispatch evidence goes to run state, not the Layer-6 audit

`hooks/skill_invocation_audit.py` builds `COMMAND_TO_SKILLS` from CT6's own canonical commands, so a `bauplan-*` dispatch would never appear as an expectation in its verdict JSON — though `_ledger_skill_invocations` (`:316`) does capture every `tool == "Skill"` entry generically, so extension would be *possible*.

It is still the wrong place. That hook is on the Stop path of every session; editing it to prove a Bauplan behavior puts an unrelated capability's evidence needs on a load-bearing enforcement path. The run instead records each dispatch to `<workspace>/.architect-team/data-eng/<slug>/`, where the lane already writes run state.

### D7 — Behavioral checks go in the existing opt-in eval tier

Arming, non-arming, and greenfield reachability are model-behavior claims, not pure functions. `tests/evals/` behind `CT6_EVALS=1` exists for exactly this, and the default suite stays key-free. The pure decision logic (given marker state and intent state → armed?) is additionally a plain function with ordinary unit tests in the default suite.

## Reuse Decisions

| Proposed | Ladder | Decision | Anchor |
|---|---|---|---|
| Third-party marketplace registration | **Reuse** | `_PLUGIN_MARKETPLACE_SOURCES` + `plugin_remediation_lines()` verbatim; add one entry | `setup.py:132` |
| Conditional presence check | **Extend** | Sibling registry beside `REQUIRED_PLUGINS`, reusing `check_plugin_presence()` | `setup.py:74`, `:1132` |
| Bauplan marker detection | **Extend** | New `_has_bauplan_markers` following `_has_frontend_markers` exactly | `discipline_registry.py:204` |
| Safety-context propagation | **Reuse** | `upsert_block` / `remove_block` / `block_fences` unchanged; only the gate predicate is new | `guidance_blocks.py:55`,`:116`,`:161` |
| Precedence rule home | **Reuse** | One new canonical section in the existing conventions skill | `common-pipeline-conventions/SKILL.md` (50 sections, 24 referrers) |
| Behavioral coverage | **Reuse** | Existing opt-in eval tier + fixture pattern | `tests/evals/`, `scripts/evals/` |
| Dispatch evidence | **Reuse** | Existing lane run-state directory | `.architect-team/data-eng/<slug>/` |

No new third-party Python dependency. CT6 stays stdlib-only.

## Risks / Trade-offs

- **False arming from inferred intent** → the inferred path never arms silently; it requires one confirmation, and a decline is recorded. The deterministic marker path is the only silent one.
- **A degraded run looks like a correctly-scoped run** → warn-and-degrade is required to name the missed capability and its remediation in the run report; the spec forbids silence.
- **Upstream drift in the bauplan plugin** (skill renamed or removed) → CT6 references the plugin by id and marketplace, never by copying its content; a missing skill degrades to the generic path rather than erroring. The skill-to-phase table is documentation and is checked by the instruction-compliance lint for internal reference integrity only.
- **`bauplan_project.yml` in a fixture or example directory arms a non-Bauplan repo** → the skip-list exclusions apply, and the eval tier includes a bare-fixture non-arming case.
- **Two tiers invite a future "just add it to REQUIRED_PLUGINS" shortcut** → the disjoint-sets invariant is spec-pinned and unit-tested.

## Migration Plan

Additive; no migration. A run against a non-Bauplan project is byte-identical in behavior to today. Rollback is removing the conditional registry entry — the detector, guidance block, and lane pointers are inert without it.

## Open Questions

None blocking. The specific injection points are decided in D4; the surface review that produced them is recorded there rather than deferred.
