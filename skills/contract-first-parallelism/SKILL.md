---
name: contract-first-parallelism
description: "Use whenever a run needs BOTH backend surface work AND a frontend that visualizes that data — a full-stack build from scratch, or an integration with existing services where the frontend needs inbound surfaces. The architect's parallelism protocol: the frontend and backend agents co-design the inbound surface contract, the architect approves it, the backend IMMEDIATELY provisions the endpoint AT ITS REAL PATH serving a contract-conforming mock payload, and the frontend then builds a fully integrated interface against that LIVE endpoint while the backend replaces the mock internals underneath. Neither side waits for the other. The same protocol covers a surface that already exists but needs new attributes. Every provisioned mock is a tracked, temporary scaffold recorded in a ledger; the deterministic engine (scripts/contract/interface_contract.py) makes a run non-closable while any surface is still mock-serving, so the parallelism borrowed is always repaid."
---

# Contract-First Parallelism (CFP-1 … CFP-6)

The frontend does not need the backend's **implementation**. It needs the
backend's **interface**. Those two things become available at wildly different
times, and treating them as one is what serializes a full-stack run.

So: settle the interface first, make it REAL immediately, and let both sides
build against it at the same time.

## The problem this replaces

The default flow serializes. The frontend reaches an element that needs data,
finds no endpoint, authors a missing-API SR, and **pauses that element**. The
backend then designs, implements, tests, and reports the endpoint. Only then is
the frontend re-dispatched to wire it. The frontend spent that entire span
blocked on build time it never actually needed to wait for — it was only ever
waiting on the *shape*.

## The protocol

### CFP-1 — Detect (architect)

Engage this protocol when BOTH hold:

- the run must add or change backend surfaces (endpoints, response payloads), AND
- the frontend needs those surfaces to visualize data — it cannot finish its
  slice without them.

Two shapes, one protocol:

| Shape | Condition | What gets provisioned |
|---|---|---|
| `new-surface` | The endpoint does not exist. | The whole endpoint at its real path, mock payload. |
| `amend-surface` | The endpoint exists but lacks attributes the UI must render. | The same live endpoint, its response extended with the new attributes carrying mock values. |

The second is NOT a lesser case: a frontend blocked on three new fields is as
blocked as one waiting on a whole endpoint. Same protocol.

Green-field full-stack builds engage this by default at Phase 2 — every surface
the frontend consumes is a CFP contract.

### CFP-2 — Co-design the contract (frontend + backend, together)

The two agents that will live with the surface design it together — not the
architect alone, and never one side dictating to the other:

- **The frontend states what it must render**: which fields, what each one
  means in the UI, what the empty / loading / error states look like, what
  drives pagination or filtering.
- **The backend states what is authoritative and feasible**: which fields the
  real source can actually produce, what they cost, what the honest error
  states are, where the shape must differ from the frontend's wish.

In teams mode this is a direct `SendMessage` exchange between the two named
teammates; in subagents mode the orchestrator relays the exchange. Either way
it is a CONVERSATION with a written artifact, not a handoff.

The output is the contract data (`contract_id`, `shape`, `method`, `path`,
`consumer`, `owner`, `purpose`, `response_fields` — each with a name, a type,
and its meaning — `error_states`, and for `amend-surface` the `added_fields`).

### CFP-3 — Architect approval (the binding moment)

