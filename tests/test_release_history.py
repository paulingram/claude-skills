"""v3.47.1 — the compact-README + complete-release-history convention.

The README used to carry ~636 lines of accumulated per-release narrative above
its durable content. That narrative now lives in `docs/RELEASE_HISTORY.md`; the
README keeps exactly ONE release section (the current release's spotlight) plus
a visible pointer block to the full history.

These tests pin the convention so it cannot silently regress:

* README carries exactly one NEW-IN release spotlight — each release SWAPS the
  spotlight rather than accumulating another one.
* README carries the house-style POINTER BLOCK, above the spotlight, where the
  narrative used to begin.
* `docs/RELEASE_HISTORY.md` exists, carries the CURRENT release (the
  complete-history convention: the current release appears in both places),
  reaches back to the earliest retained release, and is COMPLETE — it names at
  least the whole recorded move-set enumeration.

Every version literal in a repo-facing assertion is DERIVED (from
`.claude-plugin/plugin.json` or from the README's own spotlight) rather than
hardcoded, so a release bump does not have to edit this file. The mutation
fixtures below do carry literal version strings; those are fixture data, never
assertions about the repo's current version.

The `test_pin_bites_*` cases are mutation tests against the REAL shipped files:
each takes the actual README / history, applies a defect the convention exists
to forbid, and requires the predicate to REJECT it. Two encode breaks that
adversarial review found in this file's first implementation, where the pins
passed against content that had genuinely lost the property:

* B2 — a bare ``"docs/RELEASE_HISTORY.md" in text`` pointer check passed with the
  ENTIRE pointer block deleted, because the "Bumping versions" step-5 line
  elsewhere in the README mentions the same path. The pin now anchors to the
  block's STRUCTURE (its gradient divider plus the link beneath it), so mentions
  somewhere else in the file can no longer hold it up.
* B1 — the history could be truncated from 157 KB to ~6 KB, losing ~50 releases,
  with all pins green: the earliest-anchor and current-version checks are each
  satisfied by a handful of surviving bytes. The pin now also counts release
  identities against a recorded floor.
"""
import json
import re
from pathlib import Path

import pytest

README = ("README.md",)
HISTORY = ("docs", "RELEASE_HISTORY.md")
PLUGIN_JSON = (".claude-plugin", "plugin.json")

#: The countable marker of a release block in this README's grammar — the
#: gradient spotlight divider the readme-styling house aesthetic puts above a
#: release section. Anchored to the whole line so prose that merely mentions
#: "NEW IN" is not counted.
SPOTLIGHT_RE = re.compile(
    r"^█▓▒░\s+◆\s+NEW IN v(\d+\.\d+\.\d+)\s+◆\s+░▒▓█\s*$",
    re.MULTILINE,
)

#: The pointer block's own divider title — the structural anchor a stray mention
#: of the path elsewhere in the README cannot satisfy.
POINTER_DIVIDER_RE = re.compile(r"^█▓▒░\s+◆\s+RELEASE HISTORY\s+◆\s+░▒▓█\s*$")

#: The path the pointer block must link.
HISTORY_POINTER = "docs/RELEASE_HISTORY.md"

FENCE = "```"
#: How far below the divider's closing fence the linking prose may sit.
POINTER_PROSE_MAX_LINES = 8

#: The earliest release the moved narrative reaches — the v2.3.0-era digest
#: marker at the tail of the history. Its loss would mean the move dropped the
#: oldest regions.
EARLIEST_RELEASE_ANCHOR = "CARRIED FROM v2.3.0"

#: Every grammar this README family uses to NAME a release: the `### vX.Y.Z`
#: section heading, the `### Carried forward from vX.Y.Z` heading, and the
#: NEW-IN / CARRIED-FROM gradient divider titles.
#:
#: Counting only `### v` headings would be WRONG as a completeness floor — the
#: real history has 43 of those but names 55 distinct releases, the rest through
#: the divider and carried-forward grammars. Do not collapse this to a single
#: pattern without re-deriving the floor below.
RELEASE_IDENTITY_RES = (
    re.compile(r"^### (v\d+\.\d+(?:\.\d+)?)\b", re.MULTILINE),
    re.compile(r"^### Carried forward from (v\d+\.\d+(?:\.\d+)?)\b", re.MULTILINE),
    re.compile(r"^█▓▒░\s+◆\s+(?:NEW IN|CARRIED FROM) (v\d+\.\d+(?:\.\d+)?)", re.MULTILINE),
)

#: The move-set enumeration recorded by the extraction verification AT THE TIME
#: OF THE MOVE — see the RELEASE ENUMERATION section of
#: `.architect-team/demos/cr-docs-mover/byte-identical-verification.txt`:
#: "release identities named by the PRE-change README : 55 / reachable AFTER
#: (README + history): 55 / lost in the move: NONE".
#:
#: A floor, never an equality: releases are only ever APPENDED to the history, so
#: a later release raises the real count and this pin keeps holding. It exists to
#: catch the history being gutted, not to police growth.
MIN_RELEASE_IDENTITIES = 55


