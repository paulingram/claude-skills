# Phase M0 — Intake

Detect the input form per `## Inputs`. Resolve `$REQ_DIR`:

- Folder form → `$REQ_DIR` is the resolved directory.
- Prose form → write the verbatim prose to `.architect-team/mini/<slug>/prompt.md`; `$REQ_DIR` is that file's directory.

Derive `<slug>` as `YYYY-MM-DD-<lowercase-kebab-of-the-prompt-or-folder-name>` (e.g., `2026-05-26-add-bulk-export`). The slug feeds the Mini-Run trailer at Phase M7.

Create a working branch off `main`:

```bash
git fetch origin
git checkout -b mini/<slug> origin/main
```

If the cwd is not on `main` already, this is fine — the mini variant always branches from the remote's `main` so the auto-merge at M7 has a known base.

**MemPalace wake-up.** Already run as the earliest action of Phase M0 per the `## MemPalace wake-up` section above (which references the canonical rule in `mempalace-integration` `## Phase A`). Per `mempalace-integration`, persist run artifacts (the OpenSpec bundle, the QA verdicts, the architect's M3 diffs) as the run progresses.

**Front-door bindings go to the decisions ledger (v4.0.0, best-effort, never blocking).** The `appearance_mode` binding made at the top of M0 (`## Appearance-change policy (v3.14.0)`) is appended the moment it is made: `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind appearance --summary "appearance_mode bound to <mode>" --chosen "<mode>" --rejected "<other mode>=<why: flag / prose signal / default>" || python "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "<workspace>" --kind appearance --summary "appearance_mode bound to <mode>" --chosen "<mode>" --rejected "<other mode>=<why: flag / prose signal / default>"`.

**Project principles at intake (v4.0.0, per `project-principles`).** Once per project, before anything in this run binds: when `<workspace>/.architect-team/principles.json` does not exist, run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" default-set --workspace <ws>` (the reuse-first ladder lands as PROPOSED `P-R1`..`P-R4`; proposed never binds). When the user provided a document (markdown / PDF / prose), run `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates <file>`, `Read` the document around every candidate, draft one statement per real principle, and confirm the drafts in ONE `AskUserQuestion` — a DOMAIN gate (the single clarification batch M2 already allows is where it rides); nothing becomes `confirmed` silently. From here the M2 architect brief and both M4 dev briefs carry the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>` under a `Confirmed project principles` heading, exactly as `appearance_mode` is carried.
