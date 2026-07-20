# Design — credit-failover-to-login

## Proposed fix (class-scoped)

The class: **an upstream that is REACHABLE but cannot SERVE is invisible to every signal CT6 collects.** The fix is not "handle 402" — it is a classifier over upstream outcomes plus a reactor that returns the user to a working auth mode and records why, wired at every seam where CT6 observes an upstream response. Adding a second provider or a new error shape means adding a pattern to one table, not a new code path.

## Where detection lives — settled with evidence

The open question was gateway-side vs installer-side. Evidence:

- **The generated launcher writes NO log by default.** Verified: no log redirect exists in the launcher generation. So passive log-scanning would silently detect nothing on a default install. REJECTED as the primary channel.
- **A LiteLLM callback plugin** would need a Python module loaded into the litellm process — a new runtime dependency surface and a new failure mode inside the serving path. REJECTED (stdlib-only invariant; and a bug there takes the gateway down).
- **`_http_completion_probe` at `install_gateway.py:1510`** already POSTs to `/v1/messages` and already surfaces upstream status: `urllib.request.urlopen` raises `urllib.error.HTTPError` carrying `.code` and `.read()`. This is where CT6 genuinely observes the upstream. ACCEPTED.

So: **detection is installer-side and probe-based; the reactor is installer-side.** No gateway-side component, no new runtime dependency, nothing inside the serving path.

Probe-cost note: one 32-token completion. Negligible when credits exist; free when they do not (the failure is the signal).

## The classifier (the crux)

```python
def classify_upstream_error(status, body) -> str:
    # "credit-exhausted" | "rate-limited" | "transient" | "other"
```

Rules, in order:

| Signal | Verdict | Fails over? |
|---|---|---|
| status `402` | `credit-exhausted` | **YES** |
| body matches `insufficient_credit` / `insufficient credits` / `quota_exceeded` / `credit balance is too low` / `billing` / `payment required` | `credit-exhausted` | **YES** |
| status `429` | `rate-limited` | **NO — retry** |
| status `>= 500` or body matches `overloaded` | `transient` | **NO — retry** |
| anything else | `other` | **NO** |

**Order is load-bearing and test-pinned.** A `429` whose body happens to mention "quota" is the dangerous overlap: some providers return `429` with `quota` wording for a per-minute burst limit. The status check for `429` therefore runs BEFORE the body-pattern scan, so a rate limit can never be misread as exhaustion. Getting this backwards would flap the owner's auth mode on every busy minute — the exact outcome the trigger decision forbids.

Pure function: no I/O, no state, fully unit-testable. Case-insensitive body matching; `None`/empty body tolerated.

## The reactor

```python
def failover_to_login(base, settings_path, agents_dir, *, reason, detail) -> Report
```

Order matters — each step is independently safe, and the state flip must not be lost if a later step fails:

1. **Strip the env block** — `remove_claude_env(settings_path, port)` (EXISTING, merge-preserving, only removes values matching our port).
2. **Flip recorded state FIRST-CLASS** — `activated: false`, plus `failover: {at, reason, detail, provider, port}`. Rationale in the proposal: without this, v3.41.1's `maybe_heal_activation()` undoes the failover on the next SessionStart because a credit-dead gateway still passes the TCP liveness probe. `enabled` and the keys are LEFT INTACT — the gateway is still installed and the keys are still valid; only activation and the split change. `install --activate` is therefore a clean one-command return.
3. **Revert the split** — `apply_policy(agents_dir, POLICY_UNIFORM_FABLE)` (EXISTING lever). Login auth cannot serve the secondary alias; leaving 21 dev agents pointed at it would break every dev-class spawn.
4. **Return a structured report** the CLI and the hook render.

Every step is individually fail-open-ish but the report names any partial application honestly — a half-applied failover reports which steps landed rather than claiming success.

## Reuse Decisions

| New? | Thing | Decision |
|---|---|---|
| NO | `remove_claude_env` (`install_gateway.py:905`) | REUSE verbatim — already merge-preserving + port-matched. |
| NO | `apply_policy` / `POLICY_UNIFORM_FABLE` (`set_default_model.py`) | REUSE verbatim — the existing split-revert lever. |
| NO | `_write_state` / `read_env_file` / `_http_completion_probe` | REUSE verbatim. |
| NO | the `subscription` auth posture | REUSE — no third auth mode is invented. |
| YES | `classify_upstream_error` | NEW pure function in `install_gateway.py`. No existing classifier exists (grep-verified: no 402/429 handling anywhere). Lives beside the other pure helpers. |
| YES | `detect_credit_exhaustion` | NEW thin wrapper over the EXISTING probe seam; injectable prober for tests. |
| YES | `failover_to_login` | NEW orchestration over the four existing primitives. |
| YES | `maybe_failover_to_login` (hook) | NEW, deliberately mirroring `maybe_heal_activation`'s guard structure + fail-open discipline. Follows the hook's existing local-copy convention. |

## Hook ordering (v3.41.1 interaction)

`main()` runs `maybe_failover_to_login()` **BEFORE** `maybe_heal_activation()`. If a failover fires, it clears `activated`, so the activation heal's state guard correctly declines to re-apply the env block in the same run. The reverse order would strip and immediately re-apply. This ordering is test-pinned.

## Test-safety invariant

Every test sandboxes `--base-dir` / `--settings-path` / `--agents-dir` (or injects both hook paths). The v3.41.1 `_real_state_tripwire` in `tests/conftest.py` must stay silent — it is the standing proof the suite never touches the owner's real machine, and it is treated as a hard invariant, not an obstacle.

## What is deliberately NOT built

- **Automatic return from failover.** Would require polling a paid upstream on a timer. The owner asked for automatic failover; the return is the existing `install --activate`.
- **A background watcher / daemon.** No new always-on surface.
- **Gateway-side detection.** Rejected above with evidence.
