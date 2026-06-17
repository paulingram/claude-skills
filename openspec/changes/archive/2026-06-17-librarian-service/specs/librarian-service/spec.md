## ADDED Requirements

### Requirement: REQ-001 — Reference index + conceptual search (LIB-10…13)

`services/librarian/library_index.py` SHALL provide a stdlib `sqlite3` reference index storing, per document, a title, a summary, strong searchable keywords, and a concept cloud (LIB-11/12/13), with lookup by keyword and by concept and an idempotent re-index by `doc_id`. It SHALL provide a conceptual search (LIB-10) that ranks documents by the weighted overlap of the query's terms with each doc's concept cloud (weighted highest), keywords, and title+summary tokens, over unicode-folded tokens.

#### Scenario: a conceptual query ranks a concept hit above a mere text mention

- **WHEN** one document carries a query term in its concept cloud and another only mentions it once in its summary, and the query is run
- **THEN** `conceptual_search` returns the concept-cloud document first (concept ×3 outranks text ×1), and a diacritic-only difference (`cafe` vs `café`) still matches

### Requirement: REQ-002 — LLM extraction with a string-aware parse (LIB-11/12)

`services/librarian/extract.py` SHALL build an extraction prompt asking the LLM to confirm relevance and return a single JSON object (title + summary + strong keywords + concept cloud), and SHALL parse the reply with the stdlib string-aware `JSONDecoder.raw_decode` (so a `{`/`}` inside a string value cannot truncate the object), yielding a not-relevant record on an unparseable reply rather than raising. Each document SHALL get a stable id (a sha256 of its text) so re-ingesting is idempotent.

#### Scenario: a brace inside a string value does not truncate the parse

- **WHEN** the LLM reply is a JSON object whose summary string contains `}` and `{`
- **THEN** `parse_extraction` returns the full object (relevant, title, and the brace-bearing summary intact); an unparseable reply returns `relevant: False`

### Requirement: REQ-003 — Librarian orchestration on the BG runtime (LIB-1…9)

`services/librarian/librarian.py` SHALL tie a content `Source` adapter + the LLM + the index together: `research_topic` fetches a topic's documents, extracts each, indexes the relevant keepers (a `relevant AND (title OR summary)` gate), and writes the per-topic metadata file agents look for (LIB-6). It SHALL register a per-topic task on the shared `bg_runtime` scheduler (LIB-5) and emit the per-OS install descriptor (LIB-2/3). When a `body_dir` is configured it SHALL store full document bodies on disk (LIB-8) with a path-safe filename so an operator-supplied `doc_id` cannot escape the folder.

#### Scenario: fetch → extract → index → metadata, with a safe body store

- **WHEN** a topic with one relevant and one irrelevant document is researched (with a `body_dir` set)
- **THEN** only the relevant document is indexed and its metadata file written, the irrelevant one is skipped, and its body round-trips from disk via a sanitized filename that stays inside `body_dir`

### Requirement: REQ-004 — Honest boundary + separable + stdlib-only core

`services/librarian/` SHALL be a runnable stdlib-only deterministic core documented honestly as design + tests, NOT a live-deployed service. The data SOURCE (web scrape / an attached API), the MemPalace VECTOR store (LIB-9 preferred), and the Anthropic LLM SHALL be adapters behind interfaces with dependency-free fallbacks (`StaticSource` + `FakeLLMClient`); LIB-4 (centralized curation endpoint) and LIB-7 (global-MemPalace-install research) SHALL be disclosed as design-stage, not built.

#### Scenario: the adapter boundary + honest scope are documented

- **WHEN** `services/README.md` and the module docstrings are read
- **THEN** they state the design-not-deployed boundary, name the source / vector-store / LLM adapters with their stdlib fallbacks, and record LIB-4 / LIB-7 as not built

### Requirement: REQ-005 — Tests green both encodings (+ adversarial review)

A new test file SHALL cover the index (round-trip / idempotent re-index / keyword + concept search / conceptual ranking / concept cloud), the extraction (prompt + string-aware parse incl. the brace-in-string edge + stable id), and the orchestration (relevant-keep-vs-skip + metadata + scheduler tasks + install descriptor + the file-folder body store + path safety + per-topic closure binding); the full suite SHALL pass under both Windows cp1252 and `PYTHONUTF8=1`, and the service SHALL pass an independent adversarial review.

#### Scenario: suite green

- **WHEN** the suite runs under both encodings with `tests/test_services_librarian.py` present
- **THEN** there are zero failures
