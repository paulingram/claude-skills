# The six layers

### Layer 1 — Pre-execution oracle derivation (Phase 0.5 gate)

Position: a new phase inserted between Phase 0 (Detection & Normalization) and Phase 1 (Planning Validation) in every pipeline-driving skill.

Trigger: the requirement contains a parity verb (`match`, `rebuild`, `mirror`, `parity`, `make like`, `replicate`) OR names an oracle codebase / design mockup / reference URL.

Mechanism: a dedicated `oracle-deriver` agent (fable under `--split role`, read-only) walks the named oracle and produces a structured canonical spec at `<workspace>/.architect-team/oracle-spec/<change-name>.json` with these top-level fields:

```json
{
  "schema_version": 1,
  "change_name": "<name>",
  "oracle_path": "<absolute path>",
  "derived_at": "<ISO 8601 UTC>",
  "spec_shape": "component-tree" | "design-map" | "api-contract" | "data-model" | "hybrid",
  "tree": [ /* deterministically-ordered structural enumeration */ ],
  "elements": [ /* every interactive element with required wiring */ ],
  "dynamic_values": [ /* every value with its required data binding */ ],
  "chrome_topology": [ /* rendered-DOM mount-level expectations */ ],
  "schemas": [ /* every contract surface */ ],
  "_human_review_required": true
}
```

The orchestrator surfaces the spec to the user with ONE confirmation gate. On accept, `_human_review_required` flips false; the spec is frozen and becomes the binding contract every downstream layer measures against. On reject, the user's correction text re-feeds the deriver, which re-derives and re-surfaces; this repeats until the user accepts — there is no fixed cycle cap (per `common-pipeline-conventions` `## Unbounded solving discipline`), and the only pause is waiting on the user's own confirmation, which IS the deliverable.

**Why this catches the failures.** Scope-narrowing: the agent's interpretation IS the structural enumeration; reframing prose is impossible. Oracle structure mismatch: the structural diff is the FIRST artifact; subsequent work measures against it deterministically.

### Layer 2 — Adversarial-reviewer pairing (extends Phase 3)

Position: concurrent with every Phase 3 teammate dispatch. The producer-cannot-be-its-own-checker pattern (v0.9.13) scales from "is the work done" to "does the work exhibit the failure-mode the task-shape is prone to."

Task-shape taxonomy (computed at Phase 2 spawn-brief time):

| Task shape | Triggered by | Adversarial role assigned | Tool invoked |
|---|---|---|---|
| `parity-verb` | Frozen oracle spec referenced by the task | `oracle-divergence-hunter` | `verify-oracle-match` |
| `backend-dep` | Frontend task referencing a `pending-backend` or `missing-api-for-frontend-element` SR | `fake-data-hunter` | `verify-no-fake-data` |
| `shared-tree` | ANY teammate dispatch (always-on) | `git-discipline-hunter` | `verify-baseline-clean` |
| `dynamic-value` | Task touches a designed screen with non-trivial `dynamic_values[]` | `hardcoded-literal-hunter` | `verify-no-fake-data` |
| `default` | None of the above | `general-anti-pattern-hunter` | (light sweep across 4 shapes) |

The `adversarial-reviewer` agent is dispatched alongside the teammate, gets access to the teammate's tool-call log + diff, and writes its `adversarial_review` block into the SAME `<cwd>/.architect-team/reviews/<task-id>.json` evidence file. The Phase 3 hook (schema v7) requires BOTH `independent_review.verdict == "pass"` AND `adversarial_review.verdict == "pass"`. The gate opens only when both pass.

### Layer 3 — Tool-mediated execution proof (`hooks/vao_tools.py`)

Deterministic verification tools — **21** as of v3.47.0. Each produces machine-mediated proof; the agent's prose attestation is no longer accepted.

**Where each tool is specified.** `hooks/vao_tools.py` is the COMPLETE and authoritative inventory — every tool has a CLI subcommand there, and that file is the one place the full list is guaranteed current. The prose homes are split: the five original v2.0.0 tools are specified in full below, followed by `verify-check-can-fail` (the 21st). Of the remaining fifteen, `common-pipeline-conventions` `## Layer 3 gate invocation table (v3.10.0)` gives per-phase invocation contracts for exactly **four** of them (`verify-discipline-registry-current`, `verify-inflight-clarifications-processed`, `verify-deploy-mandate-satisfied`, `verify-no-unilateral-override`); the rest are specified in their own discipline sections — mostly in `common-pipeline-conventions`, some in the dedicated discipline skills — where they are written in the `verify_x_y` FUNCTION spelling rather than the hyphenated CLI name, so grep for both forms when locating one.