def _read(plugin_root: Path, parts: tuple[str, ...]) -> str:
    target = plugin_root.joinpath(*parts)
    assert target.exists(), f"{target} missing"
    return target.read_text(encoding="utf-8")


def spotlight_versions(text: str) -> list[str]:
    """Every release version whose spotlight divider appears in `text`."""
    return SPOTLIGHT_RE.findall(text)


def find_pointer_block(text: str) -> tuple[int, int] | None:
    """Locate the house-style pointer block; return its (start, end) line indices.

    The block is a bare-fenced RELEASE HISTORY gradient divider followed, within
    a few lines, by prose linking the history file. BOTH halves are required —
    that is what makes the pin bite when the block is deleted even though the
    path is still mentioned elsewhere in the README (break B2).
    """
    lines = text.splitlines()
    title = next((i for i, ln in enumerate(lines) if POINTER_DIVIDER_RE.match(ln)), None)
    if title is None:
        return None

    start = next((i for i in range(title - 1, max(title - 4, -1), -1)
                  if lines[i].strip() == FENCE), None)
    close = next((i for i in range(title + 1, min(title + 4, len(lines)))
                  if lines[i].strip() == FENCE), None)
    if start is None or close is None:
        return None

    end = next((i for i in range(close + 1,
                                 min(close + 1 + POINTER_PROSE_MAX_LINES, len(lines)))
                if HISTORY_POINTER in lines[i]), None)
    if end is None:
        return None
    return start, end


def points_at_release_history(text: str) -> bool:
    return find_pointer_block(text) is not None


def release_identities(text: str) -> set[str]:
    """Every distinct release this text NAMES, across all three grammars."""
    found: set[str] = set()
    for pattern in RELEASE_IDENTITY_RES:
        found.update(pattern.findall(text))
    return found


def _without_pointer_block(text: str) -> str:
    """The real README with its pointer block excised — the B2 mutation."""
    span = find_pointer_block(text)
    assert span is not None, "fixture precondition: the real README has a pointer block"
    start, end = span
    lines = text.splitlines()
    return "\n".join(lines[:start] + lines[end + 1:])


# --- the compact README -----------------------------------------------------


def test_readme_has_exactly_one_release_spotlight(plugin_root: Path) -> None:
    """The convention is SWAP, not accumulate: one spotlight, the current one."""
    found = spotlight_versions(_read(plugin_root, README))
    assert len(found) == 1, (
        f"README must carry exactly ONE release spotlight — found {len(found)}: "
        f"{found}. Each release swaps the README spotlight and appends to "
        f"{HISTORY_POINTER}; it does not add a second spotlight."
    )


def test_readme_spotlight_is_the_current_release(plugin_root: Path) -> None:
    """The retained spotlight must be the version plugin.json ships."""
    version = json.loads(_read(plugin_root, PLUGIN_JSON))["version"]
    found = spotlight_versions(_read(plugin_root, README))
    assert found == [version], (
        f"README's release spotlight must name the current release {version!r} "
        f"(plugin.json) — found {found}"
    )


def test_readme_carries_the_pointer_block(plugin_root: Path) -> None:
    """A reader who wants the full history must be able to find it.

    Anchored to the BLOCK, not to any mention of the path: the README names
    `docs/RELEASE_HISTORY.md` in its 'Bumping versions' section too, and those
    mentions must not be able to satisfy this pin.
    """
    assert points_at_release_history(_read(plugin_root, README)), (
        f"README has no house-style pointer block for {HISTORY_POINTER} — a "
        f"RELEASE HISTORY gradient divider followed by prose linking the file. "
        f"The compact README is only honest if the full history is one click away."
    )


def test_pointer_block_sits_where_the_narrative_began(plugin_root: Path) -> None:
    """Above the spotlight — the position the design specifies."""
    text = _read(plugin_root, README)
    span = find_pointer_block(text)
    assert span is not None, "no pointer block to position-check"
    lines = text.splitlines()
    spotlight_line = next(
        (i for i, ln in enumerate(lines) if SPOTLIGHT_RE.match(ln)), None
    )
    assert spotlight_line is not None, "no spotlight divider to position against"
    assert span[0] < spotlight_line, (
        f"the pointer block (line {span[0] + 1}) must come BEFORE the release "
        f"spotlight (line {spotlight_line + 1}) — it belongs where the release "
        f"narrative used to begin"
    )


# --- the complete history ---------------------------------------------------


def test_release_history_exists_and_is_non_empty(plugin_root: Path) -> None:
    assert _read(plugin_root, HISTORY).strip(), (
        f"{'/'.join(HISTORY)} is empty — the moved release narrative has no home"
    )


