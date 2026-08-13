# Design: close-the-open-items

## Context

Three fixes, one of which is load-bearing and two of which are its symptoms. The design question for all three is the same: **what makes a rule forcing rather than advisory?**

The evidence for why this matters is the session that produced the change. The completion lock exists because agent-asserted state cannot be trusted. It reads the harness task store for exactly that reason. And for four consecutive releases it read an empty store, because nothing registered the work — so the orchestrator's stop was, in practice, self-declared again. The gate was not evaded. It was never entered.

## Reuse Decisions

| New thing proposed | Decision | What it reuses instead |
|---|---|---|
| A second harness-task reader | **REJECTED** | `hooks/open_work.py`'s `read_harness_tasks` / `tasks_root` — one reader, one seam |
| A new hook script for the registration arm | **REJECTED** | A new arm inside `pipeline-completion-audit.py`, beside `_audit_frontend_e2e` |
| A new suite gate for measurement claims | **REJECTED** | `scripts/docs_tooling/changelog_check.py` already mechanizes the CHANGELOG's machine-checkable invariants and is already suite-gated |
| A measurement engine | **NEW** (`scripts/measure/`) | Nothing existing brackets a run; the hand-written v3.59.3 artifact is the shape, not an implementation |
| `pytest.skip` for machine-bound tests | **FORBIDDEN** | Self-provisioning in `tmp_path`, or a committed fixture |

## Decision: the registration arm triggers on the marker, not on everything

The obvious over-reach is to refuse any session that has registered no tasks. That would wedge every plain session in every project the user types in — the same blast-radius mistake the ask-ledger made when it shipped blocking and had to be demoted within a day.

So the trigger is an **ACTIVE `active-run.json`**. Inside a run, "I have registered nothing" is a real defect; outside one it is the ordinary state of a conversation. The v3.56.0 lock already covers plain sessions once work IS registered.

Note the honest asymmetry: `active-run.json` is **agent-written**, so an agent could avoid the arm by never engaging the marker. That is not a new hole — a run that never engages is already outside every continuity gate, and the v3.55.2/v3.55.4 releases exist precisely because a lane that failed to engage was invisible to them. The arm makes the *engaged* case forcing; the unengaged case remains covered by the real-time skill gate, which blocks build tools until the pipeline Skill is invoked.

## Decision: "no tasks" is an open-work condition, not a new kind of error

The arm composes with the existing lock rather than sitting beside it. An active run with zero registered tasks is treated as open work, so it flows through the same block message, the same kill-switch discipline, and the same release paths. Two consequences worth stating:

- It fires **only** on the empty case. If tasks exist and any is open, the ordinary task-list source is already blocking and this arm adds nothing.
- Marking the run complete releases it — and that path is already gated by every other audit arm. The arm does not need to re-police completion; it needs to stop *silent* completion.

## Decision: an artifact that can be hand-written is still worth emitting

`scripts/measure/` cannot prove a run happened. Anyone can write the JSON. That objection is real and it does not defeat the change, because the failure being fixed is not fabrication — nobody in this session invented a number. The failure is that a genuine measurement left **no trace**, so it could not be checked later even by the person who made it.

An emitted artifact converts "trust the prose" into "read the file", and an OPEN bracket becomes a first-class failure instead of a footnote. The residual — a determined agent writing a false artifact — is named, not papered over, and is the same residual every Layer-3 tool carries: they all read agent-supplied artifacts.

## Decision: skipping is not fixing

The tempting resolution for the five machine-bound tests is `pytest.skip` when the fixture is absent. That is refused. A skip makes a pristine run *green* while the published number is still unreproducible — it converts a visible gap into an invisible one, and the count keeps lying. Self-provisioning is preferred over committing fixtures because a fixture built by the test can never drift from what the test needs.

## Decision: identify by measurement, not by reading

The failing tests are found by running a pristine worktree, not by grepping for `.architect-team`. The orchestrator already tried the grep and it returned nothing — the wrong instrument, which is this repo's current subject. A prior worktree attempt also died on a Windows path-length limit; the short-path retry is part of the method, recorded so the next run does not rediscover it.

## Risks

| Risk | Mitigation |
|---|---|
| The registration arm wedges ordinary sessions | Trigger requires an ACTIVE run marker; a both-directions test pins the plain-session case |
| It double-blocks with the existing task source | Fires only on the empty case; pinned |
| The measurement gate fires on prose that merely mentions a number | Detection scoped to release-note claim shapes, with an honest-counterpart test |
| "Fixing" the machine-bound tests by weakening them | Each fixed test must still bite under mutation |
| The published count changes and nobody notices | The pristine run IS the acceptance criterion, and its tail is pasted |
