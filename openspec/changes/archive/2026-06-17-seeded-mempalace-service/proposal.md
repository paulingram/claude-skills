## Why

With the substrate (v3.23.0) + the Librarian (v3.24.0) + Triage (v3.25.0) + Session-Review (v3.26.0) shipped, this builds the fourth service: the **Seeded MemPalace** (CT6-6 SMP-1…5). An optional load-up from a separate service downloads a seeded MemPalace during setup (SMP-1), with a valid auth key, from the project's server (SMP-2). The seeded MemPalace ships a clear schema + curated content while leaving room for the user's own projects (SMP-3), is where phenotypes are stored with a future purchase model (SMP-4), and carries the latest research synthesis (SMP-5). It reuses the SEC handshake (the same lower-risk one the Librarian uses) + the existing phenotype store. HONEST: design + a runnable stdlib-only core + tests, NOT a live-deployed service.

## What Changes

- **`services/seeded_mempalace/bundle.py`** — the defined bundle schema + curated + phenotype catalog + research-synthesis freshness section (SMP-3/5) + a merge that preserves the user's own projects. (REQ-001)
- **`services/seeded_mempalace/catalog.py`** — the SMP-4 phenotype catalog, REUSING the existing phenotype store, gated by entitlement. (REQ-002)
- **`services/seeded_mempalace/client.py`** + **`server.py`** — the SMP-1/2 authenticated download (sign via the SEC handshake) + the server skeleton (verify + gate by the verified public key). (REQ-003)
- **Honest boundary + stdlib-only core + tests** + an adversarial review. (REQ-004)

## Capabilities

### New Capabilities

- `seeded-mempalace-service` — the CT6-6 Seeded MemPalace: an authenticated download of a seeded MemPalace bundle (schema + curated + phenotype catalog + research synthesis) that merges without clobbering the user's projects, as design + a runnable stdlib-only core.

### Modified Capabilities

- None removed. New files land under the existing top-level `services/` (v3.23.0); skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
