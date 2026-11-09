# -*- coding: utf-8 -*-
"""Test index + impact-based selector engine package.

The deterministic mechanism under the test-selection discipline
(`skills/common-pipeline-conventions/references/test-selection.md`): a per
workspace index of which test exercises which source files, endpoints and UI
elements, and a selector that turns a change set into the tests that must run
(plus the human pins, plus every test whose mapping is unknown). Stdlib-only,
no import-time side effects.

* ``engine``         -- build / select / stats / changed_files_from_git.
* ``cli``            -- the command-line surface over ``engine``.
* ``pytest_witness`` -- a small pytest plugin that records which repo files each
                        test actually executed (the runtime witness that
                        upgrades a static mapping to evidence).

Modules are also loadable by file path (the ``scripts/`` tier's house idiom),
so this ``__init__`` deliberately imports nothing.
"""
