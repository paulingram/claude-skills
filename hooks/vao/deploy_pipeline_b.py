"""VAO no-pipeline-bypass tool — the 3rd deploy-pipeline-family tool,
split out of ``deploy_pipeline.py`` to keep each module <= 900 lines
(R2 ceiling, design.md Decision 1a)."""

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


_PIPELINE_CONFESSION_MARKERS = (
    # Bypass admission
    "i bypassed all of that",
    "bypassed all of",
    "built it solo",
    "built solo",
    "i built solo",
    "i overrode your",
    "overrode your explicit choice",
    "overrode your choice",
    "i overrode",
    "wrote the code, tested it myself",
    "tested it myself, and committed it directly",
    "committed it directly",
    # Element confession (past-tense bypass)
    "no subagents",
    "no independent review",
    "no openspec",
    "no worktree",
    "the producer was the checker",
    "i tested it myself",
    # Rationalization
    "driving directly from the plan",
    "drove directly from the plan",
    "tokens into code instead of",
    "mapping/spec ceremony",
    "re-running the mapping/spec",
    "skipped the ceremony",
    "i'd already mapped the",
    "put tokens into code",
    # Post-hoc framing
    "the honest framing is",
    "i told you i was",
    "your call to make",
    "not mine to make silently",
    "deserve to know",
    "to be straight about that",
    "should be straight about that",
)


_PIPELINE_DRIVING_SKILLS = (
    "architect-team-pipeline",
    "bug-fix-pipeline",
    "mini-architect-team-pipeline",
    "ux-test-builder",
)


# Skill names that constitute legitimate openspec usage via the change-proposal
# skill (NOT a literal `openspec ` Bash call). The mini pipeline + the
# exploration flows author the openspec change through this skill rather than
# the CLI, so an invocation here is valid evidence openspec was used.
_OPENSPEC_PROPOSE_SKILLS = (
    "openspec-propose",
    "opsx:propose",
)


_PIPELINE_SLASH_COMMAND_PREFIXES = (
    "/architect-team",
    "/architect-team:bug-fix",
    "/architect-team:mini",
    "/architect-team:ux-test",
)


