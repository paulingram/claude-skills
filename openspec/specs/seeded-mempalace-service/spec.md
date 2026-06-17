# seeded-mempalace-service Specification

## Purpose
TBD - created by archiving change seeded-mempalace-service. Update Purpose after archive.
## Requirements
### Requirement: REQ-001 — Seeded bundle schema + non-clobbering merge (SMP-3/5)

`services/seeded_mempalace/bundle.py` SHALL define a seeded-MemPalace bundle with a clear schema: a `schema` section, `curated` content, a `phenotype_catalog`, and a `research_synthesis` section carrying a freshness stamp (SMP-5). `merge_into_local` SHALL refresh ONLY the seeded keys from a fresh download while preserving EVERY other top-level key in the local store untouched (SMP-3 — a re-download never clobbers the user's own projects, in any namespace).

#### Scenario: a re-download refreshes seeded sections but preserves all user projects

- **WHEN** a local store with multiple user top-level keys (the reserved namespace + custom namespaces + metadata) is merged with a fresh bundle
- **THEN** the seeded `sections` are refreshed from the bundle and every user top-level key is preserved unchanged

### Requirement: REQ-002 — Phenotype catalog reusing the store, gated by entitlement (SMP-4)

`services/seeded_mempalace/catalog.py` SHALL build a phenotype catalog by REUSING the existing phenotype store (`scripts/phenotypes/phenotypes.py::discover_phenotypes`), not a new schema. `gate_catalog` SHALL ship the full phenotype record ONLY for entitled phenotypes; a non-entitled entry SHALL retain browse metadata but no record (the future purchase model). Gating SHALL NOT alias or mutate the master catalog, and served records SHALL NOT leak the operator's internal filesystem fields.

#### Scenario: only entitled phenotypes carry full records, master is never corrupted

- **WHEN** a master catalog is gated to a subset of entitlements
- **THEN** entitled entries keep their (deep-copied) full record, non-entitled entries have `record: None` with metadata, and mutating a served record does not change the master

### Requirement: REQ-003 — Authenticated download keyed on the verified key (SMP-1/2)

`services/seeded_mempalace/client.py` SHALL sign a download request with the local Ed25519 key (REUSING `services/common/handshake.py`) and merge the returned bundle locally during setup (before MemTime). `services/seeded_mempalace/server.py` SHALL verify the signed envelope (rejecting unsigned / tampered / replayed requests) and serve the bundle with its catalog gated to the requester's entitlements — resolved by the VERIFIED PUBLIC KEY, never the self-asserted requester string (so a caller cannot impersonate another user to obtain their paid phenotypes).

#### Scenario: a forged identity cannot obtain another user's entitlements

- **WHEN** an attacker signs a valid envelope with their OWN key but puts another user's name in the payload, and entitlements are resolved by the verified public key
- **THEN** the request is authorized (the signature is valid) but the attacker receives NO entitled records; a tampered envelope is rejected outright

### Requirement: REQ-004 — Honest boundary + tests both encodings (+ adversarial review)

`services/seeded_mempalace/` SHALL be a runnable stdlib-only deterministic core documented honestly as design + tests, NOT a live-deployed service (ChromaDB, the live server, the network transport, and the billing system are adapters / operator-provided; SMP-1's MemTime is interpreted + disclosed). A new test file SHALL cover the bundle, the catalog, the client, and the server; the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the service SHALL pass an independent adversarial review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_seeded_mempalace.py` present
- **THEN** there are zero failures

