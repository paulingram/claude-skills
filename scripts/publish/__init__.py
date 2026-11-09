# -*- coding: utf-8 -*-
"""Page-publishing engine package (the `page-publishing` skill's mechanism).

* ``publish``        -- the engine + CLI (publish / revoke / list / serve-status).
* ``setup_question`` -- ecosystem detection + the one setup question + the
                        config writer `architect-team-setup` calls.
* ``adapters/``      -- local-port, gcp-signed-url, gcp-cloud-run, nominated-host.

Stdlib-only, no import-time side effects. Modules are also loadable by file path
(the ``scripts/`` tier's house idiom), so this ``__init__`` deliberately imports
nothing.
"""
