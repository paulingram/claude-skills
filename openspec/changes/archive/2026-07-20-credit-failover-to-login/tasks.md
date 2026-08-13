# Tasks — credit-failover-to-login

## 1. Implementation (single backend teammate)

- [x] 1.1 `classify_upstream_error(status, body)` in `install_gateway.py` — pure; `credit-exhausted` / `rate-limited` / `transient` / `other`; the `429`-before-body-scan ordering is load-bearing; case-insensitive; None/empty body tolerated
- [x] 1.2 `detect_credit_exhaustion(port, master_key, model, *, prober=None)` — one bounded probe over the EXISTING `_http_completion_probe` seam; injectable prober so no test opens a socket; returns verdict + observed status + body excerpt; no log-scanning
- [x] 1.3 `failover_to_login(base, settings_path, agents_dir, *, reason, detail)` — REUSE `remove_claude_env` (merge-preserving), write `activated: false` + a `failover` record via `_write_state`, revert the split via `apply_policy(..., POLICY_UNIFORM_FABLE)`; leave `enabled` + stored keys intact; return a structured report naming any partial application honestly
- [x] 1.4 `failover` CLI subcommand — bare (detect-then-act), `--check` (probe + report, change nothing), `--force` (act without probing); honors `--base-dir` / `--settings-path` / `--agents-dir`
- [x] 1.5 `status` — a `credit-failover` row when a `failover` record exists (when, why, `install --activate` remediation) + a first-class `--json` field; a never-failed-over machine's output stays byte-identical
- [x] 1.6 `install --activate` clears the `failover` record
- [x] 1.7 `maybe_failover_to_login()` in `hooks/sessionstart-run-continuity.py` — guards (recorded `activated` + `enabled` + `auth_mode == api-key`), injectable seams, fail-open on every path, one-line note; `main()` invokes it BEFORE `maybe_heal_activation()`
- [x] 1.8 Tests: classifier truth-table incl. the 429-with-quota-wording overlap and the 402/insufficient_credit/quota_exceeded/overloaded cases; detector serving vs credit-dead; failover applies all four effects + leaves enabled/keys intact; NO-failover on rate-limited/transient; the v3.41.1 heal declines after a failover (the suppression-seam pin); hook ordering; hook fail-open; status both ways; `--check` mutates nothing; `install --activate` clears the record
- [x] 1.9 Full suite green under Windows cp1252 AND `PYTHONUTF8=1`; the v3.41.1 `_real_state_tripwire` stays SILENT (the standing proof no test touched the real machine); record totals

## 2. Review gates

- [x] 2.1 Schema-v7 review evidence at `.architect-team/reviews/credit-failover.json` + an INDEPENDENT `task-reviewer` verdict (producer != checker; ONE reviewer in flight per verdict path; any orchestrator interim check goes to a SIBLING path, never the reviewer's file)
- [x] 2.2 Phase 7 master-review audit verdict = pass

## 3. Close-out

- [x] 3.1 Version bump MINOR 3.41.1 -> 3.42.0 (plugin.json + marketplace.json)
- [x] 3.2 `doc-updater` + an INDEPENDENT system-architect Documentation Currency Audit = pass (CHANGELOG, README section + badges + timeline, CLAUDE.md shape line + 3-bounded releases, both maps incl. their `note:` ledgers)
- [ ] 3.3 openspec archive; commit on `architect-team/credit-failover-to-login`; do NOT push or merge without the owner's explicit word
