# A Data-Engineering Lane + Cross-Pollination into the Full-Stack Cycle — Design Proposal

**Run:** dataeng-lane-20260802 · **Author:** system-architect · **Status:** DESIGN PROPOSAL ONLY — nothing here is built, scheduled, or specced until Paul approves
**Builds on:** `docs/analysis/DENG_TOOLKIT_COMPARISON.md` (the committed deng-toolkit comparison) — its §5 R1–R6 ranked suggestions (`DENG_TOOLKIT_COMPARISON.md:103-138`) and §6 map-server generalization (`:142-154`) are the source material; this document does not re-derive the comparison, it designs the build.
**Baseline:** CT6 v3.48.1 (`.claude-plugin/plugin.json:4`); 50 skills / 39 agents / 23 commands / 7 hooks / 21 Layer-3 tools; suite 6690 passing + 6 skipped across 223 test files (`CHANGELOG.md:20`). Every integration cite below was opened and verified against this checkout on 2026-08-02.

---

## 1. Executive summary

**One piece of infrastructure underlies both legs of this proposal: a single generic "standing, staleness-aware, MCP-queryable knowledge server" — the Librarian pattern generalized — with pluggable read-only data sources.** Point it at the **data dictionary** (`docs/data-dictionary.json`) and it is leg 1's warm data catalog (R1). Point it at the **codebase-map machine sidecars** (`lineage-graph.json` + the `*_MAP.md` frontmatter) and it is leg 2's map server (the §6 generalization). Same server core, same ranked-search shape, same freshness contract, same installer, same MCP surface discipline — two source adapters. Build the infrastructure once; serve two data-source families.

The server adopts deng-toolkit's *interface* — warm, structured, one-tool-call answers, team-shared — while keeping CT6's *semantics*: **every response carries a freshness verdict computed by the engines CT6 already ships** (`transitive_stale_nodes`, `last_mapped`/`last_built`/`last_traced` stamps, the `map_invalidated` override), content stays corroborated and provenance-stamped, and the per-run pipeline gates still run at consumption — the server serves what derivation produced and says how fresh it is; it never substitutes for the check.

Around that foundation, leg 1 adds a **first-class data-engineering pipeline lane** — entry, routing, and delivery discipline mirroring the bug-fix sibling-lane pattern — whose exploration phase REUSES the existing 7-stage `data-engineering-exploration` skill unchanged, and whose new substance is the standing catalog infrastructure (warm-check first, refresh after) plus deng's four remaining ideas rebuilt to CT6 standards: SQL-object mining (R2), a durable annotation channel (R3), usage-grounded importance (R4), an offline stakeholder review round-trip (R5), and an optional JSON-LD emitter (R6). Leg 2 carries the same foundation into the full-stack cycle and names, explicitly, the two places the standing-warm pattern must NOT reach: the run-scoped contract ledger, and the per-run freshness/witness gates.

---

## 2. The proposed improvements (restated from the review)

The full rationale, evidence, and tradeoffs live in `DENG_TOOLKIT_COMPARISON.md` §5 (`:103-138`) and §6 (`:142-154`); one line each here, tagged by leg.

| # | Improvement (one line) | Leg |
|---|---|---|
| R1 | A standing warm data-catalog service behind MCP query tools over the corroborated `data-dictionary.json` the pipeline already produces (`DENG_TOOLKIT_COMPARISON.md:107-111`) | **[both]** — it IS the generic server pointed at the dictionary source |
| R2 | A SQL-object mining skill — stored procedures / views + execution stats parsed into join/filter/metric candidates, corroboration-gated (`:113-117`) | [leg 1 data-eng] |
| R3 | A persistent, structured, per-user annotation channel on data objects, corroborated on ingest (`:119-123`) | **[both]** — data objects first; generalizes to domain-gate/bulk-verify confirmations |
| R4 | Usage-grounded importance in the data dictionary — measured read/write recency + volume feeding Stage 4 (`:125-128`) | **[both]** — data tables first; the hot-path stats idea generalizes to code maps |
| R5 | An offline stakeholder review round-trip (generate/apply, redacted, with a pinned round-trip test) (`:130-133`) | [leg 1 data-eng] |
| R6 | An optional JSON-LD emitter over `data-dictionary.json` + `lineage-graph.json`, built only when a real external consumer exists (`:135-138`) | [leg 1 data-eng] |
| §6 | The map-server MCP — `search_map` / `get_route_details` / `find_call_paths` / `get_map_status` over the map sidecars, every response freshness-stamped (`:142-154`) | **[leg 2 full-stack]** — the same generic server as R1 with the map source plugged in |

Plus the lane itself — entry + routing + delivery discipline for data-eng-primary runs — which is CT6-native structure (the bug-fix sibling precedent), not a deng import.

---

## 3. Leg 1 — a first-class data-engineering pipeline LANE

### 3a. Entry + routing

**The precedent.** CT6 already runs one full sibling lane: Phase −2 triage (`skills/architect-team-pipeline/SKILL.md:114-162`) dispatches a lightweight `bug-classifier` that returns `kind: bug | feature | mixed | unclear` (`:128-138`); `kind: bug` routes the whole run to `skills/bug-fix-pipeline` (`:140-144`), a sibling orchestrator with its own phases and disciplines (`skills/bug-fix-pipeline/SKILL.md:3,8`); explicit overrides skip the classifier — the `--bug-fix` flag and direct `/architect-team:bug-fix` invocation (`skills/architect-team-pipeline/SKILL.md:120-126`; `commands/architect-team.md:95-96`; the full command-entry shape is `commands/bug-fix.md:2-3,81-120,160-164`). The data-eng lane takes exactly this shape.

