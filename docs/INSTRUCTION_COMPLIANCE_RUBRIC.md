# Instruction-Compliance Rubric

> The written standard for "compliant instruction text" in the CLAUDE TEAM SIX
> (internal slug `architect-team`) plugin. It grades every AI-facing instruction
> surface on three **equally-weighted** dimensions. A file's grade is a **pass**
> only when all three dimensions pass — the equal weighting means each dimension
> is independently necessary, so any one failing fails the file.
>
> This document is the CONTRACT. The deterministic half of it — dimension (a) and
> cross-reference validity — is mechanized in
> `scripts/compliance/instruction_compliance.py` and pinned in
> `tests/test_instruction_compliance.py`. Dimensions (b) and (c) are LLM-judgment,
> captured per file in the review sweep at
> `.architect-team/compliance-review/sweep.json`.

## Why this exists

Agent compliance depends on the instruction surfaces being uniform, unambiguous,
and internally consistent. A skill whose frontmatter silently truncates under the
loader ships a trigger the model never sees; a rule stated two ways in two files
lets an agent pick the weaker one; a load-bearing directive phrased as "should
consider" invites the agent to skip it. This rubric makes each of those a
checkable defect rather than a matter of taste.

## Scope — the 112 in-scope files

| File class | Count | Path pattern | Frontmatter | Body title |
|---|---:|---|---|---|
| Skills | 47 | `skills/*/SKILL.md` | required (`name`, `description`) | `# <Title>` H1 |
| Agents | 39 | `agents/*.md` | required (`name`, `description`, `tools`, `model`, `color`) | operating instructions |
| Commands | 23 | `commands/*.md` | required (`description`) | `# /architect-team:<name>` H1 |
| Root instruction | 1 | `CLAUDE.md` | none (plain-doc class) | `# ` H1 |
| Maps | 2 | `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md` | none (plain-doc class) | `# ` H1 |

`CLAUDE.md` and the two maps are the **plain-doc class**: they carry no YAML
frontmatter, so the frontmatter sub-checks of dimension (a) do not apply to them
(they are graded on the remaining dimension-(a) checks — body present, a title
heading, cross-reference validity — plus (b) and (c)).

