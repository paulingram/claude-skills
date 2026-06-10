"""VAO deploy-mandate + baseline-clean family (2 tools).

The no-pipeline-bypass tool (the 3rd of this discipline family) lives in
``deploy_pipeline_b.py`` so each module stays <= 900 lines (R2 ceiling,
design.md Decision 1a). The facade imports from both.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # package shape: repo root on sys.path
    from hooks.vao.core import _utc_now_iso, _write_verdict
except ImportError:  # hooks/ on sys.path (vao is the package)
    try:
        from vao.core import _utc_now_iso, _write_verdict
    except ImportError:  # hooks/vao/ on sys.path (bare sibling)
        from core import _utc_now_iso, _write_verdict

try:  # package shape: repo root on sys.path
    from hooks.shared_rule_constants import (
        FORBIDDEN_GIT_OPERATIONS as _FORBIDDEN_GIT_PATTERNS,
    )
except ImportError:  # bare-module shape: hooks/ dir on sys.path
    from shared_rule_constants import (
        FORBIDDEN_GIT_OPERATIONS as _FORBIDDEN_GIT_PATTERNS,
    )


# The list itself now lives in ``hooks/shared_rule_constants.py`` (the single
# code source of truth) and is imported at module top as
# ``_FORBIDDEN_GIT_PATTERNS`` — the local name and downstream use are unchanged.


def verify_baseline_clean(
    tool_call_log: list[dict[str, Any]] | None = None,
    baseline_sha: str | None = None,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """Audit a teammate's tool-call log for forbidden git operations.

    Args:
      tool_call_log: a list of ledger entries; each entry should have
        ``tool``, ``args`` (with ``command`` for Bash entries), and ``ts``.
      baseline_sha: optional baseline SHA (for the verdict record; not
        used in the audit logic itself).
      out_path: optional path to write the verdict JSON.

    Returns::

        {
          "tool": "verify-baseline-clean",
          "clean": bool,
          "violations": [{"op": ..., "args": ..., "line": ..., "ts": ...}],
          "baseline_sha": str | None,
          "verdict_at": "<ISO 8601 UTC>"
        }
    """
    tool_call_log = tool_call_log or []
    violations: list[dict[str, Any]] = []
    for idx, entry in enumerate(tool_call_log):
        if entry.get("tool") != "Bash":
            continue
        args = entry.get("args", {})
        cmd = args.get("command") if isinstance(args, dict) else None
        if not isinstance(cmd, str):
            continue
        for op_name, pattern in _FORBIDDEN_GIT_PATTERNS:
            if pattern.search(cmd):
                violations.append({
                    "op": op_name,
                    "args": cmd,
                    "line": idx,
                    "ts": entry.get("ts"),
                })
                break  # one forbidden op per entry — first match wins
    verdict = {
        "tool": "verify-baseline-clean",
        "clean": len(violations) == 0,
        "violations": violations,
        "baseline_sha": baseline_sha,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


_DEPLOY_MANDATE_VERBS = (
    "deploy",
    "launch",
    "ship",
    "publish",
    "go live",
    "going live",
    "push to prod",
    "push to dev",
    "push to production",
    "roll out",
    "rolling out",
    "release to",
    "host the",
    "host it",
    "serve from",
)


_DEPLOY_COMPLETENESS_MODIFIERS = (
    "fully",
    "100%",
    "100 percent",
    "all elements",
    "real and functional",
    "no mock",
    "no fake",
    "no mocks",
    "live data",
    "log into",
    "login",
    "hosted url",
    "deployed url",
    "anything less is failure",
    "must have",
    "1 criteria",
    "one criteria",
    "end to end",
    "end-to-end",
    "the application",
    "the product",
    "every screen",
    "every page",
    "every element",
)


_PLAN_ONLY_DELIVERABLE_MARKERS = (
    "plan ✅ delivered",
    "plan delivered",
    "plan is delivered",
    "plan_action.md",
    "_plan.md",
    "as markdown",
    "as a markdown",
    "blueprint",
    "roadmap",
    "plan is a document",
    "comprehensive plan of action",
    "produce a plan",
)


_ADJACENT_DEPENDENCY_MARKERS = (
    "auth fix",
    "fixed uam",
    "demo agents",
    "demo seed",
    "dependency live",
    "dependencies ✅ live",
    "building blocks",
    "existing platforms, not your app",
    "existing platforms not your app",
    "all on your existing platforms",
    "key dependencies",
    "supporting service",
    "attachment support",
    "demo data",
)


_PARTIAL_DEPLOY_MARKERS = (
    "thin slice",
    "thin-slice",
    "quick win",
    "phase 1 live",
    "couple of screens",
    "a few screens",
    "start with just",
    "subset deployed",
    "partial deploy",
    "mvp first",
    "smallest possible vertical slice",
)


_LOCAL_DEPLOY_URL_MARKERS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "file://",
    "::1",
    "host.docker.internal",
)


def detect_deploy_mandate_in_prompt(prompt: str) -> dict[str, Any]:
    """Classify a user prompt as carrying a deploy mandate or not.

    Returns:
        {
          "active": bool,
          "target_kind": "fullstack" | "api-only" | "spa-only" | "thin-slice" | None,
          "user_prompt_excerpt": str,    # the matched verb + modifier substring (truncated)
          "matched_verbs": list[str],
          "matched_modifiers": list[str],
        }

    A prompt activates the deploy mandate when it contains at least one deploy
    verb AND at least one completeness modifier. An explicit "thin slice"
    request narrows target_kind without disabling the mandate.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        return {
            "active": False,
            "target_kind": None,
            "user_prompt_excerpt": "",
            "matched_verbs": [],
            "matched_modifiers": [],
        }
    lower = prompt.lower()
    matched_verbs = [v for v in _DEPLOY_MANDATE_VERBS if v in lower]
    matched_modifiers = [m for m in _DEPLOY_COMPLETENESS_MODIFIERS if m in lower]
    # Thin-slice phrasing is its own activation channel — the user explicitly
    # scopes the deploy mandate to a subset, but it IS still a mandate.
    has_thin_slice = any(p in lower for p in ("thin slice", "thin-slice"))
    active = bool(matched_verbs) and (bool(matched_modifiers) or has_thin_slice)

    if not active:
        return {
            "active": False,
            "target_kind": None,
            "user_prompt_excerpt": "",
            "matched_verbs": matched_verbs,
            "matched_modifiers": matched_modifiers,
        }

    # Refine target_kind from prompt content
    if any(p in lower for p in ("thin slice", "thin-slice", "mvp first", "smallest possible")):
        target_kind: str | None = "thin-slice"
    elif "api only" in lower or "api-only" in lower or "backend only" in lower:
        target_kind = "api-only"
    elif "frontend only" in lower or "spa only" in lower or "ui only" in lower:
        target_kind = "spa-only"
    else:
        target_kind = "fullstack"

    return {
        "active": True,
        "target_kind": target_kind,
        "user_prompt_excerpt": (
            (matched_verbs[0] + " ... " + matched_modifiers[0])
            if matched_verbs and matched_modifiers
            else ""
        ),
        "matched_verbs": matched_verbs,
        "matched_modifiers": matched_modifiers,
    }


