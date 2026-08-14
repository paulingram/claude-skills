# Tasks — optimize-forcing-gates

Harness task ids in parentheses; every box below was closed red-first with a
mutation witness before this file was committed (witness transcripts summarised
in design.md).

- [x] O1 (#15) release-backing arm: 10 tests both-directions, 6/6 witnesses
      caught (wiring, authoring-window, bump condition, convention check,
      block, kill-switch), wired into `audit()` and pinned in source.
- [x] O2 (#16) task-deletion arm: 13 tests both-directions, 6/6 witnesses
      caught (arm, status filter, marker, staleness, kill-switch,
      fall-through). One real regression produced and caught while building:
      the first cut early-returned for every TaskUpdate and silently un-gated
      it from the arm-1 mandate check — caught by the PRE-EXISTING arm-1 pin,
      fixed additive, then pinned from the new file's side too.
- [x] O3 (#17) measurements-dir immutability: 6 tests both-directions, 3/3
      witnesses caught (matcher, arm, parent-pair).
- [x] O4 (#18) mixed-clock sweep: class count repo-wide is ONE (the instance
      already fixed at v3.60.0). Both candidate files inspected and cleared.
- [x] Blast radius: 475 tests across the nine touched/adjacent files, green.
- [x] Release: bump 3.61.0, docs, measure-as-last-act, artifact committed,
      `--require-measurements` exit 0, merge, publish, verify installed.
