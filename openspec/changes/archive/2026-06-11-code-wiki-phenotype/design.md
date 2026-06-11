# Design — code-wiki-phenotype (v3.13.0)

## Approach

Follow `phenotype-absorption` P1–P6 verbatim against the read-only clone at `.architect-team/reference/deepwiki-open/`. The absorbed PATTERN (per the skill's generalization rubric) is deepwiki-open's presentation layer — sidebar navigation tree, markdown content pane, client-side Mermaid rendering, dark/light theming — re-expressed as a lean, generalized Next.js scaffold with a thin maps-ingestion layer. The LLM machinery (providers, RAG, Ask/chat, websocket generation flow) is the strip boundary: it is documented in the blueprint's delta section and replaced by pre-generated CT6 maps as the sole content source. `kind` is decided by the P2 analyses (expected: `singleton` — one Next.js app with filesystem content; if the analyses prove the UI inseparable from a backend process, a thin Node content endpoint stays INSIDE the same scaffold rather than forcing `pair`).

## Key decisions

1. **Lean starter over vendored fork.** The scaffold templatizes the KEY files (P4: "a representative, generalized starter"), re-implementing the deepwiki presentation pattern with a minimal dependency set (next, react, a markdown renderer, mermaid) instead of vendoring deepwiki's tree — which would drag the LLM stack back in and make the template unmaintainable. deepwiki-open lands in `provenance.absorbed_from`; its pattern, not its files, is the absorption product.
2. **Maps-ingestion contract.** `codebases.json` (a scaffold parameter post-emit fill) registers `{name, maps_dir}` per codebase; the loader enumerates each registered codebase's `docs/*_MAP.md` (the five CT6 map kinds plus any future `*_MAP.md`), builds the navigation tree (codebase → map → sections), renders markdown with Mermaid blocks hydrated client-side. "Any number of codebases" = the registry is a list; the UI gets a codebase selector.
3. **Hosting variation point** `hosting ∈ {local, aws, gcp}`, default `local`. Local = Dockerfile + docker-compose (port parameterized). aws/gcp = `iac/<cloud>/` templates shaped to PLUG INTO config-management's service layer (module-call + tfvars templates whose `post_emit_notes` say: emit the `config-management` phenotype for platform/load-balancer/registry layers, then apply these service-layer files). Cross-seed expressed as `components.deploy.via = "config-management phenotype"` — the exact ai-management precedent; no schema extension.
4. **Demo = the proof.** Emit → install → configure codebases.json at this repo's docs/ → launch → curl 200s → Playwright screenshot. Unbounded iteration until it genuinely runs; the artifacts are the evidence the gates check.

## Reuse Decisions (extend > compose > reuse > build-new)

| Proposed work | Decision | Citation |
|---|---|---|
| Absorption process | REUSE `phenotype-absorption` skill verbatim (P1–P6) | CODEBASE_MAP §4 Skills — `phenotype-absorption` row |
| Manifest/scaffold contracts | REUSE `phenotypes/SCHEMA.md` + engine `scripts/phenotypes/phenotypes.py` unchanged | CODEBASE_MAP §4 — phenotypes rows |
| Cloud IaC | COMPOSE with `config-management` phenotype via `components.deploy.via` (ai-management precedent); the scaffold ships only the service-layer plug-ins | `phenotypes/ai-management/phenotype.json` deploy.via; `phenotypes/config-management/` |
| Wiki UI | BUILD-NEW (generalized starter) inside the scaffold — justified: no existing CT6 phenotype/skill ships a UI scaffold; vendoring deepwiki wholesale re-imports the stripped LLM stack | Reuse ladder: nothing to extend/compose; provenance recorded |
| Map content | REUSE the five `*_MAP.md` artifacts as-is (producers unchanged) | CPC `## Exploration documentation standard (v3.2.0)` + map skills |
| New test file | EXTEND the existing phenotype test family pattern (`tests/test_phenotype_subsystem.py` style) with `tests/test_code_wiki_phenotype.py` | CODEBASE_MAP §4 Tests |

## Invariants

- Absorption guardrails: read-only on the clone; only `phenotypes/code-wiki/**` + `.architect-team/phenotype-analysis/**` written; generalization rubric (zero secrets/ids/domains); `validate` green before done.
- Engine + schema unchanged; the three seeds untouched.
- Repo suite green both encodings; executed-not-described demo evidence.

## Test/verification plan

`tests/test_code_wiki_phenotype.py`: engine-validate exit 0 + "code-wiki: OK"; blueprint 10 sections; manifest hosting variation + deploy.via + provenance fields; scaffold manifest parses, every `files[].src` exists, no secret-shaped strings (regex sweep); `match` ranking > 0 for two representative prompts; docker + both iac dirs present. Demo + cloud-validation evidence are run artifacts checked by the review gates (not unit-testable). Playwright: USED for the demo screenshot (criterion 4); no app code in this repo gains UI tests — the scaffold is template text. Dev-API: N/A (no API; recorded). Suite both encodings.

## Rejected alternatives

- `pair` with a Python content backend mirroring deepwiki's api/: rejected unless P2 proves necessity — a second process adds deploy surface for content that is static markdown.
- Vendored deepwiki fork as the scaffold: rejected (re-imports LLM stack; violates lean-starter rubric; license fine but maintenance unowned).
- Schema `co_seeds` field: rejected at refinement (deploy.via precedent exists).
