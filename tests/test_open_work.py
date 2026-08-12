"""Unit tests for hooks/open_work.py — the completion-lock open-work substrate.

The four properties these tests exist to hold (design.md + the approved
interface contract at `.architect-team/contracts/open-work-api.md`):

1. Source-read failures are DATA (``unreadable[]``), never exceptions — that
   split is what lets the caller BLOCK-and-name a corrupt store (REQ-6)
   instead of reading it as empty and sailing through.
2. The ask-ledger ACCUMULATES. ``run_continuity.load_transcript_slices`` is
   tail-capped, so a re-derivation pass on a long session cannot see the
   earliest directives — the ones most likely still unfinished. A stored entry
   is never removed, reopened, or downgraded by a pass that could not see its
   originating turn.
3. The turn-output classifier is pinned in BOTH directions. A rule that never
   fires is decoration; a rule that fires on a legitimate terse status update
   gets disabled by the user, which is the same as not shipping it.
4. Unknown status counts as OPEN. Unknown state is not "done".

TEST SEAM. The real harness task store is ``~/.claude/tasks/``. No test here
may read or write it: every reader takes an injected root, and the autouse
``_sandbox_tasks_root`` fixture below points the env fallback at a nonexistent
sandbox so even a forgotten injection cannot reach the developer's real store
(the same global-hermeticity pattern as conftest's ``_scrub_plugin_registry``).
"""
import json
from pathlib import Path

import pytest

from hooks import open_work as ow
from hooks import run_continuity as rc


@pytest.fixture(autouse=True)
def _sandbox_tasks_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let a test fall through to the developer's real ~/.claude/tasks."""
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "__no-real-task-store__"))


@pytest.fixture(autouse=True)
def _clear_killswitches(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kill-switches off unless a test sets one (ambient env must not leak in)."""
    for var in (
        "CT6_COMPLETION_LOCK_DISABLED",
        "CT6_TASK_LIST_GATE_DISABLED",
        "CT6_ASK_LEDGER_GATE_DISABLED",
        "CT6_TURN_OUTPUT_GATE_DISABLED",
    ):
        monkeypatch.delenv(var, raising=False)


# --- transcript record builders (the harness JSONL shape) --------------------

def _user(text: str, ts: str = "2026-08-12T10:00:00Z", **extra) -> dict:
    rec = {"type": "user", "timestamp": ts,
           "message": {"role": "user", "content": text}}
    rec.update(extra)
    return rec


def _assistant(text: str, ts: str = "2026-08-12T10:01:00Z") -> dict:
    return {"type": "assistant", "timestamp": ts,
            "message": {"role": "assistant",
                        "content": [{"type": "text", "text": text}]}}


# =============================================================================
# Group 2 — the ask-ledger. Accumulation is the load-bearing property.
# =============================================================================

def test_stored_entry_survives_a_pass_that_cannot_see_its_turn(tmp_path: Path) -> None:
    """THE test. `load_transcript_slices` is tail-capped: on a long session the
    EARLIEST directives fall outside the window. Re-deriving from that truncated
    slice must not drop them — dropping them silently allows exactly the stop
    this feature exists to refuse."""
    early = [_user("Add rate limiting to the login endpoint.", ts="2026-08-12T09:00:00Z"),
             _user("Also write the migration for the new column.", ts="2026-08-12T09:30:00Z")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(early))

    stored = ow.read_ledger(tmp_path)
    assert len(stored["entries"]) == 2, "both early directives registered"
    early_ids = {e["id"] for e in stored["entries"]}

    # The tail-capped second pass sees ONLY a later turn — the two early turns
    # have scrolled out of the window entirely.
    late = [_user("Bump the version to 3.56.0.", ts="2026-08-12T18:00:00Z")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(late))

    after = ow.read_ledger(tmp_path)
    after_ids = {e["id"] for e in after["entries"]}
    assert early_ids <= after_ids, (
        "a stored entry was dropped by a pass whose slice could not see its "
        "originating turn — the tail-cap bug this ledger exists to prevent"
    )
    assert len(after["entries"]) == 3, "the new directive is added, none removed"
    assert {e["id"] for e in ow.open_ledger_entries(tmp_path)} == after_ids, (
        "every unresolved entry still counts as open"
    )


def test_re_derivation_never_reopens_or_downgrades_a_resolved_entry(tmp_path: Path) -> None:
    """Accumulation is purely additive: union by id, stored side wins. A pass
    that re-derives an already-RESOLVED directive must not reopen it."""
    records = [_user("Fix the flaky lock test.")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(records))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]
    ow.resolve_ledger_entry(tmp_path, entry_id, evidence="tests/test_locks.py::test_x green")
    assert ow.open_ledger_entries(tmp_path) == [], "explicitly resolved -> not open"

    # The very same directive is re-derived on a later pass.
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(records))

    entries = ow.read_ledger(tmp_path)["entries"]
    assert len(entries) == 1, "re-deriving the same directive does not duplicate it"
    assert entries[0]["status"] == "resolved", "a resolved entry is never reopened"
    assert entries[0]["evidence"] == "tests/test_locks.py::test_x green"
    assert ow.open_ledger_entries(tmp_path) == []


def test_stored_first_seen_is_preserved_across_passes(tmp_path: Path) -> None:
    """The stored side wins on union, so the original first_seen survives — the
    ledger records when the user ASKED, not when the hook last looked."""
    records = [_user("Document the kill-switches in the README.",
                     ts="2026-08-12T09:00:00Z")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(records))
    first = ow.read_ledger(tmp_path)["entries"][0]["first_seen"]

    later = [_user("Document the kill-switches in the README.",
                   ts="2026-08-12T23:59:00Z")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(later))
    assert ow.read_ledger(tmp_path)["entries"][0]["first_seen"] == first


def test_accumulate_with_no_new_entries_does_not_rewrite_the_file(tmp_path: Path) -> None:
    """A no-op pass must leave the bytes alone.

    ``run_continuity``'s progress fingerprint hashes ``.architect-team/**`` stat
    data and does NOT exclude this file, so rewriting the ledger on every Stop
    would register as PROGRESS and defeat the pre-existing wedge detector that
    drives auto-escalation."""
    records = [_user("Add the regression test.")]
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(records))
    path = ow.ledger_path(tmp_path)
    before = path.read_bytes()

    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries(records))
    assert path.read_bytes() == before, (
        "a no-change accumulate rewrote the ledger — that fakes progress for "
        "run_continuity's no-progress fingerprint"
    )


def test_read_ledger_absent_is_empty_but_corrupt_raises(tmp_path: Path) -> None:
    """Absent is genuinely empty. Corrupt is UNKNOWN, and unknown is not empty —
    it raises so the caller can turn it into a named blocking violation."""
    assert ow.read_ledger(tmp_path) == {"schema": 1, "entries": []}

    path = ow.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ow.LedgerUnreadable):
        ow.read_ledger(tmp_path)


def test_read_ledger_wrong_shape_raises_rather_than_reading_as_empty(tmp_path: Path) -> None:
    path = ow.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(["not", "a", "ledger"]), encoding="utf-8")
    with pytest.raises(ow.LedgerUnreadable):
        ow.read_ledger(tmp_path)

    path.write_text(json.dumps({"schema": 1, "entries": "nope"}), encoding="utf-8")
    with pytest.raises(ow.LedgerUnreadable):
        ow.read_ledger(tmp_path)


def test_ledger_path_is_under_the_workspace_state_dir(tmp_path: Path) -> None:
    assert ow.ledger_path(tmp_path) == tmp_path / ".architect-team" / "ask-ledger.json"
    assert ow.LEDGER_FILENAME == "ask-ledger.json"


def test_derive_reads_genuine_user_prompts_only(tmp_path: Path) -> None:
    """Derivation is from the HARNESS-written transcript, so an agent cannot
    decline to register an ask. The injected records the harness also stores as
    role=user (meta echoes, system-injected notifications, sidechains) are not
    the user's directives and must not become entries."""
    records = [
        _user("Refactor the exporter."),
        _user("<the loaded skill body>", isMeta=True),
        _user("<task-notification>agent finished</task-notification>",
              promptSource="system"),
        _user("subagent chatter", isSidechain=True),
        _assistant("I'll take care of the exporter refactor and report back."),
    ]
    derived = ow.derive_ledger_entries(records)
    assert [e["text"] for e in derived] == ["Refactor the exporter."]


def test_derive_skips_bare_acknowledgements(tmp_path: Path) -> None:
    """A bare ack carries no new ask. Registering one would open an entry that
    can never be honestly resolved — noise that gets the whole gate disabled."""
    records = [_user("thanks"), _user("ok"), _user("yes"), _user("continue"),
               _user("   "), _user("Sounds good.")]
    assert ow.derive_ledger_entries(records) == []


def test_derive_entry_shape_and_stable_id(tmp_path: Path) -> None:
    text = "Wire the completion lock into main()."
    a = ow.derive_ledger_entries([_user(text, ts="2026-08-12T09:00:00Z")])[0]
    b = ow.derive_ledger_entries([_user(text, ts="2026-08-12T21:00:00Z")])[0]
    assert a["id"] == b["id"], "the id is a stable hash of the directive text"
    assert set(a) == {"id", "text", "first_seen", "status", "resolved_at", "evidence"}
    assert a["text"] == text
    assert a["status"] == "open"
    assert a["resolved_at"] is None and a["evidence"] is None
    assert a["first_seen"].endswith("Z")


# The REAL harness shape for a slash command, taken from a live transcript:
# three sibling tags, and the user's prose lives in <command-args>.
_REAL_COMMAND_PROMPT = (
    "<command-name>/architect-team:architect-team</command-name>"
    "<command-message>architect-team</command-message>"
    "<command-args>Agent Teams sessions are ending their turn with work still "
    "open. Build a completion lock that refuses the stop while registered work "
    "is open.</command-args>"
)


def test_command_prompt_derives_the_users_prose_not_nothing(tmp_path: Path) -> None:
    """F1. Dropping the whole prompt because it carries a command marker drops
    the user's DIRECTIVE with it — measured at 25 of 51 command-carrying prompts
    in the user's own history, including the prompt that commissioned this
    feature. The invocation is stripped; the prose is the ask."""
    entries = ow.derive_ledger_entries([_user(_REAL_COMMAND_PROMPT)])
    assert len(entries) == 1, "the user's ask must survive its own slash command"
    text = entries[0]["text"]
    assert text.startswith("Agent Teams sessions are ending their turn")
    assert "<command-" not in text and "/architect-team" not in text, text


def test_bare_invocation_with_no_prose_derives_nothing(tmp_path: Path) -> None:
    """The invocation alone is not an ask. A single bare argument is a setting,
    not prose — `/model opus` must not register 'opus' as an outstanding ask."""
    for text in (
        "<command-name>/architect-team:status</command-name>"
        "<command-message>status</command-message><command-args></command-args>",
        "<command-name>/clear</command-name><command-message>clear</command-message>",
        "<command-name>/model</command-name><command-message>model</command-message>"
        "<command-args>opus</command-args>",
        "<command-name>/effort</command-name><command-message>effort</command-message>"
        "<command-args>max</command-args>",
    ):
        assert ow.derive_ledger_entries([_user(text)]) == [], text


def test_flag_only_command_arguments_are_not_directives(tmp_path: Path) -> None:
    """N3. `/setup --external-llm --yes` clears the two-word bar but is options,
    not an ask. A ledger full of flag noise is how a user learns to disable the
    gate."""
    for text in (
        "<command-name>/architect-team:setup</command-name>"
        "<command-message>setup</command-message>"
        "<command-args>--external-llm --yes</command-args>",
        "<command-name>/architect-team:cleanup-worktrees</command-name>"
        "<command-args>--dry-run -v</command-args>",
    ):
        assert ow.derive_ledger_entries([_user(text)]) == [], text


def test_flags_mixed_with_prose_still_derive(tmp_path: Path) -> None:
    """The N3 guard must not eat a real ask that happens to carry a flag."""
    text = ("<command-name>/architect-team:setup</command-name>"
            "<command-args>--yes and wire the gateway to z.ai</command-args>")
    assert [e["text"] for e in ow.derive_ledger_entries([_user(text)])] == [
        "--yes and wire the gateway to z.ai"
    ]


def test_prose_outside_the_tags_is_also_kept(tmp_path: Path) -> None:
    """The older/simpler shape puts the prose after the closing tag."""
    records = [
        _user("<command-name>/architect-team:architect-team</command-name> build it"),
        _user("Also add the migration for the new column."),
    ]
    assert [e["text"] for e in ow.derive_ledger_entries(records)] == [
        "build it",
        "Also add the migration for the new column.",
    ]


def test_injected_reminder_blocks_do_not_destabilize_the_id(tmp_path: Path) -> None:
    """The harness appends <system-reminder> blocks to user prompts and their
    content churns between turns. Hashing them would mint a NEW id for the same
    directive on every pass, so the ledger could only grow and no entry could
    ever be resolved."""
    plain = "Add the migration for the new column."
    withreminder = (plain + "\n<system-reminder>tasks: 4 open, 2 done"
                    "</system-reminder>")
    a = ow.derive_ledger_entries([_user(plain)])[0]
    b = ow.derive_ledger_entries([_user(withreminder)])[0]
    assert b["text"] == plain, "the stored text is the user's words"
    assert a["id"] == b["id"]


def test_resolution_is_conservative_ambiguous_stays_open(tmp_path: Path) -> None:
    """Over-blocking fails safe; under-blocking is the reported bug. A resolve
    with no evidence, or for an id that is not stored, changes nothing."""
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries([_user("Ship the docs.")]))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]

    ow.resolve_ledger_entry(tmp_path, entry_id, evidence="")
    assert len(ow.open_ledger_entries(tmp_path)) == 1, "no evidence -> stays open"

    ow.resolve_ledger_entry(tmp_path, entry_id, evidence="   ")
    assert len(ow.open_ledger_entries(tmp_path)) == 1, "blank evidence -> stays open"

    ow.resolve_ledger_entry(tmp_path, "no-such-id", evidence="README.md updated")
    assert len(ow.open_ledger_entries(tmp_path)) == 1, "unknown id resolves nothing"

    ow.resolve_ledger_entry(tmp_path, entry_id, evidence="README.md updated")
    assert ow.open_ledger_entries(tmp_path) == []


