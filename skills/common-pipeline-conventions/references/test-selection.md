> **STOP.** Before any phase runs a test suite -- Phase 3 per slice, Phase 5 against live dev, `mini-review-sweep`, `dev-api-integration-testing`'s full run -- read this file in full and select through `scripts/test_index/cli.py`. Do not work from memory, and do not run "the whole suite" out of habit: the whole suite has exactly one scheduled moment, Phase 8.

# Test selection discipline -- the test index, the selector, the human pins

## The defect this closes

Every gate re-ran every test. Phase 3 captured "full test-suite output" per slice; Phase 5 ran the full integration suite and, since v3.65.0, enumerated `suite-manifest.json` and ran the ENTIRE dev Playwright project; `mini-review-sweep` carried the same whole-suite rule. A one-function fix re-inspected the whole house. The ingredients of a selector already existed, unconnected: `hooks/frontend_impact.py` (change set -> frontend impact), `hooks/lineage_graph.py` (`func://` identities, the runtime-witness trust gate), `suite-manifest.json` (per Playwright test: persona, kind, covered elements). This discipline adds the one missing join -- a test index -- and a selector over it.

## The index

`<workspace>/.architect-team/test-index.json` (`test-index/v1`), built by `scripts/test_index/engine.py`. Per test: `id` (`tests/test_x.py::test_a` or `<spec file>::<test name>`), `file`, `kind` (`unit` / `integration` / `e2e`), `layer` (`backend` / `frontend` / `unknown`), `files` (the repo files the test exercises), `funcs` (`func://` ids, when a lineage graph is present), `endpoints`, `elements`, `duration_s`, `always_run`, `trust`. Sources, each optional past the static pass: the python import graph (parsed with `ast`, resolved to repo files, each module also depending on its enclosing `__init__.py` files and on the repo files its string literals name -- by-path loading such as `load_module(HOOKS / "deploy_config.py")` -- walked transitively at selection time); `suite-manifest.json` (e2e tests, `covers_elements`, the `/api/...` literals in each spec file); `lineage-graph.json` (the `func://` join); `test-witness.json` (the runtime witness). The index also records `import_graph`, so a selection is reproducible from the file alone.

Trust follows the lineage graph's own rule: a **static** mapping is a hypothesis, a **runtime-witnessed** one is evidence, and **unknown** (imports that resolve to no repo file) is neither -- and an unknown mapping means run it.

## The three tiers

| Tier | What runs | Selector call |
| --- | --- | --- |
| **Phase 3** (per teammate, per slice) | The tests selected for the slice's change set, plus the pins, plus every unknown-mapping test. | `select --phase 3 --baseline <slice-base-sha>` |
| **Phase 5** (integration, live dev) | The selected integration tests against the live dev API, plus the impacted flows (`frontend_impact` names them; the selector matches e2e tests by changed endpoint and by touched element), plus the pins. | `select --phase 5 --baseline <run-base-sha> [--changed-elements ...]` |
| **Phase 8** (before the merge to main) | The FULL suite once, every layer, and the prod smoke suite (the `safety: prod` project). Results are recorded as evidence before the merge. | `select --phase 8 ...` returns everything with reason `full-suite-phase` |

"Full every time" becomes "full once per run" -- never "never". The B / M / D / U / P lanes apply the same three tiers at their own commit boundaries.

## The rules

1. **Unknown mapping means run.** A test with `trust: unknown` or an empty `files` list is selected at every phase, with reason `unknown-mapping`. Unknown is not "no tests" -- the same lesson as the completion lock, where silence is not a finding.
2. **Pins are human-owned and never lowered.** `.architect-team-deploy.json` (already agent-immutable) carries `tests.always_run` (ids or fnmatch globs, matched against id and file) and `tests.full_suite_at` (default `["phase-8"]`). `python scripts/test_index/cli.py pins --workspace <ws>` prints them. An agent may read them; it may never remove, narrow, or argue one away. Wanting a pin changed is a question for the user, asked through the existing clarification channel.
3. **The selection record is evidence.** Every `select` writes `<workspace>/.architect-team/test-selection-<ts>.json` (`test-selection/v1`): the phase, the baseline, the changed files, every selected test with its reasons, `skipped_count`, `full_suite`. The Phase 3 and Phase 5 evidence files CITE that record's path next to the test-run output; a test-run claim with no selection record behind it is an unbacked claim.
4. **The full suite at Phase 8 is not selectable.** Phase 8 -- and any phase the human lists in `full_suite_at` -- returns every test with reason `full-suite-phase`. No flag on the selector narrows it.
5. **Select, then run through the existing monitor.** The selector decides WHAT runs; `test-run-monitor` still runs it, records the output, and names which selection record it ran. A selection that was never executed verifies nothing.

