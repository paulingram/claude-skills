"""v1.8.0 agent-resume-discipline — REQ-1 through REQ-6.

Exercises `scripts/setup/agent_resume.py` and the documentation surfaces:

  REQ-1 (helper): `is_truncated`, `wrap_agent_result`, `read_checkpoint` cover
        positive + negative cases. Synthetic truncated / well-formed results.
        Mock `send_message` for resume invocation, max-attempts cap, error
        tolerance.
  REQ-2 (canonical doc): `common-pipeline-conventions/SKILL.md` carries the two
        new sections AND their schema + cadence rules.
  REQ-3 (per-agent): all 27 `agents/*.md` files carry a
        `## Checkpoint discipline` section.
  REQ-4 (per-pipeline): all 3 pipeline SKILL.md bodies reference
        `wrap_agent_result`.
  REQ-5 (test-count): >= 10 tests collected.
  REQ-6 (version): plugin metadata at 1.8.0 — verified by the
        existing `tests/test_dispatch_banner.py::test_plugin_metadata_at_1_5_0`
        after its v1.8.0 pin update.

Module loader matches `tests/test_teams_mode.py` (importlib + module fixture).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def agent_resume_module(plugin_root: Path) -> ModuleType:
    """Load scripts/setup/agent_resume.py via importlib (matches teams_mode pattern)."""
    path = plugin_root / "scripts" / "setup" / "agent_resume.py"
    assert path.exists(), f"agent_resume.py missing at {path}"
    spec = importlib.util.spec_from_file_location("agent_resume_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- is_truncated ------------------------------------------------------------


def test_is_truncated_empty_output(agent_resume_module: ModuleType) -> None:
    """Spec scenario: is_truncated detects empty output."""
    assert agent_resume_module.is_truncated({"output": ""}) is True


def test_is_truncated_missing_output_field(agent_resume_module: ModuleType) -> None:
    """Missing output field is treated as truncated."""
    assert agent_resume_module.is_truncated({}) is True


def test_is_truncated_none_input(agent_resume_module: ModuleType) -> None:
    """None / non-dict input is treated as truncated (conservative)."""
    assert agent_resume_module.is_truncated(None) is True
    assert agent_resume_module.is_truncated("not a dict") is True
    assert agent_resume_module.is_truncated(123) is True


def test_is_truncated_short_output(agent_resume_module: ModuleType) -> None:
    """Output below the minimum-char threshold is truncated."""
    assert agent_resume_module.is_truncated({"output": "ok"}) is True


@pytest.mark.parametrize(
    "marker",
    [
        "Server is temporarily limiting requests, please try again later.",
        "Got HTTP 429: rate limit exceeded",
        "Rate Limited by upstream",
        "rate-limited",
        "stream timeout while waiting for response",
        "Stream Timed Out — request aborted",
    ],
)
def test_is_truncated_detects_rate_limit_markers(
    agent_resume_module: ModuleType, marker: str
) -> None:
    """Spec scenario: is_truncated detects rate-limit markers (case-insensitive)."""
    # Pad with a Status: marker so this isn't ALSO failing the missing-marker check.
    output = f"Status: DONE\n{marker}\nbut work is on disk somewhere"
    assert agent_resume_module.is_truncated({"output": output}) is True


def test_is_truncated_missing_report_markers(agent_resume_module: ModuleType) -> None:
    """Spec scenario: is_truncated detects missing report-format markers."""
    output = (
        "I started by reading the files. Then I edited them. Then I ran tests. "
        "Everything seemed fine but then the agent thought about the problem more."
    )
    # Long enough, no rate-limit marker, but no Status: / DONE / BLOCKED either.
    assert agent_resume_module.is_truncated({"output": output}) is True


def test_is_truncated_accepts_well_formed_done(agent_resume_module: ModuleType) -> None:
    """Spec scenario: is_truncated accepts well-formed reports."""
    output = (
        "Status: DONE\n"
        "Commit SHAs: abc123\n"
        "Files touched: scripts/setup/agent_resume.py\n"
        "All checks passed."
    )
    assert agent_resume_module.is_truncated({"output": output}) is False


def test_is_truncated_accepts_blocked_report(agent_resume_module: ModuleType) -> None:
    """A BLOCKED report is well-formed too — not truncated."""
    output = (
        "Status: BLOCKED\n"
        "Need authentication credentials for the upstream API. "
        "Cannot proceed without them. No commits."
    )
    assert agent_resume_module.is_truncated({"output": output}) is False


def test_is_truncated_accepts_needs_context_report(
    agent_resume_module: ModuleType,
) -> None:
    """A NEEDS_CONTEXT report is well-formed too."""
    output = (
        "Status: NEEDS_CONTEXT\n"
        "Could not find the CODEBASE_MAP section for this slice. "
        "Need orchestrator to clarify which file contains the audit conventions."
    )
    assert agent_resume_module.is_truncated({"output": output}) is False


def test_is_truncated_case_insensitive(agent_resume_module: ModuleType) -> None:
    """Report-marker detection is case-insensitive."""
    output = (
        "status: done\n"
        "everything passed in the test run. final commit: deadbeef."
    )
    assert agent_resume_module.is_truncated({"output": output}) is False


# ---- wrap_agent_result -------------------------------------------------------


def test_wrap_agent_result_passthrough_when_not_truncated(
    agent_resume_module: ModuleType,
) -> None:
    """Spec scenario: wrap_agent_result passes through well-formed results."""
    original = {
        "output": "Status: DONE\nAll good. Commit: abc123. Files: foo.py",
        "agent_id": "agent-xyz",
    }
    out = agent_resume_module.wrap_agent_result(original, agent_id="agent-xyz")
    assert out["resumed"] is False
    assert out["attempts"] == 1
    assert out["resumed_failed"] is False
    assert out["output"] == original["output"]


def test_wrap_agent_result_truncated_no_send_message(
    agent_resume_module: ModuleType,
) -> None:
    """Truncated input + no send_message → return-as-is with detection flag.

    The orchestrator can still see the truncation but no auto-resume is run.
    """
    original = {"output": ""}
    out = agent_resume_module.wrap_agent_result(original, agent_id="agent-xyz")
    assert out["resumed"] is False
    assert out["attempts"] == 1
    assert out["resumed_failed"] is False


def test_wrap_agent_result_invokes_resume_on_truncated(
    agent_resume_module: ModuleType,
) -> None:
    """Spec scenario: wrap_agent_result invokes resume on truncated input."""
    truncated = {"output": ""}
    calls: list[dict] = []

    def fake_send(to: str, prompt: str) -> dict:
        calls.append({"to": to, "prompt": prompt})
        return {
            "output": (
                "Status: DONE\n"
                "Commit SHAs: deadbeef\n"
                "Files touched: src/foo.py\n"
                "All checks passed on resume."
            )
        }

    out = agent_resume_module.wrap_agent_result(
        truncated, agent_id="agent-xyz", send_message=fake_send
    )
    assert len(calls) == 1
    assert calls[0]["to"] == "agent-xyz"
    assert "final verdict" in calls[0]["prompt"].lower()
    assert out["resumed"] is True
    assert out["attempts"] == 2  # 1 (original) + 1 (resume)
    assert out["resumed_failed"] is False
    assert "DONE" in out["output"]


def test_wrap_agent_result_merges_resumed_with_original(
    agent_resume_module: ModuleType,
) -> None:
    """The merged output preserves the original AND appends the resumed report."""
    truncated = {
        "output": "Did some work but ran out of stream time before reporting"
    }

    def fake_send(to: str, prompt: str) -> dict:
        return {"output": "Status: DONE\nNow I'm reporting. Commit: cafe123."}

    out = agent_resume_module.wrap_agent_result(
        truncated, agent_id="x", send_message=fake_send
    )
    assert out["resumed"] is True
    assert "Did some work" in out["output"]
    assert "Status: DONE" in out["output"]
    # The merge marker should be present so callers can split the seam.
    assert "[resumed via wrap_agent_result]" in out["output"]


def test_wrap_agent_result_caps_at_max_attempts(
    agent_resume_module: ModuleType,
) -> None:
    """Spec scenario: wrap_agent_result caps at max_attempts."""
    truncated = {"output": ""}
    calls = 0

    def always_truncated(to: str, prompt: str) -> dict:
        nonlocal calls
        calls += 1
        return {"output": ""}  # Still truncated.

    out = agent_resume_module.wrap_agent_result(
        truncated, agent_id="x", send_message=always_truncated, max_attempts=2
    )
    # Exactly 2 resume attempts; never 3.
    assert calls == 2
    assert out["resumed_failed"] is True
    assert out["attempts"] == 3  # 1 original + 2 resumes


def test_wrap_agent_result_max_attempts_one(
    agent_resume_module: ModuleType,
) -> None:
    """max_attempts=1 → exactly one resume attempt."""
    calls = 0

    def always_truncated(to: str, prompt: str) -> dict:
        nonlocal calls
        calls += 1
        return {"output": ""}

    out = agent_resume_module.wrap_agent_result(
        {"output": ""}, agent_id="x", send_message=always_truncated, max_attempts=1
    )
    assert calls == 1
    assert out["resumed_failed"] is True


def test_wrap_agent_result_stops_early_on_success(
    agent_resume_module: ModuleType,
) -> None:
    """If the first resume succeeds, no second resume is sent."""
    calls = 0

    def succeed_first(to: str, prompt: str) -> dict:
        nonlocal calls
        calls += 1
        return {
            "output": (
                "Status: DONE\n"
                "Commit SHAs: abc123, def456\n"
                "Files touched: foo.py, bar.py\n"
                "Report complete after resume."
            )
        }

    out = agent_resume_module.wrap_agent_result(
        {"output": ""},
        agent_id="x",
        send_message=succeed_first,
        max_attempts=3,
    )
    assert calls == 1
    assert out["resumed"] is True
    assert out["resumed_failed"] is False


def test_wrap_agent_result_tolerates_send_message_exception(
    agent_resume_module: ModuleType,
) -> None:
    """A raising send_message is caught; its exception is recorded."""

    def raising(to: str, prompt: str) -> dict:
        raise RuntimeError("harness offline")

    out = agent_resume_module.wrap_agent_result(
        {"output": ""}, agent_id="x", send_message=raising, max_attempts=2
    )
    assert out["resumed_failed"] is True
    assert "RuntimeError" in (out.get("resume_error") or "")
    assert "harness offline" in (out.get("resume_error") or "")


def test_wrap_agent_result_preserves_extra_keys(
    agent_resume_module: ModuleType,
) -> None:
    """Original result keys (agent metadata) are carried through."""
    original = {
        "output": "Status: DONE\nClean run. Commit: abc.",
        "agent_id": "vendor-id",
        "duration_ms": 1234,
    }
    out = agent_resume_module.wrap_agent_result(original, agent_id="x")
    assert out["agent_id"] == "vendor-id"
    assert out["duration_ms"] == 1234


def test_wrap_agent_result_tolerates_none_input(
    agent_resume_module: ModuleType,
) -> None:
    """None input is treated as truncated; no crash."""

    def fake_send(to: str, prompt: str) -> dict:
        return {"output": "Status: DONE\nResumed after None input. Commit: x."}

    out = agent_resume_module.wrap_agent_result(
        None, agent_id="x", send_message=fake_send
    )
    assert out["resumed"] is True
    assert out["resumed_failed"] is False


# ---- read_checkpoint ---------------------------------------------------------


def test_read_checkpoint_returns_none_when_absent(
    agent_resume_module: ModuleType, tmp_path: Path
) -> None:
    """Spec scenario: read_checkpoint returns None when file absent."""
    result = agent_resume_module.read_checkpoint(
        "nonexistent-id", checkpoints_dir=tmp_path
    )
    assert result is None


def test_read_checkpoint_parses_existing(
    agent_resume_module: ModuleType, tmp_path: Path
) -> None:
    """Spec scenario: read_checkpoint parses an existing checkpoint."""
    payload = {
        "agent_id": "a33aa940",
        "task_id": "verify-attorney-retry",
        "schema_version": 1,
        "last_completed_step": "verification phase 3 of 5",
        "files_touched": ["src/foo.tsx"],
        "in_progress": "running verification phase 4",
        "ts": "2026-05-29T03:14:00Z",
    }
    (tmp_path / "a33aa940.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    result = agent_resume_module.read_checkpoint(
        "a33aa940", checkpoints_dir=tmp_path
    )
    assert result == payload


def test_read_checkpoint_tolerates_malformed_json(
    agent_resume_module: ModuleType, tmp_path: Path
) -> None:
    """Malformed checkpoint JSON returns None — never raises."""
    (tmp_path / "broken.json").write_text("{not valid", encoding="utf-8")
    assert (
        agent_resume_module.read_checkpoint("broken", checkpoints_dir=tmp_path)
        is None
    )


def test_read_checkpoint_tolerates_non_dict_payload(
    agent_resume_module: ModuleType, tmp_path: Path
) -> None:
    """A JSON list / scalar at the checkpoint path returns None."""
    (tmp_path / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert (
        agent_resume_module.read_checkpoint("list", checkpoints_dir=tmp_path)
        is None
    )


def test_read_checkpoint_default_dir_resolution_does_not_raise(
    agent_resume_module: ModuleType,
) -> None:
    """With checkpoints_dir=None, the function resolves via shared_state_dir.

    The exact path varies by run context — we only assert no crash and that
    the (likely absent) file returns None.
    """
    result = agent_resume_module.read_checkpoint(
        "this-id-should-not-exist-anywhere-in-the-tree-12345"
    )
    assert result is None


# ---- Structural: canonical sections in common-pipeline-conventions -----------


def test_canonical_skill_has_resume_section(plugin_root: Path) -> None:
    """REQ-2 scenario: resume discipline section exists exactly once."""
    body = (
        plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert body.count("## Background-agent resume discipline") == 1


def test_canonical_skill_has_checkpoint_section(plugin_root: Path) -> None:
    """REQ-2 scenario: checkpoint discipline section exists exactly once."""
    body = (
        plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert body.count("## Agent checkpoint discipline") == 1


def test_resume_section_documents_wrap_call(plugin_root: Path) -> None:
    """REQ-2 scenario: resume discipline documents the wrap-call rule."""
    body = (
        plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    ).read_text(encoding="utf-8")
    section = _extract_section(body, "## Background-agent resume discipline")
    assert "wrap_agent_result" in section
    # Names the truncation criteria.
    assert "truncat" in section.lower()
    # Names the 2-attempt cap.
    assert "2" in section
    # Names user-surfacing on failure.
    assert "surfac" in section.lower() or "user" in section.lower()


def test_checkpoint_section_documents_schema_and_cadence(
    plugin_root: Path,
) -> None:
    """REQ-2 scenario: checkpoint discipline documents schema + cadence."""
    body = (
        plugin_root / "skills" / "common-pipeline-conventions" / "SKILL.md"
    ).read_text(encoding="utf-8")
    section = _extract_section(body, "## Agent checkpoint discipline")
    # Path.
    assert ".architect-team/agent-checkpoints/" in section
    # Schema field names.
    for field in (
        "agent_id",
        "last_completed_step",
        "files_touched",
        "in_progress",
        "ts",
    ):
        assert field in section, f"checkpoint section missing field: {field}"
    # Cadence — ~10 tool calls.
    assert "10" in section


# ---- Structural: every agent has the checkpoint section ----------------------


def test_every_agent_has_checkpoint_discipline_section(plugin_root: Path) -> None:
    """REQ-3 scenario: every agent has the section.

    Mirrors the spec's `grep -L '^## Checkpoint discipline' agents/*.md`
    → empty assertion.
    """
    agents_dir = plugin_root / "agents"
    missing: list[str] = []
    for path in sorted(agents_dir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        if "## Checkpoint discipline" not in body:
            missing.append(path.name)
    assert not missing, f"agents missing checkpoint section: {missing}"


def test_agent_count_is_27(plugin_root: Path) -> None:
    """Sanity: the v1.8.0 fan-out claims 27 agents."""
    agents = list((plugin_root / "agents").glob("*.md"))
    assert len(agents) == 27, f"expected 27 agents, found {len(agents)}"


def test_every_agent_section_references_canonical(plugin_root: Path) -> None:
    """Each agent's section cross-references the canonical."""
    agents_dir = plugin_root / "agents"
    for path in sorted(agents_dir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        section = _extract_section(body, "## Checkpoint discipline")
        assert "common-pipeline-conventions" in section, (
            f"{path.name}: checkpoint section missing canonical cross-ref"
        )


# ---- Structural: pipelines reference wrap_agent_result -----------------------


@pytest.mark.parametrize(
    "skill_name",
    [
        "architect-team-pipeline",
        "bug-fix-pipeline",
        "mini-architect-team-pipeline",
    ],
)
def test_pipeline_references_wrap_agent_result(
    plugin_root: Path, skill_name: str
) -> None:
    """REQ-4 scenario: each pipeline body references wrap_agent_result."""
    body = (
        plugin_root / "skills" / skill_name / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "wrap_agent_result" in body, (
        f"{skill_name} body missing wrap_agent_result reference"
    )


# ---- Structural: helper module surface --------------------------------------


def test_helper_module_exports_three_functions(
    agent_resume_module: ModuleType,
) -> None:
    """REQ-1 scenario: helper exposes the three functions + the default prompt."""
    assert callable(agent_resume_module.is_truncated)
    assert callable(agent_resume_module.wrap_agent_result)
    assert callable(agent_resume_module.read_checkpoint)
    assert isinstance(agent_resume_module.DEFAULT_RESUME_PROMPT, str)
    # The prompt should ask for the standard report markers.
    prompt = agent_resume_module.DEFAULT_RESUME_PROMPT
    assert "Status:" in prompt
    assert "DONE" in prompt


def test_helper_module_is_stdlib_only(plugin_root: Path) -> None:
    """REQ-1 scenario: helper imports are stdlib only.

    Forbidden third-party imports for this helper: anything outside stdlib
    + the existing scripts/setup/* sibling modules.
    """
    body = (
        plugin_root / "scripts" / "setup" / "agent_resume.py"
    ).read_text(encoding="utf-8")
    forbidden = ("import requests", "import yaml", "import httpx", "import aiohttp")
    for token in forbidden:
        assert token not in body, f"forbidden third-party import: {token}"


# ---- helpers -----------------------------------------------------------------


def _extract_section(body: str, heading: str) -> str:
    """Return everything between `heading` and the next `## ` heading.

    Used to inspect the contents of a single section without grabbing
    neighboring content. Returns "" if heading not found.
    """
    lines = body.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.startswith(heading):
            in_section = True
            out.append(line)
            continue
        if in_section:
            if line.startswith("## ") and line.strip() != heading:
                break
            out.append(line)
    return "\n".join(out)