def test_unknown_ledger_status_counts_as_open(tmp_path: Path) -> None:
    """Same asymmetry as the task list: unknown state is not 'done'."""
    path = ow.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema": 1, "entries": [
        {"id": "a", "text": "one", "first_seen": "2026-08-12T09:00:00Z",
         "status": "wat", "resolved_at": None, "evidence": None},
        {"id": "b", "text": "two", "first_seen": "2026-08-12T09:00:00Z",
         "resolved_at": None, "evidence": None},
        {"id": "c", "text": "three", "first_seen": "2026-08-12T09:00:00Z",
         "status": "resolved", "resolved_at": "2026-08-12T10:00:00Z",
         "evidence": "done"},
    ]}), encoding="utf-8")
    assert [e["id"] for e in ow.open_ledger_entries(tmp_path)] == ["a", "b"]


# =============================================================================
# Group 1 — the harness task list. Read failures are DATA, never exceptions.
# =============================================================================

def _write_task(root: Path, session_id: str, task_id: str,
                status: str | None = "pending", owner: str | None = None,
                **extra) -> Path:
    d = Path(root) / f"session-{session_id[:8]}"
    d.mkdir(parents=True, exist_ok=True)
    rec: dict = {"id": task_id, "subject": f"subject {task_id}",
                 "description": "d", "activeForm": "doing", "owner": owner,
                 "blocks": [], "blockedBy": []}
    if status is not None:
        rec["status"] = status
    rec.update(extra)
    p = d / f"{task_id}.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    return p


def test_open_and_terminal_statuses_partition(tmp_path: Path) -> None:
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    _write_task(tmp_path, "sess1234abcd", "T-2", status="in_progress")
    _write_task(tmp_path, "sess1234abcd", "T-3", status="completed")

    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert read["unreadable"] == []
    assert len(read["items"]) == 3
    assert {i["id"] for i in ow.open_task_items(read["items"])} == {"T-1", "T-2"}
    assert ow.OPEN_STATUSES == frozenset({"pending", "in_progress"})