## The commands

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" build  --workspace <ws> [--e2e-dir e2e] [--lineage-graph P] [--witness P] --json
python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 3 --baseline <sha> --json
python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" select --workspace <ws> --phase 5 --changed-files src/a.py web/src/Cart.tsx --changed-elements cart__summary__checkout__1 --json
python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" stats  --workspace <ws> --json
python "${CLAUDE_PLUGIN_ROOT}/scripts/test_index/cli.py" pins   --workspace <ws>
# the runtime witness (a bootstrap / refresh run, not the default):
python -m pytest -p scripts.test_index.pytest_witness        # from <ws>, with the plugin root on PYTHONPATH
```

`select --baseline` reads `git diff --name-only <sha>..HEAD` plus the porcelain status of uncommitted work; `--changed-files` takes an explicit list; both may be combined. Exit `0` success, `2` usage (no change set, a git failure), `3` an internal failure -- a crash is never an empty selection.

## Bootstrapping

The first run on a codebase builds the index (`build`) and, because every mapping is still static or unknown, runs more than later runs will; the savings begin on the second change. A witness run (`pytest -p scripts.test_index.pytest_witness`) records which repo files each test executed and upgrades those tests to `runtime-witnessed`, replacing their static file lists with observed ones; `build --witness` (or the default `.architect-team/test-witness.json`) folds it in. The witness installs `sys.setprofile` per test, so that run is slower -- roughly two to three times on call-heavy code -- which is why it is a bootstrap / refresh step and not how tests run by default. Rebuild the index whenever the change set is computed; it is cheap (an `ast` pass) and a stale index is the one failure mode nothing else catches.

## The reversal of the v3.65.0 "ENTIRE dev suite" rule

v3.65.0 made Phase 5, `dev-api-integration-testing`'s full run and `mini-review-sweep` enumerate `suite-manifest.json` and run every `dev` entry. That rule is REVERSED by this discipline: Phase 5 runs the selected flows (changed endpoints, touched elements, the pins, every unknown mapping) and the whole dev project runs ONCE, at Phase 8, before the merge. The manifest is still enumerated -- it is what the selector reads -- and a failing registered flow still routes as a solution requirement exactly as before. Absent a suite manifest, the e2e side of the index is empty and behavior for Playwright flows is unchanged.

## Honest boundaries

- **Static graphs miss dynamic dispatch.** The import graph (plus literal file names) does not see plugins loaded by name, DI containers, event buses, paths computed at runtime, or config-driven routing. Those edges exist only once a witness run observed them; until then the affected tests are selected only through a pin or because they are unknown. Phase 8's full run is the safety net for everything the index did not know.
- **Frontend mapping is coarser.** Playwright flows map to endpoints and UI elements, not to functions. A changed frontend file selects e2e tests precisely only when the caller passes `--changed-elements` (from the intuition map); without them the selector selects EVERY e2e test with reason `frontend-change-coarse-mapping`, deliberately erring toward running.
- **The endpoint scan is a literal heuristic.** `/api/...` string literals in the changed files and spec files are matched textually; a route assembled at runtime is not seen.
- **The witness sees one process, one thread, and only code that has a file.** Threads it did not start, subprocesses, browsers and databases are not witnessed; a C extension is one call at the boundary; code generated by `exec` (dataclass methods, namedtuples, some ORMs) carries no file name, so a test that touches only such code observes nothing -- and an empty observation keeps the static mapping rather than replacing it with "nothing".
- **`build` is python-aware only.** Non-python source is reached through the manifest, the lineage graph and the witness, not through an import graph.

## From the constitution stub (moved v4.1.2)

Every gate runs the tests SELECTED for its change set — Phase 3 per slice (`select --phase 3`), Phase 5 the selected integration tests plus the impacted flows (`select --phase 5`) — plus the human-owned pins (`.architect-team-deploy.json` `tests.always_run`) and every unknown-mapping test; the full suite runs ONCE, at Phase 8 before the merge (`select --phase 8` is not narrowable), which REVERSES the v3.65.0 "ENTIRE dev suite at Phase 5" rule on purpose. Every selection writes a `test-selection-<ts>.json` record the evidence file cites; an agent never lowers a pin. The B / M / D / U / P lanes apply the same three tiers at their own merge boundaries.
