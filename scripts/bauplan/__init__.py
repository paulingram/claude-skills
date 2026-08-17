# -*- coding: utf-8 -*-
"""Bauplan conditional-capability support for the architect-team plugin.

Stdlib-only, ASCII-safe, NO import-time side effects. Bauplan is CT6's first
CONDITIONAL dependency - valuable on a Bauplan project, pure cost everywhere
else - so the decision of whether a run may reach a bauplan skill has to be
made explicitly rather than assumed.

- ``arming`` - the pure arming decision: given the detected project trait and
               the stated intent, is the capability armed, and does the run
               owe the user exactly one confirmation first?

Trait DETECTION itself lives with the other house trait-detectors in
``hooks/discipline_registry.py`` (``_has_bauplan_markers``), which already owns
the recursive workspace walk, the skip list, and the evidence contract.
"""