def test_missing_or_unknown_status_counts_as_open(tmp_path: Path) -> None:
    """Unknown state is not 'done'. The asymmetry is deliberate and fails safe."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status=None)
    _write_task(tmp_path, "sess1234abcd", "T-2", status="")
    _write_task(tmp_path, "sess1234abcd", "T-3", status="banana")
    _write_task(tmp_path, "sess1234abcd", "T-4", status="completed")

    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert {i["id"] for i in ow.open_task_items(read["items"])} == {"T-1", "T-2", "T-3"}


def test_malformed_task_file_is_data_not_an_exception(tmp_path: Path) -> None:
    """A blanket fail-open here reproduces the exact reported bug: one bad file
    and the gate silently passes. It lands in unreadable[] instead."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status="completed")
    bad = tmp_path / "session-sess1234" / "T-9.json"
    bad.write_text("{ not json at all", encoding="utf-8")

    read = ow.read_harness_tasks("sess1234abcd", tmp_path)  # must NOT raise
    assert [i["id"] for i in read["items"]] == ["T-1"]
    assert len(read["unreadable"]) == 1
    entry = read["unreadable"][0]
    assert Path(entry["path"]) == bad
    assert entry["reason"], "the unreadable entry names WHY it could not be read"


def test_permission_error_on_a_task_file_lands_in_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only a parse failure — a file the reader is not allowed to open is
    unknown state too, and `lock-wiring` depends on it reaching the
    block-and-name path rather than raising."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    real_read_text = Path.read_text

    def denied(self: Path, *args, **kwargs):
        if self.name == "T-1.json":
            raise PermissionError(13, "Permission denied")
        return real_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", denied)
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)  # must NOT raise
    assert read["items"] == []
    assert len(read["unreadable"]) == 1
    assert read["unreadable"][0]["path"].endswith("T-1.json")
    assert "Permission denied" in read["unreadable"][0]["reason"]


def test_unlistable_session_dir_lands_in_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    real_iterdir = Path.iterdir

    def denied(self: Path):
        if self.name == "session-sess1234":
            raise PermissionError(13, "Permission denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", denied)
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)  # must NOT raise
    assert read["items"] == []
    assert len(read["unreadable"]) == 1
    assert Path(read["unreadable"][0]["path"]).name == "session-sess1234"


def test_non_object_json_task_is_unreadable(tmp_path: Path) -> None:
    d = tmp_path / "session-sess1234"
    d.mkdir(parents=True)
    (d / "T-8.json").write_text(json.dumps(["not", "a", "task"]), encoding="utf-8")
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert read["items"] == []
    assert len(read["unreadable"]) == 1


def test_recursion_bomb_json_is_data_not_an_exception(tmp_path: Path) -> None:
    """F2. `except (OSError, ValueError)` misses RecursionError, so a
    deeply-nested JSON escapes both readers and breaks the property all of
    REQ-6 rests on. The property must hold for EVERY malformed input, not the
    two shapes that were anticipated."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status="completed")
    bomb = tmp_path / "session-sess1234" / "T-9.json"
    bomb.write_text("[" * 200000, encoding="utf-8")

    read = ow.read_harness_tasks("sess1234abcd", tmp_path)  # must NOT raise
    assert [i["id"] for i in read["items"]] == ["T-1"]
    assert len(read["unreadable"]) == 1
    assert read["unreadable"][0]["path"].endswith("T-9.json")


def test_recursion_bomb_ledger_raises_ledger_unreadable(tmp_path: Path) -> None:
    """The ledger's half of F2: still a NAMED blocking violation, never a raw
    RecursionError escaping into the hook."""
    path = ow.ledger_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[" * 200000, encoding="utf-8")
    with pytest.raises(ow.LedgerUnreadable):
        ow.read_ledger(tmp_path)


def test_sidecars_are_skipped_by_name_not_by_parse_failure(tmp_path: Path) -> None:
    """The sidecars are KNOWN non-tasks, so they are skipped by name. Anything
    else unparseable is unknown state and must surface."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    d = tmp_path / "session-sess1234"
    (d / ".lock").write_text("pid 1234", encoding="utf-8")
    (d / ".highwatermark").write_text("42", encoding="utf-8")

    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert read["unreadable"] == [], "the known sidecars are not 'unreadable'"
    assert [i["id"] for i in read["items"]] == ["T-1"]
    assert ow.TASK_SIDECARS == frozenset({".lock", ".highwatermark"})


def test_unknown_extra_file_surfaces_as_unreadable(tmp_path: Path) -> None:
    """A file in the task store that is neither a task nor a known sidecar is
    unknown state — silently dropping it is how a format change becomes an
    invisible pass."""
    _write_task(tmp_path, "sess1234abcd", "T-1", status="completed")
    (tmp_path / "session-sess1234" / "notes.txt").write_text("hi", encoding="utf-8")
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert len(read["unreadable"]) == 1
    assert read["unreadable"][0]["path"].endswith("notes.txt")


def test_missing_session_dir_is_a_clean_empty_result(tmp_path: Path) -> None:
    """Absent is genuinely empty — NOT an unreadable entry. A session that never
    registered a task must not be blocked."""
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert read["items"] == [] and read["unreadable"] == []


def test_empty_session_id_yields_no_directory(tmp_path: Path) -> None:
    for sid in ("", None):
        read = ow.read_harness_tasks(sid, tmp_path)
        assert read == {"items": [], "unreadable": [], "dir": None}


def test_session_dir_is_the_first_eight_characters(tmp_path: Path) -> None:
    _write_task(tmp_path, "abcdefgh-ijkl-mnop", "T-1", status="pending")
    read = ow.read_harness_tasks("abcdefgh-ijkl-mnop", tmp_path)
    assert Path(read["dir"]).name == "session-abcdefgh"
    assert [i["id"] for i in read["items"]] == ["T-1"]


def test_items_carry_their_source_path(tmp_path: Path) -> None:
    p = _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    read = ow.read_harness_tasks("sess1234abcd", tmp_path)
    assert Path(read["items"][0]["_path"]) == p


def test_owner_filter_scopes_to_one_teammate(tmp_path: Path) -> None:
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending", owner="lock-core")
    _write_task(tmp_path, "sess1234abcd", "T-2", status="pending", owner="lock-wiring")
    _write_task(tmp_path, "sess1234abcd", "T-3", status="pending")

    items = ow.read_harness_tasks("sess1234abcd", tmp_path)["items"]
    assert {i["id"] for i in ow.open_task_items(items)} == {"T-1", "T-2", "T-3"}
    assert [i["id"] for i in ow.open_task_items(items, owner="lock-core")] == ["T-1"]
    assert ow.open_task_items(items, owner="nobody") == []


