## 1. Implementation

- [x] 1.1 `services/seeded_mempalace/bundle.py`: the defined bundle schema (schema + curated + phenotype_catalog + research_synthesis freshness) + validate + merge preserving all user top-level keys (REQ-001)
- [x] 1.2 `services/seeded_mempalace/catalog.py`: the SMP-4 phenotype catalog REUSING discover_phenotypes; gate_catalog ships records only for entitled phenotypes (REQ-002)
- [x] 1.3 `services/seeded_mempalace/client.py`: SMP-1/2 signed download request (reuse handshake) + install/merge (REQ-003)
- [x] 1.4 `services/seeded_mempalace/server.py`: SMP-2 server skeleton — verify handshake, resolve entitlements by the verified public key, gate the catalog (REQ-003)
- [x] 1.5 `services/README.md`: Seeded MemPalace promoted to a landed Layout block (REQ-004)

## 2. Tests

- [x] 2.1 `tests/test_services_seeded_mempalace.py`: bundle build/validate/merge incl. preserve-all-user-keys; catalog build/gate/entitled-labels + real-store reuse (REQ-001, REQ-002, REQ-004)
- [x] 2.2 Signed client + install (authorized/unauthorized/invalid); server auth + gating + tamper rejection; end-to-end; impersonation-defeated / no-aliasing / no-path-leak edges (REQ-003, REQ-004)
- [x] 2.3 Full suite green under cp1252 AND `PYTHONUTF8=1` (REQ-004)

## 3. Docs + version

- [x] 3.1 Bump `.claude-plugin/plugin.json` + `marketplace.json` to 3.27.0 + `test_dispatch_banner.py` + CHANGELOG entry (REQ-004)
- [x] 3.2 README (badge + NEW IN) / CLAUDE.md (Stack + Structure + counts + recent-release) / CODEBASE_MAP (tree + tests + note) / INTEGRATION_MAP (note) / services/README brought current; skill/agent/command counts unchanged (REQ-004)

## 4. Review

- [x] 4.1 Independent adversarial review (producer ≠ checker); FIX-FIRST → remediated 5 (impersonation → entitlements keyed on the verified public key; gate_catalog master-aliasing → deep-copy; merge dropped user keys → preserve all; served-record path leak → strip; default-off replay → default a seen_nonces set) (REQ-002, REQ-003, REQ-004)
- [x] 4.2 Real verification: the impersonation-defeated path + the user-namespace preservation exercised in-process, not described (REQ-004)
