"""Tests for the Mini-Run: <slug> commit-trailer extractor.

Used by the mini-pipeline orchestrator and the future mini-review-sweep
command to identify and group commits produced by mini runs.
"""
from __future__ import annotations

from tests.helpers import mini_run_trailer


def test_extract_returns_slug_when_present():
    msg = """mini: add bulk export

Bulk export endpoint and Export button on dashboard.

Mini-Run: 2026-05-26-add-bulk-export
Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-add-bulk-export"


def test_extract_returns_none_when_absent():
    msg = "fix: typo in README\n\nNo trailer.\n"
    assert mini_run_trailer.extract(msg) is None


def test_extract_ignores_mention_in_body():
    msg = """feat: docs about Mini-Run: trailers

The Mini-Run: convention is documented here.
"""
    # The trailer must be on its own line in the trailer block; mention in prose doesn't count.
    assert mini_run_trailer.extract(msg) is None


def test_extract_handles_trailer_before_other_trailers():
    msg = """mini: foo

Mini-Run: 2026-05-26-foo
Signed-off-by: someone <a@b.c>
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-foo"


def test_extract_handles_trailer_after_other_trailers():
    msg = """mini: foo

Signed-off-by: someone <a@b.c>
Mini-Run: 2026-05-26-foo
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-foo"


def test_group_by_slug():
    commits = [
        ("sha-1", "mini: a\n\nMini-Run: 2026-05-26-foo\n"),
        ("sha-2", "mini: b\n\nMini-Run: 2026-05-26-foo\n"),
        ("sha-3", "fix: c\n\n(no trailer)\n"),
        ("sha-4", "mini: d\n\nMini-Run: 2026-05-26-bar\n"),
    ]
    groups = mini_run_trailer.group_by_slug(commits)
    assert groups == {
        "2026-05-26-foo": ["sha-1", "sha-2"],
        "2026-05-26-bar": ["sha-4"],
    }


def test_validate_slug_format():
    # Slug pattern: YYYY-MM-DD-<lowercase-kebab>
    assert mini_run_trailer.is_valid_slug("2026-05-26-add-bulk-export")
    assert not mini_run_trailer.is_valid_slug("2026-5-26-foo")          # zero-padding required
    assert not mini_run_trailer.is_valid_slug("Add-Bulk-Export")        # no date prefix
    assert not mini_run_trailer.is_valid_slug("2026-05-26-Add_Export")  # underscore + uppercase


def test_extract_returns_last_when_multiple_trailers():
    """When multiple Mini-Run: trailers exist (e.g. a re-commit that
    accumulates trailers), the LAST one wins — matches Git interpret-
    trailers convention for repeated tokens.
    """
    msg = """mini: foo

Mini-Run: 2026-05-26-stale-original-slug
Co-Authored-By: someone <a@b.c>
Mini-Run: 2026-05-26-final-slug
"""
    assert mini_run_trailer.extract(msg) == "2026-05-26-final-slug"
