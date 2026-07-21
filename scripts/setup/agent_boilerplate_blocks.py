# -*- coding: utf-8 -*-
"""Canonical boilerplate-block text for architect-team agent files.

SINGLE SOURCE OF TRUTH for three byte-identical boilerplate sections that are
duplicated across the ~30 ``agents/*.md`` files:

* ``## Forbidden git operations``   (v1.6.0 discipline)
* ``## Checkpoint discipline``      (v1.8.0 discipline)
* ``## Operating context (v1.0.0)`` (the shared teammate-context paragraph)

This module is **stdlib-only and has no import-time side effects**. It exposes:

* ``BLOCKS`` -- a dict keyed by block id, each value carrying the ``heading``,
  the ``canonical`` text, the ``match`` mode, the list of ``standard_agents``
  that must carry the canonical form, and the ``variant_agents`` that are
  explicitly ALLOWLISTED as carrying a deliberately different (role-specific)
  form and are therefore NOT required to match the canonical text.
* ``extract_block(text, heading)`` -- pull a single ``## ``-delimited block out
  of an agent file's text (universal-newline form), returning the heading line
  through the last non-blank line before the next ``## `` heading, or ``None``
  if the heading is absent.
* ``read_agent_text(path)`` -- read an agent file with universal-newline
  translation so CRLF (the on-disk Windows working-tree form) and LF compare
  equal. (The repo uses ``core.autocrlf=true``: LF in the index, CRLF in the
  working tree.)
* ``block_matches(block_text, canonical, match)`` -- the equality / prefix test.
* ``classify_agents(block_id, agents_dir)`` -- partition the agent files for a
  given block into ``{"standard": [...], "variant": [...], "other": [...]}``.

Design notes
------------
* The ``operating-context`` block is special: 27 agents share a **byte-identical
  leading paragraph** (the canonical text below). 21 of them carry ONLY that
  paragraph; the other 6 (bug-replicator, diagnostic-researcher,
  editability-reviewer, interaction-reviewer, mini-qa, qa-replayer) append
  role-specific text after it. Both kinds are ``standard_agents`` for this block
  because they all begin with the canonical prefix; the matcher for this block
  is therefore PREFIX-based (``match == "prefix"``), and the sync tool rewrites
  only the prefix region while preserving any appended text. The other two
  blocks are matched with full equality (``"equals"``).
* The three VAO agents (adversarial-reviewer, interaction-observer,
  oracle-deriver) carry deliberately role-specific variant forms of the git and
  checkpoint blocks and OMIT the v1.0.0 operating-context heading entirely. They
  are the ``variant_agents`` for all three blocks and are never rewritten.

The ``standard_agents`` / ``variant_agents`` lists below are baked from an
inventory of the tree; ``classify_agents`` re-derives the partition at runtime so
drift surfaces in the sync tool and the drift-guard tests rather than going
unnoticed.
"""

from __future__ import annotations

import pathlib
from typing import Optional

# --- canonical block text (byte-faithful; may contain U+2014 EM DASH) --------

FORBIDDEN_GIT_OPERATIONS = "## Forbidden git operations\n\nYou MUST NOT run destructive git operations: `git stash` / `git stash pop`, `git reset --hard`, `git rebase`, `git commit --amend`, `git checkout <other-branch>` / `git checkout .`, `git clean -f`. These manipulate shared state across teammates within the same run and have caused real-world clobbering — the v1.6.0 worked example in `common-pipeline-conventions` `## Teammate git discipline` documents four teammates running concurrent `git stash` against one working tree, the reflog showing 10+ consecutive `reset: moving to HEAD` entries, and three of four teammates' work lost. For baseline verification, use the orchestrator-provided `$BASELINE_SHA` (carried in your spawn brief's `baseline_sha` field per `team-spawning-and-review-gates` `## Baseline SHA capture`) with `git diff $BASELINE_SHA -- <your-files>` instead of stashing."

CHECKPOINT_DISCIPLINE = '## Checkpoint discipline\n\nWhen your work is expected to exceed ~20 tool calls, write a checkpoint to `.architect-team/agent-checkpoints/<your-agent-id>.json` every ~10 calls (or after each logical step) per `common-pipeline-conventions` `## Agent checkpoint discipline`. On resume after a stream timeout, read your own checkpoint FIRST and skip already-completed steps. The checkpoint schema: `{agent_id, task_id, last_completed_step, files_touched, in_progress, ts}`. If you have no `Write` tool (an analysis-only agent), you cannot persist a checkpoint file — instead, return your checkpoint state (the same fields) in your final report so a resumed dispatch can recover.'

