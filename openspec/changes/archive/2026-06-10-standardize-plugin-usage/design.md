## Context

CT6 depends on four external plugins/tools: superpowers, ralph-loop, cartographer, and openspec (CLI + the `openspec-propose` skill). A review found their invocation is non-uniform across the four pipeline bodies, so a run's behavior depends on which command launched it. This change standardizes that usage and makes superpowers a hard, actually-exercised dependency.

## Goals

- Predictable plugin usage regardless of `mini` or any other call.
- Superpowers is a hard-blocking prerequisite that is concretely invoked at runtime.
- All four plugins verified at setup; absence is a hard block.
- One canonical source-of-truth section all pipelines reference.

## Reuse Decision Log

| Decision | Choice | Rationale |
|---|---|---|
| RD-1 | EXTEND the 4 pipeline bodies + `common-pipeline-conventions` | The pipelines already carry phase prose; add prerequisite + invocation clauses in place. No new skill. |
| RD-2 | REUSE `setup.py` `REQUIRED_PLUGINS` + `check_plugin_presence` | Plugin-presence machinery exists and already exits 1 on absence; extend the set + harden semantics, do not rebuild. |
| RD-3 | REUSE the `vao_tools.py` tool framework | `verify_no_pipeline_bypass` already exists (v2.22.0); broaden its openspec-usage evidence rather than add a new tool. |
| RD-4 | REUSE the ralph-loop `--completion-promise` form | Already the canonical form post-v3.8.0; the task is to remove stale `--max-iterations` and make prose loops explicit. |
| RD-5 | NET-NEW: the `## Uniform plugin usage (v3.9.0)` canonical section | No single home defines the cross-pipeline contract today; this is the only substantially-new prose. |

## Decisions

- **Superpowers "hard-blocking" governs PRESENCE, not override.** The pre-flight aborts when the plugin is absent; it does NOT override user CLAUDE.md/AGENTS.md instructions (the superpowers `using-superpowers` precedence rule stands).
- **openspec-propose identifier** — determined at implementation time from `installed_plugins.json`; if it is only a vendored local skill, a dedicated resolvability check substitutes for a plugin-id entry. Either way absence is a hard block.
- **VAO no-bypass** — openspec usage is evidenced by ANY of: a literal `openspec ` Bash call, an `openspec-propose`/`opsx:propose` Skill invocation, or an `openspec/changes/<name>/` artifact set. A run using none of the three still trips `openspec-bypassed`.

## Risks / Trade-offs

- Hard-blocking superpowers could halt a run where the plugin is uninstalled — acceptable and owner-directed; the abort message is actionable (names the install command).
- Adding `openspec validate`/`archive` to mini lengthens mini runs slightly — accepted for predictability ("regardless of mini or call").
