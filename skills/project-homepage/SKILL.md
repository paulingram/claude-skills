---
name: project-homepage
description: The per-project CT6 homepage -- a static HTML page of structure, settings (keys only), decisions ledger, map freshness, test index, suite manifest, run timings. Rebuilt at setup, Phase -1, Phase 8 (doc-updater), or via /architect-team:home. How-long answers cite the timing log with basis_n, refused under five samples.
user-invocable: false
---

# project-homepage

Every project CT6 works on gets one page: what the codebase is, which switches
are set, what was decided and why, how fresh each map is, which tests exist,
and how long the work has been taking. Nothing on the page is new information;
it is the join over state files that already existed in a dozen places. The
page is **built from sources, never written by hand** -- `scripts/homepage/build.py`
is the only writer, and it records the hash of everything it read.

## What the page is

`<workspace>/.architect-team/homepage/index.html` -- static (no JavaScript, no
external resources), readable at phone width, light/dark through CSS tokens.
Title `<project> · CT6 Home`. Seven panels plus a Runs list:

| Panel | Sources | Empty state |
|---|---|---|
| Structure | top-level tree, `docs/CODEBASE_MAP.md` H2 outline + `last_mapped`, intake codebases | "CODEBASE_MAP.md is missing; Phase -1 produces it" |
| Settings | every `.architect-team-*.json` (keys + set/unset, `human-owned` badge), commit identity (name only), agent model distribution, dispatch/appearance mode, discipline registry | each source named with its `missing` state |
| Decisions | `.architect-team/decisions.jsonl` (`hooks/decisions_ledger.py`) | "each deciding phase appends one line" |
| Maps | the six maps under `<codebase>/docs/` + freshness verdict and basis from `services/knowledge_server/freshness.py` | verdict `unknowable` with the reason when the engine or git is unavailable |
| Functions | `lineage-graph.json`: node counts by kind, edge count, witnessed-edge ratio | "endpoint-trace-mapping produces it" |
| Tests | `.architect-team/test-index.json`, newest `test-selection-*.json`, every `suite-manifest.json` (counts by kind / persona / safety, pins, selection reasons) | "without it every gate runs the full suite" |
| Performance | `scripts/homepage/timings.py stats` over `run-history/timings.jsonl` | "the hooks and the notifier append to it as runs happen" |

The header stamp carries `built_at`, the count of sources read, and a
`<details>` table with each source's path, state, sha256 and mtime. A **stale
since** banner compares the previous build's recorded hashes
(`homepage/build-state.json`) with the sources now; `build.py stale --workspace "$(pwd)" --json`
gives the same verdict from a shell, and the SessionStart hook may call
`is_stale(workspace)`.

**Secrets rule.** The Settings panel renders KEYS and `set` / `unset` only.
The value of a key whose name contains `token`, `secret`, `key`, `password`,
`api` or `auth` is never read into the page, and no other value is rendered
either, except the publish config's `mode` / `adapter` / `slug`. A planted
secret in a config must be absent from the HTML (`tests/test_homepage.py`
asserts it).

## Rebuild moments

The page is only as honest as its last build, so it is rebuilt exactly where
its sources change:

1. **Setup** -- `/architect-team:architect-team-setup` builds the first page as
   the designed empty state (every panel names what will appear there).
2. **Phase -1, after the maps** -- `intake-and-mapping`'s freshness step
   rebuilds once the maps are current, so the Maps panel never shows a
   pre-remap verdict.
3. **Phase 8, by `doc-updater`** -- Step 4's whole-file currency walk ends with
   a rebuild; the page is part of the documentation inventory.
4. **On demand** -- `/architect-team:home --rebuild`; `/architect-team:status`
   prints the page location and its stale verdict.

