# Inputs

`$REQ_DIR` (bound by `/architect-team:data-eng`, or routed in from the main pipeline's Phase −2 when the classifier returns `kind: data-eng`) is the **data-engineering ask**. It comes in ONE of two forms — **both first-class, fully-supported inputs**, identical to `/architect-team`:

1. **A requirements folder** — a filesystem path resolving to a directory holding a data brief, source schemas, a business glossary, a data contract, or an OpenSpec change.
2. **A plain-language requirement** — prose typed directly: *"build the analytics warehouse dbt models"*, *"mine the billing stored procedures into a data dictionary"*. The prose ITSELF is the requirement; it is NOT a path.

The v0.9.17 same-input-forms rules apply verbatim — do NOT refuse plain-language prose, do NOT treat the first word of a sentence as a path, do NOT ask the user for a folder when prose was given. Detect the form: a single token resolving to an existing directory → form 1; otherwise → form 2. When unsure, it is form 2. The codebase the ask applies to is the cwd (a git repo) unless the prose names another path.

**Flags the `/architect-team:data-eng` command binds and this lane reads.** `--proposal-first` (pause after D1), `--appearance` (strict by nature), the commit / push / merge flags D8 reads, and — v4.0.0 — **`--full-data`**: sample-first iteration is OFF for the run. Absent the flag (the default), a transformation that targets a subset of a large table is iterated on the stratified sample plan at D2 (the Sample-first iteration section below); with it, every data step runs against the full table, no sample plan is produced or referenced, and the D8 report records the opt-out. A project principle that forbids sampling has the same effect and is named in the report.
