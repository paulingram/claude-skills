## Why

With the service-tier substrate shipped (v3.23.0 — SEC handshake + BG runtime + the same-Anthropic-key config), this builds the first concrete service on it: the **Librarian** (CT6-6 LIB-1…13). The Librarian is a background curation/research service — it pulls data for user-defined topics throughout the day, reads + extracts each download via the shared LLM, indexes the keepers into a searchable reference store, and writes the per-topic metadata files agents look for. It runs on the shared `bg_runtime` and uses the shared Anthropic key. HONEST: design + a runnable stdlib-only core + tests, NOT a live-deployed service — the data source, the vector store, and the LLM are adapters with stdlib fallbacks.

## What Changes

- **`services/librarian/library_index.py`** — a stdlib `sqlite3` keyword / summary / concept-cloud reference index (LIB-11/12/13) + the LIB-10 conceptual search (weighted overlap of query terms with each doc's concept cloud ×3 / keywords ×2 / title+summary ×1, over unicode-folded tokens). (REQ-001)
- **`services/librarian/extract.py`** — the LLM read → confirm-relevant → title / summary / strong-keywords / concept-cloud extraction (LIB-11/12), with a string-aware JSON parse (`JSONDecoder.raw_decode`) so a brace inside a string value can't truncate the object. (REQ-002)
- **`services/librarian/librarian.py`** — the fetch → extract → index → metadata orchestration (LIB-1…9) on the shared `bg_runtime` (scheduler tasks + per-OS install descriptor) + the LIB-8 file-folder body store (path-safe filename); `Source`/`StaticSource` + `LLMClient`/`FakeLLMClient` adapters. (REQ-003)
- **Honest boundary + stdlib-only core + tests** + an independent adversarial review. (REQ-004, REQ-005)

## Capabilities

### New Capabilities

- `librarian-service` — the CT6-6 Librarian: a background topic-research curation service (a searchable keyword/summary/concept reference index + conceptual search + LLM-driven extraction, on the shared BG runtime), as design + a runnable stdlib-only core.

### Modified Capabilities

- None removed. New files land under the existing top-level `services/` (v3.23.0); skill/agent/command counts are unchanged (the service tier is not a skill/agent/command).
