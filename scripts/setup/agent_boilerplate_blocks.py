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

# --- block headings ----------------------------------------------------------

FORBIDDEN_GIT_OPERATIONS_HEADING = "## Forbidden git operations"
CHECKPOINT_DISCIPLINE_HEADING = "## Checkpoint discipline"
OPERATING_CONTEXT_HEADING = "## Operating context (v1.0.0)"

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
    "backend", "bug-classifier", "bug-replicator", "codebase-map-reviewer",
    "diagnostic-researcher", "doc-updater", "editability-reviewer",
    "fix-sensibility-checker", "flow-executor", "flow-explorer", "frontend",
    "domain-researcher", "endpoint-tracer",
    "integration", "integration-explorer", "interaction-intuiter",
    "interaction-reviewer", "master-synthesizer", "mini-qa", "monitor-synthesizer",
    "prompt-refiner", "qa-replayer", "reconciler", "route-mapper", "scaffold-agent",
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
}


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
    "FORBIDDEN_GIT_OPERATIONS_HEADING",
    "CHECKPOINT_DISCIPLINE_HEADING",
    "OPERATING_CONTEXT_HEADING",
    "MATCH_EQUALS",
    "MATCH_PREFIX",
    "read_agent_text",
    "extract_block",
    "block_matches",
    "classify_agents",
]
