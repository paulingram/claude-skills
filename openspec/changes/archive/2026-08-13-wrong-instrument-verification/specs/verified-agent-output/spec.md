# verified-agent-output

## ADDED Requirements

### Requirement: A claim's cited instrument must be able to discriminate that claim
A Layer-3 tool `verify-claim-instrument-binding` SHALL answer, over an agent-authored artifact, the question neither half of `verify-check-can-fail` asks: could the cited instrument have produced a DIFFERENT result if this specific claim were false? A check may read real output and be falsifiable in general and still be blind to the one claim it is cited for; the failure is named **the borrowed green** — a real check's real green, lent to a claim the check never measured.

The artifact SHALL carry claims the agent AUTHORED, never claims the tool inferred from existing evidence. Inferring what was asserted would reproduce this defect one level up — the tool would measure a reconstructed claim rather than the claim made, and a false positive against an assertion the agent never made is unanswerable. Each claim SHALL be able to cite its subject paths, its instrument, its assertions, a discriminating witness, and the tree state the measurement was taken over.

The tool SHALL be deterministic and stdlib-only, and SHALL report what it cannot decide as a note rather than as a gap. Where binding is undecidable from the artifact — whether a needle CAN occur without running the renderer, or an assertion's polarity when it is not labelled — the tool SHALL NOT fire, because a Layer-3 tool that blocks on a heuristic gets its kill-switch set, and a gate that is off protects nothing.

#### Scenario: A mutation that leaves the cited test green is a gap
- **WHEN** a claim cites a witness whose mutated run produced the same exit code and the same passing tests as the baseline
- **THEN** the tool reports a gap: the instrument could not have come out differently had the claim been false

#### Scenario: A witness that did not actually change the file is refused
- **WHEN** a mutation witness reports identical baseline and mutated sha256 values for the mutated path
- **THEN** the tool reports a gap, because a mutation that changed nothing proves nothing about the guard

#### Scenario: A measurement over a moving tree does not bind
- **WHEN** a claim's `tree_state` before and after values differ
- **THEN** the tool reports a gap: the instrument was right but the tree it measured is not the tree the claim is about

#### Scenario: An undecidable binding is noted, never failed
- **WHEN** an absence assertion cites no negative-control capture, so whether the needle could ever have occurred is undecidable from the artifact
- **THEN** the tool emits a note naming the blind spot and does NOT report a gap

### Requirement: A review-gate claim of instrument binding is validated when present
The review-evidence schema SHALL accept an OPTIONAL `claim_instrument_binding_review` field taking the same `pass` / `n/a` / `fail` shape as its sibling VAO fields. A `fail` SHALL block task completion; an unrecognized value SHALL block; an `n/a` SHALL require its note field; and an ABSENT field SHALL leave pre-existing evidence valid, so no evidence file authored before this capability becomes invalid.

Registering the field name in the schema's optional-field vocabulary SHALL NOT by itself constitute enforcement — the vocabulary is a list, not a gate, and a field added there and nowhere else is inert. The validation branch that makes a `fail` block is the enforcement, and its presence SHALL be demonstrated by a probe that varies only the field's value against otherwise-complete evidence.

#### Scenario: A failing binding review blocks completion
- **WHEN** review evidence is otherwise complete and carries `claim_instrument_binding_review: "fail"`
- **THEN** the gate refuses completion and names the borrowed green

#### Scenario: Evidence without the field remains valid
- **WHEN** review evidence is complete and omits the field entirely
- **THEN** it validates, because the field is optional and pre-existing evidence must not be invalidated

#### Scenario: An unrecognized value is refused
- **WHEN** the field carries a value outside `pass` / `n/a` / `fail`
- **THEN** the gate refuses completion rather than treating the unknown value as acceptable
