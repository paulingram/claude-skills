"""R5 (review-improvements): hooks/locks.py concurrency fixes.

Mirrors the threaded-stress style of tests/test_inflight_inbox_atomic.py.

Four concerns (REQ-R5 scenarios R5a-d):
  R5a — Identical-scope race: acquire_lock creates the lock with
        os.open(O_CREAT|O_EXCL|O_WRONLY). Two concurrent acquisitions of the
        SAME scope cannot both win; the loser is `blocked`, surfacing the
        holder. No silent overwrite of the holder's lock file. A stale lock at
        the same path is reclaimed via an atomic os.replace of a freshly-EXCL
        temp.
  R5b — Intersecting-scope race: after a successful EXCL write, acquire_lock
        re-scans the lock dir; if a live lock with an INTERSECTING (not
        identical) scope exists with an earlier (acquired_at, session-id
        tiebreak), the later acquirer releases its own lock and returns
        acquisition-failed naming the winner. Exactly one of two racing
        intersecting acquirers ends up holding a lock.
  R5c — globs_intersect prefix/suffix candidate class: ("src/**", "**/auth.py")
        intersect at src/auth.py and must return True in BOTH argument orders.
  R5d — stale-reclaim still works (an expired lock at an intersecting scope does
        not block; the new acquirer wins).

All tests are stdlib-only and must pass on Windows (no fcntl): the EXCL-create
primitive (os.open with O_EXCL) is the cross-platform atomicity mechanism, the
same family as the inbox test's os.replace.

This NEW file is the home for the concurrency assertions; tests/test_locks.py
(the REQ-3 scenario suite) is edited only for assertions that shifted under R5.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


# ---- Module loader (matches tests/test_locks.py) -----------------------------


@pytest.fixture(scope="module")
def locks_module(plugin_root: Path) -> ModuleType:
    path = plugin_root / "hooks" / "locks.py"
    assert path.exists(), f"locks.py missing at {path}"
    spec = importlib.util.spec_from_file_location("locks_module_concurrency", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _scope_lock_id(scope_glob: str) -> str:
    return hashlib.sha256(scope_glob.encode("utf-8")).hexdigest()


def _write_lock_with_age(
    locks_dir: Path,
    scope_glob: str,
    run_id: str,
    ttl_seconds: int,
    age_seconds: int,
) -> str:
    """Write a lock file by hand whose acquired_at is `age_seconds` in the past."""
    locks_dir.mkdir(parents=True, exist_ok=True)
    lock_id = _scope_lock_id(scope_glob)
    acquired = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    payload = {
        "holder": run_id,
        "scope_glob": scope_glob,
        "acquired_at": acquired.isoformat(),
        "ttl_seconds": ttl_seconds,
        "lock_id": lock_id,
    }
    (locks_dir / f"{lock_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return lock_id


# ---- R5a: identical-scope EXCL create ----------------------------------------


def test_identical_scope_existing_file_blocks_no_overwrite(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """A second acquire of the SAME scope is blocked and does NOT overwrite the
    holder's lock file (the holder name on disk is unchanged)."""
    a = locks_module.acquire_lock("src/auth/**", 14400, "run-A", locks_dir=tmp_path)
    assert a["status"] == "acquired"
    lock_file = tmp_path / f"{a['lock_id']}.json"
    before = json.loads(lock_file.read_text(encoding="utf-8"))

    b = locks_module.acquire_lock("src/auth/**", 14400, "run-B", locks_dir=tmp_path)
    assert b["status"] == "blocked"
    assert b["held_by"] == "run-A"

    after = json.loads(lock_file.read_text(encoding="utf-8"))
    assert after["holder"] == "run-A", "the holder's lock file was silently overwritten"
    assert after["acquired_at"] == before["acquired_at"]