def _is_localhost_or_file(url: Any) -> bool:
    if not isinstance(url, str) or not url:
        return True  # empty / non-string is NOT a real deploy
    lower = url.lower()
    return any(m in lower for m in _LOCAL_DEPLOY_URL_MARKERS)


def _detect_plan_only_deliverable(final_report: str) -> list[dict[str, Any]]:
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _PLAN_ONLY_DELIVERABLE_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "plan-only-deliverable-on-deploy-mandate",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites plan-only deliverable marker(s) "
            f"{hits[:3]!r} when the deploy mandate is active. A markdown plan "
            f"is not a deployment."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. The user mandated a deploy "
            "(verb + completeness modifier matched at intake). A markdown "
            "plan does NOT satisfy the mandate. Build the actual product "
            "backend + wire the frontend + deploy both at real URLs + "
            "verify login + assert live data on every screen. Re-run Phase "
            "8 once all 5 binding criteria are met."
        ),
    }]


def _detect_adjacent_dependencies_claimed(final_report: str) -> list[dict[str, Any]]:
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _ADJACENT_DEPENDENCY_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "adjacent-dependencies-claimed-as-deployment",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites adjacent-dependency marker(s) {hits[:3]!r} "
            f"as the deliverable when the deploy mandate is active. Work on "
            f"dependent services (auth fix / demo seeds / attachment support) "
            f"is not the deployment."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. Adjacent dependency work "
            "(auth fix / dependency live / building blocks / existing "
            "platforms) does NOT satisfy a deploy mandate. The product "
            "itself must be deployed at a real URL with the frontend wired "
            "to a real backend. Cite the product's deploy URL — not the "
            "dependency URL — in the final report."
        ),
    }]


