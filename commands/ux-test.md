---
description: A persona-driven UX test orchestrator. Takes EITHER a requirements folder (containing a UX brief — persona, objectives, target site, credentials env-var reference) OR a plain-language requirement typed directly as prose. Maps the target site (fresh or freshness-checked via the existing intake-and-mapping skill), drafts a literal Playwright flow matching the user's request, dispatches 3 flow-explorer agents to propose 10-15 additional adjacent flows each, distills to a unique set, authors one .spec.ts per flow, dispatches 3 flow-executor agents to run every flow in parallel against the live target, resolves verdict disagreements via 3-cycle bounded convergence, documents bugs, and auto-routes them through the existing /architect-team:bug-fix pipeline for resolution. Auto-commits and pushes on a clean Phase U9 pass; emits a /compact prompt to free context.
argument-hint: "<requirements-folder | UX brief prose> [--site URL | --dev] [--credentials ENV_VAR_NAME] [--persona description] [--objectives text] [--no-commit] [--no-push] [--no-compact] [--allow-push-to-default] [--proposal-first]"
---

# UX-Test-Builder Orchestration

You are starting the architect-team UX test builder — a persona-driven Playwright flow discovery + execution + bug-routing capability.

**Raw arguments:** $ARGUMENTS

## Argument parsing (do this first, before invoking the skill)

**Strip the recognised flags from `$ARGUMENTS` first; everything left is the requirement.**

Flags (each independent):

- `--site <URL>` → set `TARGET_KIND = url`, `TARGET_URL = <URL>`. The site the persona will be tested against.
- `--dev` → set `TARGET_KIND = dev`. The orchestrator resolves the target from the project's `design.md` `## Dev Environment` section at Phase U0.
- `--credentials <ENV_VAR_NAME>` → the env-var NAME holding the auth secret. **NEVER the secret itself.** Example: `--credentials UX_TEST_PASSWORD`.
- `--persona <description>` → the persona description. May also be read from the prose requirement.
- `--objectives <text>` → what the persona is trying to do. May also be read from the prose requirement.
- `--no-commit` → `AUTO_COMMIT = false`, `AUTO_PUSH = false`.
- `--no-push` → `AUTO_COMMIT = true`, `AUTO_PUSH = false`.
- `--no-compact` → `AUTO_COMPACT_PROMPT = false`.
- `--allow-push-to-default` → `ALLOW_PUSH_TO_DEFAULT = true`. (Default `false`.)
- `--proposal-first` → `PROPOSAL_FIRST = true`. Runs Phase U0 → U4 (intake + site mapping + literal flow + expansion + distillation), then PAUSES for user review before authoring + executing the Playwright flows at U5/U6. Domain gates (U0 vague-input, U7 consensus-cannot-converge, `--environment production` escalation) fire regardless.
- `--environment production` → `TARGET_ENVIRONMENT = production`. Forces U6 execution to escalate before running against production (production testing is a user decision, never automatic).
- No flags → `AUTO_COMMIT = true`, `AUTO_PUSH = true`, `AUTO_COMPACT_PROMPT = true`, `ALLOW_PUSH_TO_DEFAULT = false`, `PROPOSAL_FIRST = false`, `TARGET_ENVIRONMENT = dev` (default).

### The requirement comes in ONE of two forms — BOTH are first-class, fully-supported inputs

| Form | What it is | Bind `$REQ_DIR` to |
|---|---|---|
| **Folder** | a filesystem path holding a UX brief (persona description, objectives, target reference, credentials reference) | the path |
| **Plain-language requirement** | prose — e.g., *"a secretary uploading and checking files, against https://app.example.com, credentials in $UX_TEST_PASSWORD"* | the **entire remaining string, verbatim** |

To tell them apart: if what remains after stripping flags is a single token that resolves to an existing directory → **Folder**. Otherwise → **Plain-language requirement**. **When unsure, it is a plain-language requirement** — prose is the common case for UX briefs.

The pipeline's **Phase U0 normalizes a plain-language requirement** into a structured intake record (parsing the persona + objectives + target + credentials reference from the prose, when the corresponding flags aren't passed). A requirements folder is NOT required.

### Forbidden — the following are bugs, not correct behavior

These rules mirror `/architect-team` exactly (the v0.9.17 same-input-forms rules):

- **Treating the first word of a plain-language requirement as a path.** `a`, `the`, `as`, `for`, `secretary`, `uploading` are not directories — the *whole string* is the requirement.
- **Refusing to run** — or telling the user the pipeline "needs a folder" / "only drives a requirements folder" / "I won't run against a non-existent folder" — when given prose. The UX test builder accepts a plain-language requirement directly; running it is correct.
- **Asking the user for a requirements folder.** The only thing you may ask for is the UX brief itself, and ONLY when `$ARGUMENTS` (flags stripped) is genuinely **empty** AND the `--persona` / `--objectives` flags are also absent — then ask: *"What persona, objectives, target site, and credentials env-var should the UX test builder use?"*

**Binding into the skill:** the harness does NOT propagate `$ARGUMENTS` into skill bodies. Pass the bound `$REQ_DIR` — a folder path OR the verbatim plain-language requirement string — as the input to the `ux-test-builder` skill, and substitute it for every `$REQ_DIR` reference in the skill body. When the requirement is plain-language prose, the workspace codebase (the cwd, a git repo) provides the maps for Phase U1.

## Invoke the pipeline

