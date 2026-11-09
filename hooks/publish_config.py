# -*- coding: utf-8 -*-
"""Per-project page-publishing config reader -- the private-URL publishing opt-in.

Two human-authored files feed one merged view:

  * USER level   ``~/.architect-team/publish.json`` -- shared across every project
    on this machine (a ``base_url`` the user owns, adapter defaults, GCP project).
  * PROJECT level ``<project>/.architect-team-publish.json`` -- gitignored, local
    per checkout (the same pattern as ``.architect-team-deploy.json`` and
    ``.architect-team-notify.json``; the committed
    ``.architect-team-publish.example.json`` is the schema template).

The project file wins over the user file, which wins over the built-in defaults.
The merged schema (``architect-team-publish/v1``)::

    {"schema": "architect-team-publish/v1",
     "mode": "claude" | "private-url",
     "adapter": "local-port" | "gcp-signed-url" | "gcp-cloud-run" | "nominated-host",
     "project_slug": "<repo name>",
     "token_ttl_hours": 72,
     "bind": {"host": "0.0.0.0", "port": 8787, "external_ip": null,
              "tls_cert": null, "tls_key": null},
     "gcp": {"project": null, "bucket": null, "service": null, "region": null},
     "nominated_host": {"ssh": null, "web_root": null, "public_base_url": null},
     "base_url": null}

IMMUTABILITY (enforced elsewhere -- hooks/pretool_unilateral_override_guard.py):
this reader is READ-ONLY. The pipeline and every subagent may read the config but
may NEVER create, edit, disable, delete, or skip it on their own initiative; only
a human may change it (the setup question in ``scripts/publish/setup_question.py``
writes it ONCE, with the human's recorded answer). This module never writes.

Fail-safe by construction: an absent, unreadable, or malformed config resolves to
``mode == "claude"`` -- the Artifact-tool default -- so a broken config can never
open a port, upload a file, or mint a URL. An unknown ``mode`` or ``adapter``
value is treated as absent. Stdlib-only.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

PUBLISH_CONFIG_FILENAME = ".architect-team-publish.json"
PUBLISH_EXAMPLE_FILENAME = ".architect-team-publish.example.json"
USER_CONFIG_RELPATH = Path(".architect-team") / "publish.json"

SCHEMA = "architect-team-publish/v1"
MODES = ("claude", "private-url")
ADAPTERS = ("local-port", "gcp-signed-url", "gcp-cloud-run", "nominated-host")
DEFAULT_MODE = "claude"
DEFAULT_ADAPTER = "local-port"
DEFAULT_TOKEN_TTL_HOURS = 72
DEFAULT_BIND_HOST = "0.0.0.0"
DEFAULT_BIND_PORT = 8787

DEFAULTS: Dict[str, Any] = {
    "schema": SCHEMA,
    "mode": DEFAULT_MODE,
    "adapter": DEFAULT_ADAPTER,
    "project_slug": None,
    "token_ttl_hours": DEFAULT_TOKEN_TTL_HOURS,
    "bind": {
        "host": DEFAULT_BIND_HOST,
        "port": DEFAULT_BIND_PORT,
        "external_ip": None,
        "tls_cert": None,
        "tls_key": None,
    },
    "gcp": {"project": None, "bucket": None, "service": None, "region": None},
    "nominated_host": {"ssh": None, "web_root": None, "public_base_url": None},
    "base_url": None,
}

# The nested blocks that merge key-by-key (a project file that sets only
# ``bind.port`` keeps the user file's ``bind.external_ip``).
_NESTED_BLOCKS = ("bind", "gcp", "nominated_host")

_SLUG_BAD = re.compile(r"[^a-z0-9-]+")


def project_config_path(project_root) -> Path:
    return Path(project_root) / PUBLISH_CONFIG_FILENAME


def user_config_path(home=None) -> Path:
    base = Path(home) if home is not None else Path.home()
    return base / USER_CONFIG_RELPATH


def _read_json_object(path: Path) -> Optional[Dict[str, Any]]:
    """The parsed object at ``path``, or ``None`` when absent/unreadable/malformed.
    Never raises."""
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _merge(base: Dict[str, Any], overlay: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Overlay ``overlay`` onto ``base``: top-level keys replace, the known nested
    blocks merge key-by-key, and a ``null`` in the overlay means "not stated
    here" (it never clobbers a value the lower layer set -- so the committed
    template, full of nulls, copies safely over a user-level file). Unknown
    top-level keys are carried through."""
    out = copy.deepcopy(base)
    if not isinstance(overlay, dict):
        return out
    for key, value in overlay.items():
        if key == "_comment":
            continue
        if key in _NESTED_BLOCKS and isinstance(value, dict):
            block = dict(out.get(key) or {})
            for sub_key, sub_value in value.items():
                if sub_value is None and block.get(sub_key) is not None:
                    continue
                block[sub_key] = sub_value
            out[key] = block
        elif value is None and out.get(key) is not None:
            continue
        else:
            out[key] = value
    return out


