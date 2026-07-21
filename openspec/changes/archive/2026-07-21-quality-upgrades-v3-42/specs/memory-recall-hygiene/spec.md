# memory-recall-hygiene — delta (quality-upgrades-v3-42)

## ADDED Requirements

### Requirement: Recall data envelope

Every MemPalace-sourced text block the plugin renders into a session — the wake-up/search render paths defined by the `mempalace-integration` contract and the SessionStart hook's injected context — SHALL be wrapped in a structural do-not-interpret-as-instructions data envelope at render time.

#### Scenario: rendered recall is enveloped

- **WHEN** any recall render path produces output for session ingestion
- **THEN** the output is wrapped in the recall-data envelope marking it as data, not instructions
- **AND** a test pins the wrapper on each render path

### Requirement: Optional recall allowlist

An optional room/wing allowlist SHALL gate which recalled content renders into pipeline context; the default is permissive (no allowlist configured → behavior unchanged), and with an allowlist configured, out-of-list content SHALL never render.

#### Scenario: allowlist filters recall

- **WHEN** an allowlist is configured and recall includes out-of-list content
- **THEN** the out-of-list content is excluded from the rendered output
- **AND** a test pins both the filtered and default-permissive behaviors

### Requirement: Budgeted digest cache with fail-open staleness

A TTL digest cache SHALL serve recall digests under the run-state directory with per-entity byte caps and a per-injection budget; a `mine` invalidates the affected digest; when the palace is unreachable the cache serves its last digest marked degraded-stale rather than failing.

#### Scenario: warm cache avoids live calls

- **WHEN** a second pipeline start occurs within the TTL
- **THEN** the recall digest is served from cache with zero live wake-up calls, and the cache hit is logged

#### Scenario: budgets and invalidation hold

- **WHEN** a digest exceeds its byte cap or a mine touches its source
- **THEN** the digest is truncated to budget (marked truncated) or invalidated respectively
- **AND** palace-unreachable serves stale content visibly marked degraded
