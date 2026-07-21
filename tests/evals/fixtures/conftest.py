# -*- coding: utf-8 -*-
"""Keep the eval FIXTURE data out of pytest collection.

`planted/test_calc.py` is fixture data - a masking test the LIVE outcome eval
runs inside a sandbox copy, NOT a test of this repo. Its `from calc import
total` only resolves with the sandbox on `sys.path`, so collecting it here would
error. `transcripts/` holds captured NDJSON, no Python. Excluding both subtrees
lets the fixtures be naturally named without polluting collection. (This
conftest is only loaded when the eval tier is collected, i.e. under CT6_EVALS=1;
the default run never descends here.)
"""
collect_ignore = ["planted", "transcripts"]