Invoke the `ux-test-builder` skill from this plugin (use the Skill tool with `skill: ux-test-builder`) and follow its pipeline exactly against the requirement above (a folder OR a UX brief in prose — both are valid). The skill begins at Phase U0 (Intake) and proceeds through Phase U9 (Final Report).

**Pass the `AUTO_COMMIT`, `AUTO_PUSH`, `AUTO_COMPACT_PROMPT`, `ALLOW_PUSH_TO_DEFAULT`, `PROPOSAL_FIRST`, `TARGET_KIND`, `TARGET_URL`, `TARGET_ENVIRONMENT`, and the credentials env-var NAME to the skill.** The skill's Phase U0 + Phase U6 read these to compose the intake record + execute against the right target.

## Default git behavior (when `AUTO_COMMIT = true` and `AUTO_PUSH = true`)

At the end of Phase U9, after the final report emits **"UX test plan for persona `<persona-slug>` against `<target>` executed. ..."** and the bug-fix-pipeline dispatch references:

0. **Run the completion audit FIRST:** `python3 "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check || python "${CLAUDE_PLUGIN_ROOT}/hooks/pipeline-completion-audit.py" --check`. The `|| python ...` fallback handles default Windows python.org installs where only `python` is on PATH (`python3` triggers the Microsoft Store shim there); on Unix the first form succeeds and the fallback never fires. If the final exit is non-zero, the run is incomplete — do NOT commit; resolve violations or escalate.
1. `git -C <repo-root> status --porcelain` — enumerate what changed.
2. `git -C <repo-root> add <files-the-pipeline-touched>` — stage ONLY the pipeline-touched files (the `.architect-team/ux-tests/<persona-slug>/` artifacts + any SR files written; do NOT include the bug-fix-pipeline's own work — those are queued in separate bug-fix runs).
2b. **Default-branch guard:** if the current branch is `main` / `master` AND `ALLOW_PUSH_TO_DEFAULT` is false, `git -C <repo-root> checkout -b architect-team/ux-test-<persona-slug>` before committing.
3. `git -C <repo-root> commit -m "<commit message>"` using the repo's local git config (no `-c user.name=` override).
4. `git -C <repo-root> push -u origin <branch>` — push the branch the commit landed on.
5. Report the commit SHA and push range. If the commit landed on `architect-team/ux-test-<persona-slug>`, the report MUST say so and recommend opening a PR.

If `AUTO_COMMIT = false`: skip steps 2-5; mention in the final report that changes were left uncommitted.

If `AUTO_COMMIT = true` but `AUTO_PUSH = false`: do steps 1-3 only; mention in the final report that the commit was made locally but not pushed.

## Auto-compact prompt (after the final report)

When `AUTO_COMPACT_PROMPT = true` AND Phase U9 completed cleanly, emit the standard `/compact` prompt block as the very last thing the user sees:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║  ◆  READY FOR /compact                                         ║
║                                                                ║
║  UX test complete. Context is now full of execution traces.    ║
║  Run /compact NOW to free space for the next architect-team    ║
║  invocation. Type exactly:                                     ║
║                                                                ║
║      /compact                                                  ║
║                                                                ║
║  (Pass --no-compact next time to suppress this prompt.)        ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

If `AUTO_COMPACT_PROMPT = false`: skip the block.

## Safety rules (non-negotiable)

All the same safety rules as `/architect-team`:

- NEVER force-push.
- NEVER skip git hooks (`--no-verify`). Fix the underlying issue and re-commit.
- NEVER amend the previous commit; always create a new commit.
- If `git push` fails, surface the error clearly and stop — never escalate to force-push.
- Pre-existing unstaged or staged changes are the user's in-progress work — do NOT include them; surface them in the final report.
- **NEVER schedule arbitrary wall-clock wakeups (`ScheduleWakeup`), cron jobs (`CronCreate`), or background timer tools.** The pipeline is synchronous; subagent dispatches block your turn. Do NOT tell the user "I scheduled a wakeup for N minutes."

## Production-environment rule (the one exception to live-by-default)

**`TARGET_ENVIRONMENT` defaults to `dev`.** Phase U6 runs against the dev environment (per the project's `design.md` `## Dev Environment` section) when `--dev` was passed, or against the URL when `--site` was passed.

When `--environment production` is set (or the user's prose names production as the target), Phase U6 does NOT auto-execute. The orchestrator escalates: *"This run is targeting production. Production UX testing affects real users (auth attempts, possible side effects, possible cost). Please confirm: (a) execute against production now, (b) re-run against staging instead, (c) hold for manual review."* Domain gate; pause for the user.

## Credential discipline (non-negotiable)

The `--credentials <ENV_VAR_NAME>` flag carries the env-var NAME ONLY. The secret VALUE is read from `process.env[<name>]` at Playwright runtime (by the `flow-executor` agents at U6). It is NEVER persisted to:
- the intake JSON,
- the literal flow's metadata,
- the explorers' proposals,
- the distilled-flow set,
- the Playwright `.spec.ts` files (they reference `process.env[<name>]`, not the literal value),
- the executors' verdict files,
- the captured traces,
- the captured screenshots (be careful with screenshots that may include password fields with autocomplete — use `--mask-credentials` Playwright option if available),
- the final U9 report.

If the user's prose tries to include the raw secret inline (e.g., *"login with paul@example.com / hunter2"*), the orchestrator REJECTS it: *"For credential safety, the raw password / token cannot be passed inline. Set it in an env var and pass `--credentials <ENV_VAR_NAME>` instead. The orchestrator will read the secret at Playwright runtime; it will never be persisted in any artifact."* The run does not proceed until the user complies.
