> **STOP.** Before deleting any file or directory, read this reference in full.

# Deletion discipline — full text

> The canonical home of the deletion rule summarized in `skills/common-pipeline-conventions/SKILL.md`. The machine half is `hooks/deletion_guard.py` (a PreToolUse hook on the `Bash` tool); this page is the human half. Execute it before the first `rm`, `git checkout --`, `git clean`, `find -delete`, `shutil.rmtree`, or any other command that removes content.

## The rule in one sentence

**Deletion is a decision about recoverability, and the agent does not make it from memory.** A file is deleted only when something else proves its content survives — git HEAD, a gitignore rule that says it was never meant to be kept, or a cache/temp class — and when nothing proves that, the default is to move it aside, not to remove it.

## Soft delete by default — the `trash` verb

Do not reach for `rm`. Move the path into the run's trash:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/deletion_guard.py" trash <path>... --cwd "<workspace>" [--run-id <slug>]
```

- Each path lands at `<workspace>/.architect-team/trash/<run-id or manual>/<original relative path>` (directories move whole). Nothing is clobbered: a second trashing of the same name gets a `.1` / `.2` suffix. A `.trash-manifest.jsonl` beside it records `from` / `to` / `at`, and the JSON the verb prints carries the `mv` that restores each entry.
- The verb REFUSES a path outside the workspace (the git toplevel of `--cwd`, else `--cwd`), the workspace root itself, the `.architect-team/` state dir, and anything already in the trash. A refusal exits 2 and is printed; it is never silent.
- Trash is per-run scratch state: the guard classifies it `run-state` and lets it go. Reclaim it with `prune --run-id <slug>` (or `--all`, optionally `--older-than-days N`) — at Phase 8 / B8 / M7 / D8 / U9 / P9 close-out, never mid-run while a teammate might still want the content back.

## When a hard delete may proceed — the classifier decides

Every target of a deletion-shaped Bash command is classified by what git knows about it. Preview before you act:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/deletion_guard.py" classify <path>... --cwd "<workspace>" --json
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/deletion_guard.py" check "<the exact command>" --cwd "<workspace>"
```

