# Wrong-instrument verification — audit record and follow-ups (post-v3.59.2)

The v3.59.0–v3.59.2 releases named **the borrowed green** (a real check's real green, lent to a
claim the check never measured), shipped it into the compiled principles block, and mechanized it
as the 23rd Layer-3 tool `verify-claim-instrument-binding`.

An independent adversarial audit of the **orchestrator's own claims** ran after v3.59.1 shipped.
Its working file lives at `.architect-team/design/wrong-instrument-discipline.md`, which is
**gitignored** — so its durable content is recorded here, where it survives.

## How the audit itself went wrong first, and why that matters

The audit was commissioned during v3.59.0 and **silently never ran**. Two releases shipped before
anyone noticed. Nothing caught that except re-reading the dispatch: *"I asked someone to check"*
is not evidence that anyone did. That is the same defect the releases are about, one level up — a
verification step believed complete because it was requested.

The auditor also recorded four wrong instruments it hit while auditing, which is the honest shape
of this work: the discipline does not make you immune to the failure, it makes the failure findable.

## What the audit found

| Claim audited | Verdict |
|---|---|
| 39/39 agents carry the clause, on the Evidence-before-assertion bullet | **Confirmed** — and the roster denominator, which the original instrument never measured, was supplied |
| 0/39 agents carry any sub-rule heading (the fact the whole design rests on) | **Confirmed** |
| Suite counts 7360 / 7375 | **Confirmed** by an independent full run; two qualifiers below |
| Layer-3 22 → 23 swept across five surfaces | **Refuted in part** — two surfaces did not receive the sweep |
| R6's `300 users pass validation` pin | Pin confirmed; **over-fire class demonstrated** on the shipped tool |
| "Two defects produced while building it" | **Now understates** — a third surfaced post-ship |

Everything actionable was fixed in v3.59.2 except the items below.

## CLOSED in v3.60.0 — both of them

### Hash brackets are asserted, never recorded — CLOSED

Five suite counts were reported this thread as "frozen-tree, hash-bracketed": 7284, 7305, 7360,
7375, 7386. **No bracket artifact existed on disk for any of them.** The runs happened and the
output was read, but the evidence was the orchestrator's word — unverifiable in either direction,
by anyone, later.

**Fixed by F2.** `scripts/measure/suite_measurement.py` performs a quiescence check, hashes the
tree, runs the suite, hashes again, and writes a durable artifact carrying the before/after diff
hash, the command, the exit code, the counts, and a `source_digest`. It REFUSES to back a release
label on a dirty tree, an open bracket, or a count contradicting its own output — emitting a
`provisional` verdict and exit 3 rather than a number. `changelog_check.py --require-measurements`
makes it a release gate.

**One deliberate departure from the fix sketched above:** artifacts land in `docs/measurements/`,
not `.architect-team/measurements/`. The whole point is evidence that survives, and
`.architect-team/` is gitignored — which is the mistake that made *this document* necessary.

v3.60.0 is the first release in the project's history whose published count has a recorded
measurement behind it.

**Still true, and worth stating:** a hand-written artifact is indistinguishable from a measured
one. The gate makes an unbacked number a deliberate act rather than an accidental one.

### The counts are machine-bound — CLOSED

Five committed tests hard-required gitignored `.architect-team/` fixtures and one skipped without
the local deploy config, so a fresh clone did not reproduce the published number. The auditor
proved this by predicting the pristine-worktree result in advance: **7299 / 5 failed / 7 skipped**,
rising to **7304 / 0 / 7** once the fixtures were restored.

**Fixed by F3.** The affected tests now self-provision their fixtures, so a fresh clone reproduces
the published figure rather than inheriting this machine's leftovers.

## OPEN — the backing check runs only because a human remembers

`changelog_check.py --require-measurements` is the ONLY place the existence arm
bites (the in-suite arm is deliberately lenient, see the boundary below). Nothing
invokes it. It is in the release conventions as prose, and prose is what this whole
document exists because of — *a script nobody runs is the same as a note nobody
reads*, one level up from where v3.60.0 fixed it.

**Fix:** call it from the pipeline's Phase 8 release step / the commit gate, so the
release path runs it rather than the releaser. A single call closes it.

**Not fixed in v3.60.0, deliberately.** The obvious remediation — "wire it into CI" —
was recommended and then measured: this repo has no `.github/workflows`, no
`.pre-commit-config.yaml`, no commit hook. The recommendation named a target that
does not exist, which is the same wrong-instrument shape aimed at a remediation
instead of a claim. The real target is the pipeline's own close-out, and changing a
pipeline skill body is a release, not a footnote.

