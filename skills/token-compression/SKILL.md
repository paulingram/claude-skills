---
name: token-compression
description: Use to reduce the token cost of agents' INTERNAL communication — inter-agent messages, scratch notes, internal reasoning summaries — by writing tersely ("talk like a caveman"), WITHOUT harming external output quality (output to users / other systems / final deliverables stays full-quality; TC-1). Provides a deterministic stdlib "caveman" compressor (drops articles / politeness / intensifiers + wordy phrases, preserves content words / identifiers / numbers / code verbatim) and documents evaluating a heavier ML token-compression package (LLMLingua-style) for developer agents while they run (TC-3). The deterministic engine lives in scripts/token_compression/caveman.py; this skill is the contract, including the hard internal-only boundary.
---

# Token Compression (TC-1 … TC-3)

Agents spend tokens on two kinds of text: what they say to the OUTSIDE (users,
other systems, final deliverables) and what they say to THEMSELVES and EACH OTHER
(inter-agent messages, scratch notes, internal summaries). The outside text must
stay full-quality; the internal text can be terse. This discipline compresses the
internal text to free up context, and draws a hard line so the outside text is
never touched.

The deterministic, always-available compressor lives in
**`scripts/token_compression/caveman.py`** (stdlib-only, unit-tested). This skill
is the contract + the internal-only boundary. Do not re-implement the transform in
prose — call the module.

## The hard boundary (TC-1) — internal only

**NEVER compress external output.** The caveman transform applies ONLY to:

- inter-agent messages (teammate ↔ teammate, Lead ↔ teammate),
- an agent's own scratch / working notes / internal reasoning summaries,
- internal context an agent re-reads for itself.

It must NOT touch: the final answer to the user, content sent to other systems
(API payloads, commits, file contents, PRs, emails), test output, or anything a
human or downstream system consumes. Output quality to the outside is preserved
verbatim — that is the non-negotiable line TC-1 draws.

## The caveman style (TC-2)

`compress(text)` reduces verbosity meaning-preservingly: it drops pure filler
(articles `a`/`an`/`the`, politeness `please`/`kindly`/`thanks`, intensifiers /
hedges `just`/`really`/`very`/`actually`/`basically`/`simply`/…) and a few wordy
phrases (`in order to` → `to`, `due to the fact that` → `because`), while
PRESERVING content words, identifiers, numbers, line structure, and — critically
— fenced (```` ``` ````) and inline (`` ` ``) code VERBATIM. Prepositions,
conjunctions, and copulas are kept (they carry meaning) so the compressed text
stays understandable to the agent that re-reads it.

```bash
$(command -v python3 || command -v python) scripts/token_compression/caveman.py stats --json   # measure savings
$(command -v python3 || command -v python) scripts/token_compression/caveman.py compress         # emit compressed
```

`compression_stats(text)` reports the original vs compressed token estimate + the
saved percentage so the win is measurable, not assumed.

## Evaluating a heavier package (TC-3)

The stdlib caveman compressor is the FLOOR — always available, zero dependencies,
safe. For larger wins on developer agents while they run, evaluate an ML
token-compression package (e.g. LLMLingua-style prompt compression) and apply it
to the internal channels per the same TC-1 boundary. Such a package is a
third-party dependency (NOT stdlib) and is plugged in at the application layer,
not bundled into this stdlib-only plugin — evaluate it for the specific agent
workload, measure with `compression_stats` as the baseline to beat, and keep the
caveman transform as the always-on fallback.

## Honest boundary

The caveman transform is a **lossy-of-FILLER heuristic**, not a semantic ML
compressor — it drops a fixed filler list + wordy phrases and collapses
whitespace; it does not understand meaning. Two consequences: (1) any single
token that matches a filler word case-insensitively is dropped, so a single-letter
or short token used as CONTENT outside backticks — a variable `a`, the grade `A`,
a drug/vitamin designation `A`, a list marker — can be lost; wrap such content in
`` ` `` so the code-preserve path keeps it verbatim; (2) the token counts are
estimates (~4 chars/token), not an exact tokenizer. Never apply it to external
output (TC-1), and measure rather than assume the savings.

## Cross-references

- `scripts/token_compression/caveman.py` — the deterministic compressor + stats (the machine).
- CT6-6 §3 (TC) — the requirements (internal-comms optimization; "talk like a caveman"; evaluate compression packages).