def test_tasks_root_precedence_explicit_beats_env_beats_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The injected root IS the test seam — an explicit argument must win, and
    the real ~/.claude/tasks is only the last resort."""
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("CT6_TASKS_ROOT", raising=False)
    assert ow.tasks_root() == home / ".claude" / "tasks"

    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path / "from-env"))
    assert ow.tasks_root() == tmp_path / "from-env"
    assert ow.tasks_root(tmp_path / "explicit") == tmp_path / "explicit"


def test_read_harness_tasks_honours_the_env_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CT6_TASKS_ROOT", str(tmp_path))
    _write_task(tmp_path, "sess1234abcd", "T-1", status="pending")
    read = ow.read_harness_tasks("sess1234abcd")
    assert [i["id"] for i in read["items"]] == ["T-1"]


# --- the turn-output classifier: pinned in BOTH directions -------------------

def test_three_substantial_lines_is_a_narrative(tmp_path: Path) -> None:
    """SUPERSEDED (F6): the old version of this test used three TERSE lines
    ('Fixed the parser. / Ran the suite. / All green.' — 17/14/10 chars), which
    measures the same as the F6 false positive it now has to allow. The
    line-count arm counts SUBSTANTIAL lines, so the pin moves to lines that are
    actually report-length."""
    r = ow.classify_turn_output(
        "I finished the exporter refactor and pushed it.\n"
        "The full suite is green under both encodings.\n"
        "I will start on the lineage sidecar next."
    )
    assert r["narrative"] is True
    assert r["lines"] == 3
    assert r["markers"] == []
    assert r["reason"]


def test_a_handful_of_terse_state_lines_is_not_a_narrative(tmp_path: Path) -> None:
    """F6 — the false positive did not go away when markers stopped deciding,
    it MOVED to the line-count arm. Three short markerless lines totalling 37
    non-whitespace characters is a terse state report, which is exactly what
    the block message asks for. Blocking it is the same wedge in a new place."""
    r = ow.classify_turn_output("task 2 in progress\ntask 3 pending\nno blockers")
    assert r["narrative"] is False, (
        "a terse state report is what the rule ASKS for; refusing it is the "
        "same loop that made the marker arm unshippable"
    )
    assert r["lines"] == 3, "still reported honestly — they just do not COUNT"


def test_a_short_bullet_summary_is_still_a_narrative(tmp_path: Path) -> None:
    """The F6 allowance must not become an F4 hole: a bullet list of short items
    is a summary, not terse state.

    It is caught by the MARKER arm, not the line-count arm. The first cut also
    exempted marked lines from the short-line rule; the mutation harness showed
    that clause was dead — markers already decide at >= 2 lines, while the
    line-count arm needs >= 3 — so it was removed rather than left as
    reassuring but inert code."""
    r = ow.classify_turn_output("- T-1 done\n- T-2 done\n- T-3 next")
    assert r["narrative"] is True
    assert "bullet" in r["markers"]


def test_two_substantial_markerless_lines_are_not_a_narrative(tmp_path: Path) -> None:
    """The witness for NARRATIVE_LINE_THRESHOLD itself. Two full report-length
    lines with no marker sit just under the bar; the terse two-line case cannot
    pin this any more, because F6's short-line rule now excludes those lines
    before the threshold is ever consulted."""
    r = ow.classify_turn_output(
        "I finished the exporter refactor and pushed it to the branch.\n"
        "The suite is green under both encodings and I am moving on."
    )
    assert r["narrative"] is False and r["markers"] == []
    assert r["lines"] == 2


def test_five_lines_of_plain_prose_is_a_narrative(tmp_path: Path) -> None:
    """The line-count arm has to bite ON ITS OWN: a marker-only rule would let
    a full plain-prose report through, which is the exact turn shape the user
    reported."""
    r = ow.classify_turn_output("\n".join([
        "I finished the exporter refactor.",
        "The suite is green under both encodings.",
        "I also checked the lineage sidecar and it needs no change.",
        "Next I will wire the CLI.",
        "Tell me if you want a different order.",
    ]))
    assert r["narrative"] is True
    assert r["markers"] == [] and r["lines"] == 5


def test_two_lines_with_no_marker_is_not_a_narrative(tmp_path: Path) -> None:
    """A rule that fires on a legitimate terse status update gets disabled by
    the user, which is the same as not shipping it."""
    r = ow.classify_turn_output("Working on T-3.\n4 of 17 done.")
    assert r["narrative"] is False
    assert r["lines"] == 2 and r["markers"] == []


def test_one_line_and_empty_are_not_narratives(tmp_path: Path) -> None:
    assert ow.classify_turn_output("T-3 in progress.")["narrative"] is False
    for empty in ("", "   ", "\n\n\n"):
        r = ow.classify_turn_output(empty)
        assert r["narrative"] is False and r["lines"] == 0


def test_blank_lines_do_not_count_toward_the_line_threshold(tmp_path: Path) -> None:
    r = ow.classify_turn_output("Still on T-3.\n\n\n2 left.")
    assert r["lines"] == 2 and r["narrative"] is False


@pytest.mark.parametrize("text,marker", [
    ("## Summary of the run", "heading"),
    ("# Done", "heading"),
    ("- fixed the exporter", "bullet"),
    ("* fixed the exporter", "bullet"),
    ("+ fixed the exporter", "bullet"),
    ("1. fixed the exporter", "numbered"),
    ("2) fixed the exporter", "numbered"),
    ("**Status:** blocked on review", "bold-label"),
    ("**Status**: blocked on review", "bold-label"),
    ("| task | state |", "table-row"),
])
def test_each_structural_marker_is_detected_and_reported(text: str, marker: str) -> None:
    """SUPERSEDED (v3.56.0): markers no longer trip the rule on their own.

    This test used to assert a single marker-carrying line was a narrative. That
    shipped a loop: the block message demands one line of state, and
    `**Status:** still on task 1 of 9.` — that exact shape — tripped `bold-label`
    and re-blocked, with no exit but a kill-switch. A marker cannot indicate
    report STRUCTURE in a turn too short to have any.

    What survives is what is still true and still worth pinning: DETECTION. Each
    marker kind must still be recognized and reported, because the reason string
    uses them and the length arms are what decide. The tripping assertion moves
    to `test_markers_trip_once_the_turn_is_long_enough` below.
    """
    r = ow.classify_turn_output(text)
    assert marker in r["markers"], f"{marker} must still be DETECTED"
    assert r["lines"] == 1
    assert r["narrative"] is False, "a one-line turn is never a narrative"


def test_markers_trip_once_the_turn_is_long_enough(tmp_path: Path) -> None:
    """The tripping half of the superseded marker test: a marker-carrying turn
    that is genuinely long enough IS a narrative, and the marker is reported."""
    r = ow.classify_turn_output("Here is where things stand.\n"
                                "- T-1 done\n"
                                "- T-2 in review")
    assert r["narrative"] is True
    assert "bullet" in r["markers"]
    assert r["lines"] == 3


def test_a_one_line_marked_state_is_never_a_narrative(tmp_path: Path) -> None:
    """THE ABSOLUTE FLOOR. This is the exact turn that shipped the unbreakable
    loop — the one line of state the block message demands, carrying a bold
    label. Whatever else moves in this predicate, this must not.

    (The two-line half of the old version of this test was itself a
    regression — see `test_a_two_line_summary_with_a_marker_trips` below.)"""
    r = ow.classify_turn_output("**Status:** still on task 1 of 9.")
    assert r["narrative"] is False, (
        "the block asks for one line of state; refusing one line of state is a "
        "loop whose only exit is a kill-switch"
    )
    assert "bold-label" in r["markers"], "still detected, just not decisive"

    for one_liner in ("## Done", "- shipped it", "1. shipped it", "| a | b |"):
        assert ow.classify_turn_output(one_liner)["narrative"] is False, one_liner


@pytest.mark.parametrize("text,marker", [
    ("Here is where things stand.\n- T-1 done", "bullet"),
    ("## Summary\nEverything landed.", "heading"),
    ("| task | state |\n| T-1 | done |", "table-row"),
    ("**Done:** the exporter\n**Remaining:** the sidecar", "bold-label"),
    ("Progress:\n1. shipped the exporter", "numbered"),
])
def test_a_two_line_summary_with_a_marker_trips(text: str, marker: str) -> None:
    """F4 — the correction to my correction. Making the length floor dominate
    removed the unbreakable loop AND most of the enforcement with it: every one
    of these is unmistakably a report, and every one slipped. The user's
    reported failure is literally 'every time my turn is about to end, I fill
    it with a summary', so a two-line summary is THE shape this rule exists to
    catch. Markers decide at >= 2 lines; the 1-line floor stays absolute."""
    r = ow.classify_turn_output(text)
    assert r["narrative"] is True, f"a 2-line {marker} summary must re-block"
    assert marker in r["markers"]
    assert r["lines"] == 2


def test_a_single_unbroken_paragraph_report_is_a_narrative(tmp_path: Path) -> None:
    """The long-prose arm replaces what markers were really catching: a report
    that just lacks newlines. Line count alone missed it."""
    prose = ("I finished the exporter refactor and then went through the "
             "lineage sidecar looking for anything that needed to change. " * 6)
    # F5: the threshold is measured on the RAW text, so the constant means what
    # it says. It used to measure after whitespace removal, which made the real
    # threshold ~715 raw chars and let a 700-char paragraph slip at 560 measured.
    assert len(prose.strip()) > ow.NARRATIVE_PROSE_CHARS
    r = ow.classify_turn_output(prose)
    assert r["narrative"] is True and r["lines"] == 1
    assert str(ow.NARRATIVE_PROSE_CHARS) in r["reason"]


def test_the_prose_threshold_is_measured_on_raw_text(tmp_path: Path) -> None:
    """F5, pinned as an equivalence rather than a vibe: a paragraph just over
    the constant trips and one just under does not, both measured the way the
    docstring says they are."""
    over = "x" * (ow.NARRATIVE_PROSE_CHARS + 20)
    under = "x" * (ow.NARRATIVE_PROSE_CHARS - 20)
    assert ow.classify_turn_output(over)["narrative"] is True
    assert ow.classify_turn_output(under)["narrative"] is False

    # The old whitespace-stripped basis would have measured this UNDER the
    # constant while the raw text is over it — the exact gap F5 names. 130
    # four-letter words: 520 stripped, 649 raw.
    spaced = " ".join("word" for _ in range(130))
    assert len("".join(spaced.split())) < ow.NARRATIVE_PROSE_CHARS < len(spaced), (
        "the fixture must straddle the constant, or it pins nothing"
    )
    assert ow.classify_turn_output(spaced)["narrative"] is True, (
        "measured raw, this is over the threshold and is a report"
    )


def test_a_short_paragraph_under_the_prose_cap_is_not_a_narrative(
    tmp_path: Path
) -> None:
    """The other direction of the prose arm — a genuinely brief one-liner stays
    clean, so the cap cannot creep down into ordinary state lines."""
    r = ow.classify_turn_output("Still on T-1; the exporter fix is under review.")
    assert r["narrative"] is False


def test_prose_containing_a_pipe_or_hash_is_not_a_table_or_heading(tmp_path: Path) -> None:
    """False positives train the user to disable the gate."""
    r = ow.classify_turn_output("Piping a | b into sort.\nIssue #4 is next.")
    assert r["narrative"] is False, f"unexpected markers: {r['markers']}"


def test_fenced_and_indented_code_do_not_create_markers(tmp_path: Path) -> None:
    """A '#' comment inside a code block is not a heading."""
    fenced = ow.classify_turn_output("Ran it.\n```\n# not a heading\n- not a bullet\n```")
    assert fenced["markers"] == [], f"unexpected markers: {fenced['markers']}"
    indented = ow.classify_turn_output("Ran it.\n    # not a heading")
    assert indented["markers"] == [] and indented["narrative"] is False


def test_classify_is_pure_and_tolerates_a_non_string(tmp_path: Path) -> None:
    assert ow.classify_turn_output(None)["narrative"] is False  # type: ignore[arg-type]


# --- the four kill-switches --------------------------------------------------

def test_killswitch_constants_are_the_documented_names(tmp_path: Path) -> None:
    assert ow.DISABLE_ENV == "CT6_COMPLETION_LOCK_DISABLED"
    assert ow.DISABLE_TASKS_ENV == "CT6_TASK_LIST_GATE_DISABLED"
    assert ow.DISABLE_LEDGER_ENV == "CT6_ASK_LEDGER_GATE_DISABLED"
    assert ow.DISABLE_OUTPUT_ENV == "CT6_TURN_OUTPUT_GATE_DISABLED"


def test_each_switch_reads_only_its_own_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling a noisy source must not disable the sources that work."""
    readers = {
        ow.DISABLE_ENV: ow.lock_disabled,
        ow.DISABLE_TASKS_ENV: ow.tasks_disabled,
        ow.DISABLE_LEDGER_ENV: ow.ledger_disabled,
        ow.DISABLE_OUTPUT_ENV: ow.output_disabled,
    }
    assert all(not fn() for fn in readers.values()), "all off by default"
    for var, fn in readers.items():
        monkeypatch.setenv(var, "1")
        assert fn() is True
        for other_var, other_fn in readers.items():
            if other_var != var:
                assert other_fn() is False, f"{var} leaked into {other_var}"
        monkeypatch.delenv(var)