Out of scope (not graded, per the change's non-goals): `phenotypes/<label>/`
records, requirements / OpenSpec docs, historical `CHANGELOG.md` entries, README
visual styling, and the `scripts/` / `services/` Python engines themselves.

## Grade model

- Three dimensions, **equal weight (1/3 each)**.
- A file's overall grade is **`pass` iff `dim_a == pass AND dim_b == pass AND
  dim_c == pass`**. There is no partial credit: equal weighting is operationalized
  as "each dimension is independently necessary."
- Each dimension's per-file verdict is `pass` or `fail`, with every `fail`
  carrying one or more `findings` — each finding names the dimension, the issue,
  and file-anchored evidence.

---

## Dimension (a) — Structural / format uniformity  **[DETERMINISTIC]**

Every file conforms to the structural contract for its class. This dimension is
**fully machine-checkable** and is the objective floor pinned in the test suite.

### (a.1) Frontmatter shape — skills / agents / commands

1. **Fence + parse.** The file begins with a `---` line, has a closing `---`, and
   the block between them parses under `yaml.safe_load` to a mapping.
2. **The house no-`: ` / no-` #` rule.** Any **unquoted** top-level scalar value
   MUST NOT contain a YAML-significant sequence that makes `yaml.safe_load`
   error or silently truncate the value:
   - `: ` (colon followed by a space) — YAML reads it as a nested mapping and
     raises `mapping values are not allowed here`, or truncates the value at that
     point.
   - ` #` (space followed by a hash) — YAML reads the remainder as a comment and
     **silently drops it**, so the loader receives a truncated value with no error.

   A value that needs either sequence MUST be quoted — single (`'…'`) or double
   (`"…"`) with proper escaping. Correctly-quoted values that contain `: ` or
   `## ` are compliant (e.g., a double-quoted `argument-hint` with escaped `\"`
   is correct, not a finding).

   > Worked failure mode (the exact defect this rule catches): a `description`
   > written `… splits across task-reviewer … Reads the ## QA Guidance section …`
   > loads as only the text up to `Reads the` — the ` ##` starts a YAML comment.
   > The authored 1100+ char description silently becomes ~330 chars and the
   > trigger guidance never reaches the model.
3. **Required fields per class.**
   - **Skill:** `name`, `description`. `name` MUST equal the skill's directory
     name. `description` is a substantive string (> 20 chars).
   - **Agent:** `name`, `description`, `tools`, `model`, `color`. `name` MUST
     equal the file stem. `tools` is a non-empty subset of the valid tool set
     (`Read, Edit, Write, Glob, Grep, Bash, TodoWrite, NotebookEdit, WebFetch,
     WebSearch`) with none of the retired tokens (`LS`, `NotebookRead`, `Task`).
     `model` ∈ {`opus`, `sonnet`, `haiku`, `inherit`}. `color` ∈ the documented
     palette (`red, blue, green, yellow, purple, orange, pink, cyan`).
   - **Command:** `description` (substantive string).
4. **Description length cap — 1024 chars, applied UNIFORMLY to all three
   frontmatter classes, measured on the RAW authored value.** For **skills**,
   1024 is a **real Agent Skills platform loader constraint**: a longer skill
   `description` is silently truncated (or rejected) by the loader, so trigger
   guidance at its end never reaches the model (repo evidence:
   `tests/test_skills.py::SKILL_DESCRIPTION_MAX_CHARS = 1024` and its comment;
   the stated authoring target is ≤ 600, with 1024 the hard structural ceiling).
   For **agents** and **commands** there is **no repo-proven loader cap** (no
   agent/command cap test exists), so 1024 is applied as a **uniform house-style
   ceiling** across those classes for trigger-first authoring consistency — **no
   silent per-file exemptions**. The cap is measured on the **raw authored**
   value (before any ` #` / `: ` loader truncation), so a description that only
   fits under 1024 *because* the (a.1) rule truncated it fails BOTH (a.1) and
   this cap. **Historical calibration record:** at rubric adoption, 7 files
   exceeded 1024 raw — `agents/doc-updater.md` (1381),
   `agents/fix-sensibility-checker.md` (1237), `agents/qa-replayer.md` (1213),
   `agents/mini-qa.md` (1162), `agents/prompt-refiner.md` (1070),
   `commands/mini.md` (1048), `agents/flow-explorer.md` (1046). All 7 were
   remediated by Group D (each trimmed to ≤ 1024); the current corpus has **0**
   over-cap descriptions.

   > **Engine-vs-sweep status of (a.4) — deterministic and ENGINE-CHECKED.**
   > (a.4) is a pure raw-length measurement, so it is deterministically
   > checkable. `scripts/compliance/instruction_compliance.py` implements it
   > (`DESCRIPTION_MAX_CHARS = 1024`, measured on the RAW `description` before any
   > ` #` / `: ` truncation can mask an over-length value) for **all three**
   > frontmatter classes and emits a `frontmatter-description-too-long` finding at
   > > 1024; it is pinned in `tests/test_instruction_compliance.py` (suite green
   > under both cp1252 and `PYTHONUTF8=1`). (At adoption the engine reproduced the
   > 7-file over-cap set above to the file; after Group D remediation it reports 0
   > over-cap corpus-wide.) The skills-only `tests/test_skills.py` cap pin remains
   > as the class-specific backstop. So (a.4) is not a sweep-manual carve-out — a
   > green lint cannot coexist with an over-cap description, and the done-bar holds.

### (a.2) Section structure

- **Skill:** the body opens with a single top-level `# <Title>` H1, followed by
  `## ` sections. A skill that cites other skills/agents/hooks SHOULD carry a
  `## Cross-references` (or equivalent pointer) section, and — where it is the
  canonical home of a discipline or a contract for a `scripts/` engine — say so.
- **Agent:** the body is the agent's operating instructions. The shared
  boilerplate blocks (operating-context / forbidden-git-operations / checkpoint
  discipline) are canonical across all agents; drift is already pinned by
  `scripts/setup/sync_agent_boilerplate.py` and `tests/test_agents.py`, and this
  rubric does not re-assert it.
- **Command:** the body opens with a `# /architect-team:<name>` (or `# /<name>`)
  H1, followed by `## ` sections.
- **Plain-doc class:** `CLAUDE.md` and the maps open with a `# ` H1 and are
  non-empty.

### (a.3) Cross-reference validity

Every citation written in a **recognized reference form** (below) MUST resolve to
a real in-repo target.

**Recognized reference forms (resolve against the real repo inventory).** The
`Checked by` column records the rubric-vs-engine contract: the **path forms** are
machine-checked by `scripts/compliance/instruction_compliance.py` and pinned in
the suite (the deterministic core of dimension (a.3)); the **invoke / bare-name
forms** are **LLM-judgment only** during the review sweep and are deliberately
NOT machine-checked, because they collide with legitimate prose the engine cannot
disambiguate deterministically (the cancel-vocabulary `/architect-team:stop` /
`/architect-team:cancel`, the `/architect-team:inject-webhook` future placeholder,
a `readme-theme=<name>` config key that scans like a token, and agent /
sub-command qualification names in prose). A false positive on those forms would
be an engine bug, so the engine holds the path subset and the sweep judges the rest.

| Form | Resolves against | Checked by |
|---|---|---|
| `skills/<name>` or `skills/<name>/SKILL.md` | the `skills/*/` dirs | **Deterministic** (engine) |
| `agents/<name>.md` or `agents/<name>` | the `agents/*.md` files | **Deterministic** (engine) |
| `hooks/<file>.py` | files under `hooks/` (including `hooks/vao/`) | **Deterministic** (engine) |
| `scripts/<path>.py` | files under `scripts/` | **Deterministic** (engine) |
| `docs/<FILE>.md` | **only** the maps that exist in THIS repo — `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md` | **Deterministic** (engine) |
| `/architect-team:<command>` | the 23 `commands/*.md` stems | **LLM-judgment** (prose-ambiguous; not machine-checked) |
| `` `architect-team:<skill>` `` (Skill-tool addressing) | the 47 `skills/*/` dir names | **LLM-judgment** (prose-ambiguous; not machine-checked) |
| a bare back-ticked skill name (e.g. `` `mempalace-integration` ``) | the `skills/*/` dir names, when the token exactly matches one | **LLM-judgment** (prose-ambiguous; not machine-checked) |

**NOT references — MUST NOT be flagged (documented so a false positive is a
wording fix, never an engine bug):**

- **Target-codebase map names** the plugin *produces* in a user's repo during a
  run — `DESIGN_MAP.md`, `ROUTE_MAP.md`, `INTERACTION_INTUITION_MAP.md`,
  `RESTRUCTURE_PLAN.md`, and illustrative `docs/*_MAP.md` examples
  (`API_DESIGN_MAP.md`, `DATA_DICTIONARY_MAP.md`, …). These are artifacts, not
  files in this repo, so `docs/` resolution is scoped to the two maps that
  actually exist here.
- Runtime-state paths under `.architect-team/**`, `openspec/**` artifacts,
  `~/.architect-team/**`.
- External tools, URLs, package names, and ordinary prose that merely resembles a
  path.
- A not-yet-created skill/agent placeholder the text explicitly marks as
  forthcoming.

**Pass criterion (dimension a):** fence + parse + the no-`: `/no-` #` rule +
required fields (with name match) + raw description ≤ 1024 + a class-appropriate
title/section structure + non-empty body + every recognized-form reference
resolves. Any single miss fails dimension (a).

**Determinism:** every (a) sub-check is deterministic *by nature* (each is a
pure structural or length measurement) and `scripts/compliance/instruction_compliance.py`
implements them — including **(a.4)**, the 1024-char raw-description cap, now
engine-checked for all three frontmatter classes and pinned in
`tests/test_instruction_compliance.py` (see the (a.4) engine-vs-sweep note above).
The single standing carve-out is **(a.3) cross-reference validity**, which is
engine-checked for the **path forms** only; the prose-ambiguous **invoke /
bare-name forms** are LLM-judgment in the sweep (see the `Checked by` column
above) by design, not by omission. `tests/test_instruction_compliance.py` fails
the suite on any finding the engine produces.

---

## Dimension (b) — Terminology + contradiction hygiene  **[LLM-JUDGMENT]**

The instruction corpus reads as one coherent system: one term means one thing,
no file contradicts another, and each load-bearing rule has a single canonical
home.

### (b.1) Term consistency
A term of art (e.g., "canonical home", "review gate", "solution requirement",
"baseline SHA", "confirmed-stub", "plan-approval mode", "dispatch mode") means
the **same thing everywhere it appears**. A file that reuses a term with a
divergent meaning is a finding.

### (b.2) No cross-file contradiction
No two in-scope files give conflicting directives on the same rule. Example
finding shape: file X says a teammate MAY spawn a sibling team, file Y says a
teammate MUST NOT — the two directives cannot both be followed.

### (b.3) Canonical-home discipline
A load-bearing rule is **stated once** in its canonical home and
**cross-referenced** (not silently re-stated with drift) elsewhere. The
established canonical homes include:
- `common-pipeline-conventions` — the cross-pipeline disciplines (git discipline,
  scope discipline, appearance-change policy, run continuity, cross-platform
  Python invocation, no-standing-red, no-end-of-run-deferral, …).
- `team-spawning-and-review-gates` — the review-gate evidence schema, file-scope
  rules, the teammate manifest, solution-requirement schema.
- `hooks/review_evidence_schema.py` — the machine ground truth for the evidence
  schema (prose that restates field lists must agree with it).

A rule copied verbatim into a second file with a **materially different**
statement (a changed threshold, a dropped clause, a contradicting default) is a
finding. A short pointer plus a one-line summary that faithfully matches the
canonical statement is compliant — cross-referencing is the intended pattern,
not a violation.

### (b.4) Inventory-count consistency (semi-deterministic sub-check)
Counts stated in prose — skills (47), agents (39), commands (23), phenotypes,
Layer-3 tools (20), hook scripts — are consistent with the real inventory AND
with each other across the in-scope files. This is the historical drift class
(v3.13.0 shipped a fourth phenotype while a store doc still said three); a stale
count is a (b) finding.

**Pass criterion (dimension b):** no term-drift, no cross-file contradiction, no
duplicated-with-drift canonical rule, no stale inventory count that the file
asserts.

**Determinism:** LLM-judgment, except (b.4) which is a countable, evidence-backed
sub-check. Verdicts are captured per file in the sweep and gate remediation; they
are backstopped by the deterministic dimension-(a) cross-reference check (a
contradiction that manifests as a broken reference is also caught deterministically).

---

## Dimension (c) — Literal-imperative wording  **[LLM-JUDGMENT]**

Every **load-bearing** rule is phrased as a followable imperative, not an
ambiguous hedge.

### (c.1) Load-bearing rules are imperatives
A rule that gates behavior — a review gate, a hard boundary, a
"non-negotiable", a MUST/MUST-NOT — is written as a literal imperative
("MUST", "MUST NOT", "do X", "never Y", "always Z"), so an agent reading it has
exactly one followable instruction. A load-bearing rule phrased as a soft modal
("should consider", "might want to", "it's a good idea to", "try to", "ideally")
is a finding, because it invites the agent to treat a gate as optional.

### (c.2) Hedges are allowed only on genuinely advisory guidance
Soft/heuristic wording is **correct** on guidance that is explicitly advisory — a
heuristic, a default the agent may override with judgment, a "honest boundary"
caveat. Such wording is a finding **only** when it lands on a load-bearing rule.
Grading (c) is therefore a two-part judgment: (1) is the rule load-bearing?
(2) if so, is it phrased as a literal imperative? A hedge on advisory text is a
pass.

### (c.3) No self-contradicting imperative
A single directive does not both require and permit the same action (e.g., "you
MUST do X, but you may skip X when convenient" on a gating rule).

**Pass criterion (dimension c):** every load-bearing rule is a literal
imperative; no ambiguous modal sits on a gating rule; no imperative contradicts
itself.

**Determinism:** LLM-judgment. Captured per file in the sweep; backstopped by
dimension (a) (a rule so vague it cites nothing resolvable also surfaces there)
and by the existing pipeline enforcement hooks where a discipline is machine-gated.

---

## Deterministic vs LLM-judgment — summary

| Dimension | Sub-checks | Judged by |
|---|---|---|
| (a) structural/format uniformity | frontmatter shape, no-`: `/no-` #` rule, required fields, description cap, section structure, cross-reference validity | **Deterministic** — `scripts/compliance/instruction_compliance.py` + `tests/test_instruction_compliance.py` |
| (b) terminology + contradiction hygiene | term consistency, no contradiction, canonical-home discipline | **LLM-judgment**; (b.4) inventory-count is a countable sub-check |
| (c) literal-imperative wording | load-bearing rules are imperatives, hedges only on advisory text, no self-contradiction | **LLM-judgment** |

## How a grade is recorded

Each in-scope file gets one entry in `.architect-team/compliance-review/sweep.json`:

```json
{
  "file": "skills/<name>/SKILL.md",
  "dim_a": "pass",
  "dim_b": "pass",
  "dim_c": "pass",
  "grade": "pass",
  "findings": [
    { "dim": "a", "issue": "<what>", "evidence": "<file-anchored proof>" }
  ]
}
```

`grade` is `pass` iff all three dimensions pass. Findings feed the remediation
worklist (`.architect-team/compliance-review/remediation-worklist.json`), ordered
by wave. A dimension-(b)/(c) finding that instruction WORDING alone cannot hold —
a rule agents keep violating despite clear, correct text — is additionally
recorded in `.architect-team/compliance-review/named-enforcement-gaps.json`, which
is the trigger list for a conditional `hooks/` enforcement change (an empty list
is a valid and expected outcome: enforcement is never added speculatively).

## Cross-references

- `scripts/compliance/instruction_compliance.py` — the deterministic engine for
  dimension (a) + cross-reference validity (the machine; this doc is the contract).
- `tests/test_instruction_compliance.py` — the suite pins that fail on any
  dimension-(a) finding across the in-scope set.
- `tests/test_skills.py` / `tests/test_agents.py` / `tests/test_commands.py` —
  the existing frontmatter-presence pins this rubric's dimension (a) extends
  (reusing `EXPECTED_SKILLS` / `EXPECTED_AGENTS` / `EXPECTED_COMMANDS` and
  `tests/helpers/frontmatter.py`, not re-declaring them).
- `skills/team-spawning-and-review-gates/SKILL.md` — canonical home of the
  review-gate evidence schema referenced under (b.3).
- `skills/common-pipeline-conventions/SKILL.md` — canonical home of the
  cross-pipeline disciplines referenced under (b.3).
