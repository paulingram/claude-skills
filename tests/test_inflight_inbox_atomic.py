"""A4 (review-remediation): hooks/inflight_inbox.py mark_processed rewrites the
inbox atomically (temp file + os.replace) and `run_id` is validated through
`safe_id` before it reaches the inbox filename.

Two concerns:
  1. Atomicity — a concurrent `/architect-team:inject` append (the feature's
     headline cross-terminal use case) must NOT be destroyed by a mark_processed
     rewrite, and a crash mid-write must leave the original inbox intact. The
     fix is temp-file + os.replace (atomic on POSIX and Windows), mirroring
     hooks/run_metrics.py:184-186.
  2. Path-traversal — a `run_id` containing '/', '\\', a leading '.', or the
     exact '..' is rejected via safe_id so a crafted id cannot escape the
     inbox directory.

The pre-existing tests/test_vao_inflight_clarifications.py is NOT touched
(pin c); these atomic/safe_id tests live in this dedicated NEW file.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from hooks.inflight_inbox import (
    _inbox_path,
    append_clarification,
    inbox_path_for,
    mark_processed,
    read_inbox,
    unprocessed_messages,
)


# ---- safe_id path-traversal rejection ----------------------------------------


@pytest.mark.parametrize(
    "bad_run_id",
    ["../escape", "a/b", "a\\b", "..", ".hidden", "", "../../etc/passwd"],
)
def test_inbox_path_rejects_unsafe_run_id(tmp_path: Path, bad_run_id: str) -> None:
    with pytest.raises(ValueError):
        _inbox_path(tmp_path, bad_run_id)


@pytest.mark.parametrize("good_run_id", ["run-1", "2026-06-09-foo", "abc_DEF-123"])
def test_inbox_path_accepts_safe_run_id(tmp_path: Path, good_run_id: str) -> None:
    p = _inbox_path(tmp_path, good_run_id)
    assert p.name == f"{good_run_id}.jsonl"
    assert ".architect-team" in str(p)


def test_append_with_unsafe_run_id_raises(tmp_path: Path) -> None:
    """The write path surfaces a traversal attempt as the ValueError it is."""
    with pytest.raises(ValueError):
        append_clarification(tmp_path, "../evil", "hello")


def test_read_inbox_with_unsafe_run_id_returns_empty(tmp_path: Path) -> None:
    """The read path degrades to not-found (empty list), never raises."""
    assert read_inbox(tmp_path, "../evil") == []
    assert unprocessed_messages(tmp_path, "../evil") == []


def test_mark_processed_with_unsafe_run_id_returns_none(tmp_path: Path) -> None:
    """mark_processed degrades to not-found (None) on a bad id, never raises."""
    assert (
        mark_processed(
            tmp_path,
            "../evil",
            "mid",
            classification="clarification",
            action_taken="x",
        )
        is None
    )


def test_unsafe_run_id_never_writes_outside_inbox(tmp_path: Path) -> None:
    """No file is created outside the inbox dir for a traversal id."""
    sentinel = tmp_path / "evil.jsonl"
    with pytest.raises(ValueError):
        append_clarification(tmp_path, "../evil", "hello")
    assert not sentinel.exists()


# ---- atomic rewrite ----------------------------------------------------------


def test_mark_processed_updates_target_message(tmp_path: Path) -> None:
    run_id = "run-atomic"
    m1 = append_clarification(tmp_path, run_id, "first message")
    m2 = append_clarification(tmp_path, run_id, "second message")
    updated = mark_processed(
        tmp_path, run_id, m1["message_id"],
        classification="clarification", action_taken="handled",
    )
    assert updated is not None
    assert updated["processed_at"] is not None
    assert updated["classification"] == "clarification"
    assert updated["action_taken"] == "handled"
    # The OTHER message is untouched.
    msgs = {m["message_id"]: m for m in read_inbox(tmp_path, run_id)}
    assert msgs[m2["message_id"]]["processed_at"] is None
    assert len(msgs) == 2


def test_mark_processed_leaves_no_tmp_file_behind(tmp_path: Path) -> None:
    """os.replace consumes the temp file; no `<run-id>.jsonl.tmp` survives."""
    run_id = "run-tmp"
    m1 = append_clarification(tmp_path, run_id, "msg")
    mark_processed(
        tmp_path, run_id, m1["message_id"],
        classification="clarification", action_taken="ok",
    )
    inbox = inbox_path_for(tmp_path, run_id)
    tmp_leftover = inbox.with_suffix(inbox.suffix + ".tmp")
    assert not tmp_leftover.exists(), "a .tmp leftover means the rewrite was not atomic"
    # The file is valid JSONL.
    for line in inbox.read_text(encoding="utf-8").splitlines():
        if line.strip():
            json.loads(line)


def test_mark_processed_uses_os_replace(tmp_path: Path, monkeypatch) -> None:
    """Assert the rewrite goes through os.replace (the atomicity primitive) and
    that a temp file is written first."""
    run_id = "run-osreplace"
    m1 = append_clarification(tmp_path, run_id, "msg")

    seen = {"replace_called": False, "tmp_existed_before_replace": False}
    real_replace = os.replace

    def _spy_replace(src, dst):
        seen["replace_called"] = True
        seen["tmp_existed_before_replace"] = Path(src).exists()
        return real_replace(src, dst)

    monkeypatch.setattr("hooks.inflight_inbox.os.replace", _spy_replace)
    mark_processed(
        tmp_path, run_id, m1["message_id"],
        classification="clarification", action_taken="ok",
    )
    assert seen["replace_called"], "mark_processed did not use os.replace (not atomic)"
    assert seen["tmp_existed_before_replace"], "a temp file was not written before replace"


def test_inbox_lock_rides_out_windows_permission_error(tmp_path: Path, monkeypatch) -> None:
    """v3.26.0 flake fix: on Windows a concurrent holder mid-`unlink` makes
    `os.open(O_CREAT|O_EXCL)` on the `.lock` raise PermissionError (not
    FileExistsError). `_inbox_lock` must treat it as transient contention and
    retry, never crash the caller (the failure surfaced as a PermissionError out
    of `mark_processed` under full-suite CPU contention)."""
    import hooks.inflight_inbox as ib

    run_id = "run-permerr"
    m1 = append_clarification(tmp_path, run_id, "msg")
    real_open = os.open
    calls = {"n": 0}

    def _flaky_open(path, flags, *a, **k):
        # raise PermissionError on the FIRST lock-acquire attempt, then succeed
        if str(path).endswith(".lock") and calls["n"] == 0:
            calls["n"] += 1
            raise PermissionError(13, "Permission denied")
        return real_open(path, flags, *a, **k)

    monkeypatch.setattr("hooks.inflight_inbox.os.open", _flaky_open)
    updated = ib.mark_processed(
        tmp_path, run_id, m1["message_id"],
        classification="clarification", action_taken="ok",
    )
    assert updated is not None and calls["n"] == 1  # retried past the PermissionError, did not crash


def test_concurrent_append_survives_mark_processed(tmp_path: Path) -> None:
    """Stress test the atomicity: a thread hammers append_clarification while the
    main thread repeatedly marks messages processed. Because mark_processed
    swaps the file via os.replace, no appended line is ever lost or truncated.

    We assert at the end that EVERY message_id ever appended is present in the
    final inbox exactly once and that every line parses as JSON (never a
    truncated half-write).
    """
    run_id = "run-concurrent"
    # Seed a message we will repeatedly mark.
    seed = append_clarification(tmp_path, run_id, "seed")

    appended_ids: list[str] = []
    appended_lock = threading.Lock()
    stop = threading.Event()
    errors: list[Exception] = []

    def _appender() -> None:
        i = 0
        while not stop.is_set():
            try:
                m = append_clarification(tmp_path, run_id, f"concurrent-{i}")
                with appended_lock:
                    appended_ids.append(m["message_id"])
                i += 1
            except Exception as e:  # noqa: BLE001
                errors.append(e)
                return

    t = threading.Thread(target=_appender, daemon=True)
    t.start()
    try:
        # Repeatedly rewrite the file while appends are landing.
        for _ in range(60):
            mark_processed(
                tmp_path, run_id, seed["message_id"],
                classification="clarification", action_taken="loop",
            )
    finally:
        stop.set()
        t.join(timeout=5)

    assert not errors, f"appender raised: {errors!r}"

    # Final inbox must parse cleanly line-by-line (no truncated half-writes).
    inbox = inbox_path_for(tmp_path, run_id)
    parsed_ids = []
    for line in inbox.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s:
            continue
        obj = json.loads(s)  # raises on any truncated line
        parsed_ids.append(obj["message_id"])

    # Every appended id (plus the seed) survived exactly once.
    expected = set(appended_ids) | {seed["message_id"]}
    present = set(parsed_ids)
    missing = expected - present
    assert not missing, (
        f"{len(missing)} concurrently-appended message(s) were LOST by the "
        f"mark_processed rewrite — the rewrite is not atomic. missing={list(missing)[:5]}"
    )
    # No duplicates either.
    assert len(parsed_ids) == len(present), "duplicate message ids in the inbox"