The call is the same everywhere (polyglot Python per
`common-pipeline-conventions` `## Cross-platform Python invocation`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/build.py" build --workspace "$(pwd)" [--out <path>] --json
```

(`build` is the default verb, so the bare `build.py --workspace ...` form is equivalent; `stale` is the other verb.)

A rebuild never blocks a phase: a build failure is reported (exit 3) and the
previous page stays in place with its own stamp.

## Publishing rule

The page lives on disk first; publishing follows the project's publish
setting (`.architect-team-publish.json`, human-owned):

- **`mode: claude`** -- publish the file through the Artifact tool and
  republish to the SAME artifact URL on every rebuild. The file path is stable
  (`.architect-team/homepage/index.html`), so the link is stable; a rebuild
  never mints a new artifact.
- **`mode: private-url`** -- serve at `<base_url>/<slug>/p/<token>/` (never token-free) via the publish CLI:
  `python scripts/publish/publish.py publish .architect-team/homepage/index.html --name index`
  (the `page-publishing` change owns that CLI; this skill only calls it). The
  slug defaults to the repository name; many projects share one host under
  their own paths.
- **No publish config** -- the page stays local; `/architect-team:home` prints
  the path. Publishing the homepage is a per-project opt-in on top of the
  publish setting, never implied by it.

## The estimate rule for time questions

When the user asks how long something will take -- a run, a phase, an agent,
"a medium bug fix" -- the answer comes from the ledger, not from intuition:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/homepage/timings.py" estimate --workspace "$(pwd)" \
  --lane bug-fix [--phase B3] [--agent backend] [--size medium] [--kind agent|task|phase|run] [--min-n N] [--also-user-level] [--json]
```

(`timings.py stats --workspace <ws> [--group-by lane,phase,agent] [--also-user-level] [--json]` is the Performance panel's source.)

- State `basis_n` (how many recorded intervals the number rests on) and the
  median + p90 it returns, in the words the CLI uses.
- **Below five samples the answer is "no basis yet."** Do not fill the gap
  with a guess, a typical-project figure, or a range from memory. Offer to
  answer once five runs are recorded; `--also-user-level` may widen the basis
  to every project on this machine when the user has turned the mirror on
  (`CT6_TIMINGS_USER_MIRROR=1`).
- Always close with **"history, not a promise"** -- the estimate describes
  past runs of this project, and the run in front of us may differ.

## The decisions-ledger duty

Each phase that already makes a decision appends ONE line to
`.architect-team/decisions.jsonl` at the moment it decides, naming the option
chosen and every option rejected with its reason:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/decisions_ledger.py" add --workspace "$(pwd)" \
  --kind triage --summary "<what was decided>" --chosen "<option>" \
  --rejected "<option>=<why>" --ref <artifact-path>
```

| Phase | `--kind` |
|---|---|
| Phase -2 triage (lane / scope verdict) | `triage` |
| Phase 1 reuse decision log | `reuse` |
| CFP-3 contract approval | `contract-approval` |
| Phase -2 appearance-mode binding | `appearance` |
| principle verdicts | `principles` |
| solution-requirement routing | `sr-routing` |
| any other option chosen over alternatives | `option-choice` |

The ledger is append-only: a reversed decision is a new line that says so.
`run_id` and `phase` default from `intake-state.json`; an unknown `--kind` is
refused, never coerced to `other`.

## Timing-log mechanics (for reference)

`hooks/timings_log.py` writes `run-history/timings.jsonl` (schema `timing/v1`:
`run_id, lane, phase, task_id, agent, model, dispatch_mode, kind, started_at,
ended_at, duration_s, outcome, size_bucket`). Agent intervals come from
`SubagentStart` / `SubagentStop`, task intervals from `TaskCreated` /
`TaskCompleted`, phase and run intervals from the notifier's `phase_*` /
`run_*` / `heartbeat` events (written whether or not email is configured), and
`Stop` closes the run once the active-run marker is no longer active, closing
anything still open as `outcome: unknown`. Intervals are recorded only while a
run is active in the workspace; `CT6_TIMINGS_DISABLED=1` is the kill switch.

## Honest boundaries

- The page is static: it cannot know it went stale after it was built. The
  stale banner describes the PREVIOUS build; `build.py stale` is the live
  check, and a skipped rebuild shows as an old `built_at`, never as a fresh one.
- A map's `current` verdict is change-driven (no path committed since its
  stamp); with no git, no stamp, or no freshness engine the verdict is
  `unknowable`, never a fabricated `current`.
- The timing log measures wall-clock intervals between hook events. A session
  that died mid-interval leaves `outcome: unknown`; an estimate is a median of
  recorded history for THIS project and says so.
- The decisions ledger records what a phase CHOSE to write down; it cannot
  prove a decision was made that nobody recorded.
- Publishing is observed, not enforced: the skill names the rule, the
  publish CLI and the Artifact tool carry it out.
