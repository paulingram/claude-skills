# credit-exhaustion-failover — delta spec (credit-failover-to-login)

## ADDED Requirements

### Requirement: Upstream failures are classified, and only hard-credit exhaustion may trigger failover

The gateway surface SHALL expose a pure classifier over an upstream response that returns exactly one of `credit-exhausted`, `rate-limited`, `transient`, or `other`. It SHALL classify HTTP `402`, and bodies matching the hard-credit vocabulary (`insufficient_credit` / `insufficient credits` / `quota_exceeded` / `credit balance is too low` / `billing` / `payment required`, case-insensitively), as `credit-exhausted`. It SHALL classify HTTP `429` as `rate-limited` and HTTP `>= 500` or bodies matching `overloaded` as `transient`. ONLY `credit-exhausted` SHALL be permitted to trigger a failover; `rate-limited` and `transient` are retry-classes and SHALL NEVER trigger one. The `429` status check SHALL be evaluated BEFORE the hard-credit body scan, so a rate-limit response whose body happens to carry quota wording is classified `rate-limited` and never `credit-exhausted`. The classifier SHALL be pure — no I/O, no state — and SHALL tolerate an absent or empty body.

#### Scenario: a 402 fails over

- **WHEN** the classifier is given status `402` with any body
- **THEN** it returns `credit-exhausted`

#### Scenario: a hard-credit body without a 402 fails over

- **WHEN** the classifier is given a non-402, non-429 status whose body contains `insufficient_credit` or `credit balance is too low`
- **THEN** it returns `credit-exhausted`

#### Scenario: a rate limit never fails over even when its body mentions quota

- **WHEN** the classifier is given status `429` with a body containing `quota_exceeded`
- **THEN** it returns `rate-limited`, never `credit-exhausted`

#### Scenario: a server error never fails over

- **WHEN** the classifier is given status `500`, `503`, or `529`, or a body containing `overloaded`
- **THEN** it returns `transient`, never `credit-exhausted`

### Requirement: Credit exhaustion is detected at the seam where CT6 observes the upstream

Detection SHALL be performed by a bounded probe against the live gateway's completion endpoint, reusing the existing completion-probe seam, with the prober injectable so tests never open a socket. A successful completion SHALL report no exhaustion. A failed probe SHALL be classified by the classifier above and reported with the observed status and a body excerpt as evidence. Detection SHALL NOT depend on scanning a gateway log file, because the generated launcher writes no log by default and passive scanning would therefore silently detect nothing on a default install.

#### Scenario: a serving gateway reports no exhaustion

- **WHEN** the detector probes a gateway that returns a normal completion
- **THEN** it reports no exhaustion and no failover is proposed

#### Scenario: a credit-dead gateway is detected with evidence

- **WHEN** the detector probes a gateway whose upstream returns `402`
- **THEN** it reports `credit-exhausted` and carries the observed status plus a body excerpt

### Requirement: Failover returns the user to Claude sign-in auth and makes the change stick

On a confirmed `credit-exhausted` verdict the failover SHALL: remove the gateway env block from the resolved settings.json using the existing merge-preserving remover (unrelated settings keys SHALL survive); record `activated: false` together with a `failover` record carrying at minimum the timestamp and the reason; and revert the agent model policy to uniform fable using the existing lever. It SHALL NOT invent a new auth mode — the resulting posture is the existing subscription/sign-in posture. It SHALL leave `enabled` and the stored provider keys INTACT so that `install --activate` is a clean one-command return. The recorded-state flip SHALL be treated as mandatory rather than cosmetic: because a credit-dead gateway still binds its port and still passes the TCP liveness probe, a failover that stripped the env block WITHOUT clearing the recorded activation would be silently undone by the SessionStart activation heal on the next session.

#### Scenario: failover strips the wire and flips recorded state together

- **WHEN** a failover is applied against a sandboxed state dir and settings file recording an activated api-key machine
- **THEN** the settings.json env block is gone, unrelated settings keys survive, the recorded state has `activated: false` and a `failover` record, `enabled` and the stored keys are unchanged, and the agent policy is uniform fable

#### Scenario: the failover survives the SessionStart activation heal

- **WHEN** the SessionStart activation heal runs against state a failover has just written, with the gateway port still live
- **THEN** no env block is re-applied — the cleared recorded activation suppresses the heal

### Requirement: A rate-limited or transient gateway is never failed over

A detection verdict of `rate-limited`, `transient`, or `other` SHALL leave settings.json, the recorded state, and the agent model policy byte-unchanged, and SHALL report that no failover was warranted.

#### Scenario: a 429 changes nothing

- **WHEN** detection returns `rate-limited` and the failover entry point runs without an explicit force
- **THEN** settings.json, gateway state, and the agent policy are unchanged and the report states no failover was warranted

### Requirement: The failover is surfaced on the status report with its remediation

When the recorded state carries a `failover` record, `status` SHALL name it on the human surface — when it fired, why, and the `install --activate` remediation — and SHALL expose it in the `--json` payload. A machine that has never failed over SHALL keep its existing output with no failover text.

#### Scenario: a failed-over machine says so

- **WHEN** `status` runs against state carrying a `failover` record
- **THEN** the report names the failover, its reason, and the `install --activate` remediation

#### Scenario: a never-failed-over machine is unchanged

- **WHEN** `status` runs against state with no `failover` record
- **THEN** the output carries no failover text

### Requirement: The failover is reachable as a command and at session start

The gateway CLI SHALL expose a `failover` subcommand supporting detect-then-act, a check-only mode that probes and reports while changing nothing, and a force mode that applies the failover without probing. The SessionStart hook SHALL additionally attempt the failover automatically, guarded to fire only when the recorded state is an activated api-key machine, ordered BEFORE the activation heal so a failover that fires in a given hook run is not re-healed in that same run, and failing open on every error path so a session start can never wedge.

#### Scenario: check-only changes nothing

- **WHEN** the `failover` subcommand runs in check-only mode against any machine
- **THEN** it reports the detection verdict and leaves settings.json, state, and the agent policy unchanged

#### Scenario: the hook runs the failover before the activation heal

- **WHEN** the SessionStart hook's entry point runs
- **THEN** the failover attempt is invoked before the activation heal

#### Scenario: the hook fails open

- **WHEN** the SessionStart failover encounters missing state, unparseable state, or an unreachable gateway
- **THEN** it returns no note, changes nothing, and does not raise

### Requirement: Re-activation clears the failover record

An explicit `install --activate` SHALL clear any recorded `failover` record as part of restoring activation, so a machine that has come back does not keep reporting a stale failover.

#### Scenario: re-activation clears the record

- **WHEN** `install --activate` succeeds against state carrying a `failover` record
- **THEN** the resulting recorded state has `activated: true` and no live `failover` record, and `status` reports no failover
