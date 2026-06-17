# CT6-6 Service / Server Tier

This directory holds the **service/server tier** of the Claude Team 6 (CT6-6)
program — the long-running, off-machine, or networked components: the Librarian,
the Session-Review and Evaluator/Triage services, the seeded-MemPalace service,
and the shared substrate they sit on. It is the counterpart to the in-repo plugin
tier (`skills/` + `agents/` + `commands/` + `hooks/`), which ships the spec-driven
pipeline itself.

## Honest boundary — read this first

These components are delivered as **design + a runnable, stdlib-only deterministic
core + tests**, NOT as live-deployed services. The actual cross-machine
deployment, the live triage server, the ChromaDB vector store, the Anthropic API
calls, web scraping, and any Postgres index require external infrastructure and
credentials that are **not** part of this repository and are **not** stood up by
this code. Where a component needs such a thing, the stdlib core sits behind an
**adapter boundary** with a dependency-free fallback so the logic stays testable;
the real adapter (and the deployment) is the operator's to provide. Nothing here
should be described as "deployed" or "running in production" — it is the
buildable, verifiable substrate plus the design for the parts that aren't.

## Decided model (2026-06-17)

- **Placement** — in-repo, written **separable** (REPO-3): each service is a
  self-contained dir with its own entry point so it can later be lifted into its
  own repo (REPO-1/4), e.g. when a paid/closed feature splits out.
- **Auth key** — ONE Anthropic API key serves both as the background LLM key
  (LIB-1/3) and the triage sign-up identity (SEC-2). See `common/service_config.py`.
- **Triage handshake** — a local **Ed25519** signature (SEC-3): the logger signs
  each submission; the server verifies with the public key (stores no secret).
  The project-unique "genuine logger" proof is a pluggable **attestation** — the
  separable closed/paid piece (SEC-4) — kept behind an interface here.

## Layout

- **`common/`** — the shared substrate (v3.23.0):
  - `ed25519.py` — pure-Python, stdlib-only Ed25519 (RFC 8032), no 3rd-party dep (SEC-3).
  - `handshake.py` — signed submission envelopes + replay protection + the pluggable attestation hook (SEC-1/2/3/5).
  - `bg_runtime.py` — the always-on runtime: cron-like scheduler + self-check + per-OS boot/restart install descriptors (systemd / launchd / Task Scheduler) + a log-ship interface (BG-1…4).
  - `service_config.py` — the same-Anthropic-key config + the `LLMClient` adapter interface (real Anthropic adapter is a documented boundary; `FakeLLMClient` for tests).
- **`librarian/`** — the topic-research curation service (v3.24.0; LIB-1…13):
  - `library_index.py` — a stdlib `sqlite3` keyword / summary / concept-cloud reference index + the LIB-10 conceptual search (weighted overlap — concept ×3 / keyword ×2 / text ×1 — over unicode-folded tokens; an honest deterministic stand-in for the LIB-9 vector store, NOT semantic/synonym expansion).
  - `extract.py` — the LLM read → confirm-relevant → title / summary / strong-keywords / concept-cloud extraction (LIB-11/12), with a string-aware JSON parse (a brace inside a string value can't truncate the object).
  - `librarian.py` — the fetch → extract → index → metadata orchestration on the shared `bg_runtime` (scheduler tasks + install descriptor) + the LIB-8 file-folder body store (path-safe filename). The data source (scrape / API), the MemPalace vector store (LIB-9), and the LLM are adapters with stdlib fallbacks (`StaticSource` / `FakeLLMClient`). NOT built (design-stage): LIB-4's centralized curation endpoint + LIB-7's global-MemPalace-install research.
- **`triage/`** — the Evaluator / triage service (v3.25.0; EVAL-1…17 + SEC):
  - `issue.py` — the normalized issue record + dedup fingerprint (EVAL-8/9/14), REUSING the helpdesk `logit` privacy engine (full / summary / off — **off by default**, EVAL-17).
  - `evaluator.py` — EVAL-1: review logs "as a senior agentic architect", categorize + root-cause each issue (string-aware JSON parse); EVAL-3: the ~hourly `bg_runtime` optimization task.
  - `tally_queue.py` — EVAL-4/10: batch duplicate issues by fingerprint; promote recurring ones to a longer-lasting backlog.
  - `triage.py` — the EVAL-11/12 **quarantine rule** (an issue first seen on an old version may already be fixed by an intermediate release the reporter didn't upgrade to — hold + verify from the fixed version onward) + EVAL-6 resolution log + EVAL-7/13 recurrence + EVAL-5 two-stage core-issue review.
  - `sink.py` — EVAL-2: the GitHub-issue sink adapter (payload built; the real POST is injected — operator's, like `notify.py`).
  - `server.py` — EVAL-2 + SEC: a stdlib submission server verifying a signed Ed25519 envelope (reusing `common/handshake.py`; no per-user codes; replay/tamper rejected; SEC-4 attestation pluggable + off by default) + re-applying privacy before storing. The live socket / GitHub API / Postgres / LLM are operator-provided.
- *(landing next)* `session_review/` (SR), `seeded_mempalace/` (SMP).

## Separation plan (REPO-1 … REPO-4)

Each service is written as an independent unit (its own dir, entry point, and — as
they land — installer + config). The **paid/closed** pieces (most notably the
SEC-4 project-unique attestation algorithm) are kept behind interfaces so they can
move into a separate, separately-distributed repo without touching the open core:
the open core ships the standard mechanism (Ed25519 envelope + replay) and a
stdlib stub for the closed hook; the genuine algorithm is injected. The service
tier may carry its OWN dependencies when separated (REPO-4) — it is not bound by
the plugin core's stdlib-only contract once it is its own distributable; the
stdlib-only core here is what keeps it testable inside this repo today.