def test_release_history_carries_the_current_release(plugin_root: Path) -> None:
    """Complete-history convention — the current release lives here TOO.

    The version is read from plugin.json, never hardcoded, so this pin survives
    every release bump.
    """
    version = json.loads(_read(plugin_root, PLUGIN_JSON))["version"]
    body = _read(plugin_root, HISTORY)
    assert f"v{version}" in body, (
        f"{'/'.join(HISTORY)} does not carry the current release v{version} — "
        f"the convention is COMPLETE history including current, so each release "
        f"appends here as well as swapping the README spotlight"
    )


def test_release_history_reaches_the_earliest_retained_release(
    plugin_root: Path,
) -> None:
    """The tail of the moved narrative must have survived the move."""
    body = _read(plugin_root, HISTORY)
    assert EARLIEST_RELEASE_ANCHOR in body, (
        f"{'/'.join(HISTORY)} is missing the earliest-release anchor "
        f"{EARLIEST_RELEASE_ANCHOR!r} — the oldest region of the move-set is gone"
    )


def test_release_history_is_complete(plugin_root: Path) -> None:
    """The whole move-set enumeration is still there.

    The earliest-anchor and current-version pins above are each satisfied by a
    few surviving bytes, so neither notices a history gutted in the middle. This
    one counts.
    """
    found = release_identities(_read(plugin_root, HISTORY))
    assert len(found) >= MIN_RELEASE_IDENTITIES, (
        f"{'/'.join(HISTORY)} names only {len(found)} releases — the recorded "
        f"move-set enumeration is {MIN_RELEASE_IDENTITIES} and releases are only "
        f"ever appended, so the history has lost content"
    )


def test_every_readme_spotlight_release_is_in_the_history(plugin_root: Path) -> None:
    """Nothing the README spotlights may be absent from the complete history."""
    body = _read(plugin_root, HISTORY)
    missing = [
        v for v in spotlight_versions(_read(plugin_root, README)) if f"v{v}" not in body
    ]
    assert not missing, (
        f"{'/'.join(HISTORY)} is missing releases the README spotlights: {missing}"
    )


# --- the pins bite ----------------------------------------------------------
# Mutation tests against the REAL shipped files: take the actual content, break
# it the way the convention forbids, and require the predicate to reject it.


def test_pin_bites_on_a_second_spotlight(plugin_root: Path) -> None:
    """A future release that ADDS a spotlight instead of swapping is caught."""
    text = _read(plugin_root, README)
    assert len(spotlight_versions(text)) == 1, "fixture precondition"
    doubled = text + "\n\n█▓▒░  ◆  NEW IN v9.9.9  ◆  ░▒▓█\n"
    assert len(spotlight_versions(doubled)) == 2, (
        "the spotlight counter did not see an added spotlight"
    )


def test_pin_bites_on_a_deleted_pointer_block(plugin_root: Path) -> None:
    """Break B2, as a standing pin.

    Deleting the whole pointer block must fail the pin EVEN THOUGH the README's
    'Bumping versions' step 5 still mentions `docs/RELEASE_HISTORY.md`. The
    original bare-substring check passed this mutation — which is exactly why the
    pin is anchored structurally now.
    """
    text = _read(plugin_root, README)
    mutated = _without_pointer_block(text)

    surviving = mutated.count(HISTORY_POINTER)
    assert surviving > 0, (
        "fixture precondition lost: this mutation only bites while the README "
        "mentions the path somewhere OUTSIDE the pointer block — that is the "
        "condition under which a bare substring check gives a false pass"
    )
    assert not points_at_release_history(mutated), (
        f"the pointer pin still passes with the pointer block deleted "
        f"({surviving} stray mentions of {HISTORY_POINTER!r} survive elsewhere) — "
        f"it is anchored to a substring, not to the block"
    )


def test_pin_bites_on_a_truncated_history(plugin_root: Path) -> None:
    """Break B1, as a standing pin.

    The real truncation attack: keep the header and the current-release section,
    drop everything older. The earliest-anchor pin and the current-version pin
    both still pass on the result — only the completeness count catches it.
    """
    body = _read(plugin_root, HISTORY)
    version = json.loads(_read(plugin_root, PLUGIN_JSON))["version"]

    cut = body.find("█▓▒░  ◆  NEW IN v3.41.0")
    assert cut > 0, "fixture precondition: the history's second section moved"
    truncated = body[:cut] + f"\n{EARLIEST_RELEASE_ANCHOR} — see git history\n"

    assert f"v{version}" in truncated, "the current-version pin would still pass"
    assert EARLIEST_RELEASE_ANCHOR in truncated, "the earliest-anchor pin would still pass"
    assert len(truncated) < len(body) / 10, "the mutation did not actually truncate"

    assert len(release_identities(truncated)) < MIN_RELEASE_IDENTITIES, (
        f"a history truncated from {len(body)} B to {len(truncated)} B still "
        f"satisfies the completeness floor — the floor is not measuring content"
    )


def test_pin_bites_on_a_missing_history_file(tmp_path: Path) -> None:
    """`_read` fails loudly rather than yielding empty text for a missing file."""
    (tmp_path / "docs").mkdir()
    with pytest.raises(AssertionError):
        _read(tmp_path, HISTORY)
