# Direct teammate-to-teammate messaging

When two teammates need to coordinate (e.g., backend defines a contract, frontend consumes it):

- The owning teammate publishes its result to a known path (e.g., the contract file, plus a brief in `.architect-team/handoffs/<owner>-to-<consumer>.md`).
- The consuming teammate is told in its brief: "Wait for the handoff from `<owner>` at `<path>` before starting tasks T-X, T-Y."
- Every cross-team message MUST be written to `.architect-team/handoffs/<from>-to-<to>-<timestamp>.md` — this is the primary coordination primitive and survives across sessions.
- If the harness exposes a teammate-messaging mechanism (e.g., `SendMessage`), use it as an optional shortcut in ADDITION to (not in place of) the handoff file. The orchestrator does NOT proxy.

### Message payload discipline — the visible channel carries the decision, the file carries the evidence

**`SendMessage` is rendered into the USER's transcript; a final report is not.** That asymmetry is the whole rule. A subagent's return value reaches the Lead privately, but every `SendMessage` — teammate-to-teammate, teammate-to-Lead, escalation — is surfaced to the human watching the run. So the channel's cost is the user's attention, and its payload must be priced accordingly.

**Send the decision and the one fact that forces it. Put everything else in the file.** The handoff / evidence / verdict file is already the primary primitive (above); it is also where measurement belongs. A message that carries the decision AND its full derivation pays the visible cost twice and buries the ask.

| Send in the message | Write to the file, cite by path |
|---|---|
| The decision, refusal, or question — stated first, in one sentence | Tables, matrices, per-arm hashes, row counts, byte ledgers |
| The single number or fact that forces it | The full derivation, the alternatives considered, the search log |
| What you need from the reader, and what is blocked until you get it | Test output, command transcripts, per-file diffs |
| The path to the evidence | Anything the reader does not need in order to answer |

**Do NOT use `SendMessage` for a completion report.** "I finished, here is what I did" belongs in your final report and your evidence file — both already reach the Lead. Reserve the visible channel for what genuinely needs a reader: an escalation, a refusal, a blocking question, a correction to the brief, a cross-team handoff the consumer is waiting on.

This does not weaken escalation. **A teammate that discovers its brief is wrong, or that a mandated approach cannot work, MUST still say so rather than absorbing it silently** — that is the `docs/ETHOS.md` `## Evidence integrity` obligation and it outranks brevity. Say it in three lines with a path, not thirty with a table.

Same rule for the orchestrator writing back to a teammate: a review-gate failure sends the verdict, the one measurement that proves it, and the path to the rest — not the whole reproduction.
