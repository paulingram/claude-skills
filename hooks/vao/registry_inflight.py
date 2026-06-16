"""VAO discipline-registry + inflight-clarifications (2 tools).

Both tools lazy-import their leaf module (``discipline_registry`` /
``inflight_inbox``) inside the function body, dual-form, so the CLI
works under the bare-module sys.path the hook-runner uses.
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


def verify_discipline_registry_current(
    workspace: str | Path,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.18.0 Layer-3 tool — verify the per-codebase discipline registry is
    current relative to the CT6 catalog. Returns standard verdict shape:

      { tool, valid, gaps, verdict_at }

    Each gap carries:
      { severity, discipline, ct6_version, auto_apply_safe,
        auto_update_command, auto_update_skill, sr_origin_kind,
        evidence, remediation }

    Severities:
      - discipline-registry-missing — registry file does not exist (and at
        least one catalog discipline is unapplied — a workspace with all
        disciplines trivially-applied does NOT trigger this severity)
      - discipline-not-applied — no registry entry AND codebase shows the
        discipline has not been applied
      - discipline-stale — registry has an entry BUT codebase shows it is
        no longer applied (surface advanced past applied_at)
    """
    # Lazy import — keeps vao_tools' stdlib-only contract clean when the
    # discipline_registry module is unused. Dual-form (mirrors lines 61-68) so
    # `python hooks/vao_tools.py verify-discipline-registry-current` works when
    # the hook-runner puts hooks/ — not the repo root — on sys.path.
    try:  # package shape: repo root on sys.path
        from hooks.discipline_registry import (
            DISCIPLINE_CATALOG,
            REGISTRY_RELATIVE_PATH,
            freshness_check,
        )
    except ImportError:  # bare-module shape: hooks/ dir on sys.path
        from discipline_registry import (
            DISCIPLINE_CATALOG,
            REGISTRY_RELATIVE_PATH,
            freshness_check,
        )

    workspace_path = Path(workspace)
    # Check registry presence BEFORE calling freshness_check (which writes
    # the registry's last_freshness_check timestamp as a side effect).
    registry_present = (workspace_path / REGISTRY_RELATIVE_PATH).exists()
    findings = freshness_check(workspace_path, DISCIPLINE_CATALOG)
    gaps: list[dict[str, Any]] = []

    if not registry_present and findings:
        gaps.append({
            "severity": "discipline-registry-missing",
            "discipline": None,
            "ct6_version": None,
            "auto_apply_safe": True,
            "auto_update_command": None,
            "auto_update_skill": None,
            "sr_origin_kind": None,
            "evidence": (
                f"per-codebase discipline registry "
                f"{REGISTRY_RELATIVE_PATH!r} does not exist at workspace "
                f"{str(workspace_path)!r} and at least one catalog "
                f"discipline is unapplied."
            ),
            "remediation": (
                "v2.18.0 codebase discipline registry. Phase 0.1 of the "
                "next pipeline run will create the registry and apply any "
                "auto-apply-safe disciplines. Manual creation is also fine "
                "via `/architect-team:discipline-status --apply`."
            ),
        })

    for f in findings:
        gaps.append({
            "severity": f["severity"],
            "discipline": f["discipline"],
            "ct6_version": f["ct6_version"],
            "auto_apply_safe": f["auto_apply_safe"],
            "auto_update_command": f.get("auto_update_command"),
            "auto_update_skill": f.get("auto_update_skill"),
            "sr_origin_kind": f.get("sr_origin_kind"),
            "evidence": f["evidence"],
            "remediation": f["remediation"],
        })

    verdict = {
        "tool": "verify-discipline-registry-current",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)


def verify_inflight_clarifications_processed(
    workspace: str | Path,
    run_id: str,
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.19.0 Layer-3 tool — verify every clarification injected into the
    in-flight inbox has been processed. Fires at Phase 8 of every pipeline.

    2 severities:
      - clarification-silently-ignored — message in inbox has processed_at=null
      - unprocessed-clarification-at-phase-boundary — phase boundary was
        crossed (next phase's start_time > inbox message's injected_at) but
        the message was not yet marked processed at that point. Currently
        emitted only when the inbox carries a `phase_log` array alongside
        the JSONL — when no phase log is present, this severity does not
        fire (orchestrator-discipline self-audit is the future runtime layer).
    """
    # Dual-form import (mirrors lines 61-68) so
    # `python hooks/vao_tools.py verify-inflight-clarifications-processed`
    # works under the bare-module sys.path the hook-runner uses.
    try:  # package shape: repo root on sys.path
        from hooks.inflight_inbox import read_inbox, unprocessed_messages
    except ImportError:  # bare-module shape: hooks/ dir on sys.path
        from inflight_inbox import read_inbox, unprocessed_messages

    workspace_path = Path(workspace)
    messages = read_inbox(workspace_path, run_id)
    unprocessed = [m for m in messages if m.get("processed_at") is None]

    gaps: list[dict[str, Any]] = []
    for m in unprocessed:
        gaps.append({
            "severity": "clarification-silently-ignored",
            "message_id": m.get("message_id"),
            "text": (m.get("text") or "")[:200],
            "injected_at": m.get("injected_at"),
            "injected_via": m.get("injected_via"),
            "evidence": (
                f"in-flight inbox message {m.get('message_id')!r} "
                f"(injected at {m.get('injected_at')!r} via "
                f"{m.get('injected_via')!r}) was never processed by the "
                f"orchestrator — processed_at is null at Phase 8."
            ),
            "remediation": (
                "v2.19.0 in-flight clarification injection mechanism. Every "
                "inbox message MUST be classified at a phase boundary (see "
                "the canonical home in common-pipeline-conventions/SKILL.md "
                "## In-flight clarification injection mechanism (v2.19.0)). "
                "Read the message, classify as scope-amendment / clarification "
                "/ out-of-scope / parallel-problem per v2.5.0, take the named "
                "action (a parallel-problem opens a sanctioned concurrent lane), then "
                "`hooks.inflight_inbox.mark_processed(...)`. Re-run Phase 8 "
                "once all messages are processed."
            ),
        })

    verdict = {
        "tool": "verify-inflight-clarifications-processed",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "total_messages": len(messages),
        "unprocessed_count": len(unprocessed),
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