@pytest.mark.parametrize("value,expected", [
    ("1", True), ("true", True), ("TRUE", True), ("yes", True), ("on", True),
    ("", False), ("0", False), ("false", False), ("no", False), ("  ", False),
])
def test_truthy_env_shape_matches_run_continuity(
    value: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ow.DISABLE_ENV, value)
    assert ow.lock_disabled() is expected


# =============================================================================
# Group 3 — teammate identity. Never wedge a worker on a lane it cannot close.
# =============================================================================

def test_teammate_name_from_the_mandated_bracketed_brief(tmp_path: Path) -> None:
    records = [_user("[CT6-TEAMMATE lock-core RUN turn-boundary-completion-lock]\n"
                     "\nYou own hooks/open_work.py.")]
    assert ow.teammate_name(records) == "lock-core"


def test_teammate_name_from_the_lenient_brief_form(tmp_path: Path) -> None:
    """Real briefs are also written without the brackets or the RUN tail."""
    records = [_user("CT6-TEAMMATE lock-wiring\n\nYou own the Stop hook wiring.")]
    assert ow.teammate_name(records) == "lock-wiring"


# A teams-mode spawn brief: a role:user record wrapped in the peer envelope,
# arriving as the FIRST inbound record of the teammate's transcript.
_ENVELOPE_BRIEF = ('<teammate-message teammate_id="team-lead">\n'
                   '[CT6-TEAMMATE lock-core RUN turn-boundary-completion-lock]\n'
                   'You own hooks/open_work.py.\n</teammate-message>')


def test_teams_mode_envelope_brief_resolves_the_name(tmp_path: Path) -> None:
    """N1. `_is_user_prompt` excludes the peer envelope, so a `_genuine_prompts`
    -only scan returns nothing for a teams-mode teammate and classifies the
    worker as an orchestrator. POSITION is the discriminator: the brief is the
    FIRST inbound record, so an envelope is honoured there and nowhere else."""
    assert ow.teammate_name([_user(_ENVELOPE_BRIEF)]) == "lock-core"


def test_teams_mode_teammate_is_scoped_to_its_own_lane_not_wedged(
    tmp_path: Path
) -> None:
    """N1 end-to-end, the reviewer's measured repro: three tasks owned by three
    different agents. Before the fix all three came back and the turn-output
    rule fired on the teammate's report — REQ-4 says a teammate is NEVER wedged
    on lanes it has no power to close."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="in_progress", owner="lock-core")
    _write_task(tasks, "sess1234abcd", "T-2", status="pending", owner="lock-wiring")
    _write_task(tasks, "sess1234abcd", "T-3", status="pending", owner="adversary-lock")
    records = [_user(_ENVELOPE_BRIEF),
               _assistant("## Report\n- built the substrate\n- 93 tests green")]

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert [i["id"] for i in r["open_tasks"]] == ["T-1"], (
        "held for its OWN lane only, never for T-2 / T-3"
    )
    assert r["turn_output"] is None, "a teammate's report to the Lead is its deliverable"
    assert r["open_asks"] == []


def test_teams_mode_teammate_with_no_owned_lane_may_stop(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-2", status="pending", owner="lock-wiring")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user(_ENVELOPE_BRIEF)],
                                    tasks_root=tasks)
    assert r["blocked"] is False


def test_a_mid_session_peer_envelope_cannot_supply_a_name(tmp_path: Path) -> None:
    """ADV-9's ACTUAL attack, restated precisely after N1. The Lead's own first
    prompt occupies position one; a peer message arriving LATER must not rename
    it. Position is what separates the brief from an inbound peer message."""
    records = [
        _user("Build the completion lock."),
        _user('<teammate-message teammate_id="lock-core">\n'
              '[CT6-TEAMMATE lock-core RUN slug]\ndone\n</teammate-message>'),
    ]
    assert ow.teammate_name(records) is None


def test_a_lead_holding_a_peer_envelope_is_blocked_on_every_lane(tmp_path: Path) -> None:
    """The end-to-end form of ADV-9: adopting a peer's name would have hidden
    every task that peer does not own."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending", owner="lock-core")
    _write_task(tasks, "sess1234abcd", "T-2", status="pending", owner="lock-wiring")
    records = [
        _user("Build the completion lock."),
        _user('<teammate-message teammate_id="lock-core">\n'
              '[CT6-TEAMMATE lock-core RUN slug]\ndone\n</teammate-message>'),
    ]
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert r["blocked"] is True
    assert {i["id"] for i in r["open_tasks"]} == {"T-1", "T-2"}


def test_teammate_name_is_none_without_a_resolvable_name(tmp_path: Path) -> None:
    assert ow.teammate_name([_user("Please fix the exporter.")]) is None
    assert ow.teammate_name([]) is None
    assert ow.teammate_name([_user("CT6-TEAMMATE")]) is None
    assert ow.teammate_name([_user("[CT6-TEAMMATE RUN slug]")]) is None


