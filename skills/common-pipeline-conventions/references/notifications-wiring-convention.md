# Notifications wiring convention (per-project email events — opt-in, best-effort)

A pipeline run is a long, mostly-unattended sequence of phases. The plugin ships an **opt-in per-project email notifier** so a configured list of stakeholders is kept informed as a run progresses. Every pipeline wires it at the canonical event points below.

**How it works.** If the target project's repository root contains a `.architect-team-notify.json` config file, the orchestrator emits notification events by invoking the notifier CLI at the wiring points marked in each pipeline's body. The notifier is a CLI the orchestrator invokes — **not a harness hook** — so it is driven by the same trust-based-Markdown mechanism as every other phase discipline. If the target project has **no** `.architect-team-notify.json`, the notifier is a silent no-op and the run behaves exactly as before; the feature is entirely opt-in.

**Invocation form** — run from the target project's repository root, using the polyglot Python invocation (`## Cross-platform Python invocation` above):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" <event> --project <name> [--phase ... | --summary ... | --commit ... | --layer ...] || python "${CLAUDE_PLUGIN_ROOT}/scripts/notify/notify.py" <event> --project <name> [--phase ... | --summary ... | --commit ... | --layer ...]
```

**The ten recognized event types (v3.34.0).** `<event>` is one of:

| Event | Fires | Key context flags |
|---|---|---|
| `run_start` | ONCE per run, at the moment the architecture + solution plan first exists (see run-level bookends below). The kickoff email — it embeds the plan artifacts THEMSELVES. | `--run-id`, `--details` (the requirement summary), `--plan-file <path>` (repeatable — proposal / design / tasks), `--next-step` |
| `phase_start` | At the start of each phase (the first action of that phase). | `--phase`, `--details` (what this phase is about to do), `--progress`, `--next-step` |
| `phase_complete` | At the end of each phase (the last action before moving on). | `--phase`, `--details` (what the phase accomplished), `--progress`, `--next-step` |
| `waiting_on_agents` | Whenever the Lead dispatches agents/teammates and enters a wait (see dispatch-wait pair below). | `--phase`, `--agents "<name — mission; name — mission>"`, `--details` |
| `agents_complete` | When every agent in that dispatch has returned. | `--phase`, `--agents "<name — outcome; name — outcome>"`, `--details` |
| `issue_discovered` | When an SR is picked up (main pipeline Phase 3b) or a fresh SR is written from a `bug-still-present` / `test-did-not-exercise-fix` verdict (bug-fix pipeline Phase B6) or a red verdict (mini pipeline Phase M8) or a confirmed UX-flow failure is routed (ux-test Phase U8). | `--summary`, `--details` |
| `git_commit` | Immediately after a pipeline-produced commit succeeds. | `--commit <SHA>`, `--details` (what the commit ships) |
| `deploy` | When the live dev environment is brought up. | `--layer <layer>`, `--details` |
| `run_complete` | ONCE per run, as the run's FINAL notification — the run finished end-to-end. | `--run-id`, `--elapsed`, `--commit <final SHA>`, `--details` (what shipped), `--progress` |
| `heartbeat` | NOT phase-wired — fires on the heartbeat tick (>30-min phases / post-first-hour boundaries) per the Unbounded-solving discipline's Heartbeat sub-section (v3.10.0). | `--run-id`, `--phase`, `--elapsed`, `--qa-cycles`, `--agents-dispatched` |

`notify.EVENT_TYPES` carries all ten; `phase_start` / `phase_complete` / `issue_discovered` / `git_commit` / `deploy` are the classic phase-wired subset, the v3.34.0 additions (`run_start`, `waiting_on_agents`, `agents_complete`, `run_complete`) are run-level and dispatch-level wiring, and `heartbeat` remains tick-driven.

**Informative, not just status — the content contract (v3.34.0).** The goal of these emails is that a stakeholder reading ONLY the emails can follow the run: what is about to start, where the run stands, and what was completed. Every notifier invocation therefore carries meaningful content, not a bare event name:

- **Every `phase_start`** passes `--details` with 1–3 plain-language sentences on what the phase is about to do *for this run* (e.g., `--details "Spawning a backend team for the JWT/session slice and a frontend team for the dashboard slice; each gets a paired adversarial reviewer."`), plus `--progress "<N> of <M> phases complete — <one-line recap>"` and `--next-step` when known.
- **Every `phase_complete`** passes `--details` describing what the phase actually accomplished (artifacts produced, verdicts reached, counts — not "phase done"), plus `--progress`.
- The **first `phase_start` of a run** additionally carries the requirement summary in `--details` — the engagement email — so recipients learn a run has begun *and what it is for* the moment the pipeline engages.
- A bare invocation without `--details` is non-compliant wiring except for `heartbeat` (whose liveness fields are its content) — if the orchestrator knows enough to emit the event, it knows enough to say what it means.

**Run-level bookends (`run_start` / `run_complete`) — v3.34.0.** `run_start` fires ONCE per run at the moment the architecture + solution plan first exists — main pipeline: end of Phase 1 (the validated OpenSpec bundle); bug-fix: end of B3 (the approved fix proposal); mini: end of M3 (the self-confirmed 5-artifact bundle); ux-test: end of U4 (the distilled flow catalog). It passes `--plan-file <path>` once per plan artifact (proposal.md, design.md, tasks.md — or the pipeline's equivalent) so the ONE kickoff email carries the architecture and solution plan in full (the notifier embeds each file under its own header, capped per file, missing files degrading to a note). `run_complete` fires ONCE as the run's final notification — after the last phase's `phase_complete` (Phase 8 / B8 / M7-green / U9), carrying `--details` (what shipped, test results), `--elapsed`, and `--commit <final SHA>` when a commit was produced.

**Dispatch-wait pair (`waiting_on_agents` / `agents_complete`) — v3.34.0.** At EVERY point where the Lead dispatches agents/teammates and enters a wait (team spawns, review swarms, diagnostic researchers, fix teams, parallel explorers/executors), the orchestrator emits `waiting_on_agents` naming each agent and its mission via `--agents "<name — mission>; <name — mission>"`; when that dispatch has fully returned, it emits `agents_complete` with the per-agent outcomes. Recipients always know when the run is blocked waiting on agents and when that wait ended. Pipelines name their major dispatch points inline; the rule applies to every dispatch-and-wait, named or not.

**Phase-boundary wiring (`phase_start` / `phase_complete`) — applies to every phase in every pipeline.** At the **start of each phase** the orchestrator emits `phase_start` (first action); at the **end of each phase** it emits `phase_complete` (last action before moving on); both pass `--phase "<canonical phase name>"` plus the informative flags per the content contract above, via the invocation form. These are best-effort exactly like every other notifier call — emitting them, or failing to, never blocks the phase. The remaining moment events (`issue_discovered`, `git_commit`, `deploy`) and the run/dispatch events are wired at specific phase steps inline in each pipeline's body (per-phase content, not cross-cutting boilerplate). This wiring applies to **every pipeline-driving skill** — the main architect-team pipeline, the bug-fix pipeline, the mini pipeline, and the ux-test builder alike: engaging ANY architect-team task emits its notifications.

**Best-effort, never gating — non-negotiable.** Every notifier invocation across every pipeline is **best-effort**: the notifier always exits 0, and a notification failure (missing config, missing provider secret, SMTP/network error, malformed input) NEVER blocks, fails, or alters a pipeline run. The orchestrator invokes the notifier and proceeds immediately to the next pipeline step regardless of the notifier's output — these invocations are notifications about pipeline progress, never preconditions for it. Do not gate, retry, or wait on a notifier invocation.