OPERATING_CONTEXT = '## Operating context (v1.0.0)\n\nPer `skills/team-spawning-and-review-gates/SKILL.md` `## Operating context (v1.0.0) — for teammate agents`, you are a long-lived teammate in an architect-team run — not a one-shot subagent; you stay in your role across multiple tasks within this run, you receive tasks from the Lead and write a solution requirement for any follow-up that needs a different agent type, and you do NOT spawn other agents or teams yourself.'

# The compact operating-principles block. This is the SINGLE CANONICAL SOURCE for
# CT6's load-bearing principles as they are injected into every agent AND into the
# five pipeline-driving skills: the agent sync tool inserts/refreshes it as a
# `## Operating principles` section, and scripts/setup/compile_skills.py imports
# this exact string to fill the `ct6:block:principles` fences in the skills. The
# full statements (each with its named anti-pattern) live in `docs/ETHOS.md`; this
# block is the compact, always-loaded reminder that points there.
PRINCIPLES = (
    "## Operating principles\n\n"
    "CT6 work is governed by seven load-bearing principles. The full statements — "
    "each with its named anti-pattern — live in `docs/ETHOS.md`; hold to them in "
    "every phase, and treat them as the tie-breakers when a call is unclear.\n\n"
    "- **Reuse before build.** Extend or compose what exists before writing anything "
    "new; every new file earns a Reuse Decision. Anti-pattern: the greenfield reflex.\n"
    "- **The producer is never its own checker.** Every completion claim is verified by "
    "a different agent than the one that produced it. Anti-pattern: self-attestation.\n"
    "- **Honest boundary.** Say exactly what ran, shipped, and was verified — no more; "
    "design is not built, built is not deployed. Anti-pattern: the overclaim.\n"
    "- **Unbounded solving.** Loop until the gate is green; never hand back a "
    "half-finished run on an iteration count. Anti-pattern: the arbitrary stop.\n"
    "- **Default to action.** Gates are opt-in; on reversible work, pick the sensible "
    "default and proceed. Anti-pattern: permission-seeking.\n"
    "- **Documentation currency.** Docs ship current or the run does not ship. "
    "Anti-pattern: the stale grid.\n"
    "- **Evidence before assertion.** State a result only after running the check and "
    "reading its output. Anti-pattern: the unverified \"should work\".\n\n"
    "See `docs/ETHOS.md` for the full text."
)

# --- block headings ----------------------------------------------------------

FORBIDDEN_GIT_OPERATIONS_HEADING = "## Forbidden git operations"
CHECKPOINT_DISCIPLINE_HEADING = "## Checkpoint discipline"
OPERATING_CONTEXT_HEADING = "## Operating context (v1.0.0)"
PRINCIPLES_HEADING = "## Operating principles"

# --- the three VAO agents (R4c, v3.10.0) -------------------------------------
# These three (adversarial-reviewer, interaction-observer, oracle-deriver) now
# carry the CANONICAL git + checkpoint blocks like every other agent — the
# v3.10.0 R4c re-sync eliminated their drifted paraphrases (oracle-deriver's
# variant had DROPPED the $BASELINE_SHA instruction). They remain variants for
# ONLY the operating-context block, whose `## Operating context (v1.0.0)`
# heading they deliberately OMIT (they are not Phase-2/3 teammates with the
# shared long-lived-teammate contract).
OPERATING_CONTEXT_VARIANT_AGENTS = [
    "adversarial-reviewer", "interaction-observer", "oracle-deriver",
]
# Backwards-compatible alias (older tests import VARIANT_AGENTS): the three
# operating-context variants are still the canonical "deliberately different"
# set, now scoped to operating-context only.
VARIANT_AGENTS = list(OPERATING_CONTEXT_VARIANT_AGENTS)

