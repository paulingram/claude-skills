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

**Shape the containers, not just the top level.** A field typed `array` declares
its element shape under `items`; a field typed `object` declares its members
under `fields` — both taking the same list-of-declarations form as
`response_fields`, so the contract binds all the way down and the drift check
adjudicates nested fields by their payload path (`items[].total`, `meta.count`).
This matters most for the commonest REST shape of all: a collection response
whose element shape is the thing most likely to move while the backend swaps its
internals. A container left unshaped still validates, but as an ADVISORY that
says so out loud — the architect is told the contract does not constrain its
contents, rather than the gap passing silently. Model a collection as a declared
`array` field on the response object; the drift check adjudicates named fields,
so a bare top-level JSON array is reported as a payload it cannot bind rather
than being crashed on or waved through.

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
   the declared type, carrying plausible representative values drawn from the
   project's own domain vocabulary. Every declared error state reachable (a
   documented trigger — a query flag, a known id — so the frontend can build and
   test its error paths on day one). The handler is production backend code, so
   the `verify-no-fake-data` sweep applies to it in full: see
   `## Relationship to the no-fake-data disciplines` for the values to avoid.
3. **Marked as mock — in the payload, in the ledger, and in the gate registry.**
   Three records, because three different things read them:

   - **The payload** carries an explicit provisional marker: `"_mock": true`, or
     the contract's own `provisional_marker`. This is a MACHINE check, not a
     convention — the CFP-6 retirement drift check (`drift --retirement`) blocks
     on that marker at any depth, so a surface cannot be called retired while it
     still serves its envelope. Never DECLARE the marker in `response_fields`;
     the approval gate refuses that, because a declared marker would be a
     permanently legitimate one.
   - **The ledger** at `<workspace>/.architect-team/contracts/ledger.json`
     records the surface with state `mock-serving`, its owner, and its consumer.
     The file is either a bare JSON array of entries or an object wrapping that
     array under `"contracts"` — nothing else. The gate reads it and FAILS
     CLOSED: an unrecognized state, an entry that is not an object, and an
     unrecognized wrapper each block with a named reason rather than reading as
     an empty ledger. A gate that reports the all-clear on input it could not
     parse is worse than no gate at all.
   - **The declared-gates registry** takes one entry per contract, so retirement
     is enforced by machinery rather than by memory:

     ```
     python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" declare-gate --json <contract.json> --registry "<workspace>/.architect-team/declared-gates.json" || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" declare-gate --json <contract.json> --registry "<workspace>/.architect-team/declared-gates.json"
     ```

     That records `cfp-retirement-<contract-id>`, and the v3.47.0 Stop-hook
     completion audit then refuses to let the run finish until that entry carries
     a `satisfied_at` and an evidence file with bytes in it. Re-declaring is a
     no-op, and gates other disciplines recorded are left untouched.
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

Confirm the delivered shape still matches what was approved, in the retirement
reading — which additionally requires the provisional marker to be GONE:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" drift --json <contract.json> --observed <observed-payload.json> --retirement || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" drift --json <contract.json> --observed <observed-payload.json> --retirement
```

Then the gate itself, which the pipeline runs at close-out:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger <workspace>/.architect-team/contracts/ledger.json || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" gate --ledger <workspace>/.architect-team/contracts/ledger.json
```

**Any surface still `mock-serving` (or earlier) is a blocking finding and the run
does not close** — and so is any entry the gate cannot read (see CFP-4's ledger
rules). A mock that outlives its run is exactly the technical debt the
no-fake-data disciplines exist to prevent — the ledger is what makes the
temporary genuinely temporary. There is no "retire it next run" disposition;
that is the end-of-run deferral the `no-end-of-run-deferral` discipline forbids.
A run that recorded no contracts has no ledger file, and the gate says so and
exits clean — an absent ledger is a no-op, not a failure.

Capture the gate's output, then close the declared gate each contract opened:

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" satisfy-gate --gate-id cfp-retirement-<contract-id> --evidence <captured-gate-output.txt> --registry "<workspace>/.architect-team/declared-gates.json" || python "${CLAUDE_PLUGIN_ROOT}/scripts/contract/interface_contract.py" satisfy-gate --gate-id cfp-retirement-<contract-id> --evidence <captured-gate-output.txt> --registry "<workspace>/.architect-team/declared-gates.json"
```

Until that lands, the Stop-hook completion audit blocks the run and quotes the
gate's own declaration back. Never edit or delete a registry entry to get past
it — that is the unilateral override the meta-gate catches.

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
| Placeholder values sitting in production code. | The mock handler is production code and is swept like any other — see below. |

**The backend handler is production code, and the sweep applies to it.** The
Layer-3 `verify-no-fake-data` verifier (`hooks/vao/fake_data.py`) exempts test
paths, not backend handlers, so a provisioned mock at a real path is swept in
full — and the adversarial reviewer paired with the backend teammate will flag
it, correctly, if it trips. The protocol does not carve out an exemption: an
exemption would have to outlive the mock to be useful, which is exactly the
permanence the ledger exists to prevent. Instead, CFP-4's "plausible
representative values" means values from the project's own domain vocabulary,
which are more useful to the frontend anyway. Concretely, the mock must avoid the
verifier's forbidden vocabulary: `placeholder-name` (`Jane Doe`, `John Smith`),
`placeholder-email` (`jane.doe@example.com` and friends), `lorem-ipsum`, and
`placeholder-money` (`$1,234`) — and the frontend-side handler patterns
(`page.route(...).fulfill`, `rest.get(` / `http.get(`) remain forbidden
everywhere, since the whole point is that the provisional data lives server-side
behind the real path. A mock that passes the sweep is a better mock; one that
trips it is telling you it was written from a placeholder template rather than
from the domain.

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
   carries an unretired entry — or an entry the gate reports it could not read,
   which is the same refusal for the same reason.
5. **Confirming every approved contract was registered** with `declare-gate`, so
   the close-out refusal is the machinery's and not only the architect's memory.

## Honest boundary

The engine adjudicates SHAPE — contract completeness, ledger state, drift
against an observed payload — and never performs HTTP: the observed payload is
supplied by the agent that actually hit the endpoint. So the marker check and
the drift check are only as honest as the payload someone captured: the engine
can prove a captured payload still carries its scaffold, it cannot prove the
captured payload came from the endpoint. "Plausible representative values" in a
mock payload is LLM judgment, not a machine check — the sweep above rules out a
known-bad vocabulary, which is a floor, not a guarantee of plausibility.
Enforcement of the retirement gate is real but INDIRECT: the declared-gates
entry is what the Stop-hook audit blocks on, so a contract provisioned without
`declare-gate` is a gate nothing enforces. Registering it at provisioning time —
the same action that creates the debt — is what closes that gap. And the
protocol's benefit is real but bounded: it removes the frontend's wait on
backend BUILD time; it does not remove the need for the real implementation,
and the retirement gate is what keeps that honest.
