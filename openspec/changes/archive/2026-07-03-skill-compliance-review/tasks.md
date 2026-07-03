# Task groups are labelled A–E with NON-OVERLAPPING file scopes so groups can run
# in parallel. Dependencies: C depends on B (the engine must exist to pin it);
# D and E depend on A + B (remediation needs the rubric + a working lint; the
# review that A produces is what NAMES any E enforcement gap).

## A. Rubric authoring + review sweep (scope: `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` + review artifacts under `.architect-team/`)

- [ ] A.1 Author `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` — the three equally-weighted dimensions ((a) structural/format uniformity, (b) terminology + contradiction hygiene, (c) literal-imperative wording), per-dimension pass criteria, which dimension is deterministic vs LLM-judgment, and the recognized cross-reference forms (REQ-001)
- [ ] A.2 Run the review sweep across the full in-scope set (47 SKILL.md + 39 agents + 23 commands + `CLAUDE.md` + the 2 maps), recording a per-file three-dimension grade + every finding to remediate (REQ-001), reusing `skills/structure-optimization` / `skills/documentation-currency` / independent multi-reviewer passes where they fit
- [ ] A.3 Consolidate the sweep findings into a remediation worklist keyed by file, and NAME any compliance gap that instruction wording alone cannot hold (the REQ-004 trigger list — may be empty) (REQ-001, REQ-004)

## B. Deterministic lint engine + unit tests (scope: `scripts/compliance/instruction_compliance.py` + engine unit cases in `tests/test_instruction_compliance.py`)

- [ ] B.1 Author `scripts/compliance/instruction_compliance.py` (stdlib-only, no import-time side effects), mirroring `scripts/claude_md/claude_md_efficiency.py`: frontmatter shape (parses under `yaml.safe_load`; the house `: `-in-unquoted-value detector), required-field presence per file class, section-structure expectations, cross-reference validity against the real repo inventory; expose an `assess_*` API + a `__main__` CLI (REQ-002)
- [ ] B.2 Author the engine unit tests: zero findings on the clean in-scope set; a broken cross-reference is flagged; a `: `/unparseable frontmatter is flagged; stdlib-only + no import-time side effects asserted (REQ-002)
- [ ] B.3 Run the engine across the in-scope set and feed any findings back into the group-D worklist (REQ-002)

## C. Test-pin wiring (scope: `tests/test_instruction_compliance.py` suite-level pins + extensions to `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py`) — depends on B

- [ ] C.1 Add the suite-level pin in `tests/test_instruction_compliance.py` running the engine across the full in-scope set and failing on any finding (REQ-003)
- [ ] C.2 Add the `yaml.safe_load` real-parse pin over every in-scope file via `tests/helpers/frontmatter.py` (REQ-003)
- [ ] C.3 EXTEND `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py` conventions without duplicating their frontmatter-presence coverage (reuse the expected-inventory constants + the frontmatter helper) (REQ-003)
- [ ] C.4 Confirm the full suite is green under both Windows cp1252 and `PYTHONUTF8=1` (REQ-003, REQ-005)

## D. Instruction-file remediation waves — disjoint file sets, run in parallel — depends on A + B

- [ ] D.1 Wave 1 — skills 1–24: bring each failing `skills/*/SKILL.md` to a rubric pass + clean lint, in place (REQ-005)
- [ ] D.2 Wave 2 — skills 25–47: bring each failing `skills/*/SKILL.md` to a rubric pass + clean lint, in place (REQ-005)
- [ ] D.3 Wave 3 — all 39 `agents/*.md`: bring each failing agent to a rubric pass + clean lint, in place (REQ-005)
- [ ] D.4 Wave 4 — all 23 `commands/*.md` + `CLAUDE.md` + `docs/CODEBASE_MAP.md` + `docs/INTEGRATION_MAP.md`: bring each failing file to a rubric pass + clean lint, in place (REQ-005)
- [ ] D.5 Re-run the engine across the WHOLE in-scope set after every wave; converge until zero findings and no out-of-scope surface was touched (REQ-005)

## E. Enforcement-gap changes — ONLY for a named gap from A.3 — depends on A + B

- [ ] E.1 For each named text-unenforceable gap (if any): author a stdlib-only, fail-open `hooks/*.py` enforcement script with a `CT6_*_DISABLED` kill-switch, tracing to the named gap (REQ-004)
- [ ] E.2 Wire each new hook in `hooks/hooks.json` via `${CLAUDE_PLUGIN_ROOT}` + the detect-once `$(command -v python3 || command -v python)` shim, no absolute path (REQ-004)
- [ ] E.3 Pin each enforcement change in `tests/test_hooks_structure.py` (wiring) + a dedicated behavior test (fail-open + kill-switch + the gap it closes) (REQ-004)
- [ ] E.4 If A.3 named no text-unenforceable gap, make NO hook change and record that outcome (REQ-004)

## F. Ship (scope: `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` + `CHANGELOG.md` + documentation-currency inventory) — depends on C + D (+ E if it fired)

- [ ] F.1 Bump the version in `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json`; add the `CHANGELOG.md` entry (REQ-005)
- [ ] F.2 Bring the documentation-currency inventory current (CODEBASE_MAP / INTEGRATION_MAP / CLAUDE.md / README as applicable) for the new engine + rubric + test file (+ hook if E fired) (REQ-005)
- [ ] F.3 Final full-suite run green under both cp1252 and `PYTHONUTF8=1` (REQ-005)
