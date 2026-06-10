# Design — review-remediation

The defects in this change share one root cause: **a reference pattern shipped, but the spots that should have followed it didn't.** The design discipline is therefore "reuse the already-shipped pattern verbatim" rather than invent anything. Each decision below cites the canonical pattern's `file:line`.

## Decision 1 — Detect-once polyglot for `hooks/hooks.json` (A1)

**Mirror `commands/architect-team.md:175`.** The shipped reference is:

```
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.py" <args>
```

The shell command-substitution `$(command -v python3 || command -v python)` selects the interpreter **once** (Unix: `python3`; default Windows python.org: `python`) and the script is invoked **exactly once** regardless of its exit code. This kills both failure modes of the current `python3 X || python X`: (a) the double execution + double-BLOCKED-message when the script exits 2, and (b) the silent exit-127 drop on a `python3`-only host.

**Why not keep `python3 X || python X`:** the `||` re-runs the right side whenever the left side returns *any* non-zero, including the meaningful exit-2 BLOCK. v2.16.0 already diagnosed and fixed this exact bug in the three pipeline command files; the hook wiring was simply never swept. There is no reason hooks should differ from commands.

**Test consequence (load-bearing):** the detect-once form does NOT contain the substring `" || python "` (it contains `" || command -v python"`). The two existing assertions in `tests/test_hooks_structure.py` — `test_hooks_use_python3` (asserts `cmd.startswith("python3 ")`) and `test_hooks_use_polyglot_python_fallback` (asserts `" || python " in cmd`) — will both FAIL once hooks.json is converted. The backend-dev who owns `hooks/hooks.json` MUST deliberately rewrite both tests to assert the detect-once contract instead: each command starts with `$(command -v python3 || command -v python) `, contains exactly one `.py` invocation, and names the same script throughout. This is a deliberate test rewrite, not a regression.

## Decision 2 — Dual-form import fallback for the 3 VAO CLIs (A2)