def _detect_partial_deploy_passed_off(final_report: str, target_kind: str | None) -> list[dict[str, Any]]:
    if target_kind == "thin-slice":
        return []  # user explicitly authorized the thin slice — no severity
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    hits = [m for m in _PARTIAL_DEPLOY_MARKERS if m in lower]
    if not hits:
        return []
    return [{
        "severity": "partial-deploy-passed-off-as-deploy",
        "matched_markers": hits[:5],
        "evidence": (
            f"final_report cites partial-deploy framing {hits[:3]!r} when the "
            f"deploy mandate target_kind is {target_kind!r}, not 'thin-slice'. "
            f"Partial deploys satisfy the mandate only when the user "
            f"explicitly asks for one."
        ),
        "remediation": (
            "v2.20.0 deploy mandate discipline. A thin slice is not a full "
            "deploy. Either (a) extend the implementation to cover every "
            "screen + every endpoint, OR (b) confirm with the user that the "
            "thin-slice target_kind is acceptable (re-classify the mandate "
            "to target_kind='thin-slice') BEFORE marking the run complete."
        ),
    }]


def _detect_missing_binding_criteria(
    verification_artifact: dict[str, Any],
    target_kind: str | None,
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []

    deploy_target_url = verification_artifact.get("deploy_target_url")
    frontend_url = verification_artifact.get("frontend_url")
    login_verified = verification_artifact.get("login_verified")
    login_evidence = verification_artifact.get("login_verification_evidence_path")
    live_data_assertions = verification_artifact.get("live_data_assertions") or []
    mock_residue_count = verification_artifact.get("mock_residue_count")
    unwired_elements_count = verification_artifact.get("unwired_elements_count")

    require_backend = target_kind in (None, "fullstack", "api-only", "thin-slice")
    require_frontend = target_kind in (None, "fullstack", "spa-only", "thin-slice")

    if require_backend and (not deploy_target_url or _is_localhost_or_file(deploy_target_url)):
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "deploy_target_url",
            "evidence": (
                f"deploy_target_url is missing OR localhost / file:// "
                f"({deploy_target_url!r}). A deploy mandate requires a "
                f"reachable backend URL."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Deploy the backend "
                "service to a real URL (ECS / Lambda / Cloud Run / Fly / "
                "Render / etc.); record the URL in the verification "
                "artifact's `deploy_target_url` field; confirm a 200 "
                "response on the health endpoint."
            ),
        })

    if require_frontend and (not frontend_url or _is_localhost_or_file(frontend_url)):
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "frontend_url",
            "evidence": (
                f"frontend_url is missing OR localhost / file:// "
                f"({frontend_url!r}). A deploy mandate requires a hosted "
                f"frontend the user can open in a browser."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Deploy the frontend "
                "(S3+CloudFront / Vercel / Netlify / nginx on ECS / etc.) "
                "and record the URL in the verification artifact's "
                "`frontend_url` field."
            ),
        })

    if login_verified is not True:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "login_verified",
            "evidence": (
                f"login_verified is not True ({login_verified!r}). A deploy "
                f"mandate requires a Playwright login run confirming the user "
                f"can access the post-login dashboard at the hosted URL."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Run Playwright against "
                "the hosted frontend_url; log in with a real test user; "
                "capture a screenshot of the post-login state; set "
                "login_verified=true; cite the screenshot path in "
                "login_verification_evidence_path."
            ),
        })

    if login_verified is True and not login_evidence:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "login_verification_evidence_path",
            "evidence": (
                "login_verified=true but no evidence path supplied. The "
                "claim is unverifiable without a screenshot or trace."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Cite a non-empty file "
                "path in login_verification_evidence_path (.png / .zip / "
                ".har / .json)."
            ),
        })

    if not isinstance(live_data_assertions, list) or len(live_data_assertions) == 0:
        if require_frontend:
            gaps.append({
                "severity": "deploy-mandate-not-satisfied",
                "binding_criterion": "live_data_for_every_screen",
                "evidence": (
                    "live_data_assertions[] is missing or empty. Every "
                    "screen in the oracle spec MUST have a live-data "
                    "assertion proving non-mock data renders."
                ),
                "remediation": (
                    "v2.20.0 deploy mandate discipline. For each screen "
                    "named in the oracle spec, run a Playwright assertion "
                    "that reads a live (non-mock) value from the deployed "
                    "backend; record {screen, live: true, evidence} in "
                    "live_data_assertions[]."
                ),
            })
    else:
        not_live = [a for a in live_data_assertions if not (isinstance(a, dict) and a.get("live") is True)]
        if not_live:
            gaps.append({
                "severity": "deploy-mandate-not-satisfied",
                "binding_criterion": "live_data_for_every_screen",
                "screens_not_live": [a.get("screen") for a in not_live[:5] if isinstance(a, dict)],
                "evidence": (
                    f"{len(not_live)} live_data_assertions[] entries are NOT "
                    f"live (live != true). A deploy mandate requires every "
                    f"screen on live data."
                ),
                "remediation": (
                    "v2.20.0 deploy mandate discipline. Fix the unwired "
                    "screens — wire them to the deployed backend — and "
                    "re-run Playwright to flip every assertion's `live` "
                    "field to true."
                ),
            })

    if isinstance(mock_residue_count, int) and mock_residue_count > 0:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "no_mock_residue",
            "mock_residue_count": mock_residue_count,
            "evidence": (
                f"mock_residue_count = {mock_residue_count} > 0. A deploy "
                f"mandate requires zero mock-state in production paths "
                f"(per v2.6.0 + v2.7.0)."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Remove every mock-state "
                "signature from the production code path; sweep every "
                "consumer of every shared mock source per v2.7.0; re-run "
                "the v2.6.0 live-data wiring check."
            ),
        })

    if isinstance(unwired_elements_count, int) and unwired_elements_count > 0:
        gaps.append({
            "severity": "deploy-mandate-not-satisfied",
            "binding_criterion": "no_unwired_elements",
            "unwired_elements_count": unwired_elements_count,
            "evidence": (
                f"unwired_elements_count = {unwired_elements_count} > 0. "
                f"A deploy mandate requires every interactive element wired "
                f"to a real handler."
            ),
            "remediation": (
                "v2.20.0 deploy mandate discipline. Wire every interactive "
                "element to a real backend handler (per "
                "interaction-completeness). Unwired controls cannot ship "
                "under a deploy mandate."
            ),
        })

    return gaps


