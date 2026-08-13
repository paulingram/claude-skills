# turn-boundary-completion-lock

## MODIFIED Requirements

### Requirement: Blocking is unbounded and released only by a named kill-switch
The completion lock SHALL NOT consume or honour the no-progress budget that governs the pre-existing arms — repeated no-progress stop attempts SHALL continue to block while open work remains. The lock SHALL honour four named environment kill-switches: a master switch disabling the whole lock, and one switch per source disabling the harness-task-list source, the ask-ledger source, and the turn-output rule independently. Disabling one source SHALL leave the other sources enforcing.

A run held by the lock SHALL NOT be silent. Once the lock has blocked persistently, it SHALL emit a best-effort notification through the existing project notifier so an unattended wedge produces a signal, and it SHALL CONTINUE TO BLOCK — the notification reports the state, it never releases it. The notification SHALL NOT be emitted on every stop, SHALL NOT alter the block message or the exit code, and SHALL NOT advance the continuation guard no-progress counter, because the escalation marker is agent-written and the lock deliberately does not honour it, so advancing the counter would raise the marker without releasing anything and mis-fire the guard once work finally closed. A notifier failure of any kind SHALL be swallowed. The notified state SHALL reset when the lock stops blocking, so a later wedge in the same session notifies again.

#### Scenario: Ten consecutive no-progress stops in an engaged session still block
- **WHEN** an engaged orchestrator session attempts to stop ten times in a row with open work and no progress between attempts
- **THEN** every attempt is blocked; the no-progress budget never allows the stop while open work remains

#### Scenario: Disabling the ledger source leaves the task-list source enforcing
- **WHEN** the ask-ledger kill-switch is set and open harness tasks exist
- **THEN** the ledger source contributes nothing and the stop is still blocked by the harness-task-list source

#### Scenario: A persistently wedged run emits a notification and keeps blocking
- **WHEN** the completion lock has blocked the same session past its notification threshold
- **THEN** a best-effort notification is emitted once, the stop is still refused, and the continuation guard no-progress counter is not advanced

#### Scenario: A notifier failure never affects the block
- **WHEN** the notification path raises, exits non-zero, or the project has no notifier configuration
- **THEN** the failure is swallowed, the block message is unchanged, and the hook returns the same exit code it would have returned with no notifier at all

#### Scenario: An ordinary single block does not notify
- **WHEN** the lock refuses a stop fewer times than the notification threshold
- **THEN** no notification is emitted, because a channel that fires on every ordinary block is one the reader learns to ignore

## ADDED Requirements

### Requirement: The completion lock ground truth is immutable to agents
The unilateral-override guard SHALL refuse an agent `Edit`, `Write`, or `NotebookEdit` whose target is the ask-ledger or any path under the harness task root, so the stopping condition cannot be edited by the party the gate constrains. Matching SHALL resolve the path before comparison, so case-folding, parent-directory traversal, and junction indirection do not bypass it.

The guard SHALL resolve its protected set independently of any value an agent can influence. The harness task-root override SHALL be able to ADD a location to the protected set but SHALL NOT be able to remove the real default root from it — one environment variable must never relocate both the protected store and its protection. The guard SHALL additionally compare filesystem identity, so a hardlink reaching a protected file under a different name is refused. Identity comparison SHALL fail safe: it applies only where both paths exist, an indeterminate result falls back to resolved-path comparison, and the guard SHALL NOT raise. Ordinary writes to unrelated paths SHALL remain unaffected.

#### Scenario: A redirected task root does not unprotect the real one
- **WHEN** the harness task-root override names a different directory and an agent writes to a task file under the real default root
- **THEN** the write is refused, because the protected set is the union rather than only the configured value

#### Scenario: A hardlink under another name is refused
- **WHEN** an agent writes to a path that is a hardlink to the ask-ledger under a different filename
- **THEN** the write is refused on filesystem-identity grounds

