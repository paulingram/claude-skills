## Why

A codebase review of how CT6 invokes its external plugin dependencies (superpowers, ralph-loop, cartographer, openspec) found the usage is NOT uniform across pipelines, so results differ depending on which command was run:

- **ralph-loop** — the v3.8.0 unbounded-solving change removed the iteration cap, but stale `--max-iterations N` examples survive in `README.md`, `docs/INTEGRATION_MAP.md`, and `openspec/changes/exploration-pipeline/design.md`; two exploration skills express the completion promise in prose rather than the `--completion-promise` flag.
- **superpowers** — declared a required prerequisite but never concretely invoked at runtime ("Superpowers-driven" is decorative framing); its absence is a soft warning, not a hard block.
- **openspec** — the `mini` pipeline skips BOTH `openspec validate` and `openspec archive`; `bug-fix` validates with `--strict` but not `--all`; the `openspec-propose` plugin is unverified at setup; and the VAO `verify-no-pipeline-bypass` tool false-trips `openspec-bypassed` on legitimate mini / `openspec-propose`-skill runs.

The owner directive: issue the fixes, make superpowers a HARD dependency that is actually exercised, verify ALL plugins at setup, and standardize usage so results are predictable regardless of mini or call.

## What Changes

- **Ralph-loop uniformity** — remove every stale `--max-iterations` from actual invocation examples; standardize on `/ralph-loop "<prompt>" --completion-promise "<EXIT>"`; convert the two prose-promise exploration skills to the explicit flag form. (REQ-001)
- **Superpowers as a HARD dependency, concretely invoked** — make the `setup.py` required-plugin check a hard block; add a per-pipeline pre-flight abort gate; wire concrete `superpowers:*` Skill invocations at named phases (brainstorming / TDD / systematic-debugging / verification-before-completion). (REQ-002)
- **OpenSpec gate parity** — `mini` gains `openspec validate --all --strict` + `openspec archive`; `bug-fix` validate aligns to `--all --strict`; identical gates across all implementing pipelines. (REQ-003)
- **Plugin enforcement at setup** — add the `openspec-propose` plugin to the verified prerequisite set; all required plugins block on absence. (REQ-004)
- **Canonical uniform-plugin-usage contract** — a single source-of-truth section in `common-pipeline-conventions` referenced by every pipeline body; fix the VAO `verify-no-pipeline-bypass` tool to recognize the `openspec-propose` skill path + the mini flow. (REQ-005)

## Capabilities

### New Capabilities

- `uniform-plugin-usage`: a standardized, single-source-of-truth contract for how every CT6 pipeline (architect-team / bug-fix / mini / ux-test) invokes its plugin dependencies — ralph-loop (completion-promise form, no cap), superpowers (hard-blocking prerequisite + concrete per-phase invocations), and openspec (identical validate + archive gates) — so behavior is predictable regardless of which command runs.

### Modified Capabilities

None of the existing capabilities' behavioral requirements are weakened. The pipelines gain stricter, uniform plugin-usage gates; the mapping / exploration / phenotype machinery is unchanged.

## Impact

**Affected files:**
- `scripts/setup/setup.py` — hard-block required plugins; add `openspec-propose` to the verified set.
- `hooks/vao_tools.py` — `verify-no-pipeline-bypass` recognizes the `openspec-propose` skill path + mini flow.
- `skills/common-pipeline-conventions/SKILL.md` — NEW `## Uniform plugin usage (v3.9.0)` canonical section.
- `skills/architect-team-pipeline/SKILL.md`, `skills/bug-fix-pipeline/SKILL.md`, `skills/mini-architect-team-pipeline/SKILL.md`, `skills/ux-test-builder/SKILL.md` — superpowers pre-flight + invocations; openspec gate parity.
- `README.md`, `docs/INTEGRATION_MAP.md`, `openspec/changes/exploration-pipeline/design.md`, `skills/data-engineering-exploration/SKILL.md`, `skills/domain-research-team/SKILL.md` — ralph-loop scrub + flag form.
- `tests/` — new structural + behavioral coverage; `.claude-plugin/plugin.json` + `marketplace.json` + `CHANGELOG.md` + `docs/CODEBASE_MAP.md` — version + docs.

**Affected APIs / dependencies:** no new third-party dependency. Markdown skills/bodies + stdlib Python hooks + pytest self-tests; tightens binding to the EXISTING prerequisite plugins (superpowers, ralph-loop, cartographer, openspec-propose).

**Reuse-first decision summary:** EXTEND the existing pipeline bodies + `common-pipeline-conventions` (no new skill); REUSE `setup.py`'s plugin-check machinery, the `vao_tools.py` tool framework, and the existing ralph-loop / openspec conventions. Only the canonical `## Uniform plugin usage` section is net-new prose. Full Reuse Decision Log in `design.md`.