def test_identical_scope_uses_excl_open(
    locks_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    """The lock file is created via os.open with O_EXCL (the no-overwrite
    primitive), not a plain write_text that would clobber an existing holder."""
    seen = {"excl": False}
    real_open = locks_module.os.open

    def _spy_open(path, flags, *args, **kwargs):
        if flags & locks_module.os.O_EXCL and flags & locks_module.os.O_CREAT:
            seen["excl"] = True
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(locks_module.os, "open", _spy_open)
    res = locks_module.acquire_lock("src/x/**", 60, "run-A", locks_dir=tmp_path)
    assert res["status"] == "acquired"
    assert seen["excl"], "acquire_lock did not create the lock with O_CREAT|O_EXCL"


def test_n_threads_same_scope_exactly_one_winner(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """N threads race to acquire the IDENTICAL scope. Exactly one wins; every
    other gets `blocked` surfacing the single winner. No thread sees a torn or
    overwritten lock file.

    RT-5: additionally asserts WINNER IDENTITY — the single on-disk lock's holder
    equals the run_id of the acquirer that returned `acquired`, not merely that
    one file exists. Pre-fix mechanism A (a loser os.replace-overwriting the
    in-flight winner) could leave count==1 with the on-disk holder rewritten to a
    LOSER; the count-only assert never caught that shape."""
    n = 24
    scope = "src/shared/**"
    # Track (run_id, result) so the winner's identity can be checked against the
    # on-disk holder — the count==1-but-wrong-holder variant (RT-5).
    results: list[tuple[str, dict]] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def _worker(idx: int) -> None:
        run_id = f"run-{idx}"
        try:
            barrier.wait()  # release all threads at the same instant
            r = locks_module.acquire_lock(scope, 14400, run_id, locks_dir=tmp_path)
            with results_lock:
                results.append((run_id, r))
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"a worker raised: {errors!r}"
    assert len(results) == n, "not every worker returned a result"

    acquired = [(rid, r) for rid, r in results if r.get("status") == "acquired"]
    blocked = [(rid, r) for rid, r in results if r.get("status") == "blocked"]
    assert len(acquired) == 1, (
        f"expected exactly ONE winner, got {len(acquired)} "
        f"(identical-scope overwrite race)"
    )
    assert len(blocked) == n - 1, "every loser must be blocked, not errored"

    # The single on-disk lock file names exactly one holder.
    lock_files = list(tmp_path.glob("*.json"))
    assert len(lock_files) == 1, f"expected ONE lock file, found {len(lock_files)}"
    holder = json.loads(lock_files[0].read_text(encoding="utf-8"))["holder"]
    # RT-5: the on-disk holder is the WINNING acquirer, not a loser whose reclaim
    # overwrote the in-flight winner's file.
    winner_run_id, winner_result = acquired[0]
    assert holder == winner_run_id, (
        f"on-disk holder {holder!r} is not the winning acquirer {winner_run_id!r} "
        f"(count==1 but the holder was overwritten by a loser)"
    )
    # Every blocked result surfaces that same holder.
    for _rid, r in blocked:
        assert r.get("held_by") == holder
    assert winner_result.get("lock_id") == _scope_lock_id(scope)


# ---- R5a: stale-lock reclaim via EXCL temp + os.replace ----------------------


def test_stale_identical_scope_is_reclaimed(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """An EXPIRED lock at the identical scope path is reclaimed: the new acquirer
    wins and the on-disk holder becomes the new run."""
    _write_lock_with_age(tmp_path, "src/auth/**", "run-old", 60, age_seconds=3600)
    res = locks_module.acquire_lock("src/auth/**", 14400, "run-new", locks_dir=tmp_path)
    assert res["status"] == "acquired", res
    lock_file = tmp_path / f"{res['lock_id']}.json"
    holder = json.loads(lock_file.read_text(encoding="utf-8"))["holder"]
    assert holder == "run-new", "stale identical-scope lock was not reclaimed"


def test_stale_reclaim_uses_atomic_replace(
    locks_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    """When a STALE lock survives to the EXCL-create moment (the tighter race the
    sweep does not pre-clean), the fresh lock is staged in a temp file and
    swapped in via the atomic os.replace — no destructive unlink-then-write
    window.

    To reach that branch deterministically we disable the pre-create sweep (which
    would otherwise delete the stale lock before EXCL ever sees it). The
    EXCL-create then hits FileExistsError, the lock is re-read + found expired,
    and _reclaim_stale_lock performs the os.replace swap. This is precisely the
    "a stale lock may be reclaimed via an atomic os.replace of a freshly-EXCL-
    created temp" path (REQ-R5a)."""
    _write_lock_with_age(tmp_path, "src/auth/**", "run-old", 60, age_seconds=3600)
    # Suppress the sweep so the stale lock is still on disk at EXCL-create time.
    monkeypatch.setattr(locks_module, "_sweep_stale", lambda _dir: None)

    seen = {"replace_called": False, "tmp_existed": False}
    real_replace = locks_module.os.replace

    def _spy_replace(src, dst):
        seen["replace_called"] = True
        seen["tmp_existed"] = Path(src).exists()
        return real_replace(src, dst)

    monkeypatch.setattr(locks_module.os, "replace", _spy_replace)
    res = locks_module.acquire_lock("src/auth/**", 14400, "run-new", locks_dir=tmp_path)
    assert res["status"] == "acquired", res
    assert seen["replace_called"], "stale reclaim did not use os.replace"
    assert seen["tmp_existed"], "no temp file was staged before the atomic replace"
    # The reclaimed lock now names the new holder.
    holder = json.loads(
        (tmp_path / f"{res['lock_id']}.json").read_text(encoding="utf-8")
    )["holder"]
    assert holder == "run-new"
    # No temp leftover survives the swap.
    leftovers = [p for p in tmp_path.glob("*") if ".tmp" in p.name]
    assert not leftovers, f"a temp leftover survived the reclaim: {leftovers}"


# ---- R5b: intersecting-scope race resolves to one winner ---------------------


def test_intersecting_scope_earlier_lock_wins_on_rescan(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """An EARLIER live lock with an intersecting (non-identical) scope wins: a
    later acquirer that passed its EXCL write re-scans, sees the earlier lock,
    releases its own, and returns blocked naming the earlier holder."""
    a = locks_module.acquire_lock("src/auth/**", 14400, "run-early", locks_dir=tmp_path)
    assert a["status"] == "acquired"
    # run-early is strictly earlier; the login scope intersects src/auth/**.
    b = locks_module.acquire_lock(
        "src/auth/login/**", 14400, "run-late", locks_dir=tmp_path
    )
    assert b["status"] == "blocked", b
    assert b["held_by"] == "run-early"
    # The late acquirer released its own lock — only the early lock survives.
    surviving = list(tmp_path.glob("*.json"))
    assert len(surviving) == 1
    holder = json.loads(surviving[0].read_text(encoding="utf-8"))["holder"]
    assert holder == "run-early"


def test_intersecting_scope_two_racers_exactly_one_holds(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """Two threads race with DIFFERENT-but-intersecting scopes. After the dust
    settles exactly one holds a lock; the other is blocked. (Both may EXCL-write
    their distinct hash-named files, then the post-write re-scan + tiebreak
    forces one to release.)"""
    scope_a = "src/auth/**"
    scope_b = "src/auth/login/**"  # intersects scope_a
    results: dict[str, dict] = {}
    results_lock = threading.Lock()
    barrier = threading.Barrier(2)
    errors: list[Exception] = []

    def _worker(name: str, scope: str) -> None:
        try:
            barrier.wait()
            r = locks_module.acquire_lock(scope, 14400, name, locks_dir=tmp_path)
            with results_lock:
                results[name] = r
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    t1 = threading.Thread(target=_worker, args=("run-1", scope_a))
    t2 = threading.Thread(target=_worker, args=("run-2", scope_b))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, f"a worker raised: {errors!r}"
    assert set(results) == {"run-1", "run-2"}
    statuses = sorted(r["status"] for r in results.values())
    assert statuses == ["acquired", "blocked"], (
        f"intersecting racers must resolve to one winner, got {statuses}"
    )
    surviving = list(tmp_path.glob("*.json"))
    assert len(surviving) == 1, (
        f"exactly one lock must survive an intersecting race, found {len(surviving)}"
    )


def test_intersecting_rescan_does_not_block_disjoint(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """The post-write re-scan must NOT spuriously release a lock when the other
    live locks are DISJOINT — disjoint scopes still both acquire."""
    a = locks_module.acquire_lock("src/auth/**", 14400, "run-A", locks_dir=tmp_path)
    b = locks_module.acquire_lock("src/billing/**", 14400, "run-B", locks_dir=tmp_path)
    assert a["status"] == "acquired"
    assert b["status"] == "acquired"
    assert len(list(tmp_path.glob("*.json"))) == 2


# ---- R5c: globs_intersect prefix/suffix candidate class ----------------------


def test_globs_intersect_leading_wildcard_vs_prefix_both_orders(
    locks_module: ModuleType,
) -> None:
    """("src/**", "**/auth.py") intersect at src/auth.py — True in both orders."""
    assert locks_module.globs_intersect("src/**", "**/auth.py") is True
    assert locks_module.globs_intersect("**/auth.py", "src/**") is True


@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("src/**", "**/auth.py", True),
        ("**/auth.py", "src/**", True),
        ("src/auth/**", "**/login.py", True),
        ("**/login.py", "src/auth/**", True),
        # prefix glob + suffix glob that share a deeper path.
        ("src/**", "**/auth.go", True),  # src/auth.go is a valid shared path
        ("docs/**", "**/auth.py", True),  # docs/auth.py shared path
        # A literal single-file prefix glob and a suffix glob that cannot match it.
        ("src/billing/charge.py", "**/auth.py", False),
        # identical still True.
        ("**/auth.py", "**/auth.py", True),
    ],
)
def test_globs_intersect_prefix_suffix_cases(
    locks_module: ModuleType, a: str, b: str, expected: bool
) -> None:
    assert locks_module.globs_intersect(a, b) is expected


def test_globs_intersect_preexisting_cases_unchanged(
    locks_module: ModuleType,
) -> None:
    """The new candidate class must not regress the documented headline cases."""
    assert locks_module.globs_intersect("src/auth/**", "src/auth/login/**") is True
    assert locks_module.globs_intersect("src/auth/**", "src/billing/**") is False
    assert locks_module.globs_intersect("src/*.py", "src/foo.py") is True
    assert locks_module.globs_intersect("src/*.py", "src/foo.ts") is False
    assert locks_module.globs_intersect("README.md", "README.md") is True
    assert locks_module.globs_intersect("README.md", "CHANGELOG.md") is False


# ---- R5d: stale-reclaim at intersecting scope still works --------------------


def test_stale_intersecting_lock_does_not_block(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """An expired lock at an INTERSECTING scope must not block the new acquire
    (the sweep removes it before the intersection check)."""
    _write_lock_with_age(tmp_path, "src/auth/**", "run-old", 60, age_seconds=7200)
    res = locks_module.acquire_lock(
        "src/auth/login/**", 14400, "run-new", locks_dir=tmp_path
    )
    assert res["status"] == "acquired", res
    surviving = list(tmp_path.glob("*.json"))
    assert len(surviving) == 1
    holder = json.loads(surviving[0].read_text(encoding="utf-8"))["holder"]
    assert holder == "run-new"


# ---- SR-locks-flake regression suite (atomic-publish + grace-guard fallback) --
#
# Root cause (diagnostic-plan-20260706T0125Z): acquire_lock published the lock
# NON-ATOMICALLY (os.open EXCL creates a 0-byte file, os.write fills it in a
# SEPARATE syscall). During that empty window two destroyers manufactured extra
# winners — _sweep_stale DELETED the empty file (freeing the path for a second
# EXCL create) and the Step-3 reclaim branch OVERWROTE it. The fix publishes
# atomically via a per-acquirer temp + os.link (primary path) with an
# EXCL-create-then-write + _is_inflight grace-guard fallback for no-hardlink
# filesystems. These tests deterministically provoke the OLD bug shape and pin
# the fix + the fallback + the grace semantics.


def _race_identical_scope(
    locks_module: ModuleType, locks_dir: Path, n: int = 24, scope: str = "src/shared/**"
) -> tuple[list[dict], list[Exception]]:
    """Run the N-thread identical-scope race once; return (results, errors)."""
    results: list[dict] = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(n)
    errors: list[Exception] = []

    def _worker(idx: int) -> None:
        try:
            barrier.wait()
            r = locks_module.acquire_lock(
                scope, 14400, f"run-{idx}", locks_dir=locks_dir
            )
            with results_lock:
                results.append(r)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)
    return results, errors


def test_rt1_widened_window_primary_path_exactly_one_winner(
    locks_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    """RT-1 (PRIMARY, deterministic widened-window falsification). With the
    create->write window WIDENED (os.write sleeps 10ms), the 24-thread
    identical-scope race must still yield EXACTLY ONE winner on the atomic
    os.link publish path — the widened sleep now lands inside the (unscanned)
    temp's write and the os.link publish is atomic. Pre-fix this reliably
    produced 2+ winners; the loop makes a residual surface deterministically."""
    real_write = locks_module.os.write

    def slow_write(fd, data):
        time.sleep(0.010)  # de-schedule between temp create and its write
        return real_write(fd, data)

    monkeypatch.setattr(locks_module.os, "write", slow_write)

    for iteration in range(10):
        d = tmp_path / f"it{iteration}"
        d.mkdir()
        results, errors = _race_identical_scope(locks_module, d)
        assert not errors, f"iter {iteration}: a worker raised: {errors!r}"
        acquired = [r for r in results if r.get("status") == "acquired"]
        assert len(acquired) == 1, (
            f"iter {iteration}: widened-window race produced {len(acquired)} "
            f"winners (expected exactly 1 on the atomic os.link path)"
        )
        assert len(list(d.glob("*.json"))) == 1, (
            f"iter {iteration}: expected exactly one lock file on disk"
        )
        # No in-flight temp leftover survives a settled race.
        assert not [p for p in d.glob("*") if ".tmp" in p.name], (
            f"iter {iteration}: an .tmp leftover survived"
        )


def test_rt2_fallback_no_hardlink_exactly_one_winner(
    locks_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    """RT-2 (FALLBACK path). Force the no-hardlink filesystem by making os.link
    raise OSError, so publish falls back to EXCL-create-then-write (a residual
    empty window). Under the widened window the _is_inflight grace guards on
    BOTH destroyers must still hold exactly-one-winner. Without this test the
    entire fallback + grace-guard layer is unexercised on a hardlink-capable CI
    filesystem (RT-1 always takes the primary path there)."""
    real_write = locks_module.os.write

    def slow_write(fd, data):
        time.sleep(0.008)
        return real_write(fd, data)

    def no_hardlink(src, dst):
        raise OSError("forced: hardlinks unsupported on this filesystem")

    monkeypatch.setattr(locks_module.os, "write", slow_write)
    monkeypatch.setattr(locks_module.os, "link", no_hardlink)

    for iteration in range(8):
        d = tmp_path / f"it{iteration}"
        d.mkdir()
        results, errors = _race_identical_scope(locks_module, d)
        assert not errors, f"iter {iteration}: a worker raised: {errors!r}"
        acquired = [r for r in results if r.get("status") == "acquired"]
        assert len(acquired) == 1, (
            f"iter {iteration}: fallback race produced {len(acquired)} winners "
            f"(the _is_inflight grace guards failed to hold the invariant)"
        )
        assert len(list(d.glob("*.json"))) == 1, (
            f"iter {iteration}: expected exactly one lock file on disk"
        )
        assert not [p for p in d.glob("*") if ".tmp" in p.name], (
            f"iter {iteration}: an .tmp leftover survived the fallback publish"
        )


def test_rt3_inflight_empty_file_blocks_not_reclaimed(
    locks_module: ModuleType, tmp_path: Path, monkeypatch
) -> None:
    """RT-3 (deterministic mechanism-A guard; post-fix inverse of pre-fix item 4).
    An empty (mid-write) in-flight lock file at the path must be treated as a
    LIVE holder: acquire_lock returns `blocked` and does NOT overwrite it. Reclaim
    is reserved for a lock that parses AND is expired, or an aged empty orphan."""
    scope = "src/shared/**"
    lock_id = locks_module._hash_scope(scope)
    lock_path = tmp_path / f"{lock_id}.json"
    lock_path.write_text("")  # winner os.open'd but has not yet written its payload
    # Model the sweep having already run before the winner created the file.
    monkeypatch.setattr(locks_module, "_sweep_stale", lambda _dir: None)

    res = locks_module.acquire_lock(scope, 14400, "run-loser", locks_dir=tmp_path)
    assert res["status"] == "blocked", res
    # The in-flight file was NOT overwritten by the losing acquirer.
    assert lock_path.read_text(encoding="utf-8") == "", (
        "the in-flight (empty) lock file was overwritten by a losing acquirer"
    )
    assert list(tmp_path.glob("*.json")) == [lock_path]


def test_rt4_sweep_grace_keeps_recent_empty_sweeps_aged_orphan(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """RT-4 (mechanism-B guard + crash-orphan recovery). (a) _sweep_stale must
    KEEP a recent empty in-flight file. (b) An empty file older than
    _INFLIGHT_GRACE_SECONDS is a genuine crash orphan and MUST be swept."""
    scope = "src/shared/**"
    lock_id = locks_module._hash_scope(scope)
    lock_path = tmp_path / f"{lock_id}.json"

    # (a) a recently-written empty file survives the sweep (in-flight).
    lock_path.write_text("")
    locks_module._sweep_stale(tmp_path)
    assert lock_path.exists(), "a recent empty in-flight file was wrongly swept"

    # (b) backdate its mtime beyond the grace window -> swept as a crash orphan.
    old = time.time() - (locks_module._INFLIGHT_GRACE_SECONDS + 5.0)
    os.utime(lock_path, (old, old))
    locks_module._sweep_stale(tmp_path)
    assert not lock_path.exists(), (
        "an aged empty crash-orphan (older than the grace window) was not swept"
    )