**Proposed entry surfaces (mirroring bug-fix precisely):**

1. **A `data-eng` verdict added to the existing Phase −2 classifier.** Extend `agents/bug-classifier.md`'s verdict enum from `bug | feature | mixed | unclear` to include `data-eng` (and a `data_eng_portion` field for mixed asks). No new agent — the classifier already reads language signals; its data-eng signals are the Phase 0c detection ladder that already exists (`skills/architect-team-pipeline/SKILL.md:337-358` — the prose patterns, tool keywords, codebase markers, and document markers). Low-confidence `data-eng` verdicts get the same soft-route confirmation the `bug` verdict already has (`:144`). **Builder note — the classifier edit is wider than the enum.** `agents/bug-classifier.md` pins itself "language-driven, not code-driven" (`:46`) with hard rules for exactly-five output fields and exactly-four kinds (`:217-218`); adding a fifth kind + a field moves those pins, so this is a deliberate classifier-contract change, not a one-line enum bump. And the 0c ladder's **codebase-markers arm** (`:356`) is written against Phase −1A mapping output that does not exist yet at Phase −2 time — at the front door it must re-anchor to a direct filesystem glob (a `dbt_project.yml` / `airflow/` / `models/staging/` scan) OR defer that arm to the existing Phase 0c path (a −2 miss on codebase-only signals still lands correctly at 0c, so language + tool-keyword + document markers are the −2-reliable signals and codebase-markers is the graceful-degradation arm).
2. **A `--data-eng` flag** on `/architect-team` → forces `kind: data-eng`, skips the classifier — a third bullet alongside `--bug-fix` / `--feature-only` (`skills/architect-team-pipeline/SKILL.md:120-126`; `commands/architect-team.md:95-96`).
3. **A `/architect-team:data-eng` command** (`commands/data-eng.md`, authored on the `commands/bug-fix.md` template: same dispatch banner, worktree lifecycle, flag set, two first-class input forms — folder or plain-language prose — and the same "invoke the skill, substitute `$REQ_DIR`" binding at `commands/bug-fix.md:101-120,160-164`).
4. **A new sibling orchestrator skill `skills/data-eng-pipeline/SKILL.md`** — the lane body (phases D−1…D8 below).

**The precise relationship to Phase 0c — who wins.** Phase 0c (`skills/architect-team-pipeline/SKILL.md:333-379`) is the existing MID-FLOW dispatch: a run already classified `feature` reaches Phase 0c, the detection ladder fires, and `data-engineering-exploration` runs as a stage of the feature pipeline (`:364`). That stays. The rule:

- **The lane wins at the front door.** A run whose PRIMARY ask is data-engineering — explicit flag/command, or a Phase −2 `data-eng` verdict — routes to `data-eng-pipeline` at Phase −2 and never reaches the feature pipeline's Phase 0c (the lane runs the exploration itself; there is nothing left for 0c to dispatch).
- **Phase 0c wins mid-flow.** A feature-primary run (Phase −2 said `feature`) that turns out to have a data-eng surface keeps today's Phase 0c behavior unchanged, including mixed-mode Branch C (`:366`) and the greenfield phenotype-seeding Branch B (`:365`).
- **`mixed` with a data-eng portion** generalizes the existing parallel-spawn pattern (`:148-152`): the data-eng portion goes to the lane, the rest to its pipeline, `triage_done: true` bounds recursion at depth 1 (`:118,162`).

This is deliberately NOT two competing detectors: Phase −2's data-eng signals and Phase 0c's ladder are the SAME ladder (`:337-358`) evaluated at two different moments — is the ask data-eng-shaped (front door), vs. does this feature have a data-eng surface (mid-flow).

**The lane's phases (D−1…D8) — reused structure, two new disciplines.** Mirroring how bug-fix keeps the main pipeline's structural points (`skills/bug-fix-pipeline/SKILL.md:3`):

