# Completion-lock follow-ups (post-v3.56.0)

Everything here is **reported, measured, and deliberately not fixed** in v3.56.0.
Recorded so the next run inherits the findings rather than rediscovering them.
Shipped state: `main` @ `bf4a15e`, suite 7215 / 0 / 6.

## Named lessons this run earned

These generalise past the completion lock and are the durable output of the run.

1. **A gate and its instructions are one contract.** The turn-output rule and the
   block message that tells an agent how to comply were written in the same file
   by the same author, and never checked against each other — so the gate refused
   the exact format its own message demanded. Test the pair, not the half.
2. **Pinning both directions of a rule is not the same as pinning that the rule is
   fed the right thing.** Every classifier test handed `classify_turn_output` a
   string directly, so no test could observe that the *wrong string* was being
   selected. Three revisions of thresholds could not reach T1, because T1 was in
   the input.
3. **A witness has to reproduce the real defect, not merely disturb code near it.**
   A T1 mutation that reversed block order still concatenated every block, so the
   narrative survived in the measured text and the mutant escaped — a green
   mutation log with no real witness behind it.
4. **A fix in one arm can silently retire another arm's witness.** The F6
   short-line rule excluded the fixture that the `NARRATIVE_LINE_THRESHOLD`
   mutation depended on. Nothing went red; the log would have read 31/31 with a
   constant unpinned.
5. **Measure before relaying, including your own reviewers.** T4 reached the
   orchestrator framed as pre-existing and independent of T2. It was neither — T2
   created it — and it shipped live for two commits on that framing. The same
   reflex produced a mutation count written from memory. Both were caught by
   counting, not by thinking harder.
6. **An unverifiable number is indistinguishable from an invented one.** Six
   full-suite numbers were taken on trees that were still being edited before the
   freeze-and-hash discipline was adopted. The shipped number is bracketed by a
   diff hash proving byte-identity across the run.

## Open items

### G2 — the turn-output reason is cumulative and cannot be cleared (medium)

`_turn_assistant_text` concatenates every assistant text block since the last
genuine user prompt. That is what closes T1's sign-off evasion, and it is
correct for that. The consequence: once a turn has produced a narrative, every
later Stop in that turn re-measures it. Verified — the agent replies with
exactly the one line of state the block demands and the arm still fires, `lines`
climbing 6, 7, 8. No reply the agent can write clears it, because the offending
text is already in the transcript and cannot be retracted. Only a new genuine
user prompt resets the boundary; the hook's own injected block does not (both
`promptSource=system` and `isMeta` records are excluded from `_genuine_prompts`).

**Severity is lower than it first reads, and the reason matters.** The
turn-output arm is only evaluated when work is already open, so it can never
*cause* a block that would not have happened anyway — the task list is already
holding the turn. What G2 produces is a **misleading block message**: it cites
TURN-OUTPUT RULE at an agent that complied, and prints an instruction that
cannot be satisfied. That is a message-quality defect, not a wedge, and
finishing the work still releases normally.

It is still worth fixing, because "the gate told me to do X, I did X, it still
says do X" is exactly how a user learns to distrust the message and then the
gate. **Fix: measure assistant text added since the PREVIOUS STOP rather than
since the last user prompt.** The guard state already persists per-session. T1's
evasion fix survives untouched — a summary and its sign-off arrive before the
same Stop, so both are new and both get measured.

### G1 — a summary wrapped in a fence is invisible (low)

T4 excludes fenced delimiters and fenced content from `prose_lines`,
`counting_lines` and the marker scan, so all line-based arms see nothing inside a
fence; only the >600-char prose arm still applies. A 4-line summary wrapped in
a fence classifies as `narrative=False`. Confirmed for a plain fence, a
language-tagged fence, a bulleted summary in a fence, and a fenced summary plus
sign-off.