| Class | Decision | Why |
|---|---|---|
| `temp` — `__pycache__`, `.pytest_cache`, `node_modules`, `.mypy_cache`, `.ruff_cache`, `.tox`, `.nox`, `htmlcov`, `coverage`, `.nyc_output`, `dist/`, `build/`, `*.pyc`, `*.pyo`, `*.egg-info`, `.coverage` (`TEMP_DIR_NAMES` / `TEMP_FILE_NAMES` / `TEMP_FILE_SUFFIXES` in `hooks/deletion_guard.py`); an empty directory or one holding only ignored content (`empty-or-ignored`); the OS temp dir (outside any repo); `find` whose predicates name only these | allow | Regenerable output. A TRACKED `build/` is NOT temp — it falls through to the git classes. |
| `run-state` — `.architect-team/{reviews,teammates,handoffs,trash,run-history}/` | allow | Per-run scratch the pipeline rebuilds. |
| `ignored` — `git check-ignore` matches | allow | Never under version control by design. Note the boundary below: ignored is not the same as worthless. |
| `tracked-clean` — in the index, `git status --porcelain` empty | allow, with the restore command | `git checkout HEAD -- <path>` brings it back from LOCAL HEAD. The hint says `also on origin/<branch>` only when `git branch -r --contains HEAD` is non-empty; otherwise it says the commit may not be on the remote. |
| `absent` | allow | Nothing to delete. |
| `tracked-dirty` — uncommitted changes | **ask**, naming the changed-line count from `git diff --numstat` | Those lines exist nowhere else. Commit or trash first. |
| `untracked` — not in the index, not ignored (a file, or a directory holding one) | **ask** | The working tree holds the only copy. Trash it. |
| `protected-state` — anything else under `.architect-team/` (`git-identity.json`, `decisions.jsonl`, `principles.json`, `timings.jsonl`, `active-run.json`, `locks/`, `openspec/`) | **ask** | Run state that is gitignored AND the only copy. |
| `repo-metadata` — anything under `.git/` | **ask** | Not a working-tree file; the history itself. |
| `no-repo` / `unparsable` — outside any git repo; a `$VAR`, a glob, a `$(...)`, a `| xargs rm`, a `python -c` whose target is not a string literal, a relative path with no known cwd -- and (v4.1.3) a tokenizer failure ONLY on a segment that is deletion-shaped; a here-document body is data, never a command, so a commit message with an apostrophe is silent; (v4.1.4) a variable assigned earlier in the SAME command (`W=/path; git -C $W checkout -- f`) is expanded, so the base and the targets resolve -- only a variable the command never assigns is unexpanded; (v4.1.5) a chain (`S=/p; W=$S/x`) resolves through the known names, and `git checkout -b|-B|--orphan|--detach` creates or moves a branch and restores no path (the teammate git discipline's shared-state arm still asks before a branch SWITCH) | **ask** | Recoverability cannot be proven, so it is not assumed. Expand the variable or glob yourself, then re-issue with literal paths. |
| `shared-state-git-op` — the six teammate-git operations | **deny** inside an active run, **ask** outside | See the next section. |

Several targets in one command: the most restrictive decision wins (deny > ask > allow), and the reason lists every path with its class — read all of them, not just the first.

## The six shared-state git operations are never run inside a run

`git stash`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f` — the v1.6.0 list, matched from `hooks/shared_rule_constants.py::FORBIDDEN_GIT_OPERATIONS`, the same single source every other hook reads. While `.architect-team/active-run.json` says a run is `active` (and is not stale), the guard DENIES them — teammates share one index, one working tree, one stash stack, one HEAD, and each of these rewrites it for everyone. Outside an active run they ASK: the human decides. There is no agent-side override; `CT6_DELETION_GUARD_DISABLED=1` in the launch environment is the HUMAN's lever, as every CT6 kill-switch is.

`git checkout -- <path>` / `git checkout HEAD -- <path>` / `git restore <path>` / `git rm <path>` are not in that list; they discard ONE path's content and follow the path's class (clean → allow, dirty → ask with the line count). `git restore --staged`, `git rm --cached`, `git clean -n`, `git stash list` touch nothing in the working tree and are not deletions.

## What each decision means for you

- **allow** — proceed. For `tracked-clean` the `additionalContext` carries the exact restore command; quote it in your evidence if the deletion is part of a reviewed change. The allow is still printed so the decision is visible in the transcript.
- **ask** — do not re-issue the same command hoping for a different answer, and do not reshape it to dodge the classifier (an unquoted glob, a `python -c`, a `| xargs` — these are classified MORE strictly, not less). Either (a) trash the path, (b) commit the content so it becomes `tracked-clean`, or (c) if the human is present, let them answer the prompt. A reshaped command that evades a guard is a discipline violation, not cleverness.
- **deny** — the operation is forbidden inside this run. Name the need to the Lead (`SendMessage`) or the user; never work around it.
- **nothing printed** — the command was not deletion-shaped. The guard is silent on ordinary commands so it costs nothing.

## The non-interactive fallback

In `claude -p`, a cloud session, a scheduled task, or any surface with no human at the prompt, an `ask` **is a denial** — the harness has nobody to ask, so the command does not run. Plan for it: in those modes use `trash` for anything that is not `temp` / `ignored` / `tracked-clean`, and treat an `ask` you did receive as the answer "no", not as a flaky hook. Do not retry.

## Honest boundaries

- **HEAD-recoverable is not remote-recoverable.** `tracked-clean` means the content is in the LOCAL repository's HEAD. If that commit was never pushed, a lost `.git/` (disk failure, `rm -rf` of the checkout, a worktree pruned by hand) loses it too. The restore hint names the remote branch only when one actually contains HEAD; when it says the commit may not be on the remote, believe it.
- **Gitignored is allowed, and gitignored can still be the only copy** — `.env`, local credentials, a downloaded dataset. The guard allows them because the repository declared them out of version control; it cannot know their worth. When you are unsure, trash instead.
- **The classifier reads the command text, not the process.** A deletion hidden inside a script file, a Makefile target, an npm script, or a binary is invisible to it. The rule still applies to you; the hook is a backstop, not the rule.
- **Heredoc Python** (`python - <<EOF`) is classified from the string literals in the text — a computed path yields `ask`, which is the intended direction.
- The guard proves what a command WOULD remove and whether that is recoverable; it does not prove the deletion was warranted. That judgment — and the trash-first habit — remain yours.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "It's just a scratch file, `rm` is fine" | If it is scratch the classifier says `temp` or `ignored` and allows it. If it says `untracked`, you were wrong about "just". |
| "I'll `git checkout -- .` to get a clean tree" | That is one path per modified file, each `tracked-dirty`, each someone's uncommitted work in a shared worktree. Commit or trash. |
| "The hook asked, I'll use a glob so it can't see the path" | A glob is `unparsable` → `ask`. Evasion is classified more strictly and is a discipline violation on its own. |
| "`git clean -fd` is the fastest way to reset the run dir" | It is on the forbidden list for exactly that reason: it also deletes every other teammate's `.architect-team/` evidence. Denied inside a run. |
| "It's committed, so deleting is free" | Committed LOCALLY. Check the hint: if HEAD is not on a remote branch, push first or accept the exposure knowingly. |

## From the constitution stub (moved v4.1.2)

Soft delete is the default — the `trash` verb of `hooks/deletion_guard.py` moves the content into the run's trash with a restore manifest — and a hard delete proceeds only when the guard's classifier (a PreToolUse hook on `Bash`) proves the content survives elsewhere: temp / gitignored / tracked-and-clean targets are allowed (tracked-and-clean with the restore command), tracked-and-dirty / untracked / outside-a-repo / unparsable targets ASK, and the shared-state git operations are denied during an active run. `CT6_DELETION_GUARD_DISABLED` is the human's lever.