def verify_deploy_mandate_satisfied(
    verification_artifact: dict[str, Any] | None = None,
    deploy_mandate: dict[str, Any] | None = None,
    final_report: str = "",
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.20.0 Layer-3 tool — verify the deploy mandate is fully satisfied.

    Trivially passes (`valid: True, gaps: []`) when
    `deploy_mandate.active != True` — fully backwards-compatible.

    4 named severities:
      - `deploy-mandate-not-satisfied` — required field missing or invalid
      - `plan-only-deliverable-on-deploy-mandate` — final_report cites a plan as the deliverable
      - `adjacent-dependencies-claimed-as-deployment` — final_report cites adjacent dep work
      - `partial-deploy-passed-off-as-deploy` — partial deploy claimed when target_kind isn't 'thin-slice'
    """
    mandate = deploy_mandate or {}
    if mandate.get("active") is not True:
        verdict = {
            "tool": "verify-deploy-mandate-satisfied",
            "valid": True,
            "gaps": [],
            "deploy_mandate_active": False,
            "verdict_at": _utc_now_iso(),
        }
        return _write_verdict(verdict, out_path)

    artifact = verification_artifact or {}
    target_kind = mandate.get("target_kind")
    report_text = final_report or ""

    gaps: list[dict[str, Any]] = []
    gaps += _detect_missing_binding_criteria(artifact, target_kind)
    gaps += _detect_plan_only_deliverable(report_text)
    gaps += _detect_adjacent_dependencies_claimed(report_text)
    gaps += _detect_partial_deploy_passed_off(report_text, target_kind)

    verdict = {
        "tool": "verify-deploy-mandate-satisfied",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "deploy_mandate_active": True,
        "target_kind": target_kind,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