#### `verify-oracle-match`

Input: built tree dict + frozen oracle-spec dict. Walks both with deterministic normalization (whitespace stripped, dict keys sorted, list ordering preserved). Output:

```json
{
  "tool": "verify-oracle-match",
  "matched": true|false,
  "divergences": [{"path": "App.Header.label", "expected": "...", "actual": "...", "severity": "missing-in-actual"|"extra-in-actual"|"value-mismatch"|"type-mismatch"}],
  "match_pct": 0.0-1.0,
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-baseline-clean`

Input: teammate's tool-call log path + optional baseline SHA. Greps the log for the six v1.6.0-forbidden git operations (`git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>`, `git clean -f`) without firing on legitimate read ops (`git status`, `git log`, `git diff`, `git stash list`). Output:

```json
{
  "tool": "verify-baseline-clean",
  "clean": true|false,
  "violations": [{"op": "git stash", "args": "...", "line": 7, "ts": "..."}],
  "baseline_sha": "<sha or null>",
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-no-fake-data`

Input: list of changed files (each with added lines) + the frozen oracle spec's `dynamic_values[]`. Pattern-matches every line in production code (test files are skipped) against:

- Placeholder names — `John Smith`, `Jane Doe`
- Placeholder emails — `john.doe@example.com`, etc.
- Lorem ipsum
- Placeholder money — `$1,234.00` / `$1,234.56`
- MSW handler signatures — `rest.get(`, `http.post(`, etc.
- Playwright route fulfill stubs — `page.route(... .fulfill(...)`
- Every oracle-declared dynamic-value literal (e.g., if the oracle binds `Park Family Trust` to `matter.title`, the literal `Park Family Trust` must NOT appear in production code)

Each line is matched against EVERY category — a line carrying both a placeholder name AND an MSW handler is flagged for both. Output:

```json
{
  "tool": "verify-no-fake-data",
  "clean": true|false,
  "hits": [{"file": "src/Users.tsx", "line": 0, "match": "John Smith", "category": "placeholder-name"}],
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-every-element`

Input: list of built components (each with elements) + the oracle's `elements[]`. For every oracle-named element, asserts presence in the built tree, non-stub handler, Playwright test driving it. Output:

```json
{
  "tool": "verify-every-element",
  "coverage": 0.0-1.0,
  "missing": [{"selector": "#cancel"}],
  "stub": [{"selector": "#submit", "handler": "() => {}"}],
  "untested": [{"selector": "#delete"}],
  "verdict_at": "<ISO 8601 UTC>"
}
```

#### `verify-rendered-parity` (the heirship-amendment tool)

Input: candidate rendered-DOM snapshot + oracle rendered-DOM snapshot + oracle-spec `chrome_topology[]` + optional screenshot paths + optional pre-computed pixel-diff percentage. Operates on the RENDERED DOM — NOT the source component tree. Catches the canonical heirship case where the SAME element exists in both candidate and oracle source but mounts at DIFFERENT rendered parent paths.

Output:

```json
{
  "tool": "verify-rendered-parity",
  "matched": true|false,
  "divergences": [
    {"anchor": "[data-component='TaCrumbs']",
     "expected_level": "body > [AppShellLayout] > [AppShellHeader]",
     "actual_level": "body > [AppShellLayout] > [AppShellBody] > [data-testid='page-body']",
     "severity": "architectural-mismatch"|"missing-in-candidate"|"missing-in-oracle"|"pixel-divergence"}
  ],
  "pixel_diff_pct": 0.0-1.0,
  "screenshot_paths": {"oracle": "...", "candidate": "...", "diff": null},
  "verdict_at": "<ISO 8601 UTC>"
}
```

The schema v7's `visual_fidelity_review` field MUST cite this tool's verdict path. An agent's "pixel parity: pass" attestation derived from reading source code is REJECTED at the hook layer — the cited verdict file is the source of truth.

**Why this tool is distinct from `verify-oracle-match`.** The latter walks the SOURCE component tree; that's sufficient for schema / API / structural-data parity but BLIND to chrome-level architectural divergences where the element exists in source but at the wrong mount point. The canonical heirship failure: `heirship-app-v2`'s `TAMatterDetail.tsx` rendered `<TaCrumbs />` inside its page body; the oracle (`heirship-app-v3`) renders the same `<TaCrumbs />` inside `AppShellHeader`. Source audit says matched; rendered audit catches the divergence.

#### `verify-check-can-fail` (the 21st tool — v3.47.0)

