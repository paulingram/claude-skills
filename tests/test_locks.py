"""REQ-3: Cross-session lock layer — scenarios 3.1 through 3.6.

Exercises `hooks/locks.py`:
  - acquire_lock(scope_glob, ttl_seconds, run_id, locks_dir=None) -> dict
  - release_lock(lock_id, locks_dir=None) -> None
  - detect_stale(locks_dir=None) -> list[str]
  - globs_intersect(a, b) -> bool

Each scenario uses tmp_path for isolation (no global side-effects).

Scenarios from spec.md REQ-3:
  3.1 acquire writes a lock file
  3.2 overlapping scope is blocked
  3.3 disjoint scope acquires cleanly
  3.4 stale lock is detected and released
  3.5 release frees the scope
  3.6 malformed lock file is treated as stale
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType

import pytest


# ---- Module loader -----------------------------------------------------------


@pytest.fixture(scope="module")
def locks_module(plugin_root: Path) -> ModuleType:
    """Load hooks/locks.py via importlib (matches setup_script test pattern)."""
    path = plugin_root / "hooks" / "locks.py"
    assert path.exists(), f"locks.py missing at {path}"
    spec = importlib.util.spec_from_file_location("locks_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---- Scenario 3.1: acquire writes a lock file --------------------------------


def test_acquire_lock_writes_file_with_required_fields(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    result = locks_module.acquire_lock(
        scope_glob="src/auth/**",
        ttl_seconds=14400,
        run_id="run-1",
        locks_dir=tmp_path,
    )
    assert result["status"] == "acquired"
    lock_id = result["lock_id"]
    assert isinstance(lock_id, str) and lock_id

    lock_file = tmp_path / f"{lock_id}.json"
    assert lock_file.is_file()
    payload = json.loads(lock_file.read_text(encoding="utf-8"))
    assert payload["holder"] == "run-1"
    assert payload["scope_glob"] == "src/auth/**"
    assert isinstance(payload["acquired_at"], str)
    assert payload["ttl_seconds"] == 14400
    assert payload["lock_id"] == lock_id


def test_acquire_lock_creates_dir_when_missing(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """The locks dir is created on demand — no manual mkdir required."""
    locks_dir = tmp_path / "deep" / "locks"
    assert not locks_dir.exists()
    result = locks_module.acquire_lock(
        scope_glob="src/x/**",
        ttl_seconds=60,
        run_id="run-A",
        locks_dir=locks_dir,
    )
    assert result["status"] == "acquired"
    assert locks_dir.is_dir()


# ---- Scenario 3.2: overlapping scope is blocked -----------------------------


def test_overlapping_scope_blocks_second_acquirer(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    a = locks_module.acquire_lock("src/auth/**", 14400, "run-A", locks_dir=tmp_path)
    assert a["status"] == "acquired"

    b = locks_module.acquire_lock("src/auth/login/**", 14400, "run-B", locks_dir=tmp_path)
    assert b["status"] == "blocked"
    assert b["held_by"] == "run-A"


def test_same_scope_blocks_second_acquirer(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    locks_module.acquire_lock("src/billing/**", 60, "run-A", locks_dir=tmp_path)
    b = locks_module.acquire_lock("src/billing/**", 60, "run-B", locks_dir=tmp_path)
    assert b["status"] == "blocked"
    assert b["held_by"] == "run-A"


def test_globs_intersect_identifies_overlap(locks_module: ModuleType) -> None:
    """The intersection check is the hard primitive — verify the headline cases."""
    assert locks_module.globs_intersect("src/auth/**", "src/auth/login/**") is True
    assert locks_module.globs_intersect("src/auth/login/**", "src/auth/**") is True
    assert locks_module.globs_intersect("src/**", "src/anything/here.py") is True
    assert locks_module.globs_intersect("src/auth/**", "src/auth/**") is True


# ---- Scenario 3.3: disjoint scope acquires cleanly --------------------------


def test_disjoint_scopes_both_acquire(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    a = locks_module.acquire_lock("src/auth/**", 60, "run-A", locks_dir=tmp_path)
    b = locks_module.acquire_lock("src/billing/**", 60, "run-B", locks_dir=tmp_path)
    assert a["status"] == "acquired"
    assert b["status"] == "acquired"
    assert a["lock_id"] != b["lock_id"]


def test_globs_intersect_rejects_disjoint(locks_module: ModuleType) -> None:
    assert locks_module.globs_intersect("src/auth/**", "src/billing/**") is False
    assert locks_module.globs_intersect("a/b/**", "c/d/**") is False


# ---- Scenario 3.4: stale lock is detected and released ----------------------


def _write_lock_with_age(
    tmp_path: Path,
    scope_glob: str,
    run_id: str,
    ttl_seconds: int,
    age_seconds: int,
) -> str:
    """Write a lock file by hand whose acquired_at is `age_seconds` in the past.

    Returns the lock id (sha256 of scope_glob).
    """
    import hashlib

    tmp_path.mkdir(parents=True, exist_ok=True)
    lock_id = hashlib.sha256(scope_glob.encode("utf-8")).hexdigest()
    acquired = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
    payload = {
        "holder": run_id,
        "scope_glob": scope_glob,
        "acquired_at": acquired.isoformat(),
        "ttl_seconds": ttl_seconds,
        "lock_id": lock_id,
    }
    (tmp_path / f"{lock_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return lock_id


def test_detect_stale_reports_expired_lock(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    fresh_id = _write_lock_with_age(tmp_path, "src/fresh/**", "run-X", 14400, age_seconds=60)
    stale_id = _write_lock_with_age(tmp_path, "src/stale/**", "run-Y", 60, age_seconds=3600)

    stale_ids = locks_module.detect_stale(locks_dir=tmp_path)
    assert stale_id in stale_ids
    assert fresh_id not in stale_ids


def test_stale_lock_is_auto_released_on_acquire(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """An expired lock should not block a subsequent acquire of an intersecting scope."""
    _write_lock_with_age(tmp_path, "src/auth/**", "run-old", 60, age_seconds=3600)
    result = locks_module.acquire_lock(
        "src/auth/login/**", 14400, "run-new", locks_dir=tmp_path
    )
    assert result["status"] == "acquired", result


def test_detect_stale_returns_empty_when_dir_missing(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """A missing locks dir is the no-locks case, not an error."""
    missing = tmp_path / "no-such-dir"
    assert locks_module.detect_stale(locks_dir=missing) == []


# ---- Scenario 3.5: release frees the scope ----------------------------------


def test_release_lock_removes_file_and_unblocks(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    a = locks_module.acquire_lock("src/auth/**", 60, "run-A", locks_dir=tmp_path)
    lock_id = a["lock_id"]
    assert (tmp_path / f"{lock_id}.json").is_file()

    locks_module.release_lock(lock_id, locks_dir=tmp_path)
    assert not (tmp_path / f"{lock_id}.json").exists()

    b = locks_module.acquire_lock("src/auth/**", 60, "run-B", locks_dir=tmp_path)
    assert b["status"] == "acquired"


def test_release_lock_is_idempotent(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """Releasing a missing lock id is a no-op, not an error."""
    locks_module.release_lock("does-not-exist", locks_dir=tmp_path)
    # No assertion needed — must not raise.


# ---- Scenario 3.6: malformed lock file is treated as stale ------------------


def test_malformed_lock_file_is_treated_as_stale(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """A corrupt JSON file in the locks dir should be removed by acquire and not block."""
    bad_path = tmp_path / "bad-lock.json"
    bad_path.write_text("{not valid", encoding="utf-8")

    # detect_stale should include it.
    stale = locks_module.detect_stale(locks_dir=tmp_path)
    assert "bad-lock" in stale or any(s.startswith("bad-lock") for s in stale)


def test_lock_missing_required_fields_is_stale(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """A JSON-parseable lock file missing fields is treated as stale."""
    import hashlib

    tmp_path.mkdir(parents=True, exist_ok=True)
    lock_id = hashlib.sha256(b"src/x/**").hexdigest()
    (tmp_path / f"{lock_id}.json").write_text(json.dumps({"holder": "run-Z"}), encoding="utf-8")

    stale = locks_module.detect_stale(locks_dir=tmp_path)
    assert lock_id in stale


def test_malformed_lock_does_not_block_acquire(
    locks_module: ModuleType, tmp_path: Path
) -> None:
    """A malformed lock file at the target scope's path should not block a new acquire."""
    import hashlib

    tmp_path.mkdir(parents=True, exist_ok=True)
    lock_id = hashlib.sha256(b"src/auth/**").hexdigest()
    (tmp_path / f"{lock_id}.json").write_text("not json at all", encoding="utf-8")

    result = locks_module.acquire_lock("src/auth/**", 60, "run-A", locks_dir=tmp_path)
    assert result["status"] == "acquired"


# ---- globs_intersect edge cases ---------------------------------------------


def test_globs_intersect_handles_simple_literal_match(locks_module: ModuleType) -> None:
    assert locks_module.globs_intersect("README.md", "README.md") is True
    assert locks_module.globs_intersect("README.md", "CHANGELOG.md") is False


def test_globs_intersect_handles_star_match(locks_module: ModuleType) -> None:
    assert locks_module.globs_intersect("src/*.py", "src/foo.py") is True
    assert locks_module.globs_intersect("src/*.py", "src/foo.ts") is False
