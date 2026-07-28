---
name: delivery-manifest
description: Use at the END of every completed run or piece of delivered work — fired by the close-out of all four pipelines (Phase 8 / B8 / M7 / U9, right after run-continuity mark-complete) and invocable on demand for any finished change. Produces the run's DELIVERY MANIFEST (the "bill of sale") — what problem was solved in plain speak, the testing criteria anyone can use to validate it, and (for a feature) the location of every new element with what each one does — written email-ready so it can be copied straight into a message and sent. If the user provided an example document (a prior delivery note, a company template), the manifest MATCHES ITS VOCABULARY AND LAYOUT. The deterministic engine (scripts/delivery/delivery_manifest.py) gates publishing on content completeness (required sections, per-step expected results, per-element locations, zero placeholders); the manifest embeds into the run_complete email via the notifier's plan-file flag.
---

# Delivery Manifest (the bill of sale)

A run is not delivered when the code merges — it is delivered when the person
who ASKED for it can read one document and know three things without opening
an editor. **What was the problem, in words a stakeholder uses. How do I
check it works. Where does everything new live.** That document is the
delivery manifest, and producing it is the LAST content step of every run.

The goal state is a fully documented bill of sale the user can copy-paste
into an email and send — no rewriting, no "let me clean this up first".

## When this fires

- **Automatically at every pipeline close-out**: main Phase 8, bug-fix B8,
  mini M7 (green path), ux-test U9 — after `--mark-complete`, before the
  `run_complete` notification (the manifest EMBEDS into that email).
- **On demand**: any time the user asks for a delivery summary, bill of sale,
  release note, or hand-off document for completed work — even outside a
  pipeline run (derive from the working-tree diff + conversation instead of
  run artifacts).

## The three pillars (what the manifest MUST carry)

1. **The problem, in basic speak.** One-to-three short paragraphs a
   non-engineer reads and understands — what was broken or missing, and what
   they can now do about it. NO file paths, NO code markup, NO pipeline
   jargon in this section (the engine flags path/code tokens here as
   `jargon-in-plain-speak` advisories). Write it the way you would explain it
   to the person paying for the work.
2. **Testing criteria someone can use to validate.** Numbered steps a person
   OUTSIDE the build team can execute — visit this URL, click this, run this
   one command — and EVERY step carries an explicit expected result, so
   pass/fail needs no judgment call. Derive these from the run's acceptance
   criteria / coverage map / QA-replay artifacts; prefer live-environment
   checks over "run the unit tests".
3. **For a feature — every new element, located.** A table of what was
   released: the location (file path, route, or live URL), the element's
   name, and what that element does. One row per new element; the reader
   should be able to find every new thing the release added from this table
   alone. (For a bug-fix, state what was broken, the user-visible symptom
   that is now gone, and where the fix landed; the elements table is the
   feature-type requirement.)

Plus, when known — the version/run id/date header and any deployment notes
(what was deployed where, or the exact deploy step remaining).

## Template matching (user-provided documents)

If the user provided an example document — a prior bill of sale, a company
delivery-note template, an email they liked — the manifest **matches its
vocabulary and layout**: same section names, same ordering, same tone and
terminology (if their document says "Acceptance checks", the manifest says
"Acceptance checks", not "How to validate"). Sources to check, in order:

1. A document the user explicitly points at in the conversation or intake.
2. A template-shaped file in the requirements folder or repo (names matching
   `*template*`, `*manifest*`, `*bill*`, `*delivery*` — e.g.
   `REQ_DIR/delivery-template.md`).
3. Nothing found — use the engine's DEFAULT layout via `build_manifest`.

With a template, the agent writes the layout itself; the three pillars must
still ALL be present (mapped into the template's own sections), and the
rendered text must pass `validate_text` (substance + zero placeholders).
Record the matched source in the data's `template_source` field.

## The engine (deterministic gate — publishing is conditional on it)

`scripts/delivery/delivery_manifest.py` (stdlib-only):

- Assemble the manifest DATA first (a JSON dict): `title`,
  `delivery_type` (`feature` / `bug-fix` / `improvement` / `docs` /
  `infrastructure`), `problem_statement`, `validation_steps`
  (`[{step, expected}]`), `elements` (`[{location, name, functionality}]`,
  required for features), plus optional `version` / `run_id` / `date` /
  `delivered_summary` / `deploy_notes` / `template_source`.
- `validate` — the completeness gate. ZERO error-severity findings is the
  publishing bar (missing fields, empty steps, steps without expected
  results, features without located elements, and ANY unresolved placeholder
  — TBD/TODO/FIXME and friends — all block). Advisories (`jargon-in-plain-speak`,
  `element-location-unresolved`) are prose-quality pointers to fix, not gates.
- `build` — serialize the default layout (and `--email` for the subject line).

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json <data.json> --repo-root <repo> || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" validate --json <data.json> --repo-root <repo>
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json <data.json> --out <manifest.md> --email || python "${CLAUDE_PLUGIN_ROOT}/scripts/delivery/delivery_manifest.py" build --json <data.json> --out <manifest.md> --email
```

## Output + email wiring

- Write the manifest to `.architect-team/delivery/<run-slug>-manifest.md`
  (the data JSON beside it as `<run-slug>-manifest.json`).
- Embed it into the run's FINAL notification by adding
  `--plan-file <manifest path>` to the existing `run_complete` notifier
  invocation (per `common-pipeline-conventions`
  `## Notifications wiring convention` — best-effort, never blocks). The
  recipient's inbox then carries the complete bill of sale the moment the
  run closes; the file itself is the copy-paste source thereafter.
- Present the manifest (or its path + the email subject line from
  `render_email`) to the user as the run's closing deliverable.

## Honest boundary

The engine guarantees content COMPLETENESS, not prose quality — plain-speak
writing, vocabulary matching, and layout matching are this skill's LLM
judgment. Validation steps are only as good as the run's acceptance
criteria; when the run had no live environment, say so in the steps rather
than inventing a URL. The manifest documents what SHIPPED — it never
substitutes for the doc-currency close-out (`closeout` /
`documentation-currency`), which still runs.
