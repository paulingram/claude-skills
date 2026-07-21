# design — docs-currency-v3-42-1

## Approach

Three parallel sweep teams over disjoint doc groups, each: (a) adjudicating every deterministic-scan hit in its group as current-state (fix) vs historical (preserve + disposition), (b) running a dead-pointer extraction+verification over its group (backticked/linked repo paths must resolve), (c) writing a per-doc disposition report to its own run-state file. The orchestrator merges disposition reports into the ledger, runs the verification battery, and dispatches the independent widened-surface audit (producer≠checker).

| Team | Group (non-overlapping) |
|---|---|
| S1 core-docs | README.md, CLAUDE.md, CHANGELOG.md (top entry only), docs/ current set (CODEBASE_MAP, INTEGRATION_MAP, ETHOS, CAPABILITY_INDEX, CHANGELOG_RUBRIC, INSTRUCTION_COMPLIANCE_RUBRIC), commands/architect-team-setup.md |
| S2 living-specs | openspec/specs/**/spec.md (68) + openspec/project.md if present + openspec/AGENTS.md if present |
| S3 wider-surface | phenotypes/*.md, services/*.md, skills/*/references/*.md, skills/*/SKILL.md + agents/*.md + commands/*.md bodies (grep-driven; excluding commands/architect-team-setup.md owned by S1), tests/**/*.md, any remaining walked *.md |

## Rules

1. Stale-current-state ONLY: a hit is fixed only when it asserts a superseded fact AS CURRENT; historical narrative is preserved verbatim. Frozen zones untouched except broken cross-references.
2. Living openspec specs: edits limited to factual currency (versions/counts/paths asserted as current) and dead pointers — requirement/scenario semantics are NEVER altered; `openspec validate --all --strict` must stay green after every edit.
3. Instruction-surface bodies: grep-driven scan only (version/count assertions + cited paths); no body rewrites beyond the narrow fixes; instruction-compliance lint must stay green.
4. Generated docs (CAPABILITY_INDEX.md) are fixed via their generator, never by hand.
5. Every team writes a disposition entry for EVERY doc in its group, including untouched-current ones.

## Reuse Decision Log

| Proposed new thing | Ladder verdict | Decision |
|---|---|---|
| New scanner module | REJECTED — reuse | The deterministic scan is orchestrator grep + the existing `scripts/docs_tooling/changelog_check.py` + `capability_index.py --check` + the instruction-compliance lint; per-team dead-pointer checks are scratch scripts under run state (`.architect-team/`), not repo source. |
| New docs | NONE | This run adds no new doc surface; it corrects the existing one (the CHANGELOG v3.42.1 entry is the only addition, per the append-only convention). |

## Verification

Full pytest suite both encodings; instruction-compliance lint; changelog_check (with 3.42.1); capability_index --check; openspec validate strict; the merged ledger covers all 207 walked docs; independent widened-surface audit verdict pass.
