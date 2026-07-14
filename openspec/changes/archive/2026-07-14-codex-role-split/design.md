# Design — codex-role-split

## Decisions

1. **The split is install-time policy, not ship state.** The committed tree stays uniform `model: fable` (exactly the Opus-fallback precedent): the split is applied on the user's machine by the lever/setup. This keeps every existing model pin verbatim and makes the feature a zero-risk no-op for users without Codex 5.6. The sanctioned split state IS valid frontmatter (`tests/test_agents.py` `VALID_MODELS` gains `codex-5.6-sol`) so a deployed machine sees "drifted from ship state", never "invalid".

2. **Availability is an injected input.** Harness model availability is not knowable from a stdlib script (the SETUP-ADV-1 reasoning that dropped the fable version gate as false precision). The signal is `--codex`/`--no-codex`/`--split codex`/`--auto` + `CT6_CODEX_56_AVAILABLE` — the same injected-availability convention as `service_config.resolve_model`.

3. **Tri-state env semantics, no-signal = no-op.** Truthy ⇒ available; SET-but-falsy ⇒ explicitly unavailable (restore uniform fable); ABSENT ⇒ no signal — every no-signal path (setup with no flags, `--auto` with the var absent) leaves the on-disk state untouched so a manually applied Opus fallback is never silently clobbered. Setup and the lever share these semantics (`resolve_codex_signal` mirrors `codex_signal_from_env`).

4. **Fail-safe classification.** An unclassified stem (e.g. a newly scaffolded agent) defaults to the fable bucket — never to codex — and `--check` surfaces it. The classification itself was adversarially re-derived by 3 independent classifiers (role-first / pipeline-position / family-consistency lenses); majority votes flipped 5 producer-draft calls (reconciler, reference-tracer, structure-adversary, flow-explorer → codex; diagnostic-researcher → fable); the doc-currency writers stay fable per the fail-safe (documentation, not product code).

5. **Never gates.** The setup model-policy row degrades to `warn` (with the manual `--split codex` remediation) on any lever failure or a missing agents directory; `--check-only` never writes.

## Alternatives rejected

- **Probing harness model availability from setup** — false precision; there is no deterministic probe (SETUP-ADV-1 precedent).
- **Committing the split as ship state** — would break ~38 model pins and put codex frontmatter on machines without Codex 5.6.
- **Adding codex to the uniform `--model` vocabulary** — uniform codex would violate the directive (architecture/control/design must stay on fable); refused at the CLI.
- **A new skill/command for the policy** — the setup command already owns model policy (the fable note); one more surface would fragment the deploy story. Counts stay 48/39/23.