#### Scenario: An ordinary unrelated write is allowed
- **WHEN** an agent writes to a source file that is neither the ledger nor under any protected task root
- **THEN** the write proceeds unaffected

### Requirement: Task-supplied text cannot present as enforcement output
Text originating from a task record is attacker-controlled — a task is created through the harness by whoever creates it — and it is rendered into a message the agent reads as authoritative enforcement output. Every such field SHALL be neutralized at the point it enters the message, BEFORE it is wrapped in the emitter's own punctuation: whitespace collapsed to one line, leading bullet and numbered-step shapes stripped, and colon-terminated heading shapes defanged. Neutralization applied only to the fully-assembled line is insufficient, because the emitter's own identifier prefix means a forged bullet is no longer at the start of the rendered string. Neutralization SHALL NOT render an ordinary subject unreadable.

#### Scenario: A task subject carrying a forged instruction section renders inert
- **WHEN** an open task subject contains newlines, a bullet prefix, and a colon-terminated heading imitating the block's own release section
- **THEN** the rendered block shows the subject as inert single-line content and the genuine release section appears exactly once

#### Scenario: An ordinary task subject stays readable
- **WHEN** an open task subject is ordinary prose with no injected shapes
- **THEN** it renders unchanged apart from whitespace collapse

### Requirement: The turn-output implementation is pinned by a characterization corpus
The turn-output classifier's line counters SHALL be named for what each counts, and the arms SHALL be written against the counter whose meaning matches the arm rather than the name nearest to hand — conflating them is the defect that shipped as T4. Any change to the classifier SHALL be gated by a characterization corpus asserting FULL verdict equality, not merely the boolean, across a broad range of turn shapes. The corpus SHALL be capable of detecting a counter substitution; a corpus that stays green when one counter is swapped for another is decoration.

#### Scenario: A counter substitution turns the corpus red
- **WHEN** any arm is rewritten against a different line counter than the one it means
- **THEN** the characterization corpus fails and names the turn shapes whose verdicts moved

#### Scenario: A pure renaming leaves every verdict identical
- **WHEN** the counters are renamed without intending a behaviour change
- **THEN** every corpus input produces an identical returned verdict, including the reported line count and marker set

### Requirement: A run-level completion gate binds only the work of the run that is closing
A gate that aggregates per-slice review evidence SHALL bind only slices belonging to the run now closing. The review-evidence directory is cumulative across every run in a repository, so a newly-introduced gate that reads it wholesale retroactively demands evidence from work completed before the gate existed — blocking a commit over another run's backlog. Ownership SHALL be established from state the run itself produced: a slice claimed by a teammate manifest, or written after the active-run marker's recorded start. Where NEITHER ownership signal is available the gate SHALL retain its full scope rather than disarming, because an under-blocking loop-exit gate is the defect such gates exist to remove. The gate SHALL report how many slices it excluded, so a pass is not mistaken for full coverage.

When a gate requires a live environment, providing that environment is the pipeline's responsibility and not the user's: the run SHALL bring the environment up or execute the configured deploy command, seed the records the flow needs through the application's own create path, and then execute the flow. Escalation SHALL be reserved for a genuine external blocker; presenting the user with a choice that has a recommended option is not an escalation.

#### Scenario: Inherited slices from earlier runs do not block this run
- **WHEN** the review directory holds many frontend slices from previous runs with no verdicts, and this run's own frontend slice has a genuine passing verdict
- **THEN** the gate passes, and reports how many inherited slices it excluded

#### Scenario: The run's own unverified slice still blocks
- **WHEN** this run's frontend slice has no genuine passing verdict, alongside inherited slices
- **THEN** the gate blocks, naming only this run's slice

#### Scenario: With no ownership signal the gate keeps its full scope
- **WHEN** no teammate manifest and no active-run marker exist
- **THEN** the gate evaluates every slice, because unknown provenance must not silently disarm it
