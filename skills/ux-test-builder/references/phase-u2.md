# Phase U2 — Literal flow draft

The orchestrator applies `superpowers:brainstorming` to nail down the persona's intent + the exact literal task before authoring (per `## Plugin prerequisites (v3.9.0)`), then authors ONE Playwright `.spec.ts` matching the user's described task VERBATIM. Per `playwright-user-flows`:

- Real `page.click` / `page.fill` / `page.waitFor` / `page.selectOption` / `page.press` / `page.setInputFiles`.
- Real login via the credentials env-vars (the spec reads `process.env[<env_var>]` at run time).
- Per-step expectation file written BEFORE the test runs, per `root-cause-test-failures`.
- Assertions match what the user said they expected ("upload the file, see it appear in the list").

Persisted at `<cwd>/.architect-team/ux-tests/<persona-slug>/literal-flow.spec.ts` + a structured metadata file `literal-flow.json` carrying the flow's `name`, `goal_one_line`, `steps[]`, `expected_outcome`, `source: "literal"`.

The literal flow is flow #1 in the eventual distilled set. The explorers at U3 EXPAND on it; they do not replace it.

**Grow the intuition map from the literal flow.** The user specified this flow, so the path it walks is a settled fact rather than an intuition — call the `intuition-map-lifecycle` skill's `grow` verb with the flow's elements, each upserting as a `user_verdict: confirmed` entry carrying `source: user-flow`. `grow` deliberately bypasses the Phase −1D bulk-verify gate: that gate exists to resolve the intuiter's uncertainty, and a user-specified flow carries none to resolve. **Two cases ask instead of upserting, and the second is this lane's duty.** A contradiction with an existing confirmed entry surfaces a targeted question, never a silent overwrite. The other is ambiguity, and turning a selector into an `element_id` is heuristic inference the engine cannot second-guess because it never saw the flow — so you mark any element whose extraction you are unsure of `ambiguous: true` (`extraction_confidence: low` or `unknown` is the equivalent spelling). A marked element is never upserted: no entry is written for it at all, and an `ambiguous-extraction` question naming the selector is produced instead. A missing marker reads as falsy, so an unmarked element is taken as certain and written — silence is the confident default, which is exactly why the marking is the caller's job.