def test_teammate_name_prefers_the_head_slice_when_truncated(tmp_path: Path) -> None:
    """The brief lives at the transcript HEAD; on a long-lived teammate it has
    scrolled out of the tail."""
    head = [_user("[CT6-TEAMMATE lock-core RUN slug]\nYour scope.")]
    tail = [_user("keep going")]
    assert ow.teammate_name(tail, head_records=head, truncated=True) == "lock-core"


def test_teammate_name_ignores_assistant_authored_text(tmp_path: Path) -> None:
    """The LEAD's own transcript quotes the token when it writes a brief. Only
    inbound records identify the session."""
    records = [_assistant("[CT6-TEAMMATE lock-core RUN slug] ... dispatching")]
    assert ow.teammate_name(records) is None


# =============================================================================
# The single entry point main() calls
# =============================================================================

def _blank_result_fields(result: dict) -> None:
    # `advisory_asks` joined the contract in v3.56.0 when the ledger became
    # advisory by default — recorded asks still have to surface somewhere.
    assert set(result) == {"blocked", "open_tasks", "open_asks", "advisory_asks",
                           "advisory_notes", "unreadable", "turn_output",
                           "reasons", "killswitch"}


def test_open_task_blocks_and_names_the_source_switch(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [], tasks_root=tasks)
    _blank_result_fields(r)
    assert r["blocked"] is True
    assert [i["id"] for i in r["open_tasks"]] == ["T-1"]
    assert r["killswitch"] == ow.DISABLE_TASKS_ENV
    assert r["reasons"], "a block always says why"


def test_an_ordinary_session_with_only_a_directive_is_not_blocked(
    tmp_path: Path
) -> None:
    """THE REGRESSION THAT SHIPPED (v3.56.0). One user request, zero tasks, no
    CT6 run state — an ordinary session in any project. It blocked PERMANENTLY:
    the agent finished the work, and nothing in the pipeline ever closes a
    ledger entry, so the only exit was a kill-switch.

    The principle the fix encodes: the task list may block because the HARNESS
    writes `status`, so "done" is a fact the gate reads. The ledger only knows a
    directive was GIVEN, never that it was MET — a source that cannot verify its
    own release condition must not hold a session hostage."""
    r = ow.evaluate_completion_lock(tmp_path, "", [_user("Add the changelog entry.")])
    assert r["blocked"] is False, "an ordinary session must not be wedged"
    assert r["open_asks"] == []
    assert [e["text"] for e in r["advisory_asks"]] == ["Add the changelog entry."], (
        "recorded and surfaced, just not the thing refusing the stop"
    )
    assert r["reasons"] == [] and r["killswitch"] is None


def test_a_fresh_unrelated_repo_is_left_byte_untouched(tmp_path: Path) -> None:
    """F-F. Typing one request into any repo wrote CT6 state into it — the
    directory AND the ledger file. Defensible while the ledger blocked and
    tail-cap accumulation was load-bearing; not defensible once it is advisory,
    because an advisory listing holds nothing and a directive that scrolls out
    of the window was never going to block anything."""
    r = ow.evaluate_completion_lock(tmp_path, "", [_user("fix the flaky login test")])

    assert list(tmp_path.iterdir()) == [], (
        "a repo that has never seen CT6 must be left with no directory and no file"
    )
    assert r["blocked"] is False
    assert [e["text"] for e in r["advisory_asks"]] == ["fix the flaky login test"], (
        "still derived and surfaced — in memory, just not written to disk"
    )


def test_a_ct6_workspace_still_persists_and_accumulates(tmp_path: Path) -> None:
    """The other side of F-F: where `.architect-team/` already exists the
    directory is not new pollution, so persistence — and with it the tail-cap
    accumulation property — is unchanged."""
    (tmp_path / ".architect-team").mkdir()

    ow.evaluate_completion_lock(tmp_path, "", [_user("Add the migration.")])
    assert ow.ledger_path(tmp_path).exists(), "a CT6 workspace still persists"

    # A later pass whose slice cannot see the first turn must not lose it.
    ow.evaluate_completion_lock(tmp_path, "", [_user("Bump the version to 3.56.0.")])
    texts = [e["text"] for e in ow.open_ledger_entries(tmp_path)]
    assert "Add the migration." in texts, "accumulation survives the tail cap"
    assert "Bump the version to 3.56.0." in texts


def test_opting_into_blocking_restores_persistence_anywhere(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The asymmetry is safe in the direction that matters: the moment the
    ledger can refuse a stop, accumulation is load-bearing again and the file
    comes back, even in a workspace CT6 has never touched."""
    monkeypatch.setenv(ow.LEDGER_BLOCKING_ENV, "1")
    r = ow.evaluate_completion_lock(tmp_path, "", [_user("Add the migration.")])

    assert ow.ledger_path(tmp_path).exists()
    assert r["blocked"] is True and len(r["open_asks"]) == 1


def test_an_advisory_ask_cannot_drag_in_the_turn_output_rule(tmp_path: Path) -> None:
    """The proxy-block hole: if source 3 keyed on asks BEFORE the demotion, the
    ledger would keep blocking through the very rule it was demoted out of."""
    records = [_user("Add the changelog entry."),
               _assistant("## Summary\n- did a thing\n- did another")]
    r = ow.evaluate_completion_lock(tmp_path, "", records)
    assert r["blocked"] is False
    assert r["turn_output"] is None
    assert len(r["advisory_asks"]) == 1


def test_the_ledger_blocks_only_when_blocking_is_opted_in(tmp_path: Path) -> None:
    """Opt-in restores the teeth for a user who wants them."""
    import os
    records = [_user("Add the changelog entry.")]
    os.environ[ow.LEDGER_BLOCKING_ENV] = "1"
    try:
        r = ow.evaluate_completion_lock(tmp_path, "", records)
    finally:
        del os.environ[ow.LEDGER_BLOCKING_ENV]
    assert r["blocked"] is True
    assert [e["text"] for e in r["open_asks"]] == ["Add the changelog entry."]
    assert r["advisory_asks"] == []
    assert r["killswitch"] == ow.DISABLE_LEDGER_ENV


def test_no_open_work_is_not_blocked(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="completed")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [], tasks_root=tasks)
    assert r["blocked"] is False
    assert r["reasons"] == [] and r["killswitch"] is None
    assert r["turn_output"] is None


def test_master_switch_skips_every_source(tmp_path: Path, monkeypatch) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    (tmp_path / ".architect-team").mkdir()
    ow.ledger_path(tmp_path).write_text("{corrupt", encoding="utf-8")
    monkeypatch.setenv(ow.DISABLE_ENV, "1")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user("do a thing")],
                                    tasks_root=tasks)
    assert r["blocked"] is False
    assert r["open_tasks"] == [] and r["unreadable"] == []


def test_disabling_the_ledger_leaves_the_task_source_enforcing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    monkeypatch.setenv(ow.DISABLE_LEDGER_ENV, "1")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user("Fix the bug.")],
                                    tasks_root=tasks)
    assert r["blocked"] is True
    assert r["open_asks"] == [], "the ledger source contributed nothing"
    assert [i["id"] for i in r["open_tasks"]] == ["T-1"]
    assert not ow.ledger_path(tmp_path).exists(), "a disabled source writes nothing"


def test_disabling_the_task_list_leaves_the_ledger_enforcing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Per-source independence still holds — but the ledger is ADVISORY by
    default (v3.56.0), so this test now opts blocking in explicitly. Its point
    is that one switch does not silence another source, and that survives."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    monkeypatch.setenv(ow.DISABLE_TASKS_ENV, "1")
    monkeypatch.setenv(ow.LEDGER_BLOCKING_ENV, "1")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user("Fix the bug.")],
                                    tasks_root=tasks)
    assert r["blocked"] is True
    assert r["open_tasks"] == []
    assert len(r["open_asks"]) == 1
    assert r["killswitch"] == ow.DISABLE_LEDGER_ENV


# --- SPLIT (v3.56.0) of test_evaluate_accumulates_the_ledger_from_the_transcript.
#
# That test was re-pointed three times in one release — for the advisory
# demotion, then the persistence rule, then the fresh-repo exclusion — which is
# the signature of ONE assertion path defending SEVERAL properties. A test that
# has to move on every adjacent change has stopped being a pin and become a
# maintenance tax, and worse, each re-point is an opportunity to quietly weaken
# the property that was not the reason for the edit.
#
# The three below have one reason to change each:
#   1. derivation wiring   — changes only if evaluate stops reading the transcript
#   2. durability          — changes only if what is derived stops reaching the store
#   3. advisory surfacing  — changes only if the advisory/blocking policy changes
#
# Note (1) asserts on open_asks + advisory_asks deliberately: WHICH channel an
# ask lands in is (3)'s property, not (1)'s, so a future policy flip must not
# drag the derivation pin along with it.

def test_evaluate_derives_asks_from_the_transcript_without_registration(
    tmp_path: Path
) -> None:
    """PROPERTY 1 — registration is involuntary. The entry comes from the
    harness-written transcript, not from a call the agent could decline to
    make. Channel-agnostic on purpose."""
    r = ow.evaluate_completion_lock(tmp_path, "", [_user("Add the changelog entry.")])
    recorded = [e["text"] for e in r["open_asks"] + r["advisory_asks"]]
    assert recorded == ["Add the changelog entry."], (
        "the directive was captured with no registration call of any kind"
    )


def test_a_derived_ask_reaches_the_durable_store(tmp_path: Path) -> None:
    """PROPERTY 2 — what is derived is what is stored.

    Distinct from the F-F tests beside it: those pin WHICH workspaces persist
    (the policy), this pins that the store's CONTENTS match what derivation
    produced. A change to either one should move only its own test."""
    (tmp_path / ".architect-team").mkdir()
    ow.evaluate_completion_lock(tmp_path, "", [_user("Add the changelog entry.")])

    assert ow.ledger_path(tmp_path).exists()
    assert [e["text"] for e in ow.open_ledger_entries(tmp_path)] == [
        "Add the changelog entry."
    ], "the record is the directive, verbatim and still open"


def test_a_derived_ask_surfaces_as_advisory_by_default(tmp_path: Path) -> None:
    """PROPERTY 3 — the default channel. This is the one that SHOULD move if the
    advisory/blocking policy changes again; that is its job."""
    r = ow.evaluate_completion_lock(tmp_path, "", [_user("Add the changelog entry.")])
    assert [e["text"] for e in r["advisory_asks"]] == ["Add the changelog entry."]
    assert r["open_asks"] == [] and r["blocked"] is False


def test_unreadable_task_file_blocks_and_is_named(tmp_path: Path) -> None:
    """REQ-6: unknown state is not empty."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="completed")
    (tasks / "session-sess1234" / "T-9.json").write_text("{bad", encoding="utf-8")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [], tasks_root=tasks)
    assert r["blocked"] is True
    assert r["open_tasks"] == []
    assert len(r["unreadable"]) == 1
    assert "T-9.json" in " ".join(r["reasons"])