**Known cost of the mechanism, stated so it is not rediscovered as a bug.** Any
tracked-file edit after a measurement invalidates the artifact (`source_digest`
keys committed content by blob sha), so every doc change costs a full re-measure.
Observed three times during the v3.60.0 release. This is the gate working — the
artifact must describe the tree it shipped — but it makes "one more small doc fix"
a five-minute act, and batching doc edits before the final measurement is the way
to work with it rather than around it.

## Named boundary — an in-suite arm that is vacuous at exactly release time

`tests/test_changelog_rubric.py::test_live_repo_check` asserts
`result["ok"] OR top_version == plugin_version`. The tolerance exists for a real
transient (a suite line still being authored after the bump), but the two versions
ALWAYS match at release — so at the one moment the check matters, its green proves
only that the bump happened, never that the entry carries a suite-total line.

Measured, not theorised: v3.60.0's entry initially carried
`(+241 tests; ...)` instead of the house `(<K> test files)` form. The in-suite arm
was green; `changelog_check.py --require-measurements` reported the violation.

**Decision (v3.60.0), taken deliberately and against one reviewer's advice.** The
existence arm stays OUT of the suite. `plugin.json` is bumped at the START of a cycle
while the artifact can only exist at the END, so the arm is red by construction for
the whole cycle — measured on this very release, where the suite sat red for hours
for exactly that reason. A gate that is red by design during ordinary work gets
switched off, which costs more than it buys.

The reviewer's counter was real and is NOT dismissed: dropping it removes the only
live check that a published count is backed. The proposed resolution was to wire
`changelog_check.py --require-measurements` into CI — **but this repo has no CI, no
pre-commit hook, and no commit path to wire it into.** So the honest statement is
that enforcement is now checklist-strength: a human must run the command. It is in
the release conventions in `CLAUDE.md`; it is not automatic, and calling it a gate
would overstate it.

Evidence it is worth running anyway: on this release it caught a suite-total line in
the wrong house form while the in-suite arm was green.

This is the SAME architecture the existence arm settled on — the flip-prone or
lenient arm stays out of the suite, and enforcement lives in the CLI where it runs
once, deliberately, at release. It is recorded here so nobody reads the in-suite
green as coverage it does not provide. The CLI is the gate; run it.

## CLOSED in v3.59.2

- R6 over-fire on sub-tree runs (`236 passed … for the three pin files` demanded a whole-tree bracket).
- `CODEBASE_MAP` said the vao package holds 15 modules (16) and never named `claim_binding.py`.
- `INTEGRATION_MAP` still said 22 tools and "the 5 pipeline skills".
- README carried a three-release-stale 7222 count under a v3.59.x spotlight.
- The v3.59.0 "two defects" sentence gained a pointer to the third rather than being silently rewritten.
- The `tests/test_skill_references.py` byte-ledger, whose v3.57.0 transition line had been
  **rewritten** rather than appended to, misattributing v3.59.0's bytes to v3.57.0. The gate itself
  was never weakened — the 259290 cap was untouched and both assertions stayed enforced — but the
  ledger lied about which release spent the bytes.
- `docs/ETHOS.md`'s "Evidence integrity (v3.47.0)" heading, which had come to contain a v3.59.0 rule.
- The claim that all five witnesses pass `verify-check-can-fail` unchanged: true, but **vacuous for
  W3/W4/W5**, which add no test file and fall outside that tool's jurisdiction. The demonstration
  carries weight for W1 and W2 only, and now says so.

## Verified clean

- No ETHOS overstatement: the applied text claims no enforcement beyond what shipped, and names
  `verify-check-can-fail`'s boundary accurately.
- The reuse decisions in the archived `design.md` hold — `claim_binding.py` imports `core`'s helpers
  through the house fallback ladder and writes through `_write_verdict`.
- The ~109-byte trim that made room for the clause lost no content; all three trimmed details are
  present, reworded, in `references/local-dev-test-discipline.md`.
- The byte-budget cap was never raised to make a change fit.

## The durable lesson

Three of the defects fixed across v3.59.0–v3.59.2 were **produced while building the fix for that
exact class**, and a fourth — markers silently compiled with a literal backspace byte where `\b`
was intended — was caught only because a test happened to cover it.

The discipline does not prevent the failure. It makes the failure *findable*, and only by someone
who re-runs the assertion. **Principle 2 — the producer is never its own checker — remains the
backstop, not this discipline.**
