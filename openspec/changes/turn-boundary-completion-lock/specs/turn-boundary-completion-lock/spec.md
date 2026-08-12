# turn-boundary-completion-lock

## ADDED Requirements

### Requirement: A session cannot end its turn while registered work is open
`hooks/pipeline-completion-audit.py` SHALL evaluate a completion lock in `main()` that is NOT gated behind `_is_real_run`, so it fires in every session including a plain Agent Teams session that never invokes a CT6 pipeline. The lock SHALL be evaluated ABOVE both the non-engaged early return and the no-progress budget's allow-the-stop return, so neither can pre-empt it. While the lock finds open work it SHALL refuse the stop with a structured block naming the open items and the release path. A session with zero open work SHALL be unaffected, and the pre-existing audit arms SHALL keep their existing behaviour and their `CT6_MAX_NO_PROGRESS_STOPS` budget.

#### Scenario: A plain session with open tasks and no CT6 run state is blocked
- **WHEN** the Stop hook runs with a `session_id` whose harness task dir holds at least one task with status `pending` or `in_progress`, and the workspace holds no `.architect-team/` run state
- **THEN** the hook refuses the stop and the block message names the count of open items

#### Scenario: A session with no open work is allowed to stop
- **WHEN** the Stop hook runs and every harness task is `completed` and the ask-ledger holds no unresolved entry
- **THEN** the completion lock contributes no block and the hook exits 0

### Requirement: Blocking is unbounded and released only by a named kill-switch
The completion lock SHALL NOT consume or honour the no-progress budget that governs the pre-existing arms — repeated no-progress stop attempts SHALL continue to block while open work remains. The lock SHALL honour four named environment kill-switches: a master switch disabling the whole lock, and one switch per source disabling the harness-task-list source, the ask-ledger source, and the turn-output rule independently. Disabling one source SHALL leave the other sources enforcing.

#### Scenario: Ten consecutive no-progress stops in an engaged session still block
- **WHEN** an engaged orchestrator session attempts to stop ten times in a row with open work and no progress between attempts
- **THEN** every attempt is blocked; the no-progress budget never allows the stop while open work remains

#### Scenario: Disabling the ledger source leaves the task-list source enforcing
- **WHEN** the ask-ledger kill-switch is set and open harness tasks exist
- **THEN** the ledger source contributes nothing and the stop is still blocked by the harness-task-list source

### Requirement: The ask-ledger is derived from the transcript and accumulates durably
The lock SHALL maintain an ask-ledger of the user's directives at a workspace path under `.architect-team/`. Entries SHALL be derived from the harness-written transcript rather than registered by a model-initiated call, so an agent cannot decline to register a directive. Derivation SHALL be purely additive against the stored ledger: an entry already on disk SHALL NOT be removed or reopened by a later derivation pass that cannot see it, because the transcript reader is tail-capped and a long session's earliest directives fall outside the window. An entry whose resolution is ambiguous SHALL remain open.

#### Scenario: A directive outside the transcript tail window still blocks
- **WHEN** a ledger entry was derived from an earlier turn, the transcript slice available at Stop time no longer contains that turn, and the entry is unresolved
- **THEN** the entry is still counted as open and the stop is blocked

#### Scenario: Re-derivation never removes a stored entry
- **WHEN** a derivation pass runs against a transcript slice containing fewer directives than the stored ledger
- **THEN** the stored entries are preserved and only genuinely new directives are added

### Requirement: A pipeline teammate is held only for work it owns
The lock SHALL identify a pipeline teammate session and SHALL NOT stand it down wholesale. A teammate SHALL be held only for open tasks whose `owner` matches that teammate, so it is never wedged on lanes it has no power to close.

Teammate classification SHALL require a genuine `CT6-TEAMMATE` spawn-brief token. The lock SHALL NOT stand down on the `>= 1500`-char heuristic in `run_continuity.is_teammate_transcript`, because that heuristic fires on the user's own long prompts and would silently disable the entire gate for exactly the sessions it exists to hold. A session classified only by that heuristic, with no resolvable token, SHALL be treated as an ORCHESTRATOR and held on all open tasks.

The token SHALL be resolved from the FIRST inbound record, and an envelope in that position (a teams-mode spawn brief arrives wrapped in `<teammate-message>`) SHALL be accepted. A token appearing in a later, mid-session peer envelope SHALL NOT resolve a name, so an orchestrator cannot adopt a peer's identity to shrink its own obligations.

#### Scenario: A teammate with no owned open tasks may stop
- **WHEN** a teammate session attempts to stop, open tasks exist, and none of them name that teammate as `owner`
- **THEN** the completion lock contributes no block

#### Scenario: A teammate with an owned open task is blocked
- **WHEN** a teammate session attempts to stop and at least one open task names that teammate as `owner`
- **THEN** the stop is refused and the block names that task

#### Scenario: A long user prompt does not stand the gate down
- **WHEN** a session's first prompt exceeds 1500 characters and mentions `.architect-team`, matching the upstream teammate heuristic, but carries no `CT6-TEAMMATE` token
- **THEN** the session is treated as an orchestrator and is held on all open tasks

#### Scenario: A teams-mode spawn brief in an envelope still resolves
- **WHEN** a teammate's spawn brief arrives as the first inbound record wrapped in a `<teammate-message>` envelope
- **THEN** its `CT6-TEAMMATE` name resolves and the teammate is scoped to its own lanes rather than held on every lane

#### Scenario: A mid-session peer envelope cannot supply a name
- **WHEN** an orchestrator receives a later peer message carrying a `CT6-TEAMMATE` token
- **THEN** no teammate name resolves from it and the session remains held on all open tasks

### Requirement: While work is open the turn output is one line of state, not a narrative
While the lock finds open work, it SHALL read the last assistant text block from the transcript and SHALL refuse the stop when that turn ended in a narrative report. A turn SHALL be classified as a narrative when it spans three or more lines OR carries a structural marker — a heading, a bullet list, a bold-label block, or a table. A turn of two or fewer lines carrying no structural marker SHALL NOT be classified as a narrative. The refusal SHALL state the rule so the next turn can comply.

#### Scenario: A formatted report while items are open is refused
- **WHEN** open work exists and the last assistant text block carries a heading or bullet list
- **THEN** the stop is refused and the message states the one-line-of-state rule

#### Scenario: A terse two-line status update is not a narrative
- **WHEN** open work exists and the last assistant text block is two lines with no heading, bullet, bold-label block, or table
- **THEN** the turn-output rule contributes no block

### Requirement: An own-code crash fails open but an unreadable source blocks
An unexpected exception raised inside the completion lock's own code SHALL allow the stop, matching the existing fail-open contract of the hook's top-level handler, so a bug in this code can never wedge a session. A source the lock was asked to read but could not — a malformed task JSON, an unreadable ledger, a permissions error — SHALL NOT be silently treated as empty; it SHALL block and the message SHALL name the source it could not read.

#### Scenario: A malformed task file blocks and is named
- **WHEN** the harness task dir contains a file that is not valid JSON
- **THEN** the stop is refused and the message names that unreadable source

#### Scenario: A crash inside the lock allows the stop
- **WHEN** the completion lock raises an unexpected exception
- **THEN** the hook exits 0 and the failure is surfaced on stderr
