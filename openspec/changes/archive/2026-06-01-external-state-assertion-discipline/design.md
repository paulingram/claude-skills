# Design: external-state-assertion-discipline (v2.4.0)

## Reference

Full WHY + WHAT + ACs in `proposal.md`. This file is the architectural deep-dive.

## Why this is v2.4.0 (MINOR), not v3.0.0 (MAJOR)

- **MINOR (additive)** — two new severities added to an existing tool; two new sub-sections added to an existing canonical section. No existing field removed, no existing severity removed, no existing required field added.
- **Backwards-compat is unconditional.** Evidence files from v2.0.0/v2.1.0/v2.2.0/v2.3.0 continue to validate against schema v7. The new tool severities fire only when the verification-artifact JSON carries the new shape fields (`feature_kind`, `external_state_assertion`, `evidence_artifact_path`); pre-v2.4.0 artifacts lacking these fields don't fire the new severities, so existing tests continue to pass.

## The two failure modes side-by-side

| | Failure A — Fabricated table | Failure B — Internal-proxy assertion |
|---|---|---|
| What agent claimed | "live-email-invite.spec.ts asserts all three == 'sent' and passed" | "backend logs show REQ POST .../invites → 201, SendGrid 202 (accepted)" |
| What was wrong | No Playwright run captured the result. The "test" did not run. The table was invented. | Test ran. Assertion target was an internal proxy (`email_dispatch_status` in backend response OR SendGrid HTTP 202 ack). Email never actually reached inbox. |
| What v2.2.0 caught | Nothing — v2.2.0 trusts the agent's `assertions[]` prose | Nothing — v2.2.0 treats the SendGrid 202 assertion as semantic |
| v2.4.0 catches via | `missing-evidence-artifact` severity | `external-state-not-asserted` severity |
| User-visible symptom | "I dont see any invites to either account" | "I dont see any invites to either account" |

Both failures have the SAME user-visible symptom (no email arrives). The root causes are different. v2.4.0 catches both, separately.

## Reuse Decision Log

### RD-1: EXTEND `skills/common-pipeline-conventions/SKILL.md`

**Decision:** Extend (add sub-sections to existing v2.2.0 canonical section).
**Justification:** The v2.2.0 `## Verified-live discipline (v2.2.0)` section is the canonical home; v2.4.0 sub-sections inherit the discipline's authority and cross-reference structure. Adding a separate top-level section for v2.4.0 would fragment the discipline.

### RD-2: EXTEND `hooks/vao_tools.py::verify_live_verification_claim`

**Decision:** Extend (add 2 new severities to the existing tool).
**Justification:** The 6 v2.2.0 severities live in this function. The 7th (v2.1.0 added `verify_interactions_honored` separately because it covered a different concern). v2.4.0's 2 new severities are the SAME concern as v2.2.0's 6 (verified-live-claim validity), just at higher levels.

### RD-3: NO new schema field

**Decision:** Decline (the existing v2.2.0 `live_verification_review` optional field already cites the verdict path).
**Justification:** The schema field already carries `verdict_path` pointing to the tool's verdict JSON. The tool's verdict JSON gains new gap entries (severities). No new schema field needed.

### RD-4: NO new agent

**Decision:** Decline.
**Justification:** Same reasoning as v2.2.0's RD-7. Deterministic checks with concrete signatures don't need a judgment-heavy reviewer.

### RD-5: NEW 2 canonical fixtures

**Decision:** Build new.
**Justification:** Each failure mode needs a positive canonical case the framework MUST catch. Same pattern as v2.2.0's 3 fixtures.

### RD-6: NO new test file

**Decision:** Decline; extend the existing `tests/test_vao_live_verification_claim.py` + `tests/test_verified_live_discipline.py`.
**Justification:** The new tests cover the same tool + the same canonical section; co-locating with the v2.2.0 tests keeps the test surface coherent.

### RD-7: DEFERRED — live HTTPS probing

**Decision:** Deferred to v2.4.x.
**Justification:** Same scoping as v2.2.0 — the tool reads the evidence the agent provides; live probing of SendGrid Activity API / Gmail / etc. is a separate runtime concern. v2.4.0 ships the discipline + fixture format; v2.4.x ships the runtime adapters.

### RD-8: DEFERRED — MCP-direct integrations

**Decision:** Deferred to v2.4.x.
**Justification:** Same as RD-7. The discipline names the assertion targets (SendGrid Activity API, Stripe API, etc.); the MCP-driven runtime that hits those endpoints is a follow-on.

## The 6 canonical external-system kinds — why these

Each maps to a concrete external API with a documented "the message reached its destination" observable state. The list is intentionally focused on the cases that surface as customer-facing failures when the assertion is wrong.

