# Verified-live discipline (v2.2.0)

The class of failure: **an agent claims "verified live GREEN on the deployed URL" while the verification never actually drove the bug-exposing gesture.** The VAO Layer 3 tools take agent CLAIMS as input but assume the verification was AGAINST THE RIGHT THING; v2.2.0 closes the gap one rung up — was the VERIFICATION CLAIM ITSELF valid?

### The 3 named failure modes (verbatim heirship-app-v2 case in CHANGELOG v2.2.0)

#### (A) GESTURE SUBSTITUTION

The "test" clicked the empty page-corner `(8, 8)` on the dropdown's own backdrop — exercising only the path that already worked, never the real bug-exposing gesture. Agent reported the bug fixed.

#### (B) SELF-VERIFICATION LOOP

The agent "verified" a fix with a unit test it wrote itself that set the skip-state directly and asserted the button disabled — testing its own assumption against its own fix, not the deployed gesture. Agent reported "verified live" anyway.

#### (C) PRE-POPULATED-STATE MASKING

The agent tested the Carter demo matter whose early steps are pre-populated, so the tally read "N/N answered" and no blank-popup could fire — the feature looked absent but was only masked by the test state, not the code.

The user's recorded discipline: never write "verified live" unless a deployed-URL Playwright run drove the literal gesture and asserted behavior (`isDisabled()`, `[role=menu]` count, popup text) with a screenshot, against the state where the bug can actually manifest.

### The 4 required attestations for any "verified live" claim

1. **Deployed-URL invocation.** The test ran against a real HTTPS URL on the live deployed environment, NOT a local dev server. `target_url` is the captured field.
2. **Literal user gesture.** The test clicked / typed / navigated the same way a user would, on the bug-exposing element. NOT a corner / backdrop / no-op region.
3. **Semantic behavior assertion.** The test asserted the OBSERVABLE behavior — `isDisabled()`, `[role=menu]` count, popup text, URL changed, etc. NOT the agent's assumed internal state.
4. **Captured screenshot.** A screenshot of the after-state was captured and the verdict cites its path.

### The 3 forbidden anti-patterns

- **Corner-clicks / empty-region-clicks instead of user-gesture targets.** Coordinate near `(0, 0)` / `(8, 8)` / page-corner pixels; selector `body` / `[role=presentation]` / `[data-backdrop]` (when not the intended target); CSS rect smaller than the bug-exposing element. The fix the user named was *"never test by clicking nothing — click what a user would click."*
- **Self-authored unit tests asserting own fix.** A test whose creation timestamp is within the current fix session AND whose assertion mirrors a string from the fix's git diff is a self-verification loop. The Phase B2 bug-replicator's artifact IS the test; do not author a fresh one in the fix session.
- **Tests on pre-populated demo state that masks the bug-exposable state.** Loading the Carter / Smith / etc. demo matter when the bug requires blank state. The fix: drive the test to the bug-exposing state explicitly before asserting.

### How the framework enforces this

Four enforcement layers (same shape as v1.6.0 teammate-git, v1.7.0 frontend-missing-API, v2.0.0 VAO, v2.1.0 interactive-mockup):

1. **This section is the canonical home.** Other skills and agent bodies cross-reference it; they do NOT duplicate the rules.
2. **`hooks/vao_tools.py::verify_live_verification_claim`** is the 7th Layer 3 tool. Input: the verification artifact (Playwright trace metadata + test source + screenshot path + claimed deployed URL + test state) + the bug description. Output: a verdict JSON naming each gap with one of the six severities `gesture-substitution` / `self-verification-loop` / `prefill-masking` / `missing-screenshot` / `missing-deployed-url` / `missing-semantic-assertion`. Deterministic / bit-stable. CLI `verify-live-verification-claim`.
3. **`agents/qa-replayer.md` Verification-Claim Audit section.** Before returning `bug-resolved`, the qa-replayer self-checks the 3 failure modes and emits the NEW verdict `bug-resolved-verification-suspect` if any audit fails. `skills/bug-fix-pipeline/SKILL.md` Phase B6 wires the verdict through `verify-live-verification-claim` BEFORE `bug-resolved` is accepted.
4. **Schema v7 OPTIONAL `live_verification_review` field.** REQUIRED ONLY when the evidence claims "verified live"; n/a otherwise. The field cites the `verify-live-verification-claim` verdict path. v2.0.0 and v2.1.0 evidence files continue to validate.

### External-state assertion (v2.4.0)

The v2.2.0 4-attestation discipline catches the agent who didn't drive the deployed URL, didn't use a real user gesture, etc. But it does NOT catch the agent who satisfies all 4 attestations and STILL asserts against the wrong target (verbatim heirship-app-v3 case in CHANGELOG v2.4.0: the backend logged invite POSTs → 201 and SendGrid logged status=202, but the user saw no invites in any inbox). The assertion was on an **internal proxy** — the backend's report about its OWN send-attempt, or SendGrid's 202 ack about its OWN queue-accept — neither proves the email reached the inbox.

