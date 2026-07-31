# report-claims-citation

## ADDED Requirements

### Requirement: The deferral tool gains four uncited-claim severities
`hooks/vao/deferral.py` (`verify-no-end-of-run-deferral`) SHALL gain four severities scanned over `final_report` and a new OPTIONAL `progress_reports[]` input: `uncited-completion-claim` (completion/delivery/verified markers attached to enumerated items with no citation token), `uncited-deploy-claim` ("deployed and verified"-family phrases with no post-deploy verification citation naming a loaded page / screenshot / semantic assertion), `absence-claim-uncited` (absence markers — "no test exists", "was never implemented", "is missing", "not covered" — whose only cited basis is a grep/search command), and `stalled-agent-claim-uncited` (stalled/idle/left-broken characterizations of an agent with no idle-event or handoff citation). Existing severities and passing inputs SHALL be unaffected (additive).

#### Scenario: Deployed-and-verified off status codes is flagged
- **WHEN** the final report says a revision was "deployed and verified" and the nearest citations name only HTTP status checks
- **THEN** the verdict contains an `uncited-deploy-claim` finding

#### Scenario: Grep-based absence finding is flagged
- **WHEN** the final report asserts "no test exists for X" citing only a grep command
- **THEN** the verdict contains an `absence-claim-uncited` finding

#### Scenario: Cited claims pass
- **WHEN** every completion claim carries a citation token from the extended list
- **THEN** none of the four new severities fire

#### Scenario: Quoting the machinery is mention, not use
- **WHEN** a report QUOTES a forbidden phrase in a mention context — the marker occurrence is quote-enclosed AND the window carries an attribution cue AND the window is prose or names its OWN family's severity id
- **THEN** that family does not fire on the quoted occurrence; a claim dressed in mention clothing (an enumerated status item, a bare severity-id tag without quoting, or attribution-cue stuffing around an unquoted marker) STILL fires — quoting is always required for mention, per-family id scoping prevents cross-family suppression, and the deliberate three-part construction that survives (quotes + cue + own-family id in one enumerated item) is a stated, legible boundary

#### Scenario: Gate matching is token-based with a stated semantic boundary
- **WHEN** two registered gates describe overlapping conditions in similar tokens
- **THEN** the undeclared-gate-language matcher MAY be unable to separate them — token-overlap matching cannot do semantics; this is a STATED boundary of the gate family, mitigated by the documented guidance that ship-gating prose cite `gate_id` explicitly; closing it requires a different mechanism and its own change

### Requirement: The citation-token list is extended to verdict and evidence paths
The disposition-citation token list SHALL be extended to accept verdict-path citations (`.architect-team/vao-verdicts/`, `verdict_path:`), review-evidence citations (`reviews/`, `evidence:`), and post-deploy verification citations, alongside the existing tokens (commit SHAs, `SR-`, `confirmed_stub`, test-run references).

#### Scenario: Verdict path satisfies the citation bar
- **WHEN** a completion claim cites a `.architect-team/vao-verdicts/...` path
- **THEN** it is treated as cited

### Requirement: Gate language with no registry entry is flagged
The scanner SHALL emit an `undeclared-gate-language` finding when the report carries release-gate language ("gates the release", "release gate", "the run that gates") naming a condition with no matching entry in the declared-gates registry.

#### Scenario: Gate named in prose but never registered
- **WHEN** the final report says the full suite against the live URL gates the release and declared-gates.json has no such entry
- **THEN** the verdict contains an `undeclared-gate-language` finding

### Requirement: The delivery-manifest validator enforces evidence citations
`scripts/delivery/delivery_manifest.py`'s `validate` SHALL gain error-severity findings (blocking, per the engine's zero-error gate) for: a validation step whose `expected_result` claims verified/working behavior while the manifest carries no evidence source for it, and a delivered-element entry claiming completion with no citation. Advisory findings remain advisory; existing valid manifests without such claims remain valid.

#### Scenario: Uncited verified claim blocks the manifest
- **WHEN** a manifest validation step claims a behavior is verified with no evidence citation anywhere in the manifest
- **THEN** `validate` reports a blocking error naming the step

### Requirement: The honest boundary is documented where the rules live
The skill text wiring these severities SHALL state the enforcement boundary explicitly: deterministic scanning binds PERSISTED report artifacts (the final report fed to the Phase-8 gate, progress reports passed in, the delivery manifest); the orchestrator's mid-run conversational text is governed by instruction (relay claims as claims, verdicts as facts), not by scanning.

#### Scenario: Boundary stated in the skill
- **WHEN** the delivery-manifest / conventions text for the citation gate is read
- **THEN** it names persisted artifacts as the enforced surface and mid-run chat as instruction-governed
