# Tasks — claude-compliance-compaction

Harness ids in parentheses; both closed with evidence before this file was
committed.

- [x] C1 (#19) CLAUDE.md 54,293 → 17,345 bytes: engines re-run clean after
      (instruction-compliance 0 findings), 413 CLAUDE.md-reading tests green,
      orphan-fact sweep (10 phrases, each in 2–4 canonical docs), tail
      carried byte-identical by splice.
- [x] C2 (#20) tests-badge pin: red-first (the first run caught a LIVE drift,
      7655 vs 7656), badge fixed, mutation witness caught, restored green.
- [x] Release: bump 3.61.1 everywhere the version is pinned, map ledger
      notes, measure-as-last-act, artifact committed, gate exit 0, merge,
      publish, verify installed.
