# Reading teammate state

An orchestrator coordinating parallel teammates is constantly tempted to convert *absence of a report* into *a finding about the teammate*. It is not one. A teammate is in exactly one of three KNOWABLE states, and only two of them support a conclusion:

| State | How you know it | What it supports |
|---|---|---|
| **(a) Reported** | A handoff file under `.architect-team/handoffs/`, a review-evidence file under `.architect-team/reviews/`, or the teammate's own dispatch report is on disk | Any claim the artifact substantiates — including "it left this broken", quoting the artifact |
| **(b) Idle-event fired** | The `SubagentStop` / teammate-idle hook ran for that teammate (its output is the record) | "It went idle with work outstanding", quoting the hook's structured gap list |
| **(c) In-flight** | Neither (a) nor (b) has happened yet | **Nothing.** Not "stalled", not "failed", not "stuck", not "did no work" |

**A claim that a teammate stalled, failed, went idle, or left work broken MUST cite (a) or (b); state (c) supports no conclusion.** In-flight is indistinguishable from a teammate that is mid-edit, mid-tool-call, or whose report crossed yours in flight — silence is not a finding. If you need to know, ASK the teammate directly (`SendMessage`) and wait for the answer; the answer is then evidence of kind (a). Reporting a state-(c) teammate as stalled to the user is the *silence conversion* anti-pattern in `docs/ETHOS.md` `## Evidence integrity`.

**Corollary — the mid-edit read.** A suite run on the SHARED working tree while any teammate is in-flight on intersecting scope is a MID-EDIT READ: it samples a tree that is half-way between one teammate's implementation change and its test/expectation update. Red from such a run is **unattributable** until the owner reports — it may be the owner's transient state, not a defect, and it is never attributable to a DIFFERENT teammate whose files the run also swept. Options, in order: scope the run to files no in-flight teammate owns (`git diff $BASELINE_SHA -- <files>` tells you who owns what); wait for the owner's state-(a) report; or run and record the result as *provisional, pending the owner's report* — never as a finding against a named teammate. The non-overlapping file-scope rule at the top of this skill is what makes the scoped option available; the baseline-SHA discipline is what makes it cheap.