**Deliberately not fixed, and the reasoning is the point.** Fencing a summary is
a deliberate evasion, not a natural shape — unlike T1, where the sign-off *was*
the reported behaviour. An agent that wants out already has cheaper documented
routes (`Bash` writes, `TaskUpdate(status="deleted")`), so this joins them as a
named boundary rather than becoming the next seam.

Two remedies were considered and both create one. Counting fenced lines toward
the absolute ceiling was the adversary's suggestion, made when the ceiling was
~6; G3 then raised it to 12 for a good reason, and a 6-line fenced summary now
passes under it. Scanning markers inside fences to distinguish "summary in a
fence" from "code in a fence" founders on diffs, where `- ` prefixes are both a
bullet marker and ordinary content.

This is the seam pattern stated plainly: **each fix is correct in isolation and
creates the next defect at its seam with an existing arm.** G1 is T4's seam with
fence handling; G2 and G3 are both T1's seam with the line-counting arms.

### Pin sequences, not just strings (spec gap)

Four revisions of both-directions pinning never surfaced G2, because **it is
invisible to any single-text test**. Every pin classifies one string; G2 only
appears as a *sequence of Stops*. For any rule whose input accumulates, "both
directions pinned" is insufficient — pin the sequence: narrative, then
compliance, then assert the arm clears.


### N5b — a wedged run is silent, not just unreleased (medium)

The README states that nothing releases a wedged run automatically, which is
correct and is the point of "unbounded". But that sentence does two jobs, and the
second is incidental: *nothing tells you automatically* either. A run wedged
overnight with nobody watching produces no signal.

Fixable without weakening unboundedness at all: emit a notification at the
no-progress cap **and keep blocking**. `scripts/notify/notify.py` already has a
suitable event type (`issue_discovered`).

**Do NOT** fix this by advancing the continuation guard's counter.
`escalation-pending.md` is agent-written and the lock deliberately does not honour
it (ADV-1), so the marker would appear without releasing anything, and the burned
counter would mis-fire the guard the moment work finally closed.

### T4's neighbour — `prose_lines` vs `line_count` (low, naming)

`prose_lines` now drives three arms; `line_count` only populates the reported
`lines` field. A later change that reintroduces a line-count-based arm should use
`prose_lines` unless it genuinely wants code lines counted. The two are one
careless rename apart, and that confusion is precisely what T4 was.

### N2b — hardlink under another name (low)

The ground-truth guard resolves paths, which closes case-folding, `..` traversal
and junctions. It cannot see a hardlink under a different name; that needs
`st_dev`/`st_ino` identity comparison. Low severity because creating one is a
Bash act, and Bash is already a named boundary.

### N3 — `CT6_TASKS_ROOT` moves the guard's own root (medium)

One environment variable relocates both the gate's ground truth and the guard
protecting it. Documented as a boundary; a fix would need the guard to resolve
its protected set independently of the value under attack.

### F7 — unescaped task text in the block message (low)

A task subject containing newlines and a forged `How this releases:` section
renders as a single bullet, because `_lock_clip` collapses whitespace first — so
structure cannot be spoofed and the real section still appears once. What does
land is instruction-shaped prose inside a message the agent reads as enforcement
output. The mitigation is incidental rather than deliberate. Cheap hardening:
strip bullet-prefix and colon-terminated-heading shapes inside `_lock_clip`.

### Mutation-harness classification (low, tooling)

`mutation-checks-lock-wiring.txt` derives `caught` by parsing the pytest result
line; lock-core's harness derives it from the exit code and additionally asserts
the file actually changed before running. The exit-code design removes the
class of a no-op mutation logging green; the parsing design only detects it.
Convert the weaker artifact.

### The classifier pendulum

Four revisions, each fix creating the next: markers too aggressive → markers too
weak → ceiling with no fence exemption → snippets blocked. The spec now requires
both directions pinned for every arm, but the observation that matters is the
adversary's: *the shapes that keep moving are the ones between the poles, not at
them*. A fifth revision should start by enumerating the middle, not the extremes.
