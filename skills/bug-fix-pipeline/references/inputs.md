# Inputs

`$REQ_DIR` (bound by `/architect-team:bug-fix` from the user's argument) is the **bug**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to the main `/architect-team`:

1. **A requirements folder** — a filesystem path that resolves to an existing directory holding bug-report artifacts, screenshots, prior diagnostic notes, or an OpenSpec brief.
2. **A plain-language requirement** — prose typed directly as the argument: a sentence or paragraph describing the symptom, the user's experience, expected vs. actual behavior. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — **do NOT refuse plain-language prose**, **do NOT treat the first word of a sentence as a path**, **do NOT ask the user for a folder when prose was given**. Ask only when `$REQ_DIR` is genuinely empty. The codebase the bug applies to is the cwd (a git repo) unless the prose explicitly names another path.

**Detect the form:** if `$REQ_DIR` is a single token resolving to an existing directory → form 1 (folder). Otherwise → form 2 (plain-language). When unsure, it is form 2.

**Flags the `/architect-team:bug-fix` command binds and this lane reads.** `--environment production` (B5 escalates before any production deploy), `--no-deploy` (B5 skips the dev deploy and B6b is skipped with a note in the report), `--force-bug` (B0 skips the classifier warning), `--proposal-first` (pause after B3), and — v4.0.0 — **`--full-data`**: sample-first iteration is OFF for the run. Absent the flag (the default), a data defect follows the stratified sample plan at B1 and B6 (`skills/data-eng-pipeline/references/sample-first.md`); with it, B1 replicates and B6 replays against the full table, no sample plan is produced or referenced, and the B7 report records the opt-out. A project principle that forbids sampling has the same effect and is named in the report.
