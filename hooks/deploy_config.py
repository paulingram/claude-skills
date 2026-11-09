# -*- coding: utf-8 -*-
"""Per-project deploy config reader — the v3.44.0 dev->test->prod opt-in.

`.architect-team-deploy.json` at a project's root is a HUMAN-AUTHORED opt-in
(gitignored, local per checkout — the same pattern as `.architect-team-notify.json`;
the committed `.architect-team-deploy.example.json` is the schema template). Its
presence opts the project into the dev -> test-on-dev -> prod discipline:

  - `prod_deploy.enabled` gates the whole discipline.
  - `prod_deploy.always_merge_to_prod_on_complete` makes every clean run
    auto-merge to `prod_branch` on completion.
  - `prod_deploy.prod_branch` is the production branch (default `main`).
  - `prod_deploy.deploy_command` (null = "prod" is just the merge to prod_branch)
    is a shell command run AFTER dev is green for a real external deploy.
  - `tests.always_run` (test ids or fnmatch globs) and `tests.full_suite_at`
    (phases, default ["phase-8"]) are the HUMAN test-selection pins read by
    `scripts/test_index/` -- a project can say "always run the billing suite" or
    "run everything at Phase 5 too", and no agent may lower either.

IMMUTABILITY (enforced elsewhere — hooks/pretool_unilateral_override_guard.py):
this reader is READ-ONLY. The pipeline and every subagent may read the config but
may NEVER create, edit, disable, delete, or skip it on their own initiative; only
a human may change it. This module never writes.

Fail-safe by construction: an absent, unreadable, or malformed config resolves to
"prod deploy NOT enabled" — a deploy is never triggered by a broken config, and a
hook that imports this never crashes on bad JSON. Stdlib-only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEPLOY_CONFIG_FILENAME = ".architect-team-deploy.json"
DEFAULT_PROD_BRANCH = "main"

#: The phases whose FULL suite runs when the human config says nothing. Phase 8
#: (before the merge to main) is the one scheduled full-suite moment; the
#: selector treats it as full regardless of what a config lists.
DEFAULT_FULL_SUITE_AT: tuple = ("phase-8",)


def _config_path(project_root) -> Path:
    return Path(project_root) / DEPLOY_CONFIG_FILENAME


def load_deploy_config(project_root) -> Optional[Dict[str, Any]]:
    """Return the parsed config dict, or ``None`` when absent/unreadable/malformed.

    Never raises — a broken config is treated as "no opt-in" (the safe default)."""
    path = _config_path(project_root)
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _prod_deploy_block(project_root) -> Dict[str, Any]:
    """The `prod_deploy` sub-object, or an empty dict when absent/wrong-shape."""
    data = load_deploy_config(project_root)
    if not isinstance(data, dict):
        return {}
    block = data.get("prod_deploy")
    return block if isinstance(block, dict) else {}


def is_prod_deploy_enabled(project_root) -> bool:
    """True iff a well-formed config opts in via ``prod_deploy.enabled``."""
    return bool(_prod_deploy_block(project_root).get("enabled") is True)


def should_always_merge_to_prod_on_complete(project_root) -> bool:
    """True iff the project is prod-deploy-enabled AND has opted into an automatic
    merge to the prod branch on every clean completion. A disabled config is never
    "always merge", regardless of the sub-flag."""
    block = _prod_deploy_block(project_root)
    if block.get("enabled") is not True:
        return False
    return bool(block.get("always_merge_to_prod_on_complete") is True)


def prod_branch(project_root, default: str = DEFAULT_PROD_BRANCH) -> str:
    """The production branch name (``prod_deploy.prod_branch``), or ``default``."""
    value = _prod_deploy_block(project_root).get("prod_branch")
    return value if isinstance(value, str) and value.strip() else default


def deploy_command(project_root) -> Optional[str]:
    """The external deploy shell command (``prod_deploy.deploy_command``), or
    ``None`` when unset — in which case "prod" is just the merge to prod_branch."""
    value = _prod_deploy_block(project_root).get("deploy_command")
    return value if isinstance(value, str) and value.strip() else None


def _tests_block(project_root) -> Dict[str, Any]:
    """The `tests` sub-object, or an empty dict when absent/wrong-shape."""
    data = load_deploy_config(project_root)
    if not isinstance(data, dict):
        return {}
    block = data.get("tests")
    return block if isinstance(block, dict) else {}


def _string_list(value: Any) -> Optional[List[str]]:
    """``value`` as a list of non-blank strings, or ``None`` when it is not a
    list (a malformed pin resolves to the default, never to a crash)."""
    if not isinstance(value, list):
        return None
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def tests_always_run(project_root) -> List[str]:
    """The human-owned ``tests.always_run`` pins: test ids or fnmatch globs
    matched by the selector against each test's id and file. Default ``[]``.
    An agent may read these; it may never remove or narrow one."""
    return _string_list(_tests_block(project_root).get("always_run")) or []


def tests_full_suite_at(project_root) -> List[str]:
    """The phases at which the FULL suite runs (``tests.full_suite_at``),
    default ``["phase-8"]``. The value is returned as the human wrote it; the
    selector additionally treats Phase 8 as a full-suite phase whatever the
    list says, so the Phase 8 full run is never selectable away."""
    value = _string_list(_tests_block(project_root).get("full_suite_at"))
    return list(DEFAULT_FULL_SUITE_AT) if value is None else value


def prod_deploy_disabled_by_flag(env: Optional[Dict[str, str]] = None) -> bool:
    """A human per-run opt-out: the ``CT6_NO_PROD`` env var (the programmatic form
    of ``--no-prod`` / "don't touch prod"). Only a human sets this; it never
    originates from an agent's own initiative."""
    env = os.environ if env is None else env
    return str(env.get("CT6_NO_PROD", "")).strip().lower() in {"1", "true", "yes", "on"}
