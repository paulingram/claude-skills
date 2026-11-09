# -*- coding: utf-8 -*-
"""Project homepage engine package.

The deterministic mechanism under the `project-homepage` skill: one
self-contained HTML page per project, built from the state files, maps, test
registries and timing log that already exist. Stdlib-only, no import-time
side effects.

* ``build``   -- collect every source (each with an explicit missing state),
                 render the page, record the build state, report staleness.
* ``timings`` -- stats + estimate over the timing log
                 (``.architect-team/run-history/timings.jsonl``).

Modules are also loadable by file path (the ``scripts/`` tier's house idiom),
so this ``__init__`` deliberately imports nothing.
"""
