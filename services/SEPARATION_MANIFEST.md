# CT6-6 Service-Tier Separation Manifest (REPO-1 … REPO-4)

> The two-repo plan + the machine-checkable separability boundary for the
> `services/` tier. The data form of this manifest is `services/separation.py`
> (`SEPARATION_MANIFEST`); the REPO-4 invariant is `check_separation(...)`, pinned
> by `tests/test_services_separation.py`.

## The plan (REPO-1 / REPO-2 / REPO-3)

- **REPO-1** — split into two repositories: the **open core** (this repo,
  `claude-team-6`) and **separate repo(s) for the paid/closed features**.
- **REPO-2** — rationale: some concepts are worth managing separately and justify
  charging users (e.g., the project-unique "genuine logger" signature; the
  purchasable phenotype catalog).
- **REPO-3** — for now the features stay inside CT6 under `services/`, but each is
  **designed** so it can later be separated. That design is what this manifest
  records.
- **REPO-4** — "separated out" means each service is an **effectively independent
  unit** the core can opt to use or not, **downloaded separately** rather than
  bundled. Concretely: a service reaches every external/closed capability through an
  **injected adapter** (a "seam"), never a hard import — so the service's module
  graph is stdlib + in-repo only and it lifts cleanly into its own package/repo.

## The services (all separable, REPO-3)

| Service | Dir | Reuses |
|---|---|---|
| `common` | `services/common` | — (the shared substrate: Ed25519 + handshake + bg_runtime + config) |
| `librarian` | `services/librarian` | `common` |
| `triage` | `services/triage` | `common`, `scripts/helpdesk/logit` |
| `session_review` | `services/session_review` | `common`, `triage` |
| `seeded_mempalace` | `services/seeded_mempalace` | `common`, `scripts/phenotypes/phenotypes` |

## The adapter seams (REPO-4 — where external/closed pieces plug in)

Every external or closed capability is reached through one of these **injected**
interfaces, so the open core never hard-depends on it:

| Seam | Requirement | Paid/closed? | Open stub (in-repo) | The real / closed implementation |
|---|---|---|---|---|
| `attestation_verifier` | SEC-4 | **yes** | `handshake.make_hmac_attestation_verifier` (HMAC stub) | the project-unique genuine-logger algorithm (cannot be copied) |
| `entitlements_for` | SMP-4 | **yes** | an injected lookup keyed on the **verified public key** | the entitlement / billing system |
| `LLMClient` | LIB-1 / EVAL-1 / SR-1 | no | `FakeLLMClient` | the real Anthropic adapter (SDK + network) |
| `Source` | LIB-6 | no | `StaticSource` | the real web / attached-API scraper |
| `IssueSink` / `poster` | EVAL-2 | no | `InMemorySink` / `poster=None` | the real GitHub issues API poster |
| `transport` | SMP-2 | no | an injected callable (the in-process `handle_bundle_request`) | the real HTTP fetch to the project's server |
| `bg_runtime` daemon | BG-1…4 | no | generated per-OS install descriptors | the actual OS daemon install + off-machine log ship |

## The paid / closed pieces (REPO-2 — the chargeable split)

- **SEC-4 project-unique attestation algorithm** (seam: `attestation_verifier`) — a
  unique signature proving a submission came from a GENUINE logger. It cannot live
  in the open core (anyone could copy it); the open core ships the pluggable hook +
  an HMAC stub, and the genuine algorithm is injected from the closed repo.
- **SMP-4 phenotype purchase / entitlement + billing** (seam: `entitlements_for`) —
  the purchasable phenotype catalog model is the chargeable feature; the open core
  ships the catalog + gating and resolves access by the verified key, with the
  entitlement source injected.

## How to "separate out" (REPO-4 procedure, when the time comes)

1. Lift `services/<name>/` (plus `services/common/`) into its own package/repo.
2. Carry the two reused in-repo modules it depends on, OR vendor them: the
   `scripts/helpdesk/logit.py` privacy engine (triage) and
   `scripts/phenotypes/phenotypes.py` (seeded_mempalace).
3. Provide the real adapter for each seam the service uses (the closed repo provides
   the paid seams: the SEC-4 algorithm, the entitlement source).
4. The core opts in by depending on the separated package; with the package absent,
   the core simply doesn't run that service.

## The invariant (REPO-4, enforced)

`services/separation.py::check_separation()` parses every `services/**/*.py` and
asserts each imports **only stdlib + in-repo modules at module load** — any
external/third-party top-level import is a violation (it must be injected via a
seam, not hard-imported). A lazy (in-function) import — like the deferred
`import anthropic` inside `service_config.anthropic_client` — is allowed, because it
is not a module-load dependency. This import-cleanliness is what makes each service
liftable into its own repo. `tests/test_services_separation.py` pins it.

**Honest boundary:** this manifest DESIGNS + validates the boundary. The actual repo
SPLIT — creating the separate repo and moving the closed pieces into it — is a
future operation, not performed here.
