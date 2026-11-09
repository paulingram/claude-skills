# -*- coding: utf-8 -*-
"""Codified project-principles engine package.

The deterministic mechanism under the `project-principles` skill's verbs
(`propose`, `confirm`, `add`, `retire`, `show`, `extract-candidates`, `check`,
`default-set`) over the two twins of a project's principle register: the
machine twin `<workspace>/.architect-team/principles.json` and the human twin
`<workspace>/docs/PROJECT_PRINCIPLES.md` rendered from it. Stdlib-only, no
import-time side effects.

* ``principles`` -- registry load / save / render, the verbs, the candidate
  extractor, and the verdict-sidecar check the Layer-3 tool
  ``verify-principles-respected`` (``hooks/vao/principles.py``) wraps.
* ``cli``        -- the command-line surface over ``principles``.

Modules are also loadable by file path (the ``scripts/`` tier's house idiom),
so this ``__init__`` deliberately imports nothing.
"""
