# fable-default-setup-fixes — delta spec (opus-5-model-upgrade)

## MODIFIED Requirements

### Requirement: Fable 5 service-tier default with injected fallback

`services/common/service_config.py` SHALL set `DEFAULT_MODEL = "claude-fable-5"` and `FALLBACK_MODEL = "claude-opus-5"`, and SHALL provide `resolve_model(preferred, fallback, availability_checker=None)` — returning `preferred` when no checker is injected (the live probe is an adapter boundary) and `fallback` when an injected checker rejects `preferred` — with `build_llm_client` routing through it and the module staying import-clean per `check_separation()`. The module's own prose SHALL name the same generation as the constant: `resolve_model`'s docstring SHALL NOT describe the fallback as a superseded Opus generation while `FALLBACK_MODEL` names a different one.

#### Scenario: no checker prefers fable

- **WHEN** `resolve_model()` runs with defaults and no checker
- **THEN** it returns `claude-fable-5`

#### Scenario: rejecting checker falls back to opus

- **WHEN** an injected checker returns False for `claude-fable-5`
- **THEN** `resolve_model` returns `claude-opus-5`

#### Scenario: constant and docstring name the same generation

- **WHEN** `services/common/service_config.py` is swept for version-bearing Opus prose
- **THEN** no `Opus 4.8` / `Opus-4.8` / `claude-opus-4-8` string remains anywhere in the module, so the docstring cannot contradict the constant

#### Scenario: separation invariant holds

- **WHEN** `check_separation()` runs after the change
- **THEN** `services/common/service_config.py` remains import-clean (stdlib + in-repo only)