Module: `hooks/vao/check_integrity.py`, re-exported through the `hooks/vao_tools.py` facade with the CLI subcommand `verify-check-can-fail`. Where the other twenty ask *did the work meet the bar*, this one asks the rung below: **was the check that certified it capable of failing at all?** A check that did no work exits 0, and a guard that has never been red is a green light wired to nothing.

Input: a verification artifact with `repo_root` (every relative cited path resolves against it; the `--repo-root` CLI flag overrides), a `checks[]` list of `{command, output_path}` (optionally `exit_code`, and optionally `tsconfig_path` to point the solution-shape predicate at a specific tsconfig), a `new_test_files` list (the diff-added test files), and `red_runs` — a DICT keyed by test-file path, each value `{command, output_path, observed_failure_excerpt?, red_source?}` naming which of the three acceptable red sources produced it (see `team-spawning-and-review-gates` `## Red-first — a new guard is not evidence until it has been shown to fail`). Keys are matched posix-normalized against `new_test_files`, so a Windows-authored artifact cannot produce a spurious never-shown-red. A cited `output_path` that does not exist, is not a file, or is 0 bytes is itself a failure — the same missing-evidence-artifact bar the other tools apply. `verify_check_can_fail`'s `signature_registry` parameter is the extensibility seam: pass a different registry tuple to add runners without touching scan logic.

**The REPORTING region (the load-bearing partition).** Every signature match and every runner-detection probe consults only the output's REPORTING region — the runner's own report — via `reporting_region()`. Captured stdout/stderr, live logs, the pytest `-rA` PASSES section, echoed commands and echoed test ids are excluded, because relayed text can reproduce any reporting shape verbatim: a test that PRINTS `collected 0 items` must not be able to forge a vacuous verdict, and a passing log quoting a failure line must not be able to forge a red. `_RUNNER_OUTPUT_SHAPES` widens applicability past command naming, so a wrapper (`make test`, `npm run typecheck`) that hides the runner's name but not its output shape is still classified. Output bytes are decoded through `_decode_output_bytes`: an explicit BOM wins (`utf-8-sig` / `utf-16`), else a NUL ratio at or above one third triggers `utf-16-le` then `utf-16-be`, else UTF-8 with replacement — closing the UTF-16 evasion.

**Terminal verdict wins.** `_assess_red_output` resolves a red run in three explicit modes via `_terminal_verdict()`: PRESENT — the runner's own stated result decides, full stop; AMBIGUOUS — a capture holding more than one run is REFUSED (`ambiguous-multi-run-capture`) rather than resolved by first- or last-wins; ABSENT — with no summary at all, matching degrades to the runner's framed failure sections only, never the whole region (`verdict-absent-framed-sections-only`).

Three severities:

- **`vacuous-check`** — a cited check's output matches a zero-work signature. The registry is DATA, not scan logic: pytest (`collected 0 items`, `no tests ran`), Playwright (`no tests found`, a `0 passed` with zero total), jest / vitest (`No test files found`, `No tests found`), plus the repo-state predicate for a `tsc --noEmit` resolved against a solution-shaped `tsconfig.json` (`"files": []` plus `"references"`), whose remediation names `tsc -b` as the required command form. Entries are ANCHORED or count-aware — never a raw bare substring — so a green log that merely echoes a zero-work phrase is not flagged, and the tsc predicate gates on typecheck INTENT (`tsc` / `typecheck` / `type-check` in the command) with `tsc -b` exempt, recording an indeterminate note rather than staying silent when no tsconfig resolves. Adding a runner is a data edit plus a fixture.
- **`new-guard-never-shown-red`** — a diff-added test file with no cited `red_run` block, or a block whose `red_source` is an unrecognized value. The finding names the path.
- **`red-run-not-red`** — the cited red run does not establish that THIS guard went red. The gap carries a `reasons[]` array, and there are six codes — key on `reasons[]`, not on prose:

  | Reason code | Fires when |
  |---|---|
  | `output-missing` | the cited output does not exist, is not a file, or is empty |
  | `no-failure-signature` | the REPORTING region carries no failure evidence for its runner |
  | `excerpt-not-in-output` | the quoted `observed_failure_excerpt` does not appear in that output |
  | `output-does-not-reference-test` | the output names tests, none matching this file (posix-normalized, full path OR basename) |
  | `excerpt-required-when-indeterminate` | the output names NO test, so the excerpt is mandatory and is missing |
  | `shared-anonymous-red` | one output naming no test at all is reused across several guards |

  **Sharing one capture across guards is normal and accepted when the output NAMES them** — correlation ties each guard to the output independently, so nothing is taken on trust. What is refused is the same anonymous capture reused for several guards: an excerpt cannot fix that, since one string satisfies the excerpt rule as many times as it is pasted. Fix by re-running with per-test reporting (drop `--tb=no`, add `-v`, or name the paths), or split into one capture per guard.