**Mirror `hooks/vao_tools.py:61–68`** (the file's own top-of-module pattern):

```python
try:  # package shape: repo root on sys.path
    from hooks.discipline_registry import _freshness_check, ...
except ImportError:  # bare-module shape: hooks/ dir on sys.path
    from discipline_registry import _freshness_check, ...
```

Apply at the three lazy-import sites — `from hooks.discipline_registry import ...` (~3596), `from hooks.inflight_inbox import ...` (~3676), `from hooks.override_markers import ...` (~4846). The bare-module branch is what makes `python hooks/vao_tools.py <subcommand>` work, because the hook-runner (and a hand-invocation from repo root via the script path) puts `hooks/` — not the repo root — on `sys.path[0]`.

**Why lazy (inside the subcommand handler) and not top-of-module:** these three imports are deliberately lazy so the common tools don't pay the import cost; keep them lazy, just wrap each in the same try/except. Do not hoist them.

## Decision 3 — Atomic rewrite + `safe_id` for `inflight_inbox.py::mark_processed` (A4)

**Mirror `hooks/run_metrics.py:184–186`:**

```python
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
os.replace(tmp, path)
```

`os.replace` is atomic on both POSIX and Windows, so a concurrent `/architect-team:inject` append (the feature's headline cross-terminal use case) either sees the old file or the new file, never a truncated one; a crash mid-write leaves the original intact. The current line 182 `path.write_text(...)` is the non-atomic form being replaced.

**`safe_id` on `run_id`:** `_inbox_path(workspace, run_id)` interpolates `run_id` into the inbox filename. The `safe_id()` validator already lives in `hooks/review_evidence_schema.py` and is what the sibling hooks use to reject `/`, `\`, leading-`.`, and `..`. Validate `run_id` through it at the inbox-path boundary (return `None` / no-op on rejection, matching the existing not-found contract) so a crafted `run_id` cannot escape the inbox directory. Mirror this in `append`/`read_inbox` path construction too if they share `_inbox_path`.

## Decision 4 — Minimal argparse `__main__` for `teams_mode.py` (A5) and `worktree_lifecycle.py` (A6)

These two modules have **no** CLI today, yet commands invoke them with flags. This is the only net-new code in the change. Keep each `__main__` minimal and best-effort.

**`teams_mode.py` (A5):**

```python
def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--banner", action="store_true")
    p.add_argument("--command", default=None)
    args = p.parse_args(argv)
    if args.banner:
        try:
            print(format_dispatch_banner(command=args.command))
        except Exception:
            pass  # banner is informational; never fail the command on it
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

The five invocations (`commands/{inject,monitor-tests,visual-to-api,classify-test-prod-safety,discipline-status}.md`) pass `--banner --command "/architect-team:<name>"`. Banner output is informational; the function swallows any exception and returns 0 so a banner failure never blocks a command (the v1.5.0 never-gating rule). Match the existing `format_dispatch_banner()` signature in the same module — read it before wiring so the `command=` kwarg name is exact.

**`worktree_lifecycle.py` (A6):**

```python
def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    cm = sub.add_parser("cleanup-merged")
    cm.add_argument("--against", default="origin/main")
    cm.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "cleanup-merged":
        try:
            removed = cleanup_merged_worktrees(against=args.against, dry_run=args.dry_run)
            print(f"cleanup-merged: {len(removed)} worktree(s) "
                  f"{'would be ' if args.dry_run else ''}removed")
        except Exception as e:
            print(f"cleanup-merged: skipped ({e})")
        return 0  # v1.3.0: cleanup never blocks the run
    return 0
```

The two invocations (`commands/{classify-test-prod-safety,visual-to-api}.md`) pass `cleanup-merged --against origin/main`. Per the v1.3.0 never-block rule, cleanup errors print a one-line note and exit 0. Match the existing `cleanup_merged_worktrees()` signature (`against=`, `dry_run=`) verbatim — it already exists in the module.

**Why argparse and not `sys.argv` hand-parsing:** stdlib argparse gives unknown-flag rejection for free, which is exactly what the E1 "not a silent no-op" assertion checks; a hand-rolled parser that ignores unknown args is the anti-pattern E1 exists to catch.

## Decision 5 — Subprocess encoding + timeout policy (A7)

**Mirror `scripts/setup/install_mempalace.py:71–78`** — add `encoding="utf-8", errors="replace"` to every text-mode subprocess call. `text=True` without `encoding=` decodes with the locale codec, which mojibakes (or `UnicodeDecodeError`s) on a non-ASCII branch/worktree path under cp1252. Apply to all 23 text-mode calls in `worktree_lifecycle.py` and to the text-mode calls in `worktree_paths.py` (~161), `setup.py` (~161–273), and `pipeline-completion-audit.py` (~326–329).

**Timeout policy:**
- **Local git ops** (status, rev-parse, branch, worktree add/remove, merge, merge-base) → `timeout=60`.
- **Network ops** (`git push` ~810, `git push --delete` ~852) → `timeout=300`.
- Wrap each call so `subprocess.TimeoutExpired` routes into the **existing** best-effort failure path for that call (the same branch a non-zero return code already takes) — a timeout must degrade like a normal failure, never raise to the top. The network-push timeout is the headline fix: a hung credential prompt currently hangs the run forever.

**Why bounded values and not unbounded:** an unbounded network call is indistinguishable from a hang; the run cannot recover. 60s/300s are generous for local/network git while still guaranteeing forward progress. These are the values the requirement suggests; they are conservative and adjustable in one place per call.

## Decision 6 — UTF-8 stdin decoding (A8) and `OSError` handling (A9)

**A8:** the four hooks (`pipeline-completion-audit.py:~525`, `review-gate-task.py:~107`, `teammate-idle-check.py:~43`, `pretool_unilateral_override_guard.py:~209–214`) currently read stdin through the locale text codec. A hook payload is JSON that can carry UTF-8 (an emoji in a task title); on cp1252 the decode raises and the gate degrades to a silent no-op. Switch each to:

```python
raw = sys.stdin.buffer.read().decode("utf-8", "replace")
payload = json.loads(raw) if raw.strip() else {}
```

`errors="replace"` guarantees the decode never raises, so the gate always runs.

**A9:** `review-gate-task.py:~151` and `teammate-idle-check.py:~98` catch `json.JSONDecodeError` on the evidence `read_text` but not `OSError`. A Windows sharing-violation (the evidence file open in another process) raises `OSError`, which currently propagates → exit 1 → the gate is silently skipped. Add `OSError` to the except tuple and treat it identically to the missing-file branch: a blocking gap that keeps the gate closed. A gate that cannot read its evidence must FAIL closed, never skip.

## Decision 7 — `CANONICAL_COMMANDS` regen + matcher fixes (A10)

The constant currently lists 13 entries including 3 phantoms (`mempalace-search`, `mempalace-status`, `code-review`) against 19 real commands. Regenerate it to **exactly** the 19 `commands/*.md` basenames and add a structural test asserting `CANONICAL_COMMANDS == {p.stem for p in (root/'commands').glob('*.md')}` so it can never drift again (this is the same self-checking shape `test_commands.py::EXPECTED_COMMANDS` uses, but as an equality assertion against the live directory).

**Two matcher fixes WITHOUT broadening behavior:**
- **(a) Slash form false positive:** the regex must not match `/status`-like substrings inside URLs/file paths. Anchor to start-of-line or a preceding whitespace boundary, and require the `/architect-team:`-prefixed form for generic single words (`status`, `mini`) that collide with path segments. A bare `/status` in a URL is not a command invocation.
- **(b) Prose form false negative:** also match `architect team` (space form) with an optional possessive (`my`/`your`/`the`) — "use my architect team" is the *documented* user trigger phrase (it is literally in the user's global CLAUDE.md). The current prose matcher only handles the hyphenated `architect-team` form.

Exit semantics are unchanged; add one focused test for the false-positive (URL `/status`) and one for the false-negative ("use my architect team") so the two fixes are pinned.

## Decision 8 — Evidence schema v6 → v7 example content (C1)

Ground truth is `hooks/review_evidence_schema.py`: `SCHEMA_VERSION = 7`, `REQUIRED_EVIDENCE_FIELDS` has **17** members, and there are **2** `OPTIONAL_VAO_FIELDS`. The current docs teach a v6 example with 12 fields. The replacement v7 example (for `skills/team-spawning-and-review-gates/SKILL.md:~135–139` and wherever a full example is shown) is the 17-required-field shape, with the five v7 VAO fields shown in BOTH accepted forms (the legacy string and the canonical dict-with-`verdict_path`):

```json
{
  "task_id": "T-3",
  "teammate": "backend-auth",
  "spec_review": "pass",
  "quality_review": "pass",
  "real_not_stubbed": true,
  "tests": { "added": 4, "passing": 4 },
  "demo_artifact": "curl -s localhost:8000/auth/login -d '{...}' | jq",
  "files_changed": ["backend/auth.py", "tests/test_auth.py"],
  "reuse_compliance": "ok",
  "visual_fidelity_review": "n/a",
  "visual_fidelity_review_note": "backend-only slice; no DESIGN_MAP",
  "test_completeness_review": "pass",
  "integration_testing_review": "pass",
  "ui_interaction_review": "n/a",
  "ui_interaction_review_note": "no frontend interactive surface in this slice",
  "oracle_match_review": "n/a",
  "baseline_clean_review": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-baseline-clean.json" },
  "no_fake_data_review": "n/a",
  "adversarial_review": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-adversarial.json" },
  "skill_invocation_audit": { "verdict": "pass", "verdict_path": ".architect-team/vao-verdicts/<run>-skill-invocation-audit.json" },
  "independent_review": {
    "reviewer": "task-reviewer-1",
    "verdict": "pass",
    "spec_review": "pass",
    "quality_review": "pass",
    "real_not_stubbed": true,
    "reuse_compliance": "ok",
    "reviewed_at": "2026-06-09T00:00:00Z"
  }
}
```

The two optional fields (`interactions_honored_review`, `live_verification_review`) are documented as present-only-when-applicable, not shown in the minimal example. The six bare schema-version mentions (`architect-team-pipeline:~449`, `bug-fix-pipeline:~319`, `mini-architect-team-pipeline:~212`, `common-pipeline-conventions:~2261`, `README.md:294,623,966–968,1014`, and the `team-spawning` frontmatter at line 3) flip the digit 6 → 7. The frontend-dev cross-checks the field list against `review_evidence_schema.py` so the example cannot drift from the code.

## Decision 9 — Version bump: **3.9.3** (patch)

**Recommendation: bump to 3.9.3 (patch), not 3.10.0 (minor).** Every item in this change is remediation that restores *already-documented* behavior or corrects documentation to match *already-shipped* code. No new capability is added to the plugin's public surface: the hooks were always supposed to detect-once (v2.16.0 said so), the three VAO CLIs were always supposed to run, the schema was always v7 in code, solving was already unbounded in v3.8.0, and the doc counts describe what already exists. Under the repo's de-facto semver (minor = new skill/agent/tool/discipline; patch = fix that restores documented behavior — cf. v3.9.1 "operator-precedence bug fix + archive orphaned folders" and v3.9.2 "wire openspec validate into the gate", both patches of exactly this remediation shape), this is unambiguously a patch.

The two minimal argparse `__main__` blocks (A5/A6) are the only arguable "new" surface — but they add no new *capability*; they make an existing documented invocation actually work (the banner and cleanup were specified by the commands that call them; the modules just lacked the entry point). That is a bug fix, not a feature. The 1024-char description cap (C6) and the E1 glue family are new *tests*, which never drive a minor bump. **3.9.3 it is.**

## Decision 10 — QA-contract adaptation for a no-UI codebase

`tests/test_qa_guidance_contract.py` (via `tests/helpers/qa_guidance.py`) requires the `## QA Guidance` section to contain four subsections including `### Playwright Flows`, and caps flows at ≤ 3. It does **not** require ≥ 1 flow — `parse_markdown` yields an empty `playwright_flows` list when the subsection body has no `- [AC-n] name: ...` lines, and `validate_markdown` only checks `len ≤ 3` and that every present flow binds to a real AC. So the honest representation for this plugin is: **the `### Playwright Flows` subsection is present but enumerates zero flows**, with a one-sentence justification that the codebase has no web UI. This satisfies the structural validator (4 subsections present, ≤ 3 flows, no dangling AC binding) without fabricating a browser flow against a codebase that has no browser surface. The same shape is mirrored in `coverage-map.json`'s `qa_guidance.playwright_flows: []`. The E1 CLI/hook subprocess family is the real verification backbone in place of browser flows; this is stated in the proposal's Playwright Flows subsection and here.

## Reuse Decision Log

| Need | Ladder rung | Decision | Evidence |
|---|---|---|---|
| Detect-once hook wiring | reuse | Reuse the v2.16.0 shipped form | `commands/architect-team.md:175` |
| Bare-module import fallback | reuse | Reuse the file's own top pattern | `hooks/vao_tools.py:61–68` |
| Atomic file rewrite | reuse | Reuse the temp + `os.replace` form | `hooks/run_metrics.py:184–186` |
| Path-traversal validation | reuse | Reuse `safe_id()` | `hooks/review_evidence_schema.py:145` |
| Subprocess encoding | reuse | Reuse the `encoding=/errors=` template | `scripts/setup/install_mempalace.py:71–78` |
| UTF-8 stdin decode | reuse | Reuse the `sys.stdin.buffer.read().decode(...)` idiom (already used elsewhere in the hooks) | A8 target files |
| Self-checking command set | reuse | Reuse the `glob('*.md')` directory-equality shape | `tests/test_commands.py:33` |
| `teams_mode.py` CLI (A5) | **build new** | Minimal argparse `__main__` — **no reusable CLI scaffold exists for this module**; the smallest correct entry point is net-new. Bounded to `--banner --command`. | n/a (net-new) |
| `worktree_lifecycle.py` CLI (A6) | **build new** | Minimal argparse `__main__` with one `cleanup-merged` subcommand — **no reusable CLI scaffold exists for this module**; delegates to the existing `cleanup_merged_worktrees()`. | delegate: existing helper |
| E1 glue-execution test family | **build new** | No existing test resolves-and-executes the command/hook invocation strings; this is the net-new regression backbone the review identified as missing. | n/a (net-new) |

The two new CLIs and the E1 family are the only net-new code; each is justified above (no existing capability to extend/compose/reuse for an entry point that does not exist). Everything else is in-place extension reusing a shipped reference pattern.