# Standard agents per block, baked from the current tree. classify_agents()
# re-derives these at runtime; these baked lists document the expected partition
# and let the drift-guard tests assert membership without globbing.
# R4c: the 3 VAO agents join the git + checkpoint standard sets (they get the
# canonical blocks); they stay OUT of the operating-context standard set.
STANDARD_AGENTS_FORBIDDEN_GIT = [
    "adversarial-reviewer", "interaction-observer", "oracle-deriver",
    "backend", "bug-classifier", "bug-replicator", "closeout-agent",
    "codebase-map-reviewer",
    "diagnostic-researcher", "doc-updater", "editability-reviewer",
    "fix-sensibility-checker", "flow-executor", "flow-explorer", "frontend",
    "domain-researcher", "endpoint-tracer",
    "integration", "integration-explorer", "interaction-intuiter",
    "interaction-reviewer", "master-synthesizer", "mcp-design-agent", "mini-qa",
    "monitor-synthesizer",
    "prompt-refiner", "qa-replayer", "reconciler", "reference-tracer",
    "route-mapper", "scaffold-agent", "structure-adversary", "structure-analyst",
    "system-architect", "task-reviewer", "test-completeness-verifier",
    "test-run-watcher", "visual-analyzer", "visual-capture",
]
STANDARD_AGENTS_CHECKPOINT = list(STANDARD_AGENTS_FORBIDDEN_GIT)
# Operating-context: every standard-git agent EXCEPT the 3 VAO agents (they omit
# the heading entirely).
STANDARD_AGENTS_OPERATING_CONTEXT = [
    a for a in STANDARD_AGENTS_FORBIDDEN_GIT
    if a not in OPERATING_CONTEXT_VARIANT_AGENTS
]
# Operating-principles: EVERY agent carries it — the principles are universal and
# do not vary by role (unlike operating-context, which the 3 VAO agents omit). The
# block is inserted after the checkpoint block (a universal anchor every agent has)
# and thereafter kept byte-identical to the canonical text like any equals block.
STANDARD_AGENTS_PRINCIPLES = list(STANDARD_AGENTS_FORBIDDEN_GIT)

# Match modes: "equals" -> full block must equal canonical; "prefix" -> block
# must START with canonical (extra role-specific text after it is allowed).
MATCH_EQUALS = "equals"
MATCH_PREFIX = "prefix"

BLOCKS = {
    "forbidden-git-operations": {
        "heading": FORBIDDEN_GIT_OPERATIONS_HEADING,
        "canonical": FORBIDDEN_GIT_OPERATIONS,
        "match": MATCH_EQUALS,
        "standard_agents": list(STANDARD_AGENTS_FORBIDDEN_GIT),
        "variant_agents": [],
    },
    "checkpoint-discipline": {
        "heading": CHECKPOINT_DISCIPLINE_HEADING,
        "canonical": CHECKPOINT_DISCIPLINE,
        "match": MATCH_EQUALS,
        "standard_agents": list(STANDARD_AGENTS_CHECKPOINT),
        "variant_agents": [],
    },
    "operating-context": {
        "heading": OPERATING_CONTEXT_HEADING,
        "canonical": OPERATING_CONTEXT,
        "match": MATCH_PREFIX,
        "standard_agents": list(STANDARD_AGENTS_OPERATING_CONTEXT),
        "variant_agents": list(OPERATING_CONTEXT_VARIANT_AGENTS),
    },
    # The principles block is unique among the boilerplate blocks in that it is
    # INSERTED where absent (after the checkpoint anchor) rather than only
    # replaced-in-place — every agent is a standard agent for it, so a fresh agent
    # gets the block automatically on the next sync. `insert_after_heading` names
    # the anchor block the sync tool places it after; once present it is a normal
    # equals block.
    "principles": {
        "heading": PRINCIPLES_HEADING,
        "canonical": PRINCIPLES,
        "match": MATCH_EQUALS,
        "standard_agents": list(STANDARD_AGENTS_PRINCIPLES),
        "variant_agents": [],
        "insert_after_heading": CHECKPOINT_DISCIPLINE_HEADING,
    },
}


def detect_newline(raw: bytes) -> str:
    """Return the dominant line-ending in ``raw`` (``"\\r\\n"`` or ``"\\n"``).

    Canonical home of the newline-preserving rewrite trio (v3.35.1 — formerly
    duplicated in sync_agent_boilerplate.py and set_default_model.py)."""
    crlf = raw.count(b"\r\n")
    bare_lf = raw.replace(b"\r\n", b"").count(b"\n")
    if crlf >= bare_lf and crlf > 0:
        return "\r\n"
    return "\n"


