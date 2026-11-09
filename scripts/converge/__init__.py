"""Converge-gate records (v4.1.0).

The deterministic half of the ``ct6-converge`` reviewer-convergence loop
(``workflows/ct6-converge.js`` is the orchestration half). ``record.py``
declares a convergence gate in the declared-gates registry before the loop
runs and records the loop's verdicts after it, satisfying the gate only when
the recorded verdicts say every reviewer returned ``ok``. The Stop-hook
``_audit_declared_gates`` arm then holds the run until that record exists.
Stdlib-only; no import-time side effects.
"""