def _scan_ledger_for_pipeline_elements(
    toolcall_ledger: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Count pipeline-element invocations in the ledger. Returns:

      {
        "skill_invocations": int,           # Skill tool calls naming a pipeline skill
        "agent_dispatches": int,            # Agent tool calls
        "openspec_calls": int,              # Bash with openspec subcommands
        "openspec_propose_skill_invocations": int,  # Skill calls to openspec-propose / opsx:propose
        "openspec_change_artifacts": int,   # Write/Edit into openspec/changes/<name>/
        "worktree_creations": int,          # Bash with git worktree add
        "review_evidence_files": int,       # Write/Edit calls into .architect-team/reviews/
        "first_source_edit_before_skill": bool,  # source modification preceded ANY Skill call
      }
    """
    counts = {
        "skill_invocations": 0,
        "agent_dispatches": 0,
        "openspec_calls": 0,
        "openspec_propose_skill_invocations": 0,
        "openspec_change_artifacts": 0,
        "worktree_creations": 0,
        "review_evidence_files": 0,
        "first_source_edit_before_skill": False,
    }
    if not isinstance(toolcall_ledger, list):
        return counts

    skill_seen = False
    for entry in toolcall_ledger:
        if not isinstance(entry, dict):
            continue
        tool = (entry.get("tool") or entry.get("tool_name") or "").strip()
        inp = entry.get("tool_input") or entry.get("input") or {}
        if not isinstance(inp, dict):
            inp = {}

        # Skill invocations
        if tool == "Skill":
            skill_name = (inp.get("skill") or inp.get("skill_name") or "").strip()
            skill_name_lower = skill_name.lower()
            if any(name in skill_name for name in _PIPELINE_DRIVING_SKILLS):
                counts["skill_invocations"] += 1
                skill_seen = True
            # openspec-propose / opsx:propose Skill invocation is legitimate
            # openspec usage (the mini + exploration flows author the change
            # via the skill, not the CLI). Count it independently so a pipeline
            # that proposed via the skill does NOT false-trip openspec-bypassed.
            if any(name in skill_name_lower for name in _OPENSPEC_PROPOSE_SKILLS):
                counts["openspec_propose_skill_invocations"] += 1
            continue

        # Agent dispatches
        if tool == "Agent":
            counts["agent_dispatches"] += 1
            continue

        # Source modifications BEFORE any Skill call → bypass signal
        if tool in ("Edit", "Write", "NotebookEdit") and not skill_seen:
            path = (inp.get("file_path") or inp.get("path") or "").lower()
            # Only count source edits — not edits to .architect-team/ state
            if path and ".architect-team" not in path and ".mempalace" not in path:
                counts["first_source_edit_before_skill"] = True

        # Review evidence file writes
        if tool in ("Write", "Edit", "NotebookEdit"):
            path = (inp.get("file_path") or inp.get("path") or "")
            # Normalize backslashes -> forward slashes + lowercase BEFORE any
            # membership test (A3 review-remediation). A Windows ledger path like
            # `C:\\ws\\.architect-team\\reviews\\T-1.json` would never match the
            # forward-slash `/reviews/` substring on the raw value, producing a
            # false `independent-review-bypassed`. The openspec check below
            # already normalized; the reviews check must too.
            norm = path.replace("\\", "/").lower()
            # A review-evidence file is a .json under a reviews/ dir. The parens
            # make the intent explicit: (canonical path OR loose /reviews/) AND .json.
            # Without them this parsed as `A or (B and C)`, which counted a
            # non-.json write under .architect-team/reviews/ as evidence.
            if ("/.architect-team/reviews/" in norm or "/reviews/" in norm) and ".json" in norm:
                counts["review_evidence_files"] += 1
            # An openspec/changes/<name>/ artifact write is evidence openspec
            # was used (the change-proposal flow authors proposal.md / tasks.md
            # / specs/ under this dir).
            if "openspec/changes/" in norm:
                counts["openspec_change_artifacts"] += 1

        # Bash for openspec / worktree
        if tool == "Bash":
            command = (inp.get("command") or "").lower()
            if "openspec " in command or command.startswith("openspec"):
                counts["openspec_calls"] += 1
            if "git worktree add" in command:
                counts["worktree_creations"] += 1

    return counts


def _detect_pipeline_invoked(user_prompt: str) -> bool:
    """A pipeline command is invoked if the prompt starts with (or contains
    early) one of the pipeline-driving slash command prefixes."""
    if not isinstance(user_prompt, str) or not user_prompt.strip():
        return False
    lower = user_prompt.strip().lower()
    return any(lower.startswith(p) for p in _PIPELINE_SLASH_COMMAND_PREFIXES) or any(
        p in lower[:200] for p in _PIPELINE_SLASH_COMMAND_PREFIXES
    )


def _detect_no_worktree_optout(user_prompt: str) -> bool:
    if not isinstance(user_prompt, str):
        return False
    lower = user_prompt.lower()
    return any(p in lower for p in ("--no-worktree", "no worktree", "don't create a worktree", "single tree", "in place"))


def _detect_no_openspec_optout(user_prompt: str) -> bool:
    if not isinstance(user_prompt, str):
        return False
    lower = user_prompt.lower()
    return any(p in lower for p in ("--no-openspec", "no openspec", "skip openspec"))


def _detect_confession_markers(final_report: str) -> list[str]:
    if not isinstance(final_report, str) or not final_report.strip():
        return []
    lower = final_report.lower()
    return [m for m in _PIPELINE_CONFESSION_MARKERS if m in lower]


def verify_no_pipeline_bypass(
    user_prompt: str = "",
    toolcall_ledger: list[dict[str, Any]] | None = None,
    final_report: str = "",
    out_path: Path | str | None = None,
) -> dict[str, Any]:
    """v2.22.0 Layer-3 tool — verify the pipeline was actually followed, not
    bypassed.

    Trivially passes (`valid: True, gaps: []`) when the user prompt does NOT
    invoke a pipeline-driving slash command AND no confession markers are
    detected — backwards-compatible.

    5 named severities:
      - pipeline-bypassed-after-slash-command — pipeline invoked, source
        modification preceded any Skill call
      - solo-implementation-instead-of-team-dispatch — pipeline invoked,
        zero Agent dispatches in the ledger
      - independent-review-bypassed — pipeline invoked, zero review evidence
        files written
      - openspec-bypassed — pipeline invoked but openspec was NOT used in ANY
        of the three recognized ways: (a) a literal `openspec ` Bash call,
        (b) an openspec-propose / opsx:propose Skill invocation, or
        (c) an openspec/changes/<name>/ artifact write. (unless --no-openspec
        opt-in)
      - pipeline-confession-language-detected — final_report contains the
        canonical bypass-confession markers
    """
    pipeline_invoked = _detect_pipeline_invoked(user_prompt or "")
    confession_hits = _detect_confession_markers(final_report or "")
    counts = _scan_ledger_for_pipeline_elements(toolcall_ledger)
    gaps: list[dict[str, Any]] = []

    # Confession-language detection fires regardless of pipeline_invoked —
    # the agent's own admission is sufficient evidence.
    if confession_hits:
        gaps.append({
            "severity": "pipeline-confession-language-detected",
            "matched_markers": confession_hits[:8],
            "evidence": (
                f"final_report contains {len(confession_hits)} bypass-"
                f"confession marker(s): {confession_hits[:5]!r}. The agent "
                f"admitted bypassing the pipeline. Confession is sufficient "
                f"evidence — re-run is required."
            ),
            "remediation": (
                "v2.22.0 no pipeline-bypass discipline. Re-invoke the "
                "pipeline against the same user prompt. The bypassed work "
                "must be re-evaluated through the proper multi-agent "
                "dispatch + independent review + OpenSpec + worktree flow. "
                "If the user explicitly authorized the bypass, that "
                "authorization must be cited verbatim in the final report "
                "(NOT post-hoc rationalization)."
            ),
        })

    # The remaining 4 severities only fire when pipeline was actually invoked
    if not pipeline_invoked:
        verdict = {
            "tool": "verify-no-pipeline-bypass",
            "valid": len(gaps) == 0,
            "gaps": gaps,
            "pipeline_invoked": False,
            "verdict_at": _utc_now_iso(),
        }
        return _write_verdict(verdict, out_path)

    if counts["first_source_edit_before_skill"]:
        gaps.append({
            "severity": "pipeline-bypassed-after-slash-command",
            "evidence": (
                "user prompt invokes a pipeline slash command but the "
                "toolcall ledger shows a source-code Edit/Write BEFORE any "
                "Skill(architect-team-pipeline / bug-fix-pipeline / ...) "
                "call. The agent applied methodology by hand."
            ),
            "remediation": (
                "v2.22.0 no pipeline-bypass discipline. Re-invoke the "
                "pipeline. The first action after a pipeline slash command "
                "MUST be a Skill invocation, NOT a source edit."
            ),
        })

    if counts["agent_dispatches"] == 0:
        gaps.append({
            "severity": "solo-implementation-instead-of-team-dispatch",
            "agent_dispatches": 0,
            "evidence": (
                "user prompt invokes a pipeline slash command but the "
                "ledger contains zero Agent tool calls. The pipeline's "
                "parallel backend/frontend dispatch never happened; the "
                "orchestrator did all the work itself."
            ),
            "remediation": (
                "v2.22.0 no pipeline-bypass discipline. The architect-team "
                "pipeline REQUIRES Phase 2 to dispatch backend + frontend "
                "subagents in parallel. Zero Agent dispatches means the "
                "pipeline did not run. Re-invoke with the actual subagent "
                "spawn flow."
            ),
        })

    if counts["review_evidence_files"] == 0 and counts["agent_dispatches"] > 0:
        gaps.append({
            "severity": "independent-review-bypassed",
            "review_evidence_files": 0,
            "evidence": (
                "subagents were dispatched but zero independent-review "
                "evidence files were written under .architect-team/reviews/. "
                "Producer === checker. The v6 evidence schema requires "
                "independent_review.reviewer != teammate."
            ),
            "remediation": (
                "v2.22.0 no pipeline-bypass discipline. Spawn task-reviewer "
                "agents per the v6 evidence schema. Producer cannot be its "
                "own checker."
            ),
        })

    # openspec usage is evidenced by ANY of three channels: a literal
    # `openspec ` Bash call, an openspec-propose / opsx:propose Skill
    # invocation (mini + exploration flows), or an openspec/changes/<name>/
    # artifact write. The severity fires ONLY when openspec was touched in
    # NONE of these ways. Preserves the true-positive: a pipeline that genuinely
    # never used openspec in any form still trips.
    openspec_used = (
        counts["openspec_calls"] > 0
        or counts["openspec_propose_skill_invocations"] > 0
        or counts["openspec_change_artifacts"] > 0
    )
    if not openspec_used and not _detect_no_openspec_optout(user_prompt or ""):
        gaps.append({
            "severity": "openspec-bypassed",
            "openspec_calls": 0,
            "openspec_propose_skill_invocations": counts["openspec_propose_skill_invocations"],
            "openspec_change_artifacts": counts["openspec_change_artifacts"],
            "evidence": (
                "user prompt invokes a pipeline slash command and did not "
                "opt out of OpenSpec; the ledger shows NO openspec usage in "
                "any recognized form — zero `openspec ` Bash calls, zero "
                "openspec-propose/opsx:propose Skill invocations, and zero "
                "openspec/changes/<name>/ artifact writes."
            ),
            "remediation": (
                "v2.22.0 no pipeline-bypass discipline. Author the change via "
                "`openspec init` / `openspec validate` / `openspec archive`, "
                "OR via the openspec-propose / opsx:propose skill, per the "
                "pipeline's Phase 0 / Phase 8 contract. Skipping OpenSpec "
                "means the change is undocumented in the spec layer."
            ),
        })

    verdict = {
        "tool": "verify-no-pipeline-bypass",
        "valid": len(gaps) == 0,
        "gaps": gaps,
        "pipeline_invoked": True,
        "counts": counts,
        "verdict_at": _utc_now_iso(),
    }
    return _write_verdict(verdict, out_path)
