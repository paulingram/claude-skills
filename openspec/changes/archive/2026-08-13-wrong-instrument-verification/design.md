# Design: wrong-instrument-verification

## Context

The failure being fixed is narrow and easy to mis-locate. It is not a lying agent, not broken
code, and not an unfalsifiable check. In all five witnesses the check **ran**, was **green**, read
**real output**, and could fail in general. It simply could not have come out differently if the
claim had been false. The name adopted for it is **the borrowed green**: a real check's real green,
lent to a claim the check never measured.

## Reuse Decisions

| New thing proposed | Decision | What it reuses instead |
|---|---|---|
| A new eighth ETHOS principle | **REJECTED** | Principle 7 sharpened with one clause, plus a fourth Evidence-integrity sub-rule |
| A new ETHOS section for the discipline | **REJECTED — it would have been INERT** | The compiled principles one-liner, the only surface that reaches agents |
| A judgment-based "does this feel verified" check | **REJECTED** | A deterministic Layer-3 tool over an agent-supplied artifact |
| The falsifiability check | **EXTEND, not duplicate** | `hooks/vao/check_integrity.py` already answers two of the three questions |
| The tool's plumbing | **REUSE** | `hooks/vao/core.py` verdict helpers + the `hooks/vao_tools.py` facade and CLI |

## Decision: sharpen principle 7 — and the reason a section would not have worked

The instinctive fix was a new ETHOS section naming the failure. **Measurement showed that would
have reached nobody.** Of the 39 agents:

- **39/39** carry principle 7's compiled one-liner.
- **39/39** carry the Evidence-integrity sub-rules — but folded in as *clauses inside that
  one-liner*, not as sections.
- **0/39** carry any sub-rule *heading*.

A standalone section in `docs/ETHOS.md` is read by a human maintainer and by nothing else in the
runtime. The only surface that reaches every agent is the compiled block, and the only established
mechanism for extending it is a clause. So the change is: one clause on principle 7's compiled
one-liner, principle 7's full body extended to match, a fourth Evidence-integrity sub-rule, and a
recompile — verified afterwards by counting the agents that actually carry the new text, not by
asserting that the edit was made.

That verification step is the discipline applied to its own delivery. Editing `docs/ETHOS.md` and
declaring the principle shipped would have been a textbook borrowed green: the edit is real, the
file is changed, and the instruction reaches no agent.

## Decision: the tool answers the third question, and only the third

`verify-check-can-fail` (v3.47.0) asks two questions — *did the check read anything* (zero-work
scan) and *has this guard ever been shown able to fail* (red-run-first). Both are necessary.
Neither is sufficient, and **every one of the five witnesses passes both unchanged**. W1 in
particular is the clean demonstration: the test read real output, was red-first, and asserted a
string the renderer can never produce.

The third question is: *could the cited instrument have produced a different result if this
specific claim were false?* The tool must answer that mechanically or not at all.

## Decision: honest undecidability beats a tool that flags everything

Some of this class is genuinely undecidable from an artifact. A stated counterfactual is a
prediction, and W1's author would have predicted "break the strip and the test goes red" and been
wrong — only the executed mutation showed green-either-way. Where the binding cannot be decided
mechanically the tool emits an **advisory** finding or nothing at all, and the boundary is named
rather than papered over. A Layer-3 tool that blocks on a heuristic gets its kill-switch set, and
a gate that is off protects nothing.

## Decision: the tool is held to its own standard

A tool built to catch checks that cannot fail, shipped with checks of its own that cannot fail,
would be self-refuting. So each rule carries a mutation witness classified by **exit code** with a
sha256 assertion that the mutated file actually changed — never by parsing a result line, which is
witness W5 and would be a fifth instance of the very defect inside the fix for it.

## Risks

| Risk | Mitigation |
|---|---|
| The tool over-fires and gets disabled | Advisory-by-default where undecidable; an explicit both-directions pin per rule on an honest counterpart |
| The clause bloats 45 compiled surfaces | One clause, ~20 words, measured against the skill byte budget rather than assumed |
| The principle duplicates principle 7 | It IS principle 7 — sharpened in place, not a second principle over the same act |
| The change is declared shipped without reaching agents | Recompile, then COUNT the agents carrying the new text |
| Novelty is overstated | ~80% of these facts are already recorded in principle 7's anti-pattern and the Named lessons; the contribution is the unifying counterfactual rule on the compiled surface, and the record says so |