**Stated boundaries** — recorded rather than left for a reader to find. *Same-basename correlation:* matching accepts the full posix path OR the basename, so with `tests/unit/test_guard.py` and `tests/integration/test_guard.py`, an output naming only one satisfies both — prefer captures carrying full paths. *Indeterminate correlation:* a mandatory excerpt raises the floor but does not make a citation unique; one name-free summary with an excerpt can still be cited for several guards. *Exotic encodings:* BOM-less UTF-16LE diluted below the NUL floor, a truncated odd-length UTF-16 file, and BOM-less UTF-16BE still evade the decoder; each needs a hand-rolled writer, so the residual is rated low.

```json
{
  "tool": "verify-check-can-fail",
  "valid": true|false,
  "gaps": [
    {"severity": "vacuous-check",
     "command": "python -m pytest tests/",
     "output_path": ".architect-team/checks/<run>-pytest.txt",
     "exit_code": 0,
     "runner": "pytest",
     "matched_signature": "collected 0 items",
     "evidence": "...",
     "remediation": "..."},
    {"severity": "red-run-not-red",
     "test_file": "tests/test_new_guard.py",
     "output_path": ".architect-team/red-runs/<run>-guard.txt",
     "reasons": ["shared-anonymous-red"],
     "evidence": "...",
     "remediation": "..."}
  ],
  "notes": [
    {"kind": "typecheck-tsconfig-indeterminate",
     "command": "npm run typecheck",
     "evidence": "...",
     "remediation": "..."}
  ],
  "checks_scanned": 2,
  "new_test_files_count": 1,
  "red_runs_cited": 1,
  "verdict_at": "<ISO 8601 UTC>"
}
```

`notes[]` is ALWAYS emitted (empty when there is nothing to record) and is NON-GATING — it carries the indeterminate observations the tool refuses to convert into findings, such as typecheck intent detected with no resolvable tsconfig. A note is a thing the tool could not determine, not a thing it found wrong; treat it as a prompt to supply `tsconfig_path`, never as a pass.

#### Two tools whose only prose home is this table

These two carry no discipline section of their own under their CLI name; their one-line contracts live here so no shipped tool is documented nowhere:

| Tool | Module / function | What it gates |
|---|---|---|
| `verify-affordance-coverage` | `hooks/vao_tools.py::verify_affordance_coverage` | Every detected dynamic affordance class is addressed — tested, confirmed-stub, or explicitly out-of-scope; an unaddressed class is `affordance-not-addressed`. Canonical discipline: `common-pipeline-conventions` `## Dynamic affordance discovery discipline (v2.13.0)`. |
| `verify-per-persona-path-coverage` | `hooks/vao_tools.py::verify_per_persona_path_coverage` | Each persona's declared path is actually exercised end-to-end rather than one persona's run standing in for all of them. Canonical discipline: `common-pipeline-conventions` `## Multi-persona path-coverage discipline (v2.11.0)`. |

#### The v4.0.0 additions — 26 tools in all

`hooks/vao_tools.py` lists 26 subcommands since v4.0.0 (24 at v3.66.0, when `verify-diagnosis-falsified` landed). The two additions have their own homes and are listed here so the inventory in this chapter is complete:

| Tool | Module | What it gates | Canonical home |
|---|---|---|---|
| `verify-principles-respected` | `hooks/vao/principles.py` | every confirmed project principle has a recorded verdict in the `principles-verdicts/v1` sidecar; a knowing violation is a gap, `all-options-violate` is the hard stop; cited by the optional `principles_review` field | `skills/project-principles/SKILL.md` |
| `verify-required-reads` | `hooks/vao/required_reads.py` | every chapter an `INDEX.md` declares for a phase was Read before that phase started; `required-read-skipped` is a MEASURED GAP (blocking only with `CT6_REQUIRED_READS_BLOCKING=1`) | `skills/common-pipeline-conventions/references/INDEX.md` |

Each tool writes its verdict JSON to `<cwd>/.architect-team/vao-verdicts/<task-id>-<tool>.json`. The schema v7 `*_review` field cites the verdict path; the hook reads the cited file at validation time.

> **STOP.** This chapter continues in `skills/verified-agent-output/references/the-six-layers-part-2.md`; Read it before acting on the later stages.
