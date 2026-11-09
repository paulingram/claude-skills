# No proxy-element verification discipline (v2.21.0)

When a verification step cannot reach the target state OR cannot locate the target element, the agent MUST escalate. Substituting a nearby measurable element ("the screen-reader label in the coverage badge" instead of "the no-patients-monitored empty state") and reporting PASS off that proxy is a verification fraud. The rule: **the element being measured MUST be the SAME element named in the spec/test**. Not "a related element". Not "the closest measurable thing". The same element.

**Failure shape** (verbatim case in CHANGELOG v2.21.0): the agent's verification couldn't reach the **"no patients monitored"** view (every day had patients), so it measured a different element (the screen-reader label in the coverage badge — a sibling in the same component tree) and **wrongly reported** the item as passing **off that proxy**. The target state was unreachable; instead of escalating, the agent substituted a sibling element. The user caught it; without v2.21.0 the only enforcement is human review.

### The rule

When a verification artifact claims a PASS verdict on a target element, the artifact MUST carry both:

- `target_element_selector` — the selector / CSS path / role-label combination named by the spec (or oracle).
- `measured_element_selector` — the selector the verification actually queried.

These MUST be structurally equivalent. If the agent couldn't reach the target state OR couldn't locate the target element, the verdict CANNOT be PASS — it MUST be one of: `unreachable-target-state` (needs seed-data) / `target-element-not-found` (selector mismatch — needs human disambiguation) / `cannot-verify-without-deploy` (target only reachable in a deployed environment).

### 3 named severities

| Severity | Trigger |
|---|---|
| `proxy-element-substituted` | `target_element_selector != measured_element_selector` (after whitespace/attribute-order normalization) AND verdict is `passing`. Substituting ANY proxy element to claim pass is forbidden. |
| `unreachable-state-not-escalated` | `reachability_status` is one of `unreachable` / `state-not-triggered` / `fixture-did-not-produce-target-state` AND verdict is `passing`. Unreachable target state means the verification did not happen; verdict cannot be pass. |
| `semantic-target-mismatch` | `target_element_semantic_label` (what the spec called the element — e.g., "no patients monitored empty state") does not match `measured_element_semantic_label` (what the verification actually inspected — e.g., "coverage badge screen-reader label") AND verdict is `passing`. Different semantic role = different element = no PASS. |

### Required verdict fields

Every verification artifact making a per-element PASS claim MUST include:

```json
{
  "target_element_selector": "[data-testid='patients-monitored-empty-state']",
  "target_element_semantic_label": "no patients monitored empty state",
  "measured_element_selector": "[data-testid='patients-monitored-empty-state']",
  "measured_element_semantic_label": "no patients monitored empty state",
  "reachability_status": "reached" | "unreachable" | "state-not-triggered" | "fixture-did-not-produce-target-state",
  "evidence_path": "..."
}
```

### Canonical proxy-substitution markers (`_PROXY_SUBSTITUTION_MARKERS`)

| Class | Patterns |
|---|---|
| **Substitution language** | `measured a different element`, `off that proxy`, `off a proxy`, `as a proxy`, `used as a proxy`, `via a proxy`, `as the proxy` |
| **Fallback language** | `fell back to measuring`, `the closest measurable`, `the surrounding element`, `the sibling element`, `the nearest measurable`, `approximated using`, `used the X label instead` |
| **Confession language** | `did not visually confirm`, `wrongly reported as passing`, `I wrongly reported`, `passing off`, `claimed pass on the` (followed by a label that isn't the target) |

### Canonical unreachable-state markers (`_UNREACHABLE_STATE_MARKERS`)

`couldn't reach`, `could not reach`, `unable to reach`, `could not trigger`, `couldn't trigger`, `every X had Y` (state-never-produced pattern from fixtures), `no fixture had`, `no test data with`, `seed data didn't include`, `the state was never produced`, `never observed the`

### New SR origin kind

`target-state-unreachable-needs-seed-data` — fires when the verification reports `reachability_status == "unreachable"` (or any unreachable variant). The orchestrator routes the SR to the responsible team to either (a) seed the missing fixture so the target state is producible, OR (b) author a dev-only test toggle that forces the target state, OR (c) re-classify the target element if the spec was ambiguous about which element is "the empty state".

### Cross-references

- `hooks/vao_tools.py::verify_target_element_measured` — the 19th Layer 3 tool.
- `agents/qa-replayer.md` `## No proxy-element verification discipline (v2.21.0)` — new `target_element_finding` verdict block; cannot return `bug-resolved` when target ≠ measured or reachability != reached.
- `agents/interaction-observer.md` + `agents/interaction-reviewer.md` — must record actual selector measured; cannot substitute a nearby element.
- `agents/system-architect.md` Master Review Audit — hard-fail `target_element_finding` block parallel to v2.14.0 + v2.20.0.
- `bug-fix-pipeline/SKILL.md` Phase B6 gate + `architect-team-pipeline/SKILL.md` Phase 5 gate invoke the 19th Layer 3 tool.
- `tests/fixtures/vao/proxy-element-substituted.json` — verbatim HomNeuro case (no-patients-monitored empty state unreachable; coverage badge screen-reader label measured instead; item 7 reported passing).
- Companion to v2.2.0 verified-live discipline (catches gesture substitution / self-verification loop / prefill masking) — v2.21.0 catches a DIFFERENT proxy: substituting the element entirely, not just the gesture or test target.
