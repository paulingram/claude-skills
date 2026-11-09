# -*- coding: utf-8 -*-
"""Publish adapters -- one module per hosting target.

* ``local_port``      -- a stdlib token-checking HTTP(S) server on this machine
                         (also the module the Cloud Run image copies as server.py).
* ``gcp_signed_url``  -- `gcloud storage cp` + a time-limited signed URL.
* ``gcp_cloud_run``   -- GENERATES a Dockerfile + deploy.sh; deploys nothing.
* ``nominated_host``  -- scp into a web root the user's own server already serves.

Every adapter exposes ``publish_page(...)`` and ``revoke_page(...)`` returning a
result dict (``{"ok": True, ...}`` or ``{"ok": False, "error", "remediation"}``);
the shell-out adapters route every subprocess through one injectable ``run``
seam. Modules are loaded by file path (the ``scripts/`` tier's house idiom), so
this ``__init__`` deliberately imports nothing.
"""
