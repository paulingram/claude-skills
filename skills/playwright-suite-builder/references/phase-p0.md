# Phase P0 — Target + e2e-dir resolution

Identify the frontend codebase(s) in scope (one run per codebase; a monorepo with
three frontends gets three manifests). For each, resolve `<e2e-dir>` by the
ladder below. **The suite follows the target repo's own convention** — this skill
imposes its structure INSIDE whatever layout the project already uses, and never
relocates an existing suite.

1. **The Playwright config's `testDir`** — read `playwright.config.{ts,js,mjs}`.
   If it declares a `testDir`, that directory IS `<e2e-dir>`. It wins outright.
2. **An existing conventional e2e directory** — `e2e/`, `tests/e2e/`,
   `test/e2e/`, `cypress/e2e/` when Playwright specs live there, or whichever
   directory the repo's existing browser tests already occupy. The most populated
   candidate wins; a tie escalates rather than guessing.

   **What counts as a spec** — the engine's published suffix family: a `.spec.*`
   or `.test.*` stem with a JS/TS extension (`js`, `jsx`, `ts`, `tsx`, `mjs`,
   `cjs`), matched case-insensitively and anchored on the leading dot — twelve
   suffixes in all. Both stems count, so `checkout.test.ts` is as much a suite
   member as `checkout.spec.ts`. Reconciliation walks the same family in both
   directions, which is why an unlisted `.test.tsx` is a finding rather than
   something the sweep quietly cannot see.
3. **Create `e2e/`** — **only when none exists.** A fresh directory is the last
   rung of the ladder, never the first.

Record the resolved path in the manifest's `e2e_dir`. Read the Playwright config
in full — the existing `projects[]`, `baseURL`, and `use` blocks are what P7
extends rather than replaces.

**Project principles at intake (v4.0.0, per `project-principles`).** Once per
project: when `<workspace>/.architect-team/principles.json` is absent, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" default-set --workspace <ws>`
(proposed never binds); when the user provided a document, run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" extract-candidates <file>`,
`Read` it, and confirm the drafted statements in ONE `AskUserQuestion` (a domain
gate; nothing becomes confirmed silently). Every checker dispatched at P3 and
every authoring brief at P5 carries the output of `python "${CLAUDE_PLUGIN_ROOT}/scripts/principles/cli.py" brief --workspace <ws>`
under a `Confirmed project principles` heading — a testing principle ("test names
say the behaviour", "no mocked backend in e2e") binds the suite exactly as it
binds a feature slice.
