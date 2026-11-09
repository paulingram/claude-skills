# Inputs

`$ARGUMENTS` (bound by the `/architect-team` command as `$REQ_DIR`) is the **requirement**. It comes in ONE of two forms — **both are first-class, fully-supported inputs**:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding OpenSpec artifacts, a Superpowers brief, or plain markdown.
2. **A plain-language requirement** — prose typed directly as the argument: a phrase, sentence, or paragraph describing what to build, fix, change, review, or improve. The prose ITSELF is the requirement; it is NOT a path.

A plain-language requirement is fully supported — **Phase 0's `plain` branch normalizes it into an OpenSpec change** (`openspec init` the working repo, derive a `change-name` from the prose, generate the artifact chain). It does not need a folder. Therefore:

- **Do NOT refuse a plain-language requirement.** Never tell the user the pipeline "needs a folder", "drives a requirements folder", or "won't run against a non-existent folder" — it accepts prose directly, and running it is correct.
- **Do NOT treat the first word of a plain-language requirement as a path.** `no`, `review`, `add`, `fix`, `lets` are not directories.
- **Do NOT ask the user for a requirements folder.** Ask the user something at intake ONLY when `$ARGUMENTS` is genuinely empty — then ask what they want built.
- When the requirement is plain-language prose, the **codebase under work** is the current working directory (a git repo) unless the prose explicitly names another path. The requirement says WHAT; the cwd repo is WHERE.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

If `$REQ_DIR` is a **folder** (form 1), it contains one of: **OpenSpec artifacts** (an `openspec/` directory, `proposal.md`, `specs/`, `design.md`, or `tasks.md`); a **Superpowers brief** (Superpowers-formatted metadata/headers); or **plain text / markdown** (anything else describing a feature). If `$REQ_DIR` is a **plain-language requirement string** (form 2), treat it as the `plain` input type directly. Detect the input type before doing anything else — do not assume.
