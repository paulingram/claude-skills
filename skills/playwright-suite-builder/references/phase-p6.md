# Phase P6 — Debug-flow registration

Sweep the resolved bug artifacts the workspace already carries —
`.architect-team/solution-requirements/`, the run history, `ux-tests/*/bugs/`,
and committed Phase B2 reproduction specs. For each resolved bug path:

1. Confirm a covering test exists in the suite. The B2 reproduction artifact IS
   the regression test; registration moves or references it, never rewrites it.
2. Register it as a manifest entry with `kind` `debug-flow`, `source` `bug-path`,
   and a live `origin_ref` naming the SR path or bug slug. A **null** `origin_ref`
   always blocks. A **path-shaped** one is dereferenced and a dead one blocks. A
   bare **slug** is recorded but its liveness is advisory-only — see P9's
   blocking-versus-advisory note. Prefer a repo path when you want the check to
   actually verify the reference.
3. Call the `intuition-map-lifecycle` `bug-path-upsert` verb so the map carries
   the path's elements with `source` `bug-path` and a `regression_refs[]` entry
   pointing back at this test. The manifest's `origin_ref` and the map's
   `regression_refs[]` are the two ends of one pointer.

A resolved bug with no registered debug-flow is a gap, and it is reported as one.