| Phase | What happens | Reuse |
|---|---|---|
| D−1 Intake & Mapping | Standard intake per `intake-and-mapping` (freshness short-circuit `skills/intake-and-mapping/SKILL.md:46-52`), PLUS the **warm-catalog-first check**: query the knowledge server for the dictionary + its freshness verdict before considering a rebuild — deng's "check the catalog, not the database" discipline with CT6 semantics (the server's verdict informs; the per-run gate still decides). MemPalace wake-up precedes everything as in every pipeline (`skills/mempalace-integration/SKILL.md:115-124`). | intake-and-mapping; data-dictionary sequencing (`skills/data-dictionary/SKILL.md:36-42`) |
| D0 Exploration | Dispatch `skills/data-engineering-exploration` VERBATIM — the 7-stage flow (domain → conceptual model → service design → volume/velocity → security/PII → validation/lineage/observability → OpenSpec) is not duplicated, not forked. The lane becomes its third documented caller (`skills/data-engineering-exploration/SKILL.md:12-16` — currently two callers), passing the same structured `inputs` object (`:20-35`). Once R2 exists, mined SQL-object evidence feeds Stages 2–3 as input (`:72-160`). | data-engineering-exploration, unchanged |
| D1 Planning validation | Standard Phase 1 semantics: Stage 6 validation rules become explicit acceptance criteria, missing ones fail the loop (`skills/architect-team-pipeline/SKILL.md:375`). | Phase 1 verbatim |
| D2–D5 Implement + review | Standard parallel implementation with the full evidence stack — schema v7 (`hooks/review_evidence_schema.py:48-72`), paired adversarial review, dev-API integration testing. Data-specific bar: every transformation ships with its ≥1 blocker-severity validation rule implemented and its lineage emission wired, per the Stage 6 spec it was planned against (`skills/data-engineering-exploration/SKILL.md:261,320-329`). | Phases 2–5 verbatim |
| D6 Verify | Pipeline-execution verification against the dev environment (run the DAG/models against dev data; validation rules fire; lineage events observed). | Phase 5/6 discipline |
| D7 **Catalog refresh** | The second new discipline: rebuild the affected data-dictionary tables via the engine and re-corroborate — the DD-17/18 maintenance rule (`skills/data-dictionary/SKILL.md:112-119`) executed as a lane phase, then refresh the knowledge server's index and mine to MemPalace (`:104-110`). The run leaves the catalog warm for the next one. | data_dictionary engine; knowledge server |
| D8 Close-out | Standard Phase 8: documentation-currency, completion audit, auto-commit/merge, deploy-config honored. | Phase 8 verbatim |

### 3b. What the lane implements from deng (R1–R6), rebuilt to CT6 standards

