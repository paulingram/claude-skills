export const meta = {
  name: 'ct6-converge',
  description: 'CT6 reviewer convergence: N independent reviewers in parallel, a fixer on their deficiencies, loop until every reviewer returns ok',
  whenToUse: 'Any CT6 gate that needs independent reviewers to converge (codebase map, integration map, editability, interaction completeness, master review). Replaces the ralph-loop plugin (v4.0.0).',
  phases: [
    { title: 'Review', detail: 'independent reviewers, each blind to the others' },
    { title: 'Fix', detail: 'one fixer per round, briefed with every deficiency' },
  ],
}

// args (all optional except artifacts):
//   kind           label for logs, e.g. "codebase-map"
//   promise        the completion promise text, e.g. "CODEBASE MAP COMPLETE"
//   artifacts      repo-relative paths the reviewers audit
//   reviewerAgent  subagent type for reviewers, e.g. "architect-team:codebase-map-reviewer"
//   reviewerPrompt extra instructions for reviewers (the role file already carries the method)
//   fixerAgent     subagent type for the fixer, e.g. "architect-team:route-mapper"
//   fixerPrompt    extra instructions for the fixer
//   reviewers      how many independent reviewers per round (tier 3 => 3; tier 2 => 1)
//   maxRounds      HUMAN-set ceiling only; absent means no cap (the no-self-imposed-limits rule)
// The result (with its `record` block) is handed to scripts/converge/record.py, which
// writes it under .architect-team/converge/ and satisfies the declared gate ONLY when
// converged is true and every reviewer returned ok in the final round. Declare the
// gate BEFORE running this workflow (record.py declare); the Stop audit holds the run
// until the record exists.
const a = args || {}
const kind = a.kind || 'artifact'
const promise = a.promise || `${kind.toUpperCase()} COMPLETE`
const artifacts = Array.isArray(a.artifacts) ? a.artifacts : []
const reviewers = Number.isInteger(a.reviewers) && a.reviewers > 0 ? a.reviewers : 3
const maxRounds = Number.isInteger(a.maxRounds) && a.maxRounds > 0 ? a.maxRounds : null

const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    status: { type: 'string', enum: ['ok', 'deficient'] },
    deficiencies: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          where: { type: 'string' },
          what: { type: 'string' },
          evidence: { type: 'string' },
        },
        required: ['where', 'what'],
      },
    },
  },
  required: ['status', 'deficiencies'],
}

const FIX_SCHEMA = {
  type: 'object',
  properties: {
    changed: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
  required: ['changed'],
}

const history = []
let round = 0
while (true) {
  round += 1
  if (maxRounds && round > maxRounds) {
    log(`${kind}: human-set ceiling of ${maxRounds} rounds reached without convergence`)
    return { converged: false, promise, rounds: round - 1, history, reason: 'human-set round ceiling',
      record: { schema: 'ct6-converge/v1', kind, promise, reviewers, converged: false, rounds: round - 1, history } }
  }
  const verdicts = (await parallel(Array.from({ length: reviewers }, (_, i) => () =>
    agent(
      [
        `You are reviewer ${i + 1} of ${reviewers} for the ${kind} convergence gate (round ${round}).`,
        `Audit these artifacts independently; do not assume the other reviewers exist: ${artifacts.join(', ') || '(see your brief)'}.`,
        a.reviewerPrompt || '',
        `Return status "ok" only when you found nothing to fix; otherwise "deficient" with every deficiency (where, what, evidence).`,
      ].join('\n'),
      Object.assign({ label: `${kind} review ${round}.${i + 1}`, phase: 'Review', schema: REVIEW_SCHEMA },
        a.reviewerAgent ? { agentType: a.reviewerAgent } : {})
    )
  ))).filter(Boolean)

  const deficiencies = verdicts.flatMap(v => v.status === 'ok' ? [] : v.deficiencies)
  const okCount = verdicts.filter(v => v.status === 'ok').length
  history.push({ round, reviewers_returned: verdicts.length, ok: okCount, deficiencies: deficiencies.length })
  log(`${kind} round ${round}: ${okCount}/${reviewers} ok, ${deficiencies.length} deficiencies`)

  if (verdicts.length === reviewers && okCount === reviewers) {
    log(promise)
    return { converged: true, promise, rounds: round, history,
      record: { schema: 'ct6-converge/v1', kind, promise, reviewers, converged: true, rounds: round, history } }
  }

  const fix = await agent(
    [
      `You are the fixer for the ${kind} convergence gate (round ${round}).`,
      `Artifacts: ${artifacts.join(', ') || '(see your brief)'}.`,
      a.fixerPrompt || '',
      verdicts.length < reviewers ? `${reviewers - verdicts.length} reviewer(s) returned nothing this round; treat their silence as "not yet verified", never as ok.` : '',
      `Resolve EVERY deficiency below with a targeted update (never a rewrite of what already passes), then list what you changed:`,
      JSON.stringify(deficiencies, null, 2),
    ].join('\n'),
    Object.assign({ label: `${kind} fix ${round}`, phase: 'Fix', schema: FIX_SCHEMA },
      a.fixerAgent ? { agentType: a.fixerAgent } : {})
  )
  if (!fix) {
    log(`${kind} round ${round}: the fixer returned nothing; re-reviewing`)
  }
}
