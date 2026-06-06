#!/usr/bin/env python3
"""Single source of truth for the plugin's cross-component rule constants.

Several rules are restated in multiple places — the canonical PROSE home for
each lives in ``skills/common-pipeline-conventions/SKILL.md`` (and the
per-pipeline / per-agent restatements that reference it). The corresponding
machine-readable CODE constants used to be duplicated across the hooks
(``hooks/vao_tools.py``, ``hooks/pipeline-completion-audit.py``). This module
is the single CODE source of truth so those literals cannot drift.

Prose homes (canonical):
  - FORBIDDEN_GIT_OPERATIONS — ``common-pipeline-conventions`` ``## Teammate git
    discipline`` (v1.6.0): the six destructive teammate-git operations.
  - TEST_FAILURE_ORIGINS — ``architect-team-pipeline`` Phase 3b: SR origin kinds
    that route through ``diagnostic-research-team`` and so must carry a
    diagnostic plan.
  - PARITY_VERBS — ``common-pipeline-conventions`` ``## Scope discipline``
    (v1.4.0): the six parity-implying verbs (visual + structural + behavioral
    parity).
  - ACTION_KIND_VALUES — ``interactive-mockup-discovery`` (v2.1.0): the closed
    7-value ``action_kind`` vocabulary for an oracle-spec ``interactions[]``
    entry.

This module is stdlib-only and has NO import side effects: no file I/O, no
network, no prints at import time. Importing it must be free.
"""
from __future__ import annotations

import re

# ===========================================================================
# Forbidden teammate-git operations (v1.6.0 discipline)
# ===========================================================================
#
# The six forbidden teammate-git operations from v1.6.0's discipline. Each
# pattern matches the destructive shape WITHOUT firing on legitimate
# read/inspect operations (`git status`, `git log`, `git diff`, etc).
#
# Moved here VERBATIM from hooks/vao_tools.py (previously its module-level
# ``_FORBIDDEN_GIT_PATTERNS``) so the data is byte-identical and the single
# source of truth. ``hooks/vao_tools.py`` now imports it from here.
FORBIDDEN_GIT_OPERATIONS: tuple[tuple[str, re.Pattern], ...] = (
    ("git stash", re.compile(r"\bgit\s+stash\b(?!\s+list)", re.IGNORECASE)),
    ("git reset --hard", re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE)),
    ("git rebase", re.compile(r"\bgit\s+rebase\b", re.IGNORECASE)),
    ("git commit --amend", re.compile(r"\bgit\s+commit\s+.*--amend\b", re.IGNORECASE)),
    ("git checkout other-branch", re.compile(r"\bgit\s+checkout\s+(?!--|HEAD)(?:-[bB]\s+)?[\w./-]+\b", re.IGNORECASE)),
    ("git clean -f", re.compile(r"\bgit\s+clean\s+(?:.*-f|\.\s)", re.IGNORECASE)),
)

# Backward-compatible alias — vao_tools.py historically referenced the value as
# ``_FORBIDDEN_GIT_PATTERNS``; keeping the alias here lets that file import the
# canonical value under its existing local name with no downstream change.
_FORBIDDEN_GIT_PATTERNS = FORBIDDEN_GIT_OPERATIONS


# ===========================================================================
# Test-failure SR origins (architect-team-pipeline Phase 3b)
# ===========================================================================
#
# Origins whose SRs route through diagnostic-research-team — they MUST carry a
# diagnostic plan once processed. Mirrors architect-team-pipeline Phase 3b.
#
# Moved here VERBATIM from hooks/pipeline-completion-audit.py (previously its
# module-level ``TEST_FAILURE_ORIGINS``) so the set is the single source of
# truth. ``hooks/pipeline-completion-audit.py`` now imports it from here.
TEST_FAILURE_ORIGINS = {
    "rca-product-bug",
    "playwright-failure",
    "integration-failure",
    "integration-testing-failure",
    "test-completeness-failure",
    "visual-fidelity-cascade",
}


# ===========================================================================
# Parity-implying verbs (v1.4.0 Scope discipline)
# ===========================================================================
#
# The six parity-implying verbs. Each implies visual + structural + behavioral
# parity — NOT data-only, NOT a partial fragment. Restated (prose) in
# agents/prompt-refiner.md, agents/bug-classifier.md, agents/system-architect.md,
# and agents/oracle-deriver.md; canonical prose home is
# common-pipeline-conventions ## Scope discipline.
PARITY_VERBS: tuple[str, ...] = (
    "match",
    "rebuild",
    "mirror",
    "parity",
    "make like",
    "replicate",
)


# ===========================================================================
# action_kind vocabulary (v2.1.0 Interactive-Mockup Discovery)
# ===========================================================================
#
# The closed 7-value ``action_kind`` vocabulary for an oracle-spec
# ``interactions[]`` entry. Canonical prose home: the interactive-mockup-discovery
# skill (and verified-agent-output / interaction-observer / interaction-intuiter).
ACTION_KIND_VALUES: tuple[str, ...] = (
    "navigate",
    "open-drawer",
    "open-modal",
    "submit",
    "input-text",
    "reveal",
    "no-op",
)