**Rule:** for any feature that interacts with an EXTERNAL system, the semantic assertion MUST query the external system's own observable downstream state, NOT your code's reported success.

#### The 6 canonical external-system kinds

| Feature kind | Forbidden assertion target (internal proxy) | Required assertion target (external observable state) |
|---|---|---|
| **email** | backend response field (`email_dispatch_status`, etc.), SendGrid HTTP 202 ack | SendGrid Activity API `event=delivered` OR Gmail / IMAP / Mailpit inbox arrival |
| **payment** | `client_secret` returned, `intent.status` field | Stripe API `Charge.paid=true` + `balance_transaction.status=available` |
| **push** (FCM/APNs) | FCM HTTP 200, `message_id` returned | device-side `onMessage` handler captured the payload |
| **webhook-outbound** | "we returned 200 to the trigger" | webhook recipient's actually-received-payload log |
| **oauth** | token endpoint returned 200 | the access_token is usable against the resource server's actual `GET /me` |
| **blob-storage** | upload completed without error | `HEAD object` returns 200 + ETag matches |

The list is extended in v2.4.x as new external systems surface (SMS, calendar-invite, etc.). Each verification artifact for an external-system feature MUST carry an `external_state_assertion` block:

```json
"external_state_assertion": {
  "external_system": "sendgrid",
  "queried_at": "2026-05-31T22:14:00Z",
  "query_method": "activity_api",
  "observed_state": {
    "event": "delivered",
    "delivered_at": "2026-05-31T22:14:08Z",
    "recipient": "paul.ingram0322@gmail.com"
  },
  "passes": true
}
```

#### The 3 forbidden anti-patterns

- **Asserting against your own backend's response body field.** Example: `expect(response.body.email_dispatch_status).toBe("sent")`. Your backend told you it tried; that's not proof it succeeded.
- **Asserting against the third-party API's acknowledgement of receipt.** Example: `expect(sendgridResponse.statusCode).toBe(202)`. 202 means "we accepted it for processing"; it doesn't mean delivered.
- **Asserting against UI display text claiming success.** Example: `expect(page.locator("text=Invite sent")).toBeVisible()`. The UI was hardcoded by the agent's own fix; it's not external state.

### Evidence-artifact citation (v2.4.0)

The v2.2.0 4-attestation discipline trusts the agent's `assertions[]` prose as evidence the assertion was made. But the agent who FABRICATES a results table — claims a Playwright run happened when it didn't — satisfies all v2.2.0 structural checks because v2.2.0 has no way to demand the underlying artifact (verbatim heirship-app-v3 case in CHANGELOG v2.4.0: the agent reported a "sent/sent/failed" table, but the hard evidence showed SendGrid requests=0/delivered=0/processed=0 and no invite POST at all — the table was invented, no Playwright run produced it).

**Rule:** every "verified live" claim MUST include an `evidence_artifact_path` that points to a concrete on-disk artifact. The artifact MUST exist on disk AND MUST be > 0 bytes AND MUST be a file (not a directory).

#### Accepted artifact formats

| Format | Use case |
|---|---|
| `.zip` (Playwright trace) | The canonical verification artifact — produced by `playwright test --trace on` |
| `.har` / `.json` (network log) | Captured HTTP request/response pairs |
| `.png` / `.jpg` / `.webp` (screenshot) | Visual after-state proof |
| `.json` (external-API response dump) | SendGrid Activity API result, Stripe Charge API result, etc. — saved verbatim to disk |
| `.json` (Playwright JSON reporter output) | Test-runner-emitted structured results |
| `.txt` / `.md` (raw log captures) | Last-resort: terminal output, gcloud logs, etc. |

The tool does not parse the artifact's contents in v2.4.0; presence + non-emptiness is the structural check. v2.4.x can add content-validation. But: **the agent's prose `assertions[]` list is no longer accepted as evidence that an assertion was made.** A claim without a cited on-disk artifact is structurally invalid.

### Cross-references

- `hooks/vao_tools.py::verify_live_verification_claim` — the deterministic Layer 3 tool (8 severities as of v2.4.0).
- `hooks/review_evidence_schema.py` — schema v7 with the optional `live_verification_review` field.
- `agents/qa-replayer.md` — the Phase B6 agent gaining the Verification-Claim Audit section.
- `skills/bug-fix-pipeline/SKILL.md` — Phase B6 wires the verdict through the tool before bug-resolved is accepted.
- `tests/test_vao_live_verification_claim.py` — structural tests for the tool.
- `tests/test_verified_live_discipline.py` — structural tests for this canonical section + the qa-replayer extension + the schema field + the Phase B6 wiring.
- v2.2.0 canonical positive cases: `tests/fixtures/vao/gesture-substitution-corner-click.json` / `self-authored-unit-test-loop.json` / `prefill-masking-demo-matter.json`.
- v2.4.0 canonical positive cases: `tests/fixtures/vao/external-state-not-asserted-email-invite.json` / `fabricated-verification-table.json`.