def read_preserving(path) -> tuple:
    """Read ``path`` -> (universal-newline LF text, newline style, trailing-newline)."""
    import pathlib as _pl

    raw = _pl.Path(path).read_bytes()
    newline = detect_newline(raw)
    text_lf = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    trailing = text_lf.endswith("\n")
    return text_lf, newline, trailing


def write_if_changed(path, new_text_lf: str, newline: str) -> bool:
    """Encode ``new_text_lf`` with ``newline`` and write only if the bytes differ."""
    import pathlib as _pl

    path = _pl.Path(path)
    if newline == "\n":
        encoded = new_text_lf.encode("utf-8")
    else:
        encoded = new_text_lf.replace("\n", newline).encode("utf-8")
    if path.read_bytes() == encoded:
        return False
    path.write_bytes(encoded)
    return True


def read_agent_text(path) -> str:
    """Read an agent markdown file with universal-newline translation.

    The repo uses ``core.autocrlf=true`` so the working tree carries CRLF while
    the index carries LF. Universal-newline mode normalises both to ``\n`` so the
    canonical text (stored with ``\n``) compares equal regardless of the on-disk
    line-ending form.
    """
    with open(path, "r", encoding="utf-8", newline=None) as fh:
        return fh.read()


def extract_block(text: str, heading: str) -> Optional[str]:
    """Extract a single ``## ``-delimited block from agent file text.

    Returns the heading line through the last non-blank line before the next
    ``## `` heading (trailing blank lines stripped), or ``None`` if ``heading`` is
    not present. ``text`` is expected in universal-newline (``\n``) form.
    """
    lines = text.split("\n")
    out = []
    started = False
    for line in lines:
        if not started:
            if line.rstrip() == heading:
                started = True
                out.append(line)
            continue
        if line.startswith("## ") and line.rstrip() != heading:
            break
        out.append(line)
    if not started:
        return None
    while out and out[-1].strip() == "":
        out.pop()
    return "\n".join(out)


def block_matches(block_text, canonical: str, match: str) -> bool:
    """True if ``block_text`` satisfies ``canonical`` under the given ``match`` mode."""
    if block_text is None:
        return False
    if match == MATCH_PREFIX:
        return block_text == canonical or block_text.startswith(canonical + "\n")
    return block_text == canonical


def classify_agents(block_id: str, agents_dir) -> dict:
    """Partition ``agents_dir/*.md`` for ``block_id`` into standard/variant/other.

    * ``standard`` -- files whose extracted block matches the canonical text
      (under the block's match mode) AND which are not allowlisted variants.
    * ``variant``  -- allowlisted variant agents that are present on disk.
    * ``other``    -- any agent that is neither (e.g. a new agent whose block does
      not match and is not allowlisted, or a standard agent that has drifted).

    Returns ``{"standard": [...], "variant": [...], "other": [...]}`` with each
    list sorted by agent stem.
    """
    spec = BLOCKS[block_id]
    heading = spec["heading"]
    canonical = spec["canonical"]
    match = spec["match"]
    variants = set(spec["variant_agents"])

    agents_dir = pathlib.Path(agents_dir)
    standard, variant, other = [], [], []
    for path in sorted(agents_dir.glob("*.md")):
        stem = path.stem
        block = extract_block(read_agent_text(path), heading)
        if stem in variants:
            variant.append(stem)
            continue
        if block_matches(block, canonical, match):
            standard.append(stem)
        else:
            other.append(stem)
    return {
        "standard": sorted(standard),
        "variant": sorted(variant),
        "other": sorted(other),
    }


__all__ = [
    "BLOCKS",
    "VARIANT_AGENTS",
    "FORBIDDEN_GIT_OPERATIONS",
    "CHECKPOINT_DISCIPLINE",
    "OPERATING_CONTEXT",
    "PRINCIPLES",
    "FORBIDDEN_GIT_OPERATIONS_HEADING",
    "CHECKPOINT_DISCIPLINE_HEADING",
    "OPERATING_CONTEXT_HEADING",
    "PRINCIPLES_HEADING",
    "MATCH_EQUALS",
    "MATCH_PREFIX",
    "read_agent_text",
    "detect_newline",
    "read_preserving",
    "write_if_changed",
    "extract_block",
    "block_matches",
    "classify_agents",
]
