## MODIFIED Requirements

### Requirement: All four plugins are verified at setup

The plugin setup SHALL verify all four prerequisite plugins — superpowers, ralph-loop, cartographer, and openspec-propose — and block on any absence. This blocking rule governs the hard prerequisite set ONLY. Plugins declared in the conditional-dependency tier SHALL also be verified and reported at setup, but their absence SHALL NOT contribute to a non-zero exit; the two tiers are disjoint, and no conditional member may be added to the hard set without an explicit spec change.

#### Scenario: openspec-propose is in the verified set

- **WHEN** `scripts/setup/setup.py` runs its plugin-presence check
- **THEN** the openspec-propose plugin (or its resolvable skill) is part of the verified prerequisites
- **AND** its absence contributes to a non-zero exit

#### Scenario: a conditional plugin's absence does not contribute to the exit code

- **WHEN** `scripts/setup/setup.py` runs its plugin-presence check with all four hard prerequisites present and a conditional-tier member absent
- **THEN** the conditional member is reported absent
- **AND** its absence does not contribute to a non-zero exit

#### Scenario: the two tiers stay disjoint

- **WHEN** the hard prerequisite set and the conditional tier are read
- **THEN** no plugin identifier appears in both
