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
- *(landing next)* `librarian/` (LIB), `triage/` (EVAL + SEC server), `session_review/` (SR), `seeded_mempalace/` (SMP).

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
