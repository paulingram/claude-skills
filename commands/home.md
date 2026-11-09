---
description: Build, inspect or publish the per-project CT6 homepage (.architect-team/homepage/index.html) — structure, settings, decisions, map freshness, functions, tests and performance in one static page. `--rebuild` rebuilds from the current sources, `--stale` reports whether the built page is behind its sources, `--publish` republishes per the project's publish setting. Read-only on the project; writes only under .architect-team/homepage/.
argument-hint: "[--rebuild] [--publish] [--stale]"
---

# /architect-team:home

The project's notice board. One self-contained HTML page, built from the state
files, maps, test registries and timing log that already exist, per the
`project-homepage` skill. This command never runs a pipeline and never touches
the project's own files: its only writes land under
`<workspace>/.architect-team/homepage/`.

## Flags

- *(none)* -> print where the page is, its `built_at`, and whether it is stale
  (the same as `--stale` followed by the path). If no page exists yet, build it.
- `--rebuild` -> rebuild the page from the current sources and print the new
  stamp (`built_at`, sources read, map verdict counts).
- `--stale` -> report only: is the built page behind its sources, since when,
  and which sources moved. Exit is always 0; the verdict is in the output.
- `--publish` -> after building (or rebuilding), publish per the project's
  `.architect-team-publish.json`: `mode: claude` republishes the SAME artifact
  URL via the Artifact tool; `mode: private-url` serves the page at its token
  directory `<base_url>/<slug>/p/<token>/` (never a token-free
  `<base_url>/<slug>/` — a path without a live token is 404 on every adapter
  that checks tokens, per `page-publishing`) through
  `python scripts/publish/publish.py publish <page> --name index`. With
  no publish config, say so and print the local path instead.

Natural-language equivalents: *"show me the project page"* -> no flag;
*"rebuild the homepage"* -> `--rebuild`; *"is the homepage current?"* ->
`--stale`; *"publish the homepage"* -> `--publish`.

## Invocation

Polyglot Python per `common-pipeline-conventions`
`## Cross-platform Python invocation`.

Stale check:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" stale --workspace "$(pwd)" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" stale --workspace "$(pwd)" --json 2>&1
```

Build / rebuild:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "$(pwd)" --json 2>&1 || python "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" --workspace "$(pwd)" --json 2>&1
```

`build` is the engine's default subcommand, so the bare form above and
`build.py build --workspace ...` are the same call; `--out <path>` overrides the
page path. The build prints `out` (the page path), `built_at`, `sources_read` /
`sources_total`, the per-source `hashes`, `stale_before` (what had moved since
the previous build) and `map_verdicts`. Exit `3` means the build failed and
the previous page, if any, is unchanged -- report the stderr line, do not
retry blindly.

## Where the page is

`<workspace>/.architect-team/homepage/index.html`, beside
`build-state.json` (the recorded hashes the stale check compares against).
Both are gitignored derived state: the page is rebuilt from sources at setup,
in Phase -1 after the maps, in Phase 8 by `doc-updater`, and here on demand.
Open it in a browser as a local file; it loads no scripts and no external
resources.

## Related questions

- *"How long will this take?"* -> not this command. Answer from
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/timings.py" estimate --workspace "$(pwd)" --lane <lane>`
  per the `project-homepage` estimate rule: state `basis_n`, refuse below five
  samples, "history, not a promise".
- *"What did we decide about X?"* ->
  `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" list --workspace "$(pwd)"`
  (the Decisions panel renders the same ledger).

## Out of scope

- **Pipeline invocation** -- this command never starts a run and never
  changes run state.
- **Publishing without a publish setting** -- the homepage is a per-project
  opt-in on top of `.architect-team-publish.json`; absent that file, the page
  stays local.