def slugify(value: Any) -> Optional[str]:
    """Lower-case ``value`` and collapse everything outside ``[a-z0-9-]`` to a
    hyphen; ``None`` when nothing survives."""
    if not isinstance(value, str):
        return None
    slug = _SLUG_BAD.sub("-", value.strip().lower()).strip("-")
    return slug or None


def _normalize(merged: Dict[str, Any], project_root) -> Dict[str, Any]:
    """Coerce the merged view to the schema: unknown enum values fall back to
    the defaults, the TTL is a positive int, and the slug defaults to the repo
    directory name."""
    out = dict(merged)
    out["schema"] = SCHEMA
    if out.get("mode") not in MODES:
        out["mode"] = DEFAULT_MODE
    if out.get("adapter") not in ADAPTERS:
        out["adapter"] = DEFAULT_ADAPTER
    ttl = out.get("token_ttl_hours")
    if isinstance(ttl, bool) or not isinstance(ttl, (int, float)) or ttl <= 0:
        out["token_ttl_hours"] = DEFAULT_TOKEN_TTL_HOURS
    else:
        out["token_ttl_hours"] = int(ttl)
    slug = slugify(out.get("project_slug"))
    if slug is None:
        try:
            slug = slugify(Path(project_root).resolve().name)
        except (OSError, RuntimeError):
            slug = None
    out["project_slug"] = slug or "project"
    for block in _NESTED_BLOCKS:
        if not isinstance(out.get(block), dict):
            out[block] = copy.deepcopy(DEFAULTS[block])
    bind = out["bind"]
    port = bind.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not (0 <= port <= 65535):
        bind["port"] = DEFAULT_BIND_PORT
    host = bind.get("host")
    if not isinstance(host, str) or not host.strip():
        bind["host"] = DEFAULT_BIND_HOST
    base = out.get("base_url")
    if not isinstance(base, str) or not base.strip():
        out["base_url"] = None
    else:
        out["base_url"] = base.strip().rstrip("/")
    return out


def publish_config_sources(project_root, home=None) -> Dict[str, Optional[str]]:
    """Which config files exist: ``{"user": path|None, "project": path|None}``."""
    user = user_config_path(home)
    project = project_config_path(project_root)
    return {
        "user": str(user) if user.is_file() else None,
        "project": str(project) if project.is_file() else None,
    }


def load_publish_config(project_root, home=None) -> Dict[str, Any]:
    """The merged, normalized config: defaults <- user-level <- project-level.

    Always returns a full schema-shaped dict (the defaults when neither file
    exists). Never raises -- a malformed file is treated as absent."""
    merged = _merge(DEFAULTS, _read_json_object(user_config_path(home)))
    merged = _merge(merged, _read_json_object(project_config_path(project_root)))
    return _normalize(merged, project_root)


def normalize_config(config: Optional[Dict[str, Any]], project_root=".") -> Dict[str, Any]:
    """Coerce an already-loaded (possibly partial) config dict to the full
    schema shape -- the same defaults + fallbacks ``load_publish_config``
    applies. Never raises; a non-dict yields the defaults."""
    overlay = config if isinstance(config, dict) else None
    return _normalize(_merge(DEFAULTS, overlay), project_root)


def _config(source: Union[Dict[str, Any], str, Path], home=None) -> Dict[str, Any]:
    """Accept either a pre-loaded config dict or a project root."""
    if isinstance(source, dict):
        return normalize_config(source, source.get("_project_root") or ".")
    return load_publish_config(source, home=home)


def mode(source, home=None) -> str:
    """``"claude"`` (default) or ``"private-url"``."""
    return _config(source, home)["mode"]


def adapter(source, home=None) -> str:
    """The private-URL adapter name (defaults to ``local-port``)."""
    return _config(source, home)["adapter"]


def project_slug(source, home=None) -> str:
    """The URL slug for this project (defaults to the repo directory name)."""
    return _config(source, home)["project_slug"]


def is_private_url(source, home=None) -> bool:
    """True iff a well-formed config opts into private-URL publishing."""
    return mode(source, home) == "private-url"


def token_ttl_hours(source, home=None) -> int:
    return _config(source, home)["token_ttl_hours"]


def base_url(source, home=None) -> Optional[str]:
    """The user-stated public base URL (no trailing slash), or ``None`` -- the
    adapter derives one when it is absent."""
    return _config(source, home)["base_url"]
