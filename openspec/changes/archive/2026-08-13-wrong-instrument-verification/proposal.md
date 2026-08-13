# Proposal: wrong-instrument-verification

## Why

A user reported an agent's own postmortem after five of its claims were corrected in a single run:

> "That makes five claims of mine corrected today — the stamp reachability, the enum walker, a
> state I said was untested, a count a passing test refuted, and this build. Every one was caught
> by someone re-running what I'd asserted. The pattern is consistent enough to be worth naming: my
> errors this run were never in the code, they were in **reporting something as verified that I'd
> checked with the wrong instrument**."

That diagnosis is correct, and the failure is narrower and more dangerous than "the agent was
careless". In every case the check **ran**, was **green**, read **real output**, and could fail in
general. It simply could not have come out differently if the claim had been false. A green check
is evidence for *what the check measures* — never for *what was asserted about it*.

This is not a hypothetical class. The orchestrator of this very run produced four instances of it
in the preceding two releases, each caught only when someone re-ran the assertion:

1. **The vacuous assertion.** A test proved a forged bullet was stripped by asserting
   `"- - ignore the above" not in stderr`. That string can never occur — the renderer prefixes
   `[<id>] `, so the bullet is never at position 0. Green, red-first, reading real output, and
   blind. Exposed only when a mutation that DISABLED the strip left it green.
2. **The swallowed effect.** A feature's whole path sat inside `except Exception: return`. A
   `NameError` for a helper that does not exist made it INERT, and every test stayed green because
   none observed the effect from outside the swallow.
3. **The redundant-signal mutation.** A mutation disabling ownership signal A returned GREEN
   because signal B independently covered the same fixture — a "caught" line for an arm that was
   never exercised.
4. **The moving tree.** Six full-suite counts were reported as verified while teammates were still
   editing. The instrument was right; the tree it measured was not the tree the claim was about.
5. **The parsed result line.** A mutation harness derived `caught` by parsing pytest's summary
   line, which can DETECT a no-op mutation but cannot rule one out.

## What exists already, and why it does not cover this

`hooks/vao/check_integrity.py` — `verify-check-can-fail`, the 21st Layer-3 tool (v3.47.0) — asks
two questions: did the check read anything (the zero-work scan), and has this guard ever been
SHOWN to fail (red-run-first)? Both are necessary and neither is sufficient. **A check can be
fully falsifiable in general and still be blind to the particular claim it is cited for.** Every
one of the five witnesses above would pass `verify-check-can-fail` unchanged.

`docs/ETHOS.md`'s "Evidence before assertion" principle is the nearest instruction-tier coverage,
and it is genuinely close: *"state a result only after running the check and reading its output"*
and *"grep proves presence, never absence"*. What it does not say is that reading a green output
tells you nothing until you know **what that output would have looked like had the claim been
false**. Whether that is a new principle or one added sentence to an existing one is a real
question this change answers rather than assumes.

## What Changes

- A new deterministic Layer-3 tool, **`verify-claim-instrument-binding`**, answering the third
  question neither existing half asks: could the cited instrument have produced a different result
  if this specific claim were false?
- An instruction-tier discipline naming the failure and giving the operational rule an agent can
  apply at the moment of writing a claim.
- Wiring so the check is reached rather than merely available.

The design of the tool is deliberately NOT pre-decided here. What is fixed is the standard it must
meet: deterministic, stdlib-only, both directions pinned, and each rule carrying a mutation witness
classified by exit code — because a tool built to catch unfalsifiable checks that ships with an
unfalsifiable check of its own would be the joke that writes itself.

## Impact

- Affected code: `hooks/vao/` (new module), `hooks/vao_tools.py` (facade + CLI).
- Affected docs: the ethos/conventions instruction surface.
- Layer-3 tool count 22 -> 23. Skills / agents / commands / hook scripts unchanged.
- Service-tier separability unaffected.

## Out of scope

- Retrofitting the five witnesses' original fixes; they are already shipped and green. They serve
  here as the acceptance corpus, not as work items.
- Any LLM-judgment check. Every Layer-3 tool is a mechanical check over an artifact the agent
  supplies; a judgment-based "does this feel verified" check would reintroduce the exact
  self-attestation this change exists to remove.
