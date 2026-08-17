## ADDED Requirements

### Requirement: A conditional plugin tier exists and never gates setup

`scripts/setup/setup.py` SHALL declare a conditional-dependency tier, distinct from `REQUIRED_PLUGINS`, whose members are verified and reported but whose absence SHALL NOT produce a non-zero exit from setup or from any pipeline run. The tier SHALL be domain-agnostic: adding a member SHALL require only a registry entry, not new per-plugin code.

#### Scenario: a missing conditional plugin does not fail setup

- **WHEN** `setup.py --check` runs on a machine where every `REQUIRED_PLUGINS` member is installed and the conditional plugin is absent
- **THEN** setup reports the conditional plugin as absent
- **AND** the process exit code is zero

#### Scenario: a missing hard prerequisite still fails setup

- **WHEN** `setup.py --check` runs with a `REQUIRED_PLUGINS` member absent
- **THEN** the exit code is non-zero, unchanged from present behavior
- **AND** the conditional tier's state does not alter that outcome in either direction

#### Scenario: a present conditional plugin is reported as present

- **WHEN** `setup.py --check` runs on a machine where the conditional plugin is installed
- **THEN** setup reports it present, and its row is visibly distinguished from the hard-prerequisite rows

### Requirement: Conditional plugins reuse the existing marketplace-provenance mechanism

A conditional plugin whose marketplace is a third-party source SHALL be registered through the existing `_PLUGIN_MARKETPLACE_SOURCES` mapping, and its remediation SHALL be produced by the existing `plugin_remediation_lines()` helper rather than by new bespoke string-building.

#### Scenario: remediation names the marketplace-add step first

- **WHEN** `plugin_remediation_lines()` is called for a conditional plugin whose marketplace is a third-party GitHub source
- **THEN** the returned lines are, in order, the `/plugin marketplace add <source>` line followed by the `/plugin install <name>@<market>` line

#### Scenario: no duplicate remediation machinery is introduced

- **WHEN** the conditional tier emits install guidance for any member
- **THEN** that guidance originates from `plugin_remediation_lines()`

### Requirement: A run reports a missed conditional capability instead of blocking

When a run detects that a project matches a conditional plugin's applicability trait but the plugin is not installed, the run SHALL proceed with its ordinary generic behavior AND SHALL record, in the run report, both the missed capability and its remediation lines. The run SHALL NOT block, pause, or fail on this condition.

#### Scenario: warn and degrade

- **WHEN** a run's target project matches a conditional plugin's trait and the plugin is absent
- **THEN** the run completes using generic behavior
- **AND** the run report names the missed capability and its remediation lines

#### Scenario: silence is not acceptable

- **WHEN** the same condition holds
- **THEN** the run report SHALL NOT omit the missed capability, since a silently generic run is indistinguishable from a correctly-scoped one
