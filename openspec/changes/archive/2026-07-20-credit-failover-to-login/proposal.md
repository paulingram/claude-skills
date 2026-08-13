# Proposal — credit-failover-to-login

## Why

When the external-LLM gateway's upstream runs out of credits, every Claude Code session pointed at that gateway breaks and stays broken. The owner's words (2026-07-19):

> "we need a way to fail over if we are out of credits. we should fail to our login."

Today there is **no credit handling anywhere in the gateway surface** — grep-verified across `scripts/setup/install_gateway.py`: no `402`, no `insufficient_credit`, no `quota_exceeded`, no `429` classification. A credit-dead gateway keeps binding its port, keeps passing the v3.41.1 TCP liveness probe, and keeps being reported `enabled` — so every surface reads healthy while every session 402s. The user's only recovery is to know, unprompted, to run `uninstall` or hand-edit `settings.json`.

The class this closes: **an upstream that is REACHABLE but cannot SERVE is indistinguishable from a healthy upstream on every signal CT6 currently collects.** v3.41.1 fixed the client-side wire being silently cut; this fixes the upstream silently being unable to serve.

## What Changes

- **A pure upstream-error classifier.** `classify_upstream_error(status, body)` returns one of `credit-exhausted` / `rate-limited` / `transient` / `other`. This is the crux of the feature and it is 100% unit-testable with no I/O. The distinction is load-bearing: **a `429` rate-limit must NEVER trigger failover** — a transient burst limit that flipped the owner's auth mode would flap it on every busy minute. Only the hard-credit class (`402`, `insufficient_credit`, `quota_exceeded`, `credit balance is too low`, `billing`) fails over; `429` and `5xx`/`overloaded` are retry-classes.

- **Probe-based detection at the seams CT6 actually observes.** The launcher writes no log by default (verified — there is no log redirect in the generated launcher), so passive log-scanning is NOT a reliable detection channel and is deliberately NOT the design. CT6 observes upstream status exactly where it already speaks to the gateway: `_http_completion_probe` raising `urllib.error.HTTPError`. The new `detect_credit_exhaustion()` performs ONE bounded 32-token probe and classifies the outcome. Cost note: the probe is negligible when credits exist and free when they do not (the failure IS the signal).

- **`failover_to_login()` — the reactor, reusing existing machinery, inventing no new auth mode.**
  1. `remove_claude_env(settings_path, port)` — the EXISTING merge-preserving stripper — drops `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN` so Claude Code falls back to Claude sign-in (the existing `subscription` posture).
  2. **Flips recorded state** — `activated: false` plus a `failover` record. This is NOT cosmetic: per v3.41.1, `maybe_heal_activation()` re-applies the env block whenever state records `activated + enabled + api-key` and the port is live. A credit-dead gateway still binds its port, so a failover that stripped the block WITHOUT flipping recorded state would be silently undone on the very next SessionStart and re-point the owner at a gateway that cannot serve. Recorded consent is the suppression seam (test-pinned upstream); flipping it is what makes the failover stick.
  3. Reverts the role split to uniform fable via the EXISTING `apply_policy(..., POLICY_UNIFORM_FABLE)` lever — login auth cannot serve the secondary alias, so leaving 21 agents pointed at it would break every dev-class teammate spawn.
  4. Records `failover: {at, reason, detail, provider, port}` in `gateway.json` so `status` can report it.

- **`status` reports the failover loudly** — a dedicated `credit-failover` row naming when it fired, why, and the `install --activate` remediation. A machine that never failed over keeps byte-identical output.

- **A `failover` CLI subcommand** — `failover` (detect-then-act), `failover --force` (act without probing, for "I know I'm out"), `failover --check` (probe + classify, report, change nothing). `--check` is the dry-run the owner can trust.

- **SessionStart wiring** — `maybe_failover_to_login()` in `hooks/sessionstart-run-continuity.py`, symmetric to the existing `maybe_heal_activation()`, ordered BEFORE it (a failover that fires must not be immediately re-healed in the same hook run). Fail-open on every path.

- **The return path is the existing `install --activate`** — it already applies the env block, re-applies the split, and records `activated: true`; it now also CLEARS the failover record. No new "un-failover" surface. Automatic return is deliberately NOT built: it would require polling a paid upstream on a timer, and the owner asked for automatic failover, not automatic return.

## Capabilities

### New Capabilities

- `credit-exhaustion-failover`: when the gateway's upstream cannot serve for hard-credit reasons, CT6 automatically returns the user to Claude sign-in auth with the split off, records why, and says how to come back — and never does so for a transient rate limit.

## Impact

- `scripts/setup/install_gateway.py` — the classifier, the detector, `failover_to_login()`, the `failover` subcommand, the `status` row, the `install --activate` failover-clear. REUSES `remove_claude_env` / `_write_state` / `read_env_file` / `_http_completion_probe`; adds no new auth mode.
- `scripts/setup/set_default_model.py` — REUSED unchanged (`apply_policy` + `POLICY_UNIFORM_FABLE`).
- `hooks/sessionstart-run-continuity.py` — `maybe_failover_to_login()` + `main()` wiring, ordered before the activation heal.
- `tests/` — a new test module; the v3.41.1 conftest tripwire stays green (every test sandboxed).
- `CHANGELOG.md`, `README.md`, `CLAUDE.md`, `docs/CODEBASE_MAP.md`, `docs/INTEGRATION_MAP.md`; version 3.41.1 → 3.42.0 (MINOR — new capability).
- NOT touched: the owner's live machine (no activation, no config regeneration, no restart).
