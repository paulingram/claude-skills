# Design — optimize-forcing-gates

## The review that scoped this

"Is this optimal?" splits into settled-by-measurement (keep) and
closeable (build). The dividing rule: a boundary is closeable when the fix
needs no unproven hypothesis and cannot create a wedge or an
unsatisfiable-gate window.

| Item | Verdict | Reason |
|---|---|---|
| existence arm placement | keep | red-by-construction in-suite; measured live |
| re-measure cost | keep | intrinsic — artifact must describe the shipped tree |
| F14 | keep open | unmeasurable (0/707); speculative fix = the documented error |
| settings symlinks | keep open | privilege-blocked four times; recorded untested |
| backing check uninvoked | **build (O1)** | wiring, not hypothesis |
| deleted releases the lock | **build (O2)** | tool-call block, no wedge possible |
| hand-written artifact | **half-build (O3)** | tool layer closeable; authenticity is not |
| clock-decay class | **sweep (O4)** | one-of-two-places applied to the fix itself |

## O1 — why the firing condition has three clauses

Each clause exists because its absence was MEASURED as a failure mode during
the v3.60.0 release:

1. **run-bumped-the-manifest** — without it, every non-release run in this
   repo is compared against the previous release's artifact, whose digest the
   run's own edits have already moved: STALE on every stop, forever. (The
   currency arm is correct at release time and meaningless mid-cycle.)
2. **entry-names-the-manifest** — without it, the arm is red from the moment
   plugin.json bumps until the CHANGELOG entry lands, i.e. red for the whole
   authoring window by construction. This is the same lesson that moved the
   existence arm out of the test suite; blocking the window gets a gate
   switched off.
3. **workspace-carries-the-convention** — the Stop hook runs everywhere;
   without the clause every non-CT6 repo would subprocess a script it does
   not have.

The check itself is delegated to `changelog_check.py --require-measurements`
via a subprocess seam (`_run_backing_check`) — the arms share ONE
implementation with the release CLI, so agreement is structural (the same
decision escape-artist-2's finding C forced on `find_release_artifacts`).
Infrastructure failure fails open; only a measured violation blocks.

## O2 — the wedge analysis

The F9 lesson made wedges the first question, not an afterthought. This arm
cannot wedge: it blocks `TaskUpdate(status="deleted")` only, and every lane
holding an open task can always close it with `status="completed"` (an
unmanifested task completes with no evidence requirement). The block message
names that path. Worker sessions are deliberately NOT stood down — deletion
is never load-bearing for a worker, and a worker-shaped transcript must not
be a bypass costume.

## O3 — what is and is not claimed

Closed: the Edit/Write/NotebookEdit route to authoring or doctoring an
artifact. NOT closed (and stated in the block message itself): Bash writes,
and the fundamental indistinguishability of a hand-written artifact — there
is no trusted signer in this environment. The rule converts forgery from an
available accident into a deliberate act on a named surface.

## Defects produced while building (the honest ledger)

1. **O2's first cut un-gated TaskUpdate from arm 1** — early return instead
   of additive fall-through. The one-of-two-places shape, mine, caught by the
   pre-existing `test_blocks_build_and_dispatch_tools_allows_setup_tools`
   pin before it shipped. Fixed additive; now pinned from both files.
2. **Heredoc mangling, twice more** (a `\\x` escape and a `\\n` in appended
   test code) — the recurring environment trap; both caught at collection
   time, both fixed by switching to the file tools. No shipped effect.
3. **O3's first witness run used multi-line anchors against CRLF** — witness
   invalid, not code wrong; re-run with single-line anchors, then
   function-scoped spans for the two anchors the sticky arm duplicates.
4. **O1's subprocess calls shipped without pinned encodings** — all three
   `text=True` calls decoded with the locale codec, mojibake under cp1252.
   Caught by the house suite gate `test_subprocess_encoding` on the full-suite
   probe (A7); fixed to `encoding="utf-8", errors="replace"` before commit.
