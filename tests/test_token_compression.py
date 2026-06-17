"""Tests for the v3.22.0 token-compression engine (TC-1 … TC-3).

Covers the deterministic machine `scripts/token_compression/caveman.py`: the
meaning-preserving caveman `compress` (filler drop + phrase subs + code/structure
preservation), `estimate_tokens`, `compression_stats`, the CLI, and the skill
contract surface (incl. the hard internal-only boundary).
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "token_compression" / "caveman.py"

_spec = importlib.util.spec_from_file_location("caveman", MODULE_PATH)
cv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cv)  # type: ignore[union-attr]


# --------------------------------------------------------------------------- #
# compress
# --------------------------------------------------------------------------- #

def test_drops_filler_keeps_content() -> None:
    out = cv.compress("Please just read the very important config file 42 now")
    low = out.lower()
    # filler dropped
    for f in ("please", "just", "the", "very"):
        assert f not in low.split()
    # content words + the number preserved
    assert "read" in low and "important" in low and "config" in low and "42" in out


def test_preserves_prepositions_and_copulas() -> None:
    out = cv.compress("the value is in the map of results").lower().split()
    # meaning-bearing function words are kept (only articles dropped)
    assert "is" in out and "in" in out and "of" in out
    assert "the" not in out


def test_preserves_inline_and_fenced_code_verbatim() -> None:
    src = "the helper `the_value` does x\n```\nthe quick brown fox\n```\nplease run it"
    out = cv.compress(src)
    assert "`the_value`" in out          # inline code preserved (the_value kept)
    assert "the quick brown fox" in out  # fenced code preserved verbatim
    # prose 'the'/'please' outside code are dropped
    assert "please" not in out.lower().split()


def test_preserves_line_structure() -> None:
    out = cv.compress("the first line\nthe second line")
    assert out.count("\n") == 1  # newline preserved
    assert out == "first line\nsecond line"


def test_phrase_substitutions() -> None:
    assert "to" in cv.compress("do this in order to win").lower().split()
    assert "in order to" not in cv.compress("do this in order to win").lower()
    assert "because" in cv.compress("failed due to the fact that x").lower().split()


def test_compress_empty_is_safe() -> None:
    assert cv.compress("") == ""
    assert cv.compress(None) == ""  # type: ignore[arg-type]


def test_boundary_space_preserved_around_code() -> None:
    # prose words must not glue to an adjacent code span when rejoined
    out = cv.compress("run the `cmd` now please")
    assert "`cmd`" in out
    assert "`cmd`now" not in out  # a space survives on each side of the code span
    assert "run `cmd` now" == out


def test_unbalanced_backticks_do_not_crash() -> None:
    # an odd/trailing backtick must not raise; prose still compresses
    out = cv.compress("the value `x and the rest")
    assert "value" in out  # no crash, content preserved


def test_compress_to_nothing_ratio() -> None:
    s = cv.compression_stats("the a an please just very")  # all filler
    assert s["compressed_text"].strip() == ""
    assert s["compressed_tokens_est"] == 0
    assert s["ratio"] == 0.0 and s["saved_pct"] == 100.0


# --------------------------------------------------------------------------- #
# estimate_tokens + stats
# --------------------------------------------------------------------------- #

def test_estimate_tokens() -> None:
    assert cv.estimate_tokens("") == 0
    assert cv.estimate_tokens("   ") == 0
    assert cv.estimate_tokens("abcd") >= 1
    # monotonic-ish: longer text -> more tokens
    assert cv.estimate_tokens("a" * 400) > cv.estimate_tokens("a" * 40)


def test_compression_stats_reports_savings() -> None:
    text = "Please just read the very important configuration file in order to proceed"
    s = cv.compression_stats(text)
    assert s["schema"] == "token-compression-stats/v1"
    assert s["compressed_chars"] < s["original_chars"]   # actually shorter
    assert s["compressed_tokens_est"] <= s["original_tokens_est"]
    assert 0.0 <= s["ratio"] <= 1.0
    assert s["saved_pct"] >= 0.0
    assert "configuration" in s["compressed_text"]  # content preserved


def test_stats_on_empty_is_neutral() -> None:
    s = cv.compression_stats("")
    assert s["ratio"] == 1.0 and s["saved_pct"] == 0.0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def test_cli_compress_stdin() -> None:
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "compress"],
        input="please read the very long file", capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    assert "please" not in res.stdout.lower().split()
    assert "read" in res.stdout.lower() and "file" in res.stdout.lower()


def test_cli_stats_json(tmp_path: Path) -> None:
    f = tmp_path / "in.txt"
    f.write_text("Please just read the very important file", encoding="utf-8")
    res = subprocess.run(
        [sys.executable, str(MODULE_PATH), "stats", "--input", str(f), "--json"],
        capture_output=True, text=True, timeout=60,
    )
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["schema"] == "token-compression-stats/v1"
    assert payload["compressed_tokens_est"] <= payload["original_tokens_est"]


# --------------------------------------------------------------------------- #
# the skill contract surface
# --------------------------------------------------------------------------- #

def test_skill_present_and_documents_tc() -> None:
    body = (REPO_ROOT / "skills" / "token-compression" / "SKILL.md").read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "caveman.py" in body
    for tag in ("TC-1", "TC-2", "TC-3"):
        assert tag in body
    # the hard internal-only boundary (TC-1) is stated
    low = body.lower()
    assert "internal" in low and "external" in low
    assert "never compress external" in low or "never apply it to external" in low
