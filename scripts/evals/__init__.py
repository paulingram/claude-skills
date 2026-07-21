# -*- coding: utf-8 -*-
"""Behavioral eval tier for the architect-team plugin (REQ-012, REQ-009).

Stdlib-only, ASCII-safe, NO import-time side effects. This package is the
machine behind the opt-in behavioral eval tier:

- ``runner``   - drives the ``claude`` CLI non-interactively, parses its
                 stream-json transcript into a structured record.
- ``judge``    - LLM-as-judge for outcome evals; the verdict itself is a
                 DETERMINISTIC Python threshold check, never a judge self-claim.
- ``collector``- writes per-run result JSON and compares consecutive runs.
- ``budget``   - a warn-first budget-regression gate over run-to-run deltas.

Nothing here runs at import time and nothing here reaches the network on
import; the live path is exercised only by the opt-in ``tests/evals`` tier
(gated on the ``CT6_EVALS=1`` environment flag) and by the orchestrator's
single integration smoke.
"""
