# -*- coding: utf-8 -*-
# @prod-safe — pure offline unit tests: no network, no dev/prod API, no DB; the
# only side effects are writes under pytest's tmp_path (not a _MUTATION_PATTERN).
"""Tests for the Claude Design import engine (the `claude-design-mcp-import` change).

Covers the deterministic machine `scripts/claude_design/claude_design_import.py`:
offer detection (URL form, MCP-mention form, `?file=`/`Implement:` parse, no-offer),
`parse_design_url` decode edges, whole-project materialization + path-safety
(absolute + `..` traversal), the fetch orchestration against a
`FakeClaudeDesignSource`, the instruct-then-fallback plan, plus the CLI and the
skill / wiring instruction surface. All offline (no network, no live MCP).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "claude_design" / "claude_design_import.py"

_spec = importlib.util.spec_from_file_location("claude_design_import", MODULE_PATH)
cdi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cdi)  # type: ignore[union-attr]

# The finance-dashboard example URL from the change's spec scenarios.
DESIGN_URL = "https://claude.ai/design/p/f46f3d34?file=finance-dashboard%2FFinance+Dashboard.html"


# --------------------------------------------------------------------------- #
# Requirement: Claude Design offer detection
# --------------------------------------------------------------------------- #

def test_url_form_is_detected() -> None:
    offer = cdi.detect_claude_design_offer(f"Please match this design: {DESIGN_URL}")
    assert offer["detected"] is True
    assert "design-url" in offer["trigger_forms"]
    assert offer["project_id"] == "f46f3d34"
    # file_selector is URL-decoded: %2F -> '/', '+' -> ' '.
    assert offer["file_selector"] == "finance-dashboard/Finance Dashboard.html"
    assert offer["project_url"] == DESIGN_URL


def test_url_form_detected_without_scheme() -> None:
    offer = cdi.detect_claude_design_offer("build claude.ai/design/p/abc123 for me")
    assert offer["detected"] is True
    assert offer["trigger_forms"] == ["design-url"]
    assert offer["project_id"] == "abc123"
    assert offer["file_selector"] is None


def test_mcp_mention_form_is_detected() -> None:
    # Names the claude_design MCP but carries NO design URL.
    offer = cdi.detect_claude_design_offer(
        "Pull the project from the claude_design MCP and build it."
    )
    assert offer["detected"] is True
    assert offer["trigger_forms"] == ["mcp-mention"]
    assert offer["project_id"] is None
    assert offer["project_url"] is None


def test_mcp_endpoint_counts_as_mcp_mention() -> None:
    offer = cdi.detect_claude_design_offer(
        "The MCP endpoint is https://api.anthropic.com/v1/design/mcp — connect it."
    )
    assert offer["detected"] is True
    assert "mcp-mention" in offer["trigger_forms"]
    assert offer["mcp_endpoint"] == "https://api.anthropic.com/v1/design/mcp"


def test_both_trigger_forms_present_are_sorted() -> None:
    offer = cdi.detect_claude_design_offer(f"claude_design MCP + {DESIGN_URL}")
    # inclusive-OR: both forms fire; trigger_forms is sorted.
    assert offer["trigger_forms"] == ["design-url", "mcp-mention"]
    assert offer["detected"] is True


def test_implement_target_is_parsed() -> None:
    text = f"{DESIGN_URL}\nImplement: finance-dashboard/Finance Dashboard.html\n"
    offer = cdi.detect_claude_design_offer(text)
    assert offer["implement_target"] == "finance-dashboard/Finance Dashboard.html"


def test_implement_target_absent_is_none() -> None:
    offer = cdi.detect_claude_design_offer(DESIGN_URL)
    assert offer["implement_target"] is None


def test_no_offer_returns_not_detected() -> None:
    offer = cdi.detect_claude_design_offer(
        "Just build a login page from these screenshots in ./designs."
    )
    assert offer["detected"] is False
    assert offer["trigger_forms"] == []
    assert offer["project_id"] is None
    assert offer["file_selector"] is None
    assert offer["mcp_endpoint"] is None


def test_detect_handles_empty_and_none() -> None:
    for empty in ("", None):
        offer = cdi.detect_claude_design_offer(empty)  # type: ignore[arg-type]
        assert offer["detected"] is False
        assert offer["trigger_forms"] == []


def test_detection_is_deterministic() -> None:
    text = f"{DESIGN_URL}\nImplement: finance-dashboard/Finance Dashboard.html"
    a = cdi.detect_claude_design_offer(text)
    b = cdi.detect_claude_design_offer(text)
    assert a == b
    # byte-identical JSON (sort_keys) — the determinism contract.
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# --------------------------------------------------------------------------- #
# parse_design_url decode edges
# --------------------------------------------------------------------------- #

def test_parse_design_url_decodes_selector() -> None:
    parsed = cdi.parse_design_url(DESIGN_URL)
    assert parsed["project_id"] == "f46f3d34"
    assert parsed["base_url"] == "https://claude.ai/design/p/f46f3d34"
    assert parsed["file_selector"] == "finance-dashboard/Finance Dashboard.html"


def test_parse_design_url_no_query() -> None:
    parsed = cdi.parse_design_url("https://claude.ai/design/p/xyz789")
    assert parsed["project_id"] == "xyz789"
    assert parsed["file_selector"] is None


def test_parse_design_url_non_matching_never_raises() -> None:
    for junk in ("", None, "not a url", "https://example.com/other", "claude.ai/design/nope"):
        parsed = cdi.parse_design_url(junk)  # type: ignore[arg-type]
        assert parsed["project_id"] is None
        assert parsed["base_url"] is None
        assert parsed["file_selector"] is None


def test_parse_design_url_trailing_sentence_punctuation_trimmed() -> None:
    # A URL that ends a sentence must not carry the trailing period into the id.
    parsed = cdi.parse_design_url("see https://claude.ai/design/p/f46f3d34.")
    assert parsed["project_id"] == "f46f3d34"


def test_parse_design_url_plus_and_percent_encoding() -> None:
    parsed = cdi.parse_design_url("claude.ai/design/p/p1?file=a%2Fb+c%2Fd.html")
    assert parsed["file_selector"] == "a/b c/d.html"


# --------------------------------------------------------------------------- #
# Requirement: Native MCP fetch and whole-project materialization
# --------------------------------------------------------------------------- #

def test_materialize_writes_every_file(tmp_path: Path) -> None:
    files = [
        {"path": "index.html", "content": "<html>root</html>"},
        {"path": "finance-dashboard/Finance Dashboard.html", "content": "<main>dash</main>"},
        {"path": "assets/app.js", "content": "console.log('x')"},
    ]
    dest = tmp_path / "proj"
    result = cdi.materialize_project(files, dest)
    assert result["materialized_dir"] == str(dest)
    assert result["files_written"] == sorted(
        ["index.html", "finance-dashboard/Finance Dashboard.html", "assets/app.js"]
    )
    assert result["rejected"] == []
    # content is intact on disk
    assert (dest / "index.html").read_text(encoding="utf-8") == "<html>root</html>"
    assert (dest / "finance-dashboard" / "Finance Dashboard.html").read_text(
        encoding="utf-8"
    ) == "<main>dash</main>"
    assert (dest / "assets" / "app.js").read_text(encoding="utf-8") == "console.log('x')"


def test_materialize_files_written_is_sorted(tmp_path: Path) -> None:
    files = [
        {"path": "z.html", "content": "z"},
        {"path": "a.html", "content": "a"},
        {"path": "m.html", "content": "m"},
    ]
    result = cdi.materialize_project(files, tmp_path / "d")
    assert result["files_written"] == ["a.html", "m.html", "z.html"]


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    files = [
        {"path": "../../etc/evil", "content": "pwned"},
        {"path": "safe.html", "content": "ok"},
    ]
    result = cdi.materialize_project(files, dest)
    # the traversal entry is rejected; the safe one is written
    assert result["files_written"] == ["safe.html"]
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["path"] == "../../etc/evil"
    # nothing was written outside the dest dir
    assert not (tmp_path / "etc" / "evil").exists()
    assert not (tmp_path.parent / "etc" / "evil").exists()
    assert (dest / "safe.html").read_text(encoding="utf-8") == "ok"


def test_absolute_paths_are_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "proj"
    files = [
        {"path": "/etc/passwd", "content": "root"},
        {"path": "C:\\Windows\\evil.txt", "content": "win"},
        {"path": "//server/share/evil", "content": "unc"},
        {"path": "keep.html", "content": "keep"},
    ]
    result = cdi.materialize_project(files, dest)
    assert result["files_written"] == ["keep.html"]
    assert {r["path"] for r in result["rejected"]} == {
        "/etc/passwd", "C:\\Windows\\evil.txt", "//server/share/evil"
    }


def test_safe_relpath_normalizes_and_rejects() -> None:
    assert cdi._safe_relpath("a/b/c.html") == "a/b/c.html"
    assert cdi._safe_relpath("a\\b\\c.html") == "a/b/c.html"   # backslashes normalized
    assert cdi._safe_relpath("./a/./b.html") == "a/b.html"      # '.' segments dropped
    for bad in ("/abs", "../up", "a/../../b", "C:\\x", "//unc/x", "", "   "):
        with pytest.raises(ValueError):
            cdi._safe_relpath(bad)


def test_focus_is_recorded(tmp_path: Path) -> None:
    offer = cdi.detect_claude_design_offer(
        f"{DESIGN_URL}\nImplement: finance-dashboard/Finance Dashboard.html"
    )
    source = cdi.FakeClaudeDesignSource(
        {"index.html": "<a>", "finance-dashboard/Finance Dashboard.html": "<b>"}
    )
    result = cdi.import_claude_design(offer, source, tmp_path)
    assert result["focus"] == {
        "file_selector": "finance-dashboard/Finance Dashboard.html",
        "implement_target": "finance-dashboard/Finance Dashboard.html",
    }
    # the whole project (both files), not only the ?file= selection, is present
    assert result["files_written"] == sorted(
        ["index.html", "finance-dashboard/Finance Dashboard.html"]
    )


# --------------------------------------------------------------------------- #
# fetch orchestration against a FakeClaudeDesignSource
# --------------------------------------------------------------------------- #

def test_import_materializes_via_fake_source(tmp_path: Path) -> None:
    offer = cdi.detect_claude_design_offer(DESIGN_URL)
    source = cdi.FakeClaudeDesignSource(
        files_by_project={"f46f3d34": [
            {"path": "index.html", "content": "<html>"},
            {"path": "styles.css", "content": "body{}"},
        ]}
    )
    result = cdi.import_claude_design(offer, source, tmp_path)
    assert result["status"] == "materialized"
    assert result["project_id"] == "f46f3d34"
    # materialized to dest_root/<project_id>/
    assert result["materialized_dir"] == str(tmp_path / "f46f3d34")
    assert result["files_written"] == ["index.html", "styles.css"]
    assert (tmp_path / "f46f3d34" / "index.html").read_text(encoding="utf-8") == "<html>"


def test_fake_source_returns_copies(tmp_path: Path) -> None:
    source = cdi.FakeClaudeDesignSource({"a.html": "A"})
    first = source.fetch_project("anything")
    first[0]["content"] = "MUTATED"
    second = source.fetch_project("anything")
    assert second[0]["content"] == "A"  # source is not mutated by a caller


def test_base_source_is_a_seam_not_callable() -> None:
    with pytest.raises(NotImplementedError):
        cdi.ClaudeDesignSource().fetch_project("x")


def test_import_not_detected_does_not_fetch(tmp_path: Path) -> None:
    offer = cdi.detect_claude_design_offer("no design here")

    class Boom(cdi.ClaudeDesignSource):
        def fetch_project(self, project_id, *, file_selector=None):
            raise AssertionError("must not fetch when not detected")

    result = cdi.import_claude_design(offer, Boom(), tmp_path)
    assert result["status"] == "not-detected"
    assert result["files_written"] == []


# --------------------------------------------------------------------------- #
# Requirement: Instruct-then-fallback when the MCP is unavailable
# --------------------------------------------------------------------------- #

def test_plan_when_unavailable_falls_back() -> None:
    offer = cdi.detect_claude_design_offer(DESIGN_URL)
    plan = cdi.plan_when_unavailable(offer, local_fallback_available=True)
    assert plan["action"] == "instruct-then-fallback"
    assert plan["fallback"] == "zip-local"
    # the instruction names connecting the claude_design MCP AND running /design-login
    assert "claude_design" in plan["instruction"]
    assert "/design-login" in plan["instruction"]


def test_plan_when_unavailable_halts_without_fallback() -> None:
    offer = cdi.detect_claude_design_offer(DESIGN_URL)
    plan = cdi.plan_when_unavailable(offer, local_fallback_available=False)
    assert plan["action"] == "instruct-then-halt"
    assert plan["fallback"] is None
    assert "/design-login" in plan["instruction"]


def test_import_when_mcp_unavailable_returns_plan(tmp_path: Path) -> None:
    offer = cdi.detect_claude_design_offer(DESIGN_URL)

    class Boom(cdi.ClaudeDesignSource):
        def fetch_project(self, project_id, *, file_selector=None):
            raise AssertionError("must not fetch when the MCP is unavailable")

    result = cdi.import_claude_design(offer, Boom(), tmp_path, mcp_available=False)
    assert result["action"] == "instruct-then-fallback"
    assert result["fallback"] == "zip-local"


# --------------------------------------------------------------------------- #
# Requirement: Both input sources stay first-class (detection is additive)
# --------------------------------------------------------------------------- #

def test_local_only_input_is_not_detected() -> None:
    # A plain local design directory reference is NOT a Claude Design offer, so
    # the existing local design-input discovery proceeds unchanged.
    offer = cdi.detect_claude_design_offer("Design lives in $REQ_DIR/designs/*.png")
    assert offer["detected"] is False


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #

def test_cli_detect_json() -> None:
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "detect", DESIGN_URL, "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0  # detected -> exit 0
    payload = json.loads(res.stdout)
    assert payload["detected"] is True
    assert payload["project_id"] == "f46f3d34"


def test_cli_detect_no_offer_exit_1() -> None:
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "detect", "nothing here"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 1  # not detected -> exit 1


def test_cli_detect_at_file(tmp_path: Path) -> None:
    f = tmp_path / "prompt.txt"
    f.write_text(f"match {DESIGN_URL}", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "detect", f"@{f}", "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    assert json.loads(res.stdout)["project_id"] == "f46f3d34"


def test_cli_parse_url_json() -> None:
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "parse-url", DESIGN_URL, "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["project_id"] == "f46f3d34"
    assert payload["file_selector"] == "finance-dashboard/Finance Dashboard.html"


def test_no_import_side_effects() -> None:
    for name in ("detect_claude_design_offer", "parse_design_url", "materialize_project",
                 "import_claude_design", "plan_when_unavailable", "ClaudeDesignSource",
                 "FakeClaudeDesignSource", "main"):
        assert hasattr(cdi, name), f"missing public API: {name}"
    res = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util;"
         f"s=importlib.util.spec_from_file_location('m',r'{MODULE_PATH}');"
         "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout == "", f"import produced stdout (side effect): {res.stdout!r}"


# --------------------------------------------------------------------------- #
# the skill contract + wiring instruction surface
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_the_engine() -> None:
    body = (REPO_ROOT / "skills" / "claude-design-import" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "claude_design_import.py" in body                 # cites the engine
    assert "oracle-deriver" in body                          # routes into the VAO path
    assert "interactive-mockup" in body                      # as an interactive-mockup oracle
    assert "/design-login" in body                           # the MCP-unavailable branch


def test_oracle_deriver_recognizes_materialized_project() -> None:
    body = (REPO_ROOT / "agents" / "oracle-deriver.md").read_text(encoding="utf-8")
    assert "claude-design-import" in body
    assert "interactive-mockup" in body.lower()


def test_design_fidelity_mapping_lists_materialized_dir() -> None:
    body = (REPO_ROOT / "skills" / "design-fidelity-mapping" / "SKILL.md").read_text(encoding="utf-8")
    assert "claude-design-import" in body


def test_intake_and_mapping_documents_additive_source() -> None:
    body = (REPO_ROOT / "skills" / "intake-and-mapping" / "SKILL.md").read_text(encoding="utf-8")
    assert "claude-design-import" in body


def test_design_consuming_commands_carry_the_reference() -> None:
    for cmd in ("architect-team", "visual-to-api", "ux-test"):
        body = (REPO_ROOT / "commands" / f"{cmd}.md").read_text(encoding="utf-8")
        assert "claude-design-import" in body, f"{cmd}.md missing the Claude Design reference"


def test_non_design_commands_do_not_reference_claude_design() -> None:
    # bug-fix and mini are not design-consuming; they must NOT carry the reference.
    for cmd in ("bug-fix", "mini"):
        body = (REPO_ROOT / "commands" / f"{cmd}.md").read_text(encoding="utf-8")
        assert "claude-design-import" not in body, f"{cmd}.md should not reference Claude Design"


# --------------------------------------------------------------------------- #
# Hardening (adversarial-review remediation): 4 MINOR fixes
# --------------------------------------------------------------------------- #

# Fix 1 — the real prompt shape: the URL is glued straight onto the Implement:
# directive with no separator, so the naive parse pollutes file_selector with
# `Implement:` and misses the mid-line target.
GLUED_PROMPT = (
    "https://claude.ai/design/p/f46f3d34-90b5-4031-b2b9-9b6aff0cf02a"
    "?file=finance-dashboard%2FFinance+Dashboard.html"
    "Implement: finance-dashboard/Finance Dashboard.html"
)


def test_glued_url_and_implement_directive() -> None:
    offer = cdi.detect_claude_design_offer(GLUED_PROMPT)
    assert offer["detected"] is True
    assert offer["project_id"] == "f46f3d34-90b5-4031-b2b9-9b6aff0cf02a"
    # file_selector is CLEAN — the glued Implement: directive is stripped off it
    assert offer["file_selector"] == "finance-dashboard/Finance Dashboard.html"
    assert "Implement" not in offer["file_selector"]
    assert offer["implement_target"] == "finance-dashboard/Finance Dashboard.html"


def test_clean_separate_line_implement_unchanged() -> None:
    # the clean separate-line form must still parse identically (no regression)
    text = (
        "https://claude.ai/design/p/f46f3d34-90b5-4031-b2b9-9b6aff0cf02a"
        "?file=finance-dashboard%2FFinance+Dashboard.html\n"
        "Implement: finance-dashboard/Finance Dashboard.html\n"
    )
    offer = cdi.detect_claude_design_offer(text)
    assert offer["project_id"] == "f46f3d34-90b5-4031-b2b9-9b6aff0cf02a"
    assert offer["file_selector"] == "finance-dashboard/Finance Dashboard.html"
    assert offer["implement_target"] == "finance-dashboard/Finance Dashboard.html"


# Fix 2 — an OS write error on ONE file must not abort the whole batch.
def test_materialize_survives_os_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_write = Path.write_text

    def flaky_write(self, data, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self.name == "bad.html":
            raise OSError("simulated OS-illegal filename")
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write)
    dest = tmp_path / "proj"
    files = [
        {"path": "good1.html", "content": "g1"},
        {"path": "bad.html", "content": "b"},
        {"path": "nested/good2.html", "content": "g2"},
    ]
    result = cdi.materialize_project(files, dest)  # must NOT raise
    assert result["files_written"] == ["good1.html", "nested/good2.html"]
    assert len(result["rejected"]) == 1
    assert result["rejected"][0]["path"] == "bad.html"
    assert "OSError" in result["rejected"][0]["error"] or "simulated" in result["rejected"][0]["error"]
    assert (dest / "good1.html").read_text(encoding="utf-8") == "g1"
    assert (dest / "nested" / "good2.html").read_text(encoding="utf-8") == "g2"


# Fix 3 — project_id extraction must survive a case-insensitive URL match.
def test_project_id_case_insensitive_url() -> None:
    offer = cdi.detect_claude_design_offer("CLAUDE.AI/DESIGN/P/AbC123")
    assert offer["detected"] is True
    assert offer["project_id"] == "AbC123"  # case preserved, not None


def test_parse_design_url_uppercase_host() -> None:
    parsed = cdi.parse_design_url("HTTPS://CLAUDE.AI/DESIGN/P/AbC123?file=x.html")
    assert parsed["project_id"] == "AbC123"
    assert parsed["file_selector"] == "x.html"


# Fix 4 — a bare `claude_design` substring must not fire a false mcp-mention.
def test_claude_design_substring_no_false_mention() -> None:
    offer = cdi.detect_claude_design_offer("my var claude_design_config = 1")
    assert offer["detected"] is False
    assert offer["trigger_forms"] == []


def test_claude_design_word_boundary_positive() -> None:
    for text in ("use the claude_design MCP", "the claude_design."):
        offer = cdi.detect_claude_design_offer(text)
        assert offer["detected"] is True, text
        assert "mcp-mention" in offer["trigger_forms"], text
