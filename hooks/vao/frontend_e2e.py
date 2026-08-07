"""VAO frontend-E2E loop-exit family (1 tool) — v3.55.0.

``verify-frontend-e2e-loop-exit`` is the 22nd Layer-3 tool. It answers one
question a green "I tested the frontend" claim cannot answer about itself: *was
this actually a click-driven, as-the-user, live-environment Playwright flow — or
was it described, API-only, vacuous, or backed by a trace that is not there?*

The mandate (user, 2026-08-07): a frontend-impacting change is not done until a
real user clicked through it against a live environment. This tool is the
genuineness half; the run-level backstop that BLOCKS the commit is
``_audit_frontend_e2e`` in ``hooks/pipeline-completion-audit.py``.

It reads an E2E verdict artifact and returns ``{valid, gaps[]}``, biting on four
escape modes, each a distinct gap severity:

  * ``e2e-described-not-executed`` — ``executed_against_live_env`` is not True,
    OR no ``trace_path`` is recorded at all. A flow that was written up but never
    run proves nothing.
  * ``e2e-api-only-no-user-actions`` — no ``user_driven_actions`` entry is a
    genuine user interaction (``click`` / ``fill`` / ``getByRole(...).click`` /
    ``check`` / ``selectOption`` / ``press`` / ...). Every action is a
    ``page.request.*`` / ``fetch`` direct-API form (or the list is empty). Hitting
    the API is not being the user.
  * ``e2e-vacuous-navigate-assert`` — no assertion is on VISIBLE end-to-end state
    (``toBeVisible`` / ``toHaveText`` / ``toHaveURL`` / ...). The only assertions
    are a page title or a navigation — a navigate-and-assert-title that never
    looks at what the user would see.
  * ``e2e-trace-claimed-but-absent`` — ``trace_path`` is set but names a file that
    does not exist on disk. A claimed trace that is not there is not evidence.

Artifact contract (written by the frontend / integration agent when it runs
Playwright — the deliverable of ``skills/playwright-user-flows``)::

    {
      "schema_version": 1,
      "slice": "<slice-name>",
      "verdict": "passed" | "failed",
      "executed_against_live_env": bool,
      "live_url": "<url>",
      "user_driven_actions": [{"action": str, "selector": str}, ...],
      "trace_path": "<path to the captured Playwright trace>",
      "visible_state_assertions": [str, ...],
      "test_files": [str, ...]
    }

The verb is classified off the ``action`` field, never the ``selector`` URL — a
``page.request.post`` to ``/api/click-log`` must not read as a click. Deterministic,
stdlib-only; never runs a browser and never performs HTTP — the artifact is the
frontend agent's executed output. The only write is the verdict file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict


# A genuine user interaction — the Playwright methods a real user's click/fill/
# select maps to, plus the locator getters (getByRole/getByLabel/...) that only
# a user-facing element is addressed through. Word-anchored so a substring never
# leaks (`select_?option` matches selectOption/select_option; the `_?` absorbs
# the snake_case Python-Playwright form as well as the camelCase JS form).
_E2E_USER_ACTION_RE = re.compile(
    r"(?i)\b("
    r"click|dblclick|fill|type|press|check|uncheck|select_?option|"
    r"tap|hover|set_?input_?files|drag_?to|select_?text|focus|"
    r"get_?by_?role|get_?by_?label|get_?by_?text|get_?by_?placeholder|"
    r"get_?by_?test_?id|get_?by_?alt_?text|get_?by_?title"
    r")\b"
)

# The locator-getter subset — the only user signal trusted off a bare selector
# (when no `action` verb is named). A `type` off a CSS selector (`input[type=…]`)
# must never read as a user action, which is why the full verb set is applied to
# the `action` field only.
_E2E_USER_LOCATOR_RE = re.compile(
    r"(?i)\b(get_?by_?role|get_?by_?label|get_?by_?text|get_?by_?placeholder|"
    r"get_?by_?test_?id|get_?by_?alt_?text|get_?by_?title)\b"
)

# A direct-API call — hitting the endpoint, not driving the UI. `page.request.*`,
# a `request.post(...)`, a bare `fetch(`, an APIRequestContext, axios/XHR.
_E2E_API_ACTION_RE = re.compile(
    r"(?i)("
    r"page\.request\b|\brequest\s*\.\s*(get|post|put|patch|delete|head|fetch)\b|"
    r"\bfetch\s*\(|\bapi_?request_?context\b|\baxios\b|\bxml_?http_?request\b|"
    r"\bxhr\b|\.request\s*\("
    r")"
)

# An assertion on VISIBLE end-to-end state — what the user would actually see or
# where they would actually be. `to_?have_?url` (toHaveURL) counts: the
# navigation RESULT is user-visible state. `toHaveTitle` deliberately does NOT —
# a title assert is the vacuous navigate-and-assert-title tell.
_E2E_VISIBLE_STATE_RE = re.compile(
    r"(?i)\b(to_?be_?visible|to_?have_?text|to_?contain_?text|to_?have_?value|"
    r"to_?have_?values|to_?be_?checked|to_?be_?enabled|to_?be_?disabled|"
    r"to_?be_?hidden|to_?have_?class|to_?have_?count|to_?have_?attribute|"
    r"to_?have_?css|to_?be_?focused|to_?have_?screenshot|to_?have_?url|"
    r"to_?be_?editable|to_?be_?empty|to_?have_?id)\b"
)


def _e2e_action_text(entry: Any) -> tuple[str, str]:
    """(action, selector) as stripped strings. A bare string entry is its action."""
    if isinstance(entry, dict):
        return (str(entry.get("action") or "").strip(),
                str(entry.get("selector") or "").strip())
    return (str(entry or "").strip(), "")


def _e2e_is_user_driven_action(entry: Any) -> bool:
    """True iff this action is a genuine user interaction (not a direct-API call).

    The verb is read off the ``action`` field. Only when no ``action`` is named
    is the ``selector`` consulted — and then only for a locator getter, never a
    bare CSS ``type=`` — so a ``page.request.post`` to ``/api/click-log`` is never
    mistaken for a click.
    """
    action, selector = _e2e_action_text(entry)
    if _E2E_API_ACTION_RE.search(action):
        return False
    if _E2E_USER_ACTION_RE.search(action):
        return True
    if not action:
        if _E2E_API_ACTION_RE.search(selector):
            return False
        if _E2E_USER_LOCATOR_RE.search(selector):
            return True
    return False


def _e2e_is_visible_state_assertion(assertion: Any) -> bool:
    """True iff the assertion is on visible end-to-end state (not title/navigate)."""
    return bool(_E2E_VISIBLE_STATE_RE.search(str(assertion)))


def _e2e_resolve_trace(trace_path: Any, repo_root: Path | None) -> tuple[str, str]:
    """Resolve a claimed trace to (status, resolved).

    status is ``"none"`` (no path recorded), ``"present"`` (a real file exists),
    or ``"absent"`` (a path was claimed but no file exists). Tries the path as
    absolute, then relative to ``repo_root``, then relative to cwd — a genuine
    trace is accepted regardless of which root the agent recorded it against.
    """
    if not isinstance(trace_path, str) or not trace_path.strip():
        return "none", ""
    raw = trace_path.strip().replace("\\", "/")
    candidate = Path(raw)
    tried: list[Path] = []
    if candidate.is_absolute():
        tried.append(candidate)
    else:
        if repo_root is not None:
            tried.append(Path(repo_root) / raw)
        tried.append(candidate)
    for t in tried:
        try:
            if t.is_file():
                return "present", str(t)
        except OSError:
            continue
    return "absent", raw


_REMEDIATION = (
    "Run the flow as a real user with Playwright against the live dev "
    "environment: click/fill/select the actual controls (not page.request/fetch), "
    "assert on visible end-to-end state (toBeVisible/toHaveText/toHaveURL), and "
    "capture the trace. Write the passing verdict to "
    ".architect-team/frontend-e2e/<slice>-verdict.json — that executed artifact, "
    "not a description or a note, is what opens the loop-exit gate."
)


def verify_frontend_e2e_loop_exit(
    verification_artifact: dict[str, Any] | None = None,
    repo_root: Path | str | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v3.55.0 Layer-3 tool — verify a frontend E2E verdict is GENUINE.

    Args:
      verification_artifact: the E2E verdict artifact (see the module docstring
        for the contract). A non-dict is treated as empty (fails, never raises).
      repo_root: base for resolving a relative ``trace_path``; falls back to the
        artifact's own ``repo_root`` field.
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-frontend-e2e-loop-exit",
          "valid": bool,
          "gaps": [{"severity", "evidence", "remediation"}],
          "user_driven_action_count": int,
          "visible_state_assertion_count": int,
          "trace_status": "none" | "present" | "absent",
          "verdict_at": "<ISO 8601 UTC>"
        }

    Four severities, each a distinct escape mode: ``e2e-described-not-executed``,
    ``e2e-api-only-no-user-actions``, ``e2e-vacuous-navigate-assert``,
    ``e2e-trace-claimed-but-absent``. A genuine artifact returns ``valid: true``
    with zero gaps.
    """
    artifact = verification_artifact if isinstance(verification_artifact, dict) else {}
    base = repo_root if repo_root is not None else artifact.get("repo_root")
    root = Path(base) if isinstance(base, (str, Path)) and str(base).strip() else None

    executed = artifact.get("executed_against_live_env") is True
    trace_status, trace_resolved = _e2e_resolve_trace(artifact.get("trace_path"), root)

    actions = artifact.get("user_driven_actions")
    actions = actions if isinstance(actions, list) else []
    user_driven = [a for a in actions if _e2e_is_user_driven_action(a)]

    assertions = artifact.get("visible_state_assertions")
    assertions = assertions if isinstance(assertions, list) else []
    visible = [s for s in assertions if _e2e_is_visible_state_assertion(s)]

    gaps: list[dict[str, Any]] = []

    # 1 — described-not-executed: not run against a live env, or no trace at all.
    if not executed or trace_status == "none":
        reasons: list[str] = []
        if not executed:
            reasons.append("executed_against_live_env is not true")
        if trace_status == "none":
            reasons.append("no trace_path is recorded")
        gaps.append({
            "severity": "e2e-described-not-executed",
            "evidence": (
                "the E2E flow was described but not executed against a live "
                "environment: " + "; ".join(reasons) + ". A flow that was never "
                "run proves nothing."
            ),
            "remediation": _REMEDIATION,
        })

    # 4 — trace-claimed-but-absent: a path was recorded but the file is gone.
    if trace_status == "absent":
        gaps.append({
            "severity": "e2e-trace-claimed-but-absent",
            "evidence": (
                f"trace_path {artifact.get('trace_path')!r} is recorded but no "
                f"file exists there — a claimed trace that is not on disk is not "
                f"evidence the flow ran."
            ),
            "remediation": _REMEDIATION,
        })

    # 2 — api-only: no genuine user interaction among the actions.
    if not user_driven:
        gaps.append({
            "severity": "e2e-api-only-no-user-actions",
            "evidence": (
                f"none of the {len(actions)} recorded action(s) is a genuine "
                f"user interaction (click / fill / getByRole(...).click / check / "
                f"selectOption / press); they are direct-API (page.request / "
                f"fetch) or empty. Hitting the API is not being the user."
            ),
            "remediation": _REMEDIATION,
        })

    # 3 — vacuous: no assertion on visible end-to-end state.
    if not visible:
        gaps.append({
            "severity": "e2e-vacuous-navigate-assert",
            "evidence": (
                f"none of the {len(assertions)} recorded assertion(s) is on "
                f"visible end-to-end state (toBeVisible / toHaveText / toHaveURL); "
                f"a navigate-and-assert-title never looks at what the user sees."
            ),
            "remediation": _REMEDIATION,
        })

    verdict = {
        "tool": "verify-frontend-e2e-loop-exit",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "user_driven_action_count": len(user_driven),
        "visible_state_assertion_count": len(visible),
        "trace_status": trace_status,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
