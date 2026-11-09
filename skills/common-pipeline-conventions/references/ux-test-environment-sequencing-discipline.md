# UX-test environment sequencing discipline (v2.13.0)

UX tests MUST run in BOTH environments — **LOCAL first, LIVE DEV last** — in that order. The local pass is fast feedback (debugger, hot-reload, breakpoints); the live-dev pass is real-world verification (the deployed bundle, real env vars, the same URL the user hits). Running tests only locally silently never verifies the deployed code. Running tests only against the live dev URL loses the fast-feedback loop and burns deploy time per iteration.

**Failure shape** (verbatim case in CHANGELOG v2.13.0): *"all my stuff tests locally and never tests the full spectrum"* — UX testing must first occur on local and then finally on the real live dev site, but execution kept hitting `localhost`; the deployed environment was never independently verified, so gaps that only appear in the deployed bundle (env-var differences, CDN, third-party widgets) went undetected.

### The rule (non-negotiable)

Every persona in the v2.11.0 `persona-inventory.json` MUST have AT LEAST TWO entries in `playwright_test_runs[]` with the same `persona_id`:

1. **One local run** — `entry_url` matches a `_LOCAL_ENV_HOST_PATTERNS` value (`localhost`, `127.0.0.1`, `0.0.0.0`, `file://`, `*.local`).
2. **One live-dev run** — `entry_url` matches the persona's `entry_point` (the deployed URL declared in `persona-inventory.json`).

Both runs must execute the same golden-path flow. The local run gives the implementer the debugger-equipped fast feedback; the live-dev run proves the deployed bundle agrees.

### Severity

`live-dev-environment-not-tested` — added to `verify_per_persona_path_coverage` (v2.11.0 extended). Fires when:

- A persona has at least one `playwright_test_runs[]` entry against a `_LOCAL_ENV_HOST_PATTERNS` value AND no entry against the declared `entry_point` URL, OR
- A persona has at least one entry against the declared `entry_point` URL AND no entry against any `_LOCAL_ENV_HOST_PATTERNS` value.

Both directions are caught — local-only AND live-only are equally forbidden. A persona run for which NEITHER environment ran is still caught by the existing v2.11.0 `persona-path-not-tested` severity.

### Cross-references

- `hooks/vao_tools.py::verify_per_persona_path_coverage` — v2.11.0 tool, extended in v2.13.0 with the 5th severity.
- `hooks/vao_tools.py::_LOCAL_ENV_HOST_PATTERNS` — the canonical local-host pattern list.
- `agents/qa-replayer.md` `## UX-test environment sequencing discipline (v2.13.0)` — re-replay protocol now mandates both environments.
- `agents/frontend.md` `## UX-test environment sequencing discipline (v2.13.0)` — implementer's slice-end report cites BOTH a local + live-dev playwright run per persona.
- `tests/fixtures/vao/local-only-no-live-dev-run.json` — verbatim user case (all 4 personas tested only against localhost; none against the deployed dev URL).
- Companion to v2.11.0 multi-persona path-coverage (same axis — per-persona test execution) + v2.2.0 verified-live discipline (which mandates the deployed URL be invoked but doesn't require the BOTH-environments sequence).
