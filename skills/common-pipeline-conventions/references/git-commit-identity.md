# Git commit identity discipline (v3.67.0) — full text

> The canonical home of the rule summarized in `skills/common-pipeline-conventions/SKILL.md` `## Git commit identity discipline (v3.67.0)`. Execute it in full before the first commit-authoring git command of a run; do not work from memory.

## The defect this closes

A run commits on behalf of whoever is driving it, in whatever repo they point CT6 at. Until v3.67.0 the identity came from wherever git happened to find one — the repo's ambient config (unset on a fresh clone, or wrong), or a hardcoded author override that belonged to ONE maintainer's own repo and had leaked into a shipped skill body, so every user of that lane committed as that maintainer. Neither is a decision the tool may make for the user. **The tool never decides who a commit is attributed to.**

## The record

`<main-worktree>/.architect-team/git-identity.json`:

```json
{
  "name": "Ada Lovelace",
  "email": "ada@example.test",
  "source": "asked | user-stated | confirmed-local-git-config | confirmed-global-git-config",
  "recorded_at": "2026-08-29T10:00:00Z"
}
```

- **One record per checkout.** It resolves to the MAIN worktree (`parent(git rev-parse --git-common-dir)`), so every run worktree of the checkout shares it — the `shared_state_dir()` rule.
- **Never committed.** `.architect-team/` is gitignored; identity is per PERSON, and a committed record would make one collaborator's identity everyone's.
- **Never derived from git config silently, never written INTO git config.** CT6 reads `git config` only to propose a candidate; the user's git config stays the user's.
- **`source` is the evidence trail** — it says how the identity was established. `asked` / `user-stated` = the user gave it; `confirmed-*-git-config` = a candidate the user explicitly confirmed.

## Resolution order — `hooks/git_identity.py resolve`

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" resolve --json
```

Prints `{"status": "recorded" | "candidate" | "missing", "name", "email", "source", "record_path"}` and exits 0 whenever resolution succeeded (the status is in the output — a non-zero exit is an error, never a status, so the polyglot `||` form is safe).

1. **`recorded`** — use it. One line to the user: *"Committing as `<name> <email>` (recorded for this checkout)."* No question.
2. **`candidate`** — git's local (first) or global (second) config names someone. This is a PROPOSAL: ask via `AskUserQuestion` — *"Commit as `<name> <email>`? (found in this repo's local / your global git config)"* — with two options: **Yes, record it for this checkout** / **No — I'll give a different name and email**. Record the answer with `--source confirmed-local-git-config` / `confirmed-global-git-config`, or `--source asked` when they typed a different one.
3. **`missing`** — nothing is configured anywhere. Ask via `AskUserQuestion` (free text): *"Who should this run's commits be attributed to? Reply `Name <email>`."* Record with `--source asked`.

Then:

```bash
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" set --name "<name>" --email "<email>" --source <asked|confirmed-local-git-config|confirmed-global-git-config>
```

`set` REFUSES (exit 2) a blank name, a newline in the name, or an email without an `@` / with whitespace or angle brackets — a refusal, never a silent default.

**This is a DOMAIN gate** (the v0.9.21 carve-out): the answer is the user's own fact, so the question fires regardless of `--proposal-first` and is never a "process gate" the default-to-action rule may skip. It fires ONCE per checkout — the record is the memory. It runs at the front door — after the dispatch banner, BEFORE the auto-cleanup / branch-reconciliation / auto-worktree steps can author anything — in every lane command: `/architect-team`, `/architect-team:bug-fix`, `/architect-team:mini`, `/architect-team:data-eng`, `/architect-team:ux-test`, `/architect-team:playwright-suite`.

## Every commit-authoring command carries the record

`commit`, `merge` and `revert` author commits. Each one a run issues carries the recorded identity EXPLICITLY — the checkout's ambient git config is never relied on (the typo'd or missing config is the case this exists for):

```bash
# the wrapper — injects `-c user.name=… -c user.email=…` from the record; REFUSES (exit 2) when unrecorded
$(command -v python3 || command -v python) "${CLAUDE_PLUGIN_ROOT}/hooks/git_identity.py" --cwd "<workspace>" git -- -C <repo-root> commit -m "<message>"

# or the explicit pair, read from the record (`git_identity.py status --json`)
git -C <repo-root> -c user.name="<name>" -c user.email="<email>" commit -m "<message>"
```

The auto-merge helper (`scripts/setup/worktree_lifecycle.py::merge_branch_to_main_and_prune`) reads the same record and authors the merge commit as that person. The Phase 8 / B8 / M7 / D8 / U9 / P9 commit steps each say so.

## Enforcement — `hooks/pretool_skill_gate.py` Arm 4

During an ACTIVE, non-stale run, a Bash command that authors a commit is REFUSED when the checkout has no record, when the command carries no `-c user.name= / -c user.email=` pair (and is not the wrapper), or when it carries a DIFFERENT identity. The block prints the exact wrapper command and the required action. Deliberate shape, pinned in `tests/test_git_identity.py`: payload-only (no transcript dependence); scoped to the run marker so a plain session's own git usage is never hijacked; `escalation-pending.md` does not stand it down; its own kill-switch `CT6_GIT_IDENTITY_GATE_DISABLED=1` (read from the environment Claude Code was launched from) is the human's lever.

## Changing the identity

The user says who they are; the tool records it. *"Commit as Jane Doe <jane@example.test> from now on"* → `git_identity.py set --name "Jane Doe" --email jane@example.test --source user-stated`. An agent never changes a record on its own initiative, and never "corrects" a name it thinks is misspelled — it asks.

## Honest boundary

The arm proves a record EXISTS and that every commit CARRIES it; it cannot prove the user was asked before the record was written. The `source` field plus the front-door step (a visible `AskUserQuestion` in the transcript) are the evidence trail; an agent that writes a record without asking has violated the discipline, and the record's `source: asked` on a transcript with no question is the tell a reviewer looks for.

## Anti-pattern rationalizations to reject

| Rationalization | Rebuttal |
|---|---|
| "git config already has a name, I'll just use it" | A candidate is confirmed, never adopted. The config on this machine may be a typo, a previous employer, or nobody. |
| "The repo's CLAUDE.md shows an author override, I'll reuse it" | That override is ONE person's, for ONE repo. Reusing it commits as someone else. Ask. |
| "Asking is a process gate; default-to-action says proceed" | Identity is a domain gate — the user's fact, not a process choice. |
| "I'll set the user's git config so future commits work" | CT6 writes its own record; the user's git config is theirs. |
| "It's just the merge commit" | A merge authors a commit. It carries the record like every other. |

## From the constitution stub (moved v4.1.2)

The rule: a run commits as the PERSON driving it, and the tool never decides who that is. The front door resolves it once per checkout (`hooks/git_identity.py resolve`): a recorded `<main-worktree>/.architect-team/git-identity.json` is used silently; a candidate from local/global git config is CONFIRMED with the user first; nothing found means the user is ASKED for name + email — a domain gate, never a hardcoded default, never the user's git config rewritten. Every commit-authoring command then carries the record explicitly (the `git_identity.py git --` wrapper or `-c user.name=… -c user.email=…`), and `pretool_skill_gate.py` Arm 4 refuses one that lacks or contradicts it during an active run (`CT6_GIT_IDENTITY_GATE_DISABLED` is the human's lever).