**R1 — the standing warm catalog behind MCP tools (the foundation piece — see §5 for the full server design).**
*CT6 shape:* a new `services/knowledge_server/` member serving `search_dictionary` / `get_table_details` / `find_relations` / `get_dictionary_status` over the artifact pair the pipeline already produces — `docs/DATA_DICTIONARY_MAP.md` + `docs/data-dictionary.json` (`scripts/data_dictionary/data_dictionary.py:38-39`; `skills/data-dictionary/SKILL.md:26-27`) — returning the same corroborated, provenance-stamped content (`data_dictionary.py:43-48`).
*Reuse:* the content engine is DONE — builder `build_from_sqlite` (`data_dictionary.py:315`), reference map (`:277`), relation/blend map (`:292`). The ranked-search shape is the Librarian's — `LibraryIndex` with concept×3 / keyword×2 / text×1 weighting and `conceptual_search` (`services/librarian/library_index.py:31-33,51,126`). The standing-service pattern is the Librarian's — `Scheduler` on the BG runtime (`services/common/bg_runtime.py:42,64`), the daemon sibling-import bootstrap (`services/librarian/daemon.py:32-39`). The installer pattern is `scripts/setup/install_librarian.py` (`:2-47` — subcommands, `--check-only`, the never-auto-register honest boundary). The live-serving confirmation bar is the gateway's `confirm_gateway_serving` (`scripts/setup/install_gateway.py:1652`) — the installer never claims "serving" without a live round-trip.
*Freshness (the CT6 inversion of deng's 7-day wall clock):* `get_dictionary_status` answers with two honest arms — (a) **repo-derived staleness**: the by-table reference map lists the code files touching each table (`data_dictionary.py:277`); any of them changed since `last_built` (`skills/data-dictionary/SKILL.md:26`) ⇒ stale, change-driven like `intake-and-mapping`'s check (`skills/intake-and-mapping/SKILL.md:46-52`); (b) **DB-derived currency is UNKNOWABLE without a connection** — reported as `built_at` + "DB state unverified since" rather than a fake "fresh". A warm catalog that hides staleness would institutionalize exactly the wrong thing; every tool response carries the verdict.

**R2 — SQL-object mining (stored procedures / views + execution stats).**
*CT6 shape:* a new deterministic engine `scripts/sql_mining/sql_mining.py` (stdlib-only: a minimal vendored T-SQL/ANSI pattern extractor for joins, filters, aggregate/ratio metric shapes — NOT a sqlglot dependency; see decision D6) + a `warehouse-sql-mining` skill as its contract. No new agent: the engine is CLI-driven like `data_dictionary.py` (`:26-27` documents that CLI shape); the lane's D0 phase invokes it directly and feeds its output to the exploration stages.
*Where the output lands (all corroboration-gated):* mined field/metric candidates enter the dictionary as provenance `inference` — never anything stronger (`data_dictionary.py:43-48`) — and pass through `corroborate_definition` before any claim survives (`:231`); mined table-to-table read/write relationships become lineage `data_asset` evidence (`hooks/lineage_graph.py:69` — `data_asset` is already a node kind; `reads`/`writes` already edge kinds `:72-74`); join/filter/metric patterns become Stage 2/3 inputs (`skills/data-engineering-exploration/SKILL.md:72-160`).
*The fidelity rule (deng's lesson):* the engine surfaces parse-coverage stats (objects parsed / skipped / failed) in its artifact, and nothing mined bypasses corroboration — otherwise CT6 imports deng's fidelity problem along with its idea (`DENG_TOOLKIT_COMPARISON.md:117`).

**R3 — the persistent annotation channel on data objects.**
*CT6 shape:* per-user annotation files `docs/data-annotations/<user>.json` in the TARGET repo (team-shared via git; per-user files never merge-conflict — deng's genuinely good pattern), typed with deng's vocabulary taken as-is (`note` / `quality_flag {TRUSTED, STALE, INCOMPLETE, EXPERIMENTAL}` / `deprecation`), anchored to `table` / `table.field` ids from `data-dictionary.json`. Engine home: `scripts/data_dictionary/annotations.py` (composes with the dictionary engine; validate-on-write, atomic write).
*The CT6 inversion:* an annotation carrying a factual claim (`claims_key`, `expected_type`) routes through `corroborate_definition` on ingest (`data_dictionary.py:231`) — flagged ⚠ and confidence-downgraded on conflict, exactly like a provided definition (`skills/data-dictionary/SKILL.md:95-102`) — so the store never accumulates confidently-wrong tribal knowledge the way deng's can.
*Serving + recall:* the knowledge server's `get_table_details` merges annotations at query time (deng's merge-at-read pattern); annotations are mined to MemPalace alongside the dictionary artifact (`skills/data-dictionary/SKILL.md:104-110`). What CT6 already collects in-run — domain-gate answers, bulk-verify resolutions — gains a durable, structured, queryable home instead of only prose recall.

**R4 — usage-grounded importance in the dictionary.**
*CT6 shape:* an optional per-engine `usage_stats` adapter in the dictionary engine (following `build_from_sqlite`'s adapter shape, `data_dictionary.py:315`): SQL Server `dm_*` views, Postgres `pg_stat_*`; SQLite honestly has none. Output: a per-table `usage` block (read/write recency, volume) in `data-dictionary.json`, provenance `live-data` since it IS measured (`:43-48`).
*Consumption:* Stage 4's volume/velocity analysis gets measured baselines instead of pure estimates (`skills/data-engineering-exploration/SKILL.md:164-198` — `current_rows`, `peak_qps_or_rps` become measurements where stats exist); the knowledge server ranks `search_dictionary` results by it; R5's review rows sort by it.
*The honesty rule:* absent stats ≠ zero usage — the block is omitted, never zero-filled (deng's silently-single-target SSRS arm is the named anti-pattern, `DENG_TOOLKIT_COMPARISON.md:128`).

**R5 — the offline stakeholder review round-trip.**
*CT6 shape:* a `generate-review` / `apply-review` pair in the dictionary engine — CSV via stdlib `csv` first (Excel later behind an openpyxl adapter boundary if wanted). Row filter: fields with `low` confidence or ⚠ corroboration conflicts (`skills/data-dictionary/SKILL.md:95-102`), sorted by R4 usage when present. Returned corrections ingest as `provided_defs` and pass through the corroboration gate like every other human claim (`data_dictionary.py:231,315`).
*Privacy:* the file leaves the machine, so it passes through the helpdesk redaction engine first — the allow-list `summary` level (`scripts/helpdesk/logit.py:34,42-45`; allow-list, not deny-list, so unknown keys can't leak).
*The non-negotiable:* the produce/consume pair ships WITH a pinned round-trip test (write → edit → read → assert every column lands in the field it was written from). deng's is column-drifted on two of three sheets precisely because no such test exists (`DENG_TOOLKIT_COMPARISON.md:133,164`).

**R6 — the optional JSON-LD emitter.**
*CT6 shape:* a pure stdlib serializer (`scripts/data_dictionary/jsonld_export.py`) from `data-dictionary.json` + `lineage-graph.json` (both machine-complete — `data_dictionary.py:38-39`; `skills/endpoint-trace-mapping/SKILL.md:69-80`) into JSON-LD for the external catalog/lineage ecosystems Stage 6 already names (openlineage / marquez / datahub, `skills/data-engineering-exploration/SKILL.md:267`).
*The gate:* built only when a run names a REAL external consumer — formats without consumers rot into aspiration (`DENG_TOOLKIT_COMPARISON.md:138`). Deferred by default; see decision D7.

**What stays CT6-native (unchanged, non-negotiable).** The deng pieces above are STANDING INFRASTRUCTURE around the pipeline; the pipeline discipline is untouched: the 7-stage exploration keeps its mandatory Stage 5 security/PII classification (`skills/data-engineering-exploration/SKILL.md:200-228`) and Stage 6 validation/lineage/observability with the ≥1-blocker-rule-per-transformation gate (`:230-331`, blocker rule `:261`); the review gates and evidence schema v7 (`hooks/review_evidence_schema.py:48-72`); the corroboration inversion — human claims verified, not transcribed (`data_dictionary.py:210,231`); provenance honesty including the no-DB path's explicit "live inspection did NOT run" (`skills/data-dictionary/SKILL.md:121-134`); phenotype seeding for the IaC layer (`config-management` is a seeded phenotype at `phenotypes/config-management/phenotype.json`; Stage 3 already always proposes it, `skills/data-engineering-exploration/SKILL.md:136-158`).

### 3c. Blend-in points (exact files/phases)

| Piece | Wires into | Change shape |
|---|---|---|
| Classifier verdict | `agents/bug-classifier.md`; verdict schema at `skills/architect-team-pipeline/SKILL.md:128-138` | enum + `data_eng_portion` field; signals from the 0c ladder `:337-358` |
| Routing bullet | `skills/architect-team-pipeline/SKILL.md:140-158` (a `kind: data-eng` bullet mirroring `kind: bug` at `:142`) + a front-door-vs-mid-flow precedence note at `:333-335` | additive prose |
| `--data-eng` flag | `commands/architect-team.md:95-96` (third bullet) + `skills/architect-team-pipeline/SKILL.md:120-126` | additive |
| New command | `commands/data-eng.md` (template: `commands/bug-fix.md`) + registration in the command→skill map `hooks/skill_invocation_audit.py:118` (`COMMAND_TO_SKILLS`, reused by the real-time `pretool_skill_gate`) | new file + map entry |
| Lane skill | `skills/data-eng-pipeline/SKILL.md`; declares itself the third caller in `skills/data-engineering-exploration/SKILL.md:12-16` | new file + one bullet |
| Warm-check (D−1) | knowledge server query before the `skills/intake-and-mapping/SKILL.md:46-52`-style dictionary freshness decision | lane-skill prose |
| Catalog refresh (D7) | `skills/data-dictionary/SKILL.md:112-119` maintenance rule, executed via the engine + server re-index + MemPalace mine (`:104-110`) | lane-skill prose |
| R2 output | dictionary `provided_defs`/`inference` path (`data_dictionary.py:43-48,231`), lineage `data_asset` nodes (`hooks/lineage_graph.py:69`), exploration Stages 2–3 (`skills/data-engineering-exploration/SKILL.md:72-160`) | engine + skill |
| R3 store | `docs/data-annotations/<user>.json`; merge-at-query in the server; corroborate-on-ingest (`data_dictionary.py:231`); mine per `skills/data-dictionary/SKILL.md:104-110` | engine module |
| R4 stats | dictionary sidecar `usage` block; Stage 4 consumption (`skills/data-engineering-exploration/SKILL.md:164-198`) | engine adapter |
| R5 round-trip | dictionary confidence/conflict fields (`skills/data-dictionary/SKILL.md:95-102`); redaction via `scripts/helpdesk/logit.py:34,42-45` | engine subcommands |
| R6 emitter | `docs/data-dictionary.json` + `lineage-graph.json` (`skills/endpoint-trace-mapping/SKILL.md:69-80`); consumers per `skills/data-engineering-exploration/SKILL.md:267` | small serializer |

### 3d. Phased rollout, effort, blast radius

Routing wires in once R1 exists (the lane's D−1/D7 catalog steps presume a server to talk to; shipping the lane first would ship it hollow).

**Phase 1 — R1: the warm catalog + MCP foundation (== the generic server, §5).**
Effort: moderate (the largest single piece — a new services member + installer + entry-point-exercised tests). Blast radius: `services/knowledge_server/` (new; must keep `check_separation` green — `services/separation.py:161` asserts every `services/**/*.py` is import-clean stdlib+in-repo); `scripts/setup/install_knowledge_server.py`; ONE new command (`commands/knowledge-install.md`, mirroring `commands/librarian-install.md`'s existence) → command count 23→24, moving the canonical-command pin (`tests/test_skill_invocation_audit_canonical.py:53` asserts `== 23`), `COMMAND_TO_SKILLS` (`hooks/skill_invocation_audit.py:118`), `docs/CAPABILITY_INDEX.md` regeneration, the README/`CLAUDE.md` count lines, and a CHANGELOG entry per the rubric. No skill/agent/hook/Layer-3 count changes. New test files ~4–6 (server core, both source adapters, freshness verdicts, the stdio entry point itself — the deng §7.1 lesson made structural).

**Phase 2 — the lane + R2/R3/R4.**
*Lane:* skills 50→51 (`data-eng-pipeline`), commands 24→25 (`data-eng`), agents unchanged (classifier edit only — deliberately no new agent, so the model-policy lever and its role classification are untouched). Pins moved: the two count surfaces above again, plus the instruction-compliance zero-findings pin (`tests/test_instruction_compliance.py` grades every new SKILL.md/command's frontmatter + cross-references — mind the house no-`": "`-in-description rule). Effort: moderate (the skill body is mostly reused structure).
*R2:* `scripts/sql_mining/` engine + 1 skill (51→52) + tests. Effort: significant — the parser is the real work; scope it T-SQL-first (decision D6).
*R3:* engine module + server merge-at-query + a section in the data-dictionary skill. Effort: small.
*R4:* dictionary engine adapter + tests. Effort: small-moderate (per additional DB engine).

**Phase 3 — R5/R6.**
*R5:* engine generate/apply subcommands + the pinned round-trip test + logit redaction wiring. Effort: small-moderate.
*R6:* the serializer, gated on a named consumer. Effort: low. Neither moves any count except tests.

---

## 4. Leg 2 — cross-pollination into the full-stack cycle

### 4a. The map-server MCP — the same server, a different source

The §6 generalization (`DENG_TOOLKIT_COMPARISON.md:142-154`) lands as the knowledge server's SECOND source adapter — **this is the key structural insight of the whole proposal: leg-2's map server and leg-1's R1 catalog are ONE server with two data sources.** Nothing map-specific is built twice: the ranked search, the freshness contract, the MCP surface, the installer, the daemon are shared; the map source contributes only its read adapters and tool bindings.

The four tools, over the machine sidecars CT6 already commits:

- **`search_map`** — ranked keyword search across `CODEBASE_MAP` / `ROUTE_MAP` / `INTEGRATION_MAP` / `ENDPOINT_TRACE_MAP` content and the `lineage-graph.json` node inventory. Search core: the same `LibraryIndex` weighting shape (`services/librarian/library_index.py:31-33,126`).
- **`get_route_details`** — a route's components/endpoints from the route map's structured content.
- **`find_call_paths`** — path queries over `lineage-graph.json` (`skills/endpoint-trace-mapping/SKILL.md:69-80`) — the direct generalization of deng's `find_join_paths` from FK edges to the `calls` / `reads` / `writes` / `modifies` / `serves` / `originates` / `serves_route` edge vocabulary (`hooks/lineage_graph.py:72-74`), walking the reachability kinds (`:87`).
- **`get_map_status`** — per-map freshness: `last_mapped` / `last_traced` stamps (`skills/intake-and-mapping/SKILL.md:48`; `skills/endpoint-trace-mapping/SKILL.md:45-54`), the `map_invalidated` override array (`skills/intake-and-mapping/SKILL.md:50`), and — the part deng could not do — **true change-driven staleness** from `transitive_stale_nodes(graph, changed_paths)` with `changed_paths` from `git log` since the stamp (`hooks/lineage_graph.py:578`; per-node semantics `:546`; the rule's home `skills/endpoint-trace-mapping/SKILL.md:144-149`). deng's status tool answers from a wall clock; CT6's answers from what actually changed.

**Every response from every tool carries its freshness verdict** — not only `get_map_status`. A `find_call_paths` answer over a graph with stale nodes in the queried subtree says so in the response envelope. Each tool's response shape is a CLOSED contract designed with CT6's own MCP output-contract engine — `build_output_contract` / `validate_against_contract` (`scripts/mcp_design/output_contract.py:49,122`) — so the server's outputs meet the same standardization bar CT6 prescribes for embedded agents.

What it buys the full-stack cycle: every map-consulting agent (planners, intuiters, diagnostic researchers, the refiner's codebase grounding) gets one-tool-call structured answers instead of Read+Grep over 1,500-line markdown — a fraction of the token cost — and CT6's intelligence opens to non-CT6 consumers (any MCP client).

### 4b. Other patterns that generalize

- **The annotation channel as persistent domain-gate memory.** CT6's bulk-verify gate resolves every low-confidence interaction intuition with the user once per run (`skills/interaction-intuition/SKILL.md:10`); the confirmations are mined to MemPalace as prose (`:27`). R3's annotation store generalizes: a bulk-verify resolution ("this button calls POST /api/orders/cancel — confirmed") persists as a STRUCTURED annotation anchored to the element/endpoint id, warm and queryable through the server, team-shared via git — so run N+3 looks the fact up instead of re-asking or re-deriving. The gate still fires for genuinely new/changed elements (it is a domain gate — the user-confirmation step IS the feature, `:107`); what generalizes is the MEMORY of past confirmations, surfaced as prior evidence with provenance `direct-user-input`, never as a silent skip of the gate. Recalled annotations ride the existing recall-hygiene envelope discipline (data, not instructions).
- **Usage-grounded hot-path stats.** R4's idea applied to code: measured execution frequency (from the dev-environment runs and Playwright flows CT6 already executes) attached to lineage-graph endpoints/functions, so diagnosis and review prioritize by observed traffic, not just by requirement. Cheap once the server exists (a `usage` field on nodes the map source serves); a later run's scope.

### 4c. Explicit non-applications — where the standing-warm pattern must NOT reach

1. **The run-scoped contract ledger stays run-scoped.** The contract-first-parallelism ledger is deliberately forward-only (`proposed → approved → mock-serving → live`, `scripts/contract/interface_contract.py:31-32`) with a retirement gate that makes any still-mock-serving surface non-closable (`:35-36`) and FAIL-CLOSED reads (`:46-52`). A warm, ambient, cross-run mock-serving ledger is precisely the fail-open debt the v3.48.1 hardening existed to kill (`CHANGELOG.md:7-10`). The knowledge server NEVER serves ledger state.
2. **The per-run freshness/witness gates still run at consumption.** The server serves artifacts + reports freshness; pipeline consumption still runs the gate: intake's freshness short-circuit decides remap per run (`skills/intake-and-mapping/SKILL.md:46-52`), and diagnosis still refuses a lineage subgraph that fails the witness gate — recall ≥ 0.9, hallucination ≤ 0.05 (`hooks/lineage_graph.py:470`; `skills/endpoint-trace-mapping/SKILL.md:128-132`). The server is a read path, never a trust shortcut.
3. **Convergence artifacts are verification events, not cache entries.** Caching the OUTPUT of the 3-reviewer convergences and the bulk-verify (that is what the committed maps and the R3 annotations are) is fine; the server must never tempt the pipeline to skip the ACT of independent re-derivation when inputs changed.

---

## 5. The generic knowledge server — the shared foundation, sketched once

Named here once so both legs above can reference it. Working name: **`services/knowledge_server/`** (final name is Paul's call, decision D3).

- **Core:** a stdlib-only MCP server speaking JSON-RPC 2.0 over stdio — the protocol handshake (`initialize` / `tools/list` / `tools/call`) hand-implemented in stdlib, no `mcp` SDK dependency (decision D4). This keeps `check_separation` green (`services/separation.py:161`) and — decisively — makes the ENTRY POINT itself testable in-suite: the tests drive the stdio loop end-to-end, which is the structural refusal of deng's launch-dead server defect (`DENG_TOOLKIT_COMPARISON.md:163` — its `main()` cannot start as written and no test would have noticed).
- **Source adapters (the pluggable seam):** `DictionarySource` over `docs/data-dictionary.json` (+ `docs/data-annotations/`), `MapSource` over `lineage-graph.json` + the map files' frontmatter. Both read-only. The adapter interface is designed for both from day one even if one ships first.
- **Search:** composes the Librarian's `LibraryIndex` (`services/librarian/library_index.py:51,126`) — the sibling-import pattern the Librarian daemon already uses (`services/librarian/daemon.py:32-39`) — rather than extending the Librarian daemon itself: the Librarian's domain is topic-research curation (fetch → extract → index, `services/librarian/librarian.py:61,82`); the knowledge server's domain is serving repo-derived sidecars. Shared substrate, separate services (decision D3).
- **Refresh:** a `bg_runtime.Scheduler` tick (`services/common/bg_runtime.py:64`) re-indexes when sidecar mtimes/hashes change. No LLM anywhere in the server — it is fully deterministic.
- **Freshness contract:** every tool response carries `{verdict: current|stale|unknowable, basis: [...]}` computed per source — maps via `transitive_stale_nodes` + stamps + `map_invalidated`; dictionary via reference-file git-drift + `built_at`, with DB-side currency honestly `unknowable` absent a connection. Never a bare wall clock.
- **Install:** `scripts/setup/install_knowledge_server.py` on the `install_librarian.py` template (`:2-47`): provisions `~/.architect-team/knowledge/`, generates + PRINTS the MCP registration (never auto-edits the user's MCP config), `--check-only`/`--json`/`status`/`uninstall --purge` parity, and a live-serving confirmation in the `confirm_gateway_serving` mold (`scripts/setup/install_gateway.py:1652`) — a real `tools/call` round-trip before the word "serving" is ever printed.
- **Scope:** per-repo indexes first; the cross-repo aggregation index (deng's home-dir catalog) is an opt-in later increment (decision D2).

---

## 6. Reuse-first ledger

Every row's cite opened and verified this session. "Extends/composes" is literal — the named engine is imported/invoked, not re-implemented.

| New piece | Extends / composes | Why not greenfield |
|---|---|---|
| Knowledge server core | `services/librarian/library_index.py:51,126` (ranked index + conceptual search); `services/common/bg_runtime.py:42,64` (ServiceTask/Scheduler); sibling-import bootstrap per `services/librarian/daemon.py:32-39`; separability invariant `services/separation.py:161` | The service tier already ships the standing-daemon substrate + a weighted search index; only the MCP stdio loop + source adapters are new |
| DictionarySource (R1) | `scripts/data_dictionary/data_dictionary.py:38-39,277,292,315` (artifact pair, reference map, relation map, builder); `skills/data-dictionary/SKILL.md:26-27` | The catalog CONTENT engine is complete and corroborated; the server only serves it |
| MapSource (leg 2) | `lineage-graph.json` schema per `skills/endpoint-trace-mapping/SKILL.md:69-80`; edge vocabulary `hooks/lineage_graph.py:72-74,87` | The graph + its query-relevant edge kinds already exist; `find_call_paths` is a walk, not a model |
| Freshness verdicts | `hooks/lineage_graph.py:546,578` (transitive staleness); `skills/intake-and-mapping/SKILL.md:46-52` (stamp + `map_invalidated` discipline); `skills/endpoint-trace-mapping/SKILL.md:144-149` | CT6's change-driven freshness engines are the exact thing deng lacked; serving them is reuse, rebuilding them would be malpractice |
| Tool output contracts | `scripts/mcp_design/output_contract.py:49,122` (closed-schema builder + validator) | CT6 already ships the machine for standardized tool outputs; the server eats its own dog food |
| Server installer | `scripts/setup/install_librarian.py:2-47` (lifecycle/CLI/honest-boundary template); live-confirmation bar `scripts/setup/install_gateway.py:1652` | Third instance of a proven installer pattern; new posture decisions would be gratuitous drift |
| Lane entry (flag/command/classifier) | `skills/architect-team-pipeline/SKILL.md:114-162` (triage + routing), `:120-126` (flag overrides); `commands/bug-fix.md:2-3,81-120,160-164` (command template); `commands/architect-team.md:95-96`; `hooks/skill_invocation_audit.py:118` (command→skill map) | The sibling-lane entry machinery exists end-to-end for bug-fix; the lane is its second instantiation |
| Lane exploration phase | `skills/data-engineering-exploration/SKILL.md:12-16` (caller registry), `:20-35` (inputs contract), Stages 1–7 (`:44-348`) | The 7-stage flow is the hard-won asset; the lane adds a caller, never a fork |
| R2 mining engine | outputs into `data_dictionary.py:43-48` (provenance), `:231` (corroboration gate), `hooks/lineage_graph.py:69` (`data_asset` nodes), `skills/data-engineering-exploration/SKILL.md:72-160` (Stage 2/3 consumption) | Only the parser is new; every downstream home for its output already exists with the right gates |
| R3 annotations | anchor ids from `data-dictionary.json`; ingest via `data_dictionary.py:231`; conflict semantics `skills/data-dictionary/SKILL.md:95-102`; mining per `:104-110`; leg-2 analog anchored on `skills/interaction-intuition/SKILL.md:10,27,107` | The corroboration + mining + gate machinery is in place; the store is a thin, typed persistence layer over it |
| R4 usage stats | adapter shape `data_dictionary.py:315`; consumption `skills/data-engineering-exploration/SKILL.md:164-198` | One additive sidecar block + one adapter per engine; Stage 4 is already built to eat exactly this |
| R5 round-trip | row filter from `skills/data-dictionary/SKILL.md:95-102`; ingest via `data_dictionary.py:231,315`; redaction `scripts/helpdesk/logit.py:34,42-45` | Generate/apply is two small functions over existing fields; the privacy engine is done |
| R6 JSON-LD | `data-dictionary.json` (`data_dictionary.py:38-39`) + `lineage-graph.json` (`skills/endpoint-trace-mapping/SKILL.md:69-80`); consumers named at `skills/data-engineering-exploration/SKILL.md:267` | Pure serialization of two machine-complete sidecars |

---

## 7. Recommended build sequence — what the follow-up runs do

Approving this document hands the next runs a spec-ready backlog in this order. **The ordering principle: leg-1-R1 and leg-2's map server are the SAME generic server — build that shared foundation FIRST; everything else either rides it or feeds it.**

1. **Run A — `knowledge-server-foundation`** (Phase 1). The generic server core (stdlib MCP stdio loop + source-adapter seam + freshness contract + `LibraryIndex` composition) + the DictionarySource end-to-end + the MapSource's four tools + installer + entry-point-exercised tests + closed output contracts. If run scope forces a cut, the MapSource tools may complete in Run B — but the adapter seam and freshness contract are designed for both sources from the first commit. Gate: the live `tools/call` confirmation + suite green + `check_separation` green.
2. **Run B — `data-eng-lane`** (Phase 2, lane). The `data-eng-pipeline` skill, the classifier verdict, `--data-eng`, `commands/data-eng.md`, the routing/precedence edits, the D−1 warm-check + D7 catalog-refresh phases wired to Run A's server. Gate: an end-to-end lane run against a sample data-eng ask (the exploration skill dispatched as third caller; catalog warm afterward).
3. **Run C — `warehouse-sql-mining`** (Phase 2, R2). The mining engine + skill, T-SQL-first, corroboration-gated outputs into dictionary + lineage + exploration. Largest independent engine; benefits from the lane existing to consume it.
4. **Run D — `data-annotations`** (Phase 2, R3 + the leg-2 generalization's first step). The annotation store + corroborate-on-ingest + server merge-at-query; bulk-verify confirmations begin persisting as structured annotations.
5. **Run E — `usage-stats + review-round-trip`** (Phase 2 R4 + Phase 3 R5 — small enough to pair). The usage adapter feeding Stage 4 and the CSV generate/apply pair with its pinned round-trip test.
6. **Run F — `jsonld-emitter`** (Phase 3, R6) — ONLY when a named external consumer exists; otherwise it stays in the backlog deliberately.

Each run is a normal `/architect-team` invocation with this document + the comparison as `$REQ_DIR` inputs; each lands with the standard evidence, doc-currency, and CHANGELOG obligations, and each states its honest boundary (in particular: Run A's installer confirms live serving on THIS machine; nothing is ever described as deployed).

---

## 8. Open decisions for Paul

Each is a crisp fork; my recommendation is marked. Nothing builds until these are settled.

- **D1 — Lane shape.** Full sibling pipeline (`data-eng-pipeline`, the bug-fix pattern) **[recommended]** vs. strengthening Phase 0c in place (no new lane; data-eng stays a mid-feature dispatch). The sibling gives data-eng-primary asks their own entry, phases, and close-out discipline; 0c-only keeps the surface smaller but leaves "build me a warehouse" masquerading as a feature run forever.
- **D2 — Catalog scope.** Per-repo catalog first, opt-in cross-repo aggregate index later **[recommended]** vs. deng-style shared home-dir catalog from day one. Per-repo keeps the trust story simple (one repo, one corroborated dictionary, git-shared); cross-repo aggregation is a later increment once the server is proven.
- **D3 — Server home.** New `services/knowledge_server/` composing `library_index` **[recommended]** vs. extending the Librarian daemon itself. Separate keeps each service's domain clean (curation vs. serving); extending saves an installer but couples unrelated lifecycles.
- **D4 — MCP transport.** Hand-rolled stdlib JSON-RPC stdio **[recommended]** vs. the `mcp` SDK behind an adapter boundary. Stdlib honors the house rule, keeps `check_separation` green, and makes the entry point suite-testable; the SDK buys protocol currency at the cost of a dependency and a mocked boundary.
- **D5 — Annotation-as-memory aggressiveness.** Data objects first, interaction/bulk-verify confirmations in a second step (Run D as scoped) **[recommended]** vs. generalizing to all domain-gate memory at once. Incremental keeps the gate-integrity question (served memory must inform, never skip, the gate) reviewable in isolation.
- **D6 — R2 parser scope.** Vendored minimal stdlib extractor, T-SQL-first **[recommended]** vs. sqlglot behind an adapter. The stdlib extractor covers joins/filters/metric shapes with honest parse-coverage stats; sqlglot parses more but imports a dependency and an un-audited fidelity surface.
- **D7 — R6 timing.** Defer until a run names a real external consumer **[recommended]** vs. build in Phase 3 regardless. The comparison's own evidence (advertised-but-ungenerated artifacts rotting) argues for deferral.
- **D8 — Installer surface.** A new `/architect-team:knowledge-install` command **[recommended]** vs. folding server install into `librarian-install`. A separate command matches D3's separation and keeps each installer's honest-boundary story independent; folding avoids a count bump (23→24) at the cost of a two-headed installer.

---

*End of proposal. Nothing in this document authorizes a build; §7's runs execute only on Paul's approval, and every effort/blast-radius figure above is engineering judgment, not measurement.*