The architect (`system-architect`, `## Interface Contract Approval`) reviews and
approves. Run the engine's gate first — a contract that cannot pass it cannot
be built against:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" validate --json <contract.json> || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" validate --json <contract.json>
```

Zero error-severity findings is the bar. The architect additionally judges what
the engine cannot: does this shape serve the actual user-facing requirement, does
it fit the existing API conventions in `CODEBASE_MAP` / `API_DESIGN_MAP`, does it
reuse rather than duplicate an existing surface (reuse-first still applies — the
cheapest contract is the one that already exists).

**Once approved the contract is BINDING.** Neither side changes it unilaterally.
A change either side discovers to be necessary goes back through the architect as
an amendment, and the architect tells the other side. This is what makes the
parallelism safe: the frontend is building against a promise, so the promise
cannot move silently.

Write the approved contract to
`<workspace>/.architect-team/contracts/<contract-id>.json` and render the
artifact (`... doc --json <contract.json> --out <contract-id>.md`).

### CFP-4 — Immediate provisioning (backend, first action)

The backend provisions the surface **immediately** — before it builds the real
logic, as the first thing it does with the approved contract:

1. **At the REAL path.** The endpoint lives exactly where the contract says it
   will live. The frontend must never call a temporary path, a different port,
   or a "mock server" it will later have to be re-pointed away from. Re-pointing
   is exactly the rework this protocol exists to avoid.
2. **Serving a contract-conforming payload.** Every declared field present, with
   the declared type, carrying plausible representative values. Every declared
   error state reachable (a documented trigger — a query flag, a known id — so
   the frontend can build and test its error paths on day one).
3. **Marked as mock, in the response and in the ledger.** The payload carries an
   explicit provisional marker the retirement check can see (e.g. a
   `"_mock": true` envelope field or the documented project equivalent), and the
   surface is recorded in
   `<workspace>/.architect-team/contracts/ledger.json` with state
   `mock-serving`, its owner, and its consumer.
4. **Announced.** The backend tells the frontend the surface is live. The
   frontend starts integrating in the same phase — this is the moment the
   parallelism is won.

The mock is **server-side, behind the real path**. This is the whole point and
it is why this is not the forbidden pattern: the frontend holds no fixture, no
`page.route` intercept, no hardcoded shape. It performs real HTTP against a real
endpoint and renders what comes back. See `## Relationship to the no-fake-data
disciplines`.

### CFP-5 — Parallel build (both, simultaneously)

- **Frontend** builds the COMPLETE integration against the live endpoint: real
  fetch, real deserialization, real loading and empty and error states, real
  rendering per `dynamic-value-discovery`. Its slice can reach done-shaped —
  fully wired, tested against a live surface — without the backend's internals
  existing. It does NOT wait, and it does NOT hedge with a local fallback.
- **Backend** replaces the mock internals with the real data source, honoring the
  contract exactly. It may change anything under the hood — data access, caching,
  the service layer, the schema — because the only thing the frontend depends on
  is the contract, and the contract is not moving.

If either side discovers the contract must change, it goes back to CFP-3. It
does not adapt around a mismatch quietly.

### CFP-6 — Retirement gate (mandatory, before the run can close)

The parallelism was borrowed against a mock. Closing the run repays it.

For every contract, the backend flips the surface to real data and the change is
verified end-to-end **through the same live path the frontend already calls** —
the frontend needs no change at retirement, which is the proof the abstraction
held. Record `verified_by` (the evidence: the integration test, the Playwright
flow, the observed payload) and transition the entry to `live`.

Confirm the delivered shape still matches what was approved:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" drift --json <contract.json> --observed <observed-payload.json> || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" drift --json <contract.json> --observed <observed-payload.json>
```

Then the gate itself, which the pipeline runs at close-out:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger <workspace>/.architect-team/contracts/ledger.json || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger <workspace>/.architect-team/contracts/ledger.json
```

**Any surface still `mock-serving` (or earlier) is a blocking finding and the run
does not close.** A mock that outlives its run is exactly the technical debt the
no-fake-data disciplines exist to prevent — the ledger is what makes the
temporary genuinely temporary. There is no "retire it next run" disposition;
that is the end-of-run deferral the `no-end-of-run-deferral` discipline forbids.

The ledger state machine is forward-only: `proposed → approved → mock-serving →
live`. A live surface never reverts to serving its mock.

## Relationship to the no-fake-data disciplines

This protocol does not weaken them — it is the sanctioned way to satisfy them
while staying parallel. The distinction is WHERE the provisional data lives:

| Forbidden (unchanged) | This protocol |
|---|---|
| Frontend renders a mockup literal as if dynamic. | Frontend renders whatever the live endpoint returns. |
| Frontend intercepts the network (`page.route`) and calls it tested. | No interception; real HTTP to the real path. |
| Frontend hardcodes the response shape in a component. | Shape comes from the wire, per the approved contract. |
| A mock with no owner and no expiry becomes permanent debt. | Every mock is ledger-tracked and gate-enforced to `live` before close. |

`agents/frontend.md` `## Missing-API discipline` still governs the case where NO
contract-first protocol is running: the frontend authors the SR and pauses that
element rather than improvising. CFP is the DEFAULT when the architect has
engaged it at Phase 2; the SR-and-pause path is the fallback for a surface
discovered mid-slice that the architect has not yet contracted.

When a surface is discovered mid-slice, the frontend's SR is a fine entry point:
the architect can convert it into a CFP contract (the SR already documents the
shape) and get the frontend unblocked in one provisioning step instead of a full
backend round trip.

## What the architect owns

1. **Detecting the condition** at Phase 2, before teams are spawned — so the
   contracts exist and the surfaces are provisioned while the teams start, not
   after they block.
2. **Approving contracts** and holding them binding.
3. **Refusing a contract that cannot be built against** — an untyped field, a
   missing error state, a surface that duplicates an existing one.
4. **Owning the ledger** as run state, and refusing to close the run while it
   carries an unretired entry.

## Honest boundary

The engine adjudicates SHAPE — contract completeness, ledger state, drift
against an observed payload — and never performs HTTP: the observed payload is
supplied by the agent that actually hit the endpoint. "Plausible representative
values" in a mock payload is LLM judgment, not a machine check. And the
protocol's benefit is real but bounded: it removes the frontend's wait on
backend BUILD time; it does not remove the need for the real implementation,
and the retirement gate is what keeps that honest.
