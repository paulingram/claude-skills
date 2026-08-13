# Completion-lock follow-ups (post-v3.56.0)

Findings from the adversarial passes, each marked with what actually shipped —
FIXED, NARROWED, or a named boundary. Recorded so the next run inherits the
reasoning rather than rediscovering it, including the remedies that were
measured and **declined**, which are the most expensive thing to re-derive.

Shipped state: `main` @ `e767297`+, suite 7221 / 0 / 6, frozen-tree measured.

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

## Findings and their disposition

### G2 — cumulative turn-output reason (FIXED, but its precondition is UNVERIFIED)

`_turn_assistant_text` concatenates every assistant text block since the last
genuine user prompt — that is what closes T1's sign-off evasion. The side effect
was that once a turn produced a narrative, every later Stop re-measured it: the
agent replied with exactly the one line of state the block demanded and the arm
still fired, `lines` climbing 6, 7, 8, with no reply able to clear it.

**Fixed** by advancing the measurement boundary in-transcript, detected from the
non-genuine `role: user` record the harness feeds a blocked Stop back as, keyed
on this module's own kill-switch names rather than the emitter's prose. Verified
by sequence: narrative -> TRIP, complies -> CLEARS, complies again -> CLEARS.

**The precondition is not verified, and it may make the fix inert.** The boundary
only advances if the harness actually writes the blocked-Stop feedback into the
transcript as a `role: user` record that `load_transcript_slices` can see. A scan
of 38 transcripts across every project on this machine — including long CT6
pipeline runs in which the v3.30.0 continuation guard has certainly blocked —
found **zero** such records. Every apparent hit was a `tool_result`, a skill
body, or a peer `teammate-message`.

That is suggestive, not conclusive: the completion lock itself had never blocked
on this machine before today, and the Stop-hook contract does deliver `reason`
to the model (ralph-loop depends on exactly that), so the open question is
narrowly whether it is *persisted* in the JSONL rather than whether it is
delivered.

**If it is not persisted, G2 is unfixed** — the boundary never advances and the
behaviour is exactly as described above. It degrades to the prior behaviour and
never to something worse. Severity remains bounded either way: `turn_output` is
only evaluated when work is already open, so G2 can never *cause* a block that
would not happen anyway; it produces a misleading message citing a rule the
agent already satisfied.

**Next step: a live check post-install.** Trigger one real block, then grep the
session transcript for the block text as a `role: user` record. If absent, move
the boundary to durable per-session state — but note the constraint that killed
the first attempt: `note_continuation_block` is written only for engaged CT6
runs, so it is empty in the plain sessions this lock exists for, and writing it
from here would reintroduce the F-F pollution in every repo the user types in.

### G1 — a fenced summary evades the line arms (NARROWED, residual pinned)

T4 excluded fenced content from the line arms and the marker scan, so a summary
wrapped in a fence was invisible to everything but the >600-char prose arm.

**Narrowed:** fenced lines now count toward the absolute ceiling, so a fenced
summary trips at >= 12 total lines. **Residual:** a 4-line fenced summary is 6
lines and still evades. Both the fix and the gap are pinned in the suite by
`test_a_fenced_summary_reaches_the_ceiling_when_long_enough`, so the residual
lives in tests rather than only in prose.

**Two candidate remedies were measured and both declined**, and the reason is
the durable part. Counting fenced lines toward a ceiling of ~6 was correct when
proposed — G3 then raised the ceiling to 12 for a good reason and it no longer
reached. Treating "a fence containing markdown markers" as prose was measured
against ten realistic fenced shapes and **misclassified 7 of 9 code samples**: a
unified diff and a git diff (`- old` is both a removed line and a bullet), YAML
(`- name: build`), a shell session with `#` comments, a documentation sample, a
markdown table, and an `ls` listing. Adopting it would reintroduce the T4
false-positive class wholesale — and quoting a diff in a status update is
genuinely common, unlike fencing a summary, which is deliberate.

G1 therefore stays a **named boundary** alongside `Bash` writes and
`TaskUpdate(status="deleted")`: an agent that wants out has cheaper routes.

### G3 — ordinary narration tripped the ceiling (FIXED)

Six one-line narration blocks in one turn — the ordinary shape of an agent
narrating between tool calls — concatenated to 6 prose lines and tripped, on a
turn containing no report at all. T1's seam with T2: `too_many_lines` counted
every prose line while `long_enough` counted only >= 24-char lines.
`NARRATIVE_ABSOLUTE_LINES` raised 6 -> 12, which still catches T2's 30 x 19 with
margin and clears a normal working turn. Switching the absolute arm to
`counting_lines` was rejected because it would un-fix T2.

### H1 / H4 / N-obs — the sixth revision (FIXED, with a stated residual)

A final adversarial pass at `2c7cc5e` found that **G3 was fixed for its witness,
not for its class**. G3 was reported as "six one-line narration blocks" and fixed
by raising `NARRATIVE_ABSOLUTE_LINES` 6 -> 12 — which only ever reached the
short-line arm. The `long_enough` arm counted lines of `>= 24` chars and fired at
`>= 3`, and ordinary narration sentences run 45-60 chars. Measured: three natural
sentences of 59 / 62 / 56 chars -> `narrative=True`. Narrating between tool calls
is the single most common thing an agent does, so with work open every such turn
was refused with an instruction it had already satisfied.

**Fixed by RETIRING the `long_enough` arm entirely.** There is no threshold that
separates "three narration sentences" from "a three-line markerless report" —
they are the same shape, and six revisions of tuning proved it. STRUCTURE is what
identifies a report: the marker arm carries that at `>= 2` lines, and markerless
prose is now caught only by volume (the 12-line ceiling) or length (the 600-char
arm).

**H4 — the marker vocabulary was ASCII-only.** In the 2-line band the marker arm
is the ONLY arm that can fire, so the spec's named catch rested on three exact
characters (`-`, `*`, `+`). A Unicode bullet or an en-dash defeated it, verified.
Widened to the glyphs a model actually emits.

**STATED RESIDUAL (the N-obs band, now wider).** A markerless prose report of
3..11 lines under 600 chars is allowed. This is the accepted, deliberate cost of
not blocking ordinary narration. It is not a defect to be fixed by another
threshold — that is precisely the pendulum that produced six revisions. If a
future run wants it closed, the answer is a different signal, not a different
number.

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