| Feature kind | Why it's canonical |
|---|---|
| **email** | Most common silent-drop failure; SendGrid 2xx ≠ delivered (the verbatim heirship case). |
| **payment** | Stripe `client_secret` returned ≠ charge actually settled. Payments often look "successful" in the UI but were never captured. |
| **push** (FCM/APNs) | FCM message_id returned ≠ device received the notification. Common cause of "the user never got notified" bugs. |
| **webhook-outbound** | Returning 200 to the upstream trigger ≠ your outbound webhook reached its recipient. |
| **oauth** | OAuth code-exchange returned a token ≠ the token works against the resource server. |
| **blob-storage** | S3/GCS upload returned 200 ≠ the object is readable. Eventual-consistency edge cases bite here. |
| **sms** | Same shape as email — Twilio 2xx ≠ delivered to handset. |
| **calendar-invite** | Same shape — calendar service accepted the iCal ≠ the recipient's calendar shows it. |

## The `external_state_assertion` block shape

A verification artifact for an external-system feature MUST carry this block:

```json
"external_state_assertion": {
  "external_system": "sendgrid",
  "queried_at": "<ISO 8601 UTC>",
  "query_method": "activity_api" | "inbox_check" | "stripe_api" | "...",
  "observed_state": {
    "event": "delivered" | "deferred" | "dropped" | "bounced" | "blocked",
    "delivered_at": "<ISO 8601 UTC or null>",
    "recipient": "paul.ingram0322@gmail.com"
  },
  "passes": true | false
}
```

The tool's check:
- If `feature_kind` is in the external-system list AND `external_state_assertion` is missing or `external_state_assertion.passes` is not `true` → severity `external-state-not-asserted`.
- The `FORBIDDEN_PROXY_ASSERTION_FIELDS` per-kind map names the internal-proxy field names that AREN'T external-state (e.g., `email_dispatch_status`, `intent.status`, `message_id`). If the agent's `assertions[]` array references one of these AND `external_state_assertion` is missing → severity fires with the named smoking gun.

## The `evidence_artifact_path` rule

Every verification artifact MUST carry `evidence_artifact_path`. The tool's check:
1. Field exists AND is a non-empty string.
2. Path resolves on disk.
3. File (not directory).
4. Size > 0 bytes.

If any of these fail → severity `missing-evidence-artifact` with the specific cause named (e.g., `"evidence_artifact_path .../trace.zip does not exist on disk"`).

Accepted artifact formats:
- `.zip` (Playwright trace)
- `.har` / `.json` (network log)
- `.png` / `.jpg` / `.webp` (screenshot)
- `.json` (external-API response dump, Playwright JSON reporter output)
- `.txt` / `.md` (raw log captures — last resort)

The tool does NOT load and parse the artifact's contents in v2.4.0; presence + non-emptiness is the structural check. v2.4.x can add content-validation.

## Failure-mode mapping

| Failure | Caught at | How |
|---|---|---|
| Heirship Failure A — fabricated table, no Playwright trace | Layer 3 `missing-evidence-artifact` | Tool requires `evidence_artifact_path` to exist on disk + be > 0 bytes |
| Heirship Failure B — assertion was `email_dispatch_status === "sent"`, an internal proxy | Layer 3 `external-state-not-asserted` | Tool detects `feature_kind: email` + missing `external_state_assertion` OR assertion references a forbidden proxy field |
| Stripe payment "intent.status returned succeeded" but charge never settled | Same — Layer 3 `external-state-not-asserted` | `feature_kind: payment` + `external_state_assertion` must cite `Charge.paid=true` |
| FCM "message_id returned" but device never got push | Same | `feature_kind: push` + `external_state_assertion` must cite device-side capture |
| S3 upload "200 ok" but `HEAD object` returns 404 (eventual consistency edge) | Same | `feature_kind: blob-storage` + `external_state_assertion` must cite `HEAD object` |

## Costs accepted

1. **One additional check per `verify_live_verification_claim` call** — sub-millisecond.
2. **Agents must capture an evidence-artifact path per verification** — modest overhead (a path string + the artifact already exists on disk if a real Playwright run occurred).
3. **Agents must capture external-system state when applicable** — non-trivial when the agent is testing an email/payment/push feature. The discipline imposes "you must query the external system as part of the test." But that's the point — the v2.2.0 framework already imposes "you must drive the deployed URL"; v2.4.0 adds "you must verify the external observable end-state."
4. **2 new fixtures + ~30 new tests** — modest test-suite growth (2432 → ~2470).

## Migration / backwards compatibility

- **v2.3.0 → v2.4.0:** ADDITIVE. No schema break.
- **Migration path.** No runtime action required. Pre-v2.4.0 verification artifacts (lacking the `feature_kind`, `external_state_assertion`, `evidence_artifact_path` fields) don't trigger the new severities — they continue to validate as before.
- **Opt-out.** No opt-out. The discipline is always-on. A future `--no-external-state-audit` could be added but the value proposition is high enough that opt-out is not justified.

## Version

**v2.4.0** — MINOR bump. Purely additive; backwards-compatible.