def test_an_unreadable_ledger_does_not_block_while_it_is_advisory(
    tmp_path: Path
) -> None:
    """F1 — SUPERSEDES the old `test_unreadable_ledger_blocks_and_is_named`.

    The demotion to advisory never touched the unreadable path, so the advisory
    source kept exactly one blocking power: being broken. That is the wrong half
    to keep — pure wedge, zero enforcement value, on the source the user was
    told is advisory. It degrades to advisory too, loudly."""
    (tmp_path / ".architect-team").mkdir()
    ow.ledger_path(tmp_path).write_text("{corrupt", encoding="utf-8")

    r = ow.evaluate_completion_lock(tmp_path, "", [])
    assert r["blocked"] is False, "an advisory source cannot wedge a session"
    assert r["unreadable"] == [], "not a blocking violation while advisory"
    assert any("ask-ledger.json" in n for n in r["advisory_notes"]), (
        "surfaced loudly — degraded, not swallowed"
    )


def test_an_unreadable_ledger_still_blocks_when_blocking_is_opted_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction: once the ledger can refuse a stop, an unreadable one
    is unknown state again and REQ-6 applies to it."""
    (tmp_path / ".architect-team").mkdir()
    ow.ledger_path(tmp_path).write_text("{corrupt", encoding="utf-8")
    monkeypatch.setenv(ow.LEDGER_BLOCKING_ENV, "1")

    r = ow.evaluate_completion_lock(tmp_path, "", [])
    assert r["blocked"] is True
    assert len(r["unreadable"]) == 1
    assert "ask-ledger.json" in " ".join(r["reasons"])


def test_an_unreadable_task_store_always_blocks(tmp_path: Path) -> None:
    """F1 must not leak into REQ-6: the TASK store is harness-written ground
    truth, so an unreadable one is unknown state and keeps blocking."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="completed")
    (tasks / "session-sess1234" / "T-9.json").write_text("{bad", encoding="utf-8")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [], tasks_root=tasks)
    assert r["blocked"] is True and len(r["unreadable"]) == 1


def test_an_advisory_note_rides_along_when_something_else_blocks(
    tmp_path: Path
) -> None:
    """Loudly means visible: when the turn IS refused, the degraded ledger is
    named in the reasons the caller already renders."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    (tmp_path / ".architect-team").mkdir()
    ow.ledger_path(tmp_path).write_text("{corrupt", encoding="utf-8")

    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [], tasks_root=tasks)
    assert r["blocked"] is True
    assert r["killswitch"] == ow.DISABLE_TASKS_ENV, "the TASK is the cause"
    assert any("ask-ledger.json" in line for line in r["reasons"])


def test_switching_blocking_on_recovers_the_advisory_period(tmp_path: Path) -> None:
    """F3 — the persistence transition lost history. Directives arrive advisory
    in a fresh repo so nothing is written; the window moves; the operator sets
    the opt-in exactly as the README invites — and the ledger begins at the
    switch, missing precisely the OLDEST asks. On the first persist pass the
    head slice is derived too: it is already loaded, already passed in, and it
    covers the transcript START, which is the region the tail cap loses."""
    import os
    early = [_user("Add rate limiting to the login endpoint.",
                   ts="2026-08-12T09:00:00Z")]
    later = [_user("Bump the version to 3.56.0.", ts="2026-08-12T18:00:00Z")]

    # Advisory period: nothing is written, by design (F-F).
    ow.evaluate_completion_lock(tmp_path, "", early)
    assert not ow.ledger_path(tmp_path).exists()

    # The operator opts in. The early turn has scrolled out of the tail and now
    # survives only in the head slice.
    os.environ[ow.LEDGER_BLOCKING_ENV] = "1"
    try:
        ow.evaluate_completion_lock(tmp_path, "", later, head_records=early,
                                    truncated=True)
    finally:
        del os.environ[ow.LEDGER_BLOCKING_ENV]

    texts = [e["text"] for e in ow.open_ledger_entries(tmp_path)]
    assert "Add rate limiting to the login endpoint." in texts, (
        "the advisory-period directive must survive the switch"
    )
    assert "Bump the version to 3.56.0." in texts


def test_a_resolved_entry_survives_a_later_pass_that_re_sees_its_turn(
    tmp_path: Path
) -> None:
    """CORRECTED (mutation harness): the first draft of this test claimed to pin
    the first-pass restriction on the head sweep, and a mutation that swept the
    head on EVERY pass escaped it. The reason is worth keeping — accumulation
    unions by id with the STORED side winning, so re-deriving a resolved
    directive cannot reopen it, whether the sweep runs once or always. So the
    restriction is a cost guard with no behavioural witness (said plainly in the
    module), and what this test actually defends is the property that makes it
    safe: no resurrection."""
    import os
    early = [_user("Add rate limiting to the login endpoint.")]
    os.environ[ow.LEDGER_BLOCKING_ENV] = "1"
    try:
        ow.evaluate_completion_lock(tmp_path, "", early)
        entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]
        ow.resolve_ledger_entry(tmp_path, entry_id, evidence="shipped")
        assert ow.open_ledger_entries(tmp_path) == []

        ow.evaluate_completion_lock(tmp_path, "", [_user("Something else.")],
                                    head_records=early, truncated=True)
    finally:
        del os.environ[ow.LEDGER_BLOCKING_ENV]

    texts = [e["text"] for e in ow.open_ledger_entries(tmp_path)]
    assert "Add rate limiting to the login endpoint." not in texts, (
        "a resolved entry must not be resurrected by a head sweep"
    )


def test_turn_output_rule_only_fires_when_open_work_exists(tmp_path: Path) -> None:
    """It is a shape constraint on a turn that should not have been final, not a
    general style rule."""
    narrative = [_assistant("## Summary\n\n- did a thing\n- did another")]
    r = ow.evaluate_completion_lock(tmp_path, "", narrative)
    assert r["blocked"] is False, "no open work -> the rule is not evaluated"
    assert r["turn_output"] is None


def test_narrative_turn_with_open_work_is_refused(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="in_progress")
    records = [_assistant("## Where things stand\n\n- T-1 is nearly done\n- T-2 next")]
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert r["blocked"] is True
    assert r["turn_output"] is not None and r["turn_output"]["narrative"] is True
    assert "heading" in r["turn_output"]["markers"]
    assert any("one line of state" in line for line in r["reasons"]), r["reasons"]


def test_terse_turn_with_open_work_does_not_add_a_turn_output_block(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="in_progress")
    records = [_assistant("T-1 in progress.\n16 of 17 open.")]
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert r["blocked"] is True, "still blocked by the open task"
    assert r["turn_output"] is None, "the turn-output rule contributed no block"
    assert r["killswitch"] == ow.DISABLE_TASKS_ENV


def test_turn_output_switch_disables_only_that_rule(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="in_progress")
    monkeypatch.setenv(ow.DISABLE_OUTPUT_ENV, "1")
    records = [_assistant("## Summary\n- one\n- two")]
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert r["turn_output"] is None
    assert r["blocked"] is True and r["killswitch"] == ow.DISABLE_TASKS_ENV


def test_master_switch_named_when_more_than_one_source_fires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blocking opted in (v3.56.0) because this test's point is the killswitch
    ARBITRATION across several blocking sources — which needs two of them to be
    able to block. An advisory ask is not a blocking source."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    monkeypatch.setenv(ow.LEDGER_BLOCKING_ENV, "1")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user("Fix the bug.")],
                                    tasks_root=tasks)
    assert r["blocked"] is True
    assert r["open_tasks"] and r["open_asks"]
    assert r["killswitch"] == ow.DISABLE_ENV, (
        "with several sources firing, name the switch that releases all of them"
    )


def test_an_advisory_ask_leaves_the_task_switch_named(tmp_path: Path) -> None:
    """The arbitration counterpart: with the ledger advisory, only ONE source is
    really blocking, so the precise per-source switch is what gets named."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user("Fix the bug.")],
                                    tasks_root=tasks)
    assert r["blocked"] is True
    assert r["killswitch"] == ow.DISABLE_TASKS_ENV
    assert len(r["advisory_asks"]) == 1 and r["open_asks"] == []


