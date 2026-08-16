# block-menu — delta for agent-directive-block-menu (v3.61.2)

## ADDED Requirements

### Requirement: The continuation block is an agent directive, never user-facing text

The block text SHALL open with an instruction that it is addressed to the
agent and must never be printed, quoted, or paraphrased to the user, and that
the agent must never ask the user which option applies. The finished case
SHALL precede the escalation case, carry a fully-qualified mark-complete
command (absolute script path and `--root <workspace>`, both injected by the
hook), and state that the agent runs it itself without human approval. The
escalation case SHALL be named the only user-facing case.

#### Scenario: the no-relay rule leads

- **GIVEN** any block emission (guard path or lock-composed path)
- **WHEN** the text is built
- **THEN** it forbids relaying to the user before any option is presented

#### Scenario: the exit command is cwd-independent

- **GIVEN** a workspace at any path
- **WHEN** the text is built
- **THEN** the mark-complete command carries `--root` naming that workspace

#### Scenario: order inside the decision procedure

- **GIVEN** the full-form block
- **WHEN** positions are measured INSIDE the decision procedure (not the worklist)
- **THEN** the mark-complete option precedes the escalation option

### Requirement: Consecutive identical blocks are terse

The block SHALL collapse, once the emitting path's existing consecutive
counter reaches 2, to a short form that retains the no-relay rule, the repeat
number, the worklist head with a remainder count, and the fully-qualified
mark-complete command. The counters SHALL be ones that already exist and are
excluded from the progress fingerprint; no new state file may be introduced
for this purpose.

#### Scenario: first block is full, third is terse

- **GIVEN** a wedged workspace and three consecutive real Stop invocations in one session
- **WHEN** the stderr of each is compared
- **THEN** the first carries the full decision procedure, the third the terse form, and every one blocks

#### Scenario: terseness never disarms

- **GIVEN** any repeat count
- **WHEN** the terse form is emitted
- **THEN** the stop is still refused and the exit command is still present
