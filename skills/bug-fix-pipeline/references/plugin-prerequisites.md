# Plugin prerequisites (v3.9.0)

**superpowers is a CONDITIONAL plugin (v4.0.0; it was a hard dependency from v3.9.0 to v3.67.0).** A pre-flight check still runs as the very first action of this pipeline and resolves availability either way: (a) `~/.claude/plugins/installed_plugins.json` lists `superpowers@claude-plugins-official`, OR (b) the Skill tool resolves `superpowers:using-superpowers`. When it is present the lane uses the superpowers skills named below. When it is absent the lane does NOT abort: it prints one line naming the gap and the install remediation (`/plugin marketplace add claude-plugins-official` then `/plugin install superpowers`), records `methodology: native` in `intake-state.json`, and runs the same disciplines in their native form per `skills/common-pipeline-conventions/references/native-methodology.md`. The same rule covers `cartographer` (native mapping fallback in that chapter) and the retired `ralph-loop`, whose job the `ct6-converge` workflow does (`skills/common-pipeline-conventions/references/converge-workflows.md`). The canonical source of truth is `common-pipeline-conventions` `## Uniform plugin usage (v3.9.0)`.

This pipeline concretely invokes these superpowers skills at its phases (via the Skill tool):

- `superpowers:brainstorming` — design / intake (Phase B3 proposal authoring, before drafting the fix design).
- `superpowers:test-driven-development` — implementation (Phase B2 reproduction-as-regression-test + Phase B5 implement, before writing the fix code).
- `superpowers:systematic-debugging` — RCA / diagnosis (Phase B1 replication + Phase B3 diagnostic-research-team, before proposing any fix).
- `superpowers:verification-before-completion` — review / completion gates (Phase B6 QA replay + Phase B7 archive, before claiming the bug resolved).

**Precedence.** User `CLAUDE.md` / `AGENTS.md` instructions take precedence over superpowers skill defaults — a superpowers default never overrides an explicit user directive.