# --- teammate owner-scoping through the entry point --------------------------

_BRIEF = "[CT6-TEAMMATE lock-core RUN turn-boundary-completion-lock]\nYour scope."


def test_teammate_with_no_owned_open_task_may_stop(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending", owner="lock-wiring")
    _write_task(tasks, "sess1234abcd", "T-2", status="pending")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user(_BRIEF)],
                                    tasks_root=tasks)
    assert r["blocked"] is False, "a teammate is never wedged on another lane"
    assert r["open_tasks"] == []


def test_teammate_with_an_owned_open_task_is_blocked_and_it_is_named(tmp_path: Path) -> None:
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="in_progress", owner="lock-core")
    _write_task(tasks, "sess1234abcd", "T-2", status="pending", owner="lock-wiring")
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user(_BRIEF)],
                                    tasks_root=tasks)
    assert r["blocked"] is True
    assert [i["id"] for i in r["open_tasks"]] == ["T-1"]
    assert "T-1" in " ".join(r["reasons"])


def test_a_long_user_prompt_is_an_orchestrator_not_a_teammate(tmp_path: Path) -> None:
    """ADV-8, the worst of the nine in practice. `is_teammate_transcript`'s
    >= 1500-char fallback heuristic fires on a long user prompt containing
    '.architect-team'; `teammate_name` then resolves nothing. Standing down
    there means THE USER'S OWN LONG PROMPTS silently disable the whole gate —
    and the prompt that commissioned this feature is exactly that shape.
    Heuristic-only classification with no token is an ORCHESTRATOR."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending", owner="lock-core")
    _write_task(tasks, "sess1234abcd", "T-2", status="pending")
    long_prompt = ("Build the completion lock.\n" + ("x" * 1600)
                   + "\n.architect-team/reviews/")

    assert rc.is_teammate_transcript([_user(long_prompt)]) is True, (
        "the repro anchor: the heuristic still classifies this as a teammate"
    )
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", [_user(long_prompt)],
                                    tasks_root=tasks)
    assert r["blocked"] is True, "a long user prompt must not disable the gate"
    assert {i["id"] for i in r["open_tasks"]} == {"T-1", "T-2"}, (
        "an orchestrator is held on ALL open tasks, not an owner-scoped subset"
    )


def test_a_genuine_token_without_a_resolvable_name_still_stands_down(
    tmp_path: Path
) -> None:
    """The standdown survives — but ONLY behind a genuine CT6-TEAMMATE token,
    never behind the heuristic. A real worker with an unparseable name must not
    be wedged on lanes it cannot close."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending", owner="lock-core")
    r = ow.evaluate_completion_lock(
        tmp_path, "sess1234abcd",
        [_user("[CT6-TEAMMATE RUN slug]\nYou own the substrate.")],
        tasks_root=tasks)
    assert r["blocked"] is False
    assert r["open_tasks"] == [] and r["open_asks"] == []


# --- F3: the ledger's release valve must be reachable by a human -------------

def test_cli_lists_the_open_asks_with_their_ids(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """F3. Without a user-facing exit the ledger is a one-way ratchet whose only
    release is a kill-switch, and the first false positive makes the user
    disable the whole gate — the same as not shipping it."""
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries([_user("Ship the docs.")]))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]

    assert ow.main(["list", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert entry_id in out and "Ship the docs." in out


def test_cli_resolves_an_entry_with_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries([_user("Ship the docs.")]))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]

    assert ow.main(["resolve", entry_id, "--evidence", "README.md updated",
                    "--root", str(tmp_path)]) == 0
    assert ow.open_ledger_entries(tmp_path) == []
    stored = ow.read_ledger(tmp_path)["entries"][0]
    assert stored["status"] == "resolved" and stored["evidence"] == "README.md updated"


def test_cli_refuses_a_resolve_with_no_evidence_or_an_unknown_id(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """Conservative resolution reaches the CLI too — ambiguous stays open."""
    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries([_user("Ship the docs.")]))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]

    assert ow.main(["resolve", entry_id, "--evidence", "  ",
                    "--root", str(tmp_path)]) != 0
    assert len(ow.open_ledger_entries(tmp_path)) == 1

    assert ow.main(["resolve", "no-such-id", "--evidence", "x",
                    "--root", str(tmp_path)]) != 0
    assert len(ow.open_ledger_entries(tmp_path)) == 1


def test_cli_is_reachable_as_a_real_command(tmp_path: Path) -> None:
    """A user-facing valve nobody can invoke is not a valve. Runs the module the
    way a human would, in a subprocess."""
    import subprocess
    import sys

    ow.accumulate_ledger(tmp_path, ow.derive_ledger_entries([_user("Ship the docs.")]))
    entry_id = ow.read_ledger(tmp_path)["entries"][0]["id"]
    script = Path(ow.__file__)

    listed = subprocess.run(
        [sys.executable, str(script), "list", "--root", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert listed.returncode == 0, listed.stderr
    assert entry_id in listed.stdout

    done = subprocess.run(
        [sys.executable, str(script), "resolve", entry_id,
         "--evidence", "shipped in v3.56.0", "--root", str(tmp_path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert done.returncode == 0, done.stderr
    assert ow.open_ledger_entries(tmp_path) == []


def test_teammate_is_not_held_for_the_users_ledger_asks(tmp_path: Path) -> None:
    """REQ-4 holds a teammate ONLY for tasks it owns. The ask-ledger is the
    USER's directives — a worker cannot resolve those, and its structured report
    back to the Lead is its deliverable, not a violation."""
    tasks = tmp_path / "tasks"
    _write_task(tasks, "sess1234abcd", "T-1", status="pending", owner="someone-else")
    records = [_user(_BRIEF + "\nAlso add the migration."),
               _assistant("## Report\n- built it\n- tests green")]
    r = ow.evaluate_completion_lock(tmp_path, "sess1234abcd", records, tasks_root=tasks)
    assert r["blocked"] is False
    assert r["open_asks"] == [] and r["turn_output"] is None

