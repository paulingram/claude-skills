# -*- coding: utf-8 -*-
"""Deterministic capability-index generator (REQ-003).

Stdlib-only (PyYAML used only if importable, exactly as `tests/helpers/frontmatter.py`
does), no import-time side effects. Scans this plugin's three AI-facing capability
inventories — `skills/*/SKILL.md`, `commands/*.md`, `agents/*.md` — and emits a
single generated catalog, `docs/CAPABILITY_INDEX.md`: one line per capability, its
identity name plus the first sentence of its frontmatter description (truncated to a
fixed width). The file is GENERATED, never hand-edited; drift between it and the live
frontmatter is caught by `tests/test_capability_index.py`.

It mirrors the established `scripts/compliance/instruction_compliance.py` engine
shape: a self-contained frontmatter reader (so `scripts/` never imports `tests/`),
pure builder functions, a byte-stable serializer, and a `__main__` CLI with no work
at import time.

Public surface::

    build_inventory(root)  -> {"skills": [(name, summary), ...],
                               "commands": [...], "agents": [...]}   # each sorted
    render_index(root)     -> str    # the exact bytes of docs/CAPABILITY_INDEX.md
    write_index(root)      -> Path    # writes the file, returns its path
    check_index(root)      -> {"ok": bool, "reason": str, "path": str}

CLI:  capability_index.py [--write | --check] [<root>]
  --write  regenerate docs/CAPABILITY_INDEX.md in place (default action)
  --check  compare the committed file to a fresh render; exit non-zero on drift
"""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any, Optional, Union

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False


# The generated artifact lives here. `render_index` is the source of truth for its
# bytes; the committed copy is a materialized cache the suite keeps fresh.
INDEX_REL_PATH = "docs/CAPABILITY_INDEX.md"
REGEN_COMMAND = "python3 scripts/docs_tooling/capability_index.py --write"

# Per-capability summary width. The first sentence of the description is truncated
# to this many characters at a word boundary (textwrap.shorten), so every catalog
# line stays scannable. ~140 chars per the REQ-003 contract.
SUMMARY_MAX_CHARS = 140
# The truncation marker appended by `_summary`. This module is utf-8 SOURCE (the
# `# -*- coding: utf-8 -*-` declaration above + explicit encoding="utf-8" on every
# read/write), exactly like the sibling engines scripts/compliance/instruction_compliance.py
# and scripts/claude_md/claude_md_efficiency.py — it is NOT pure-ASCII source and does
# not claim to be; the em-dashes in this file and this ellipsis are intentional utf-8
# literals, and the suite runs green under both Windows cp1252 and PYTHONUTF8=1.
_ELLIPSIS = "…"

# A frontmatter key line at column 0 with a same-line plain-scalar value. Mirrors
# the instruction-compliance engine — every description in this corpus is a
# single-line scalar (a block-scalar `>`/`|` description does not occur), so a
# tolerant flat read is sufficient and yaml-independent.
_RE_FM_KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")

# YAML double-quoted-scalar escape table. The flat fallback MUST decode these
# identically to `yaml.safe_load`, or the generated index would differ byte-for-byte
# between a PyYAML machine and a no-PyYAML machine — silently failing `--check` on
# the other environment. In this corpus only `\"` occurs (one skill description);
# the rest of the table is for robustness. The one deliberate divergence from
# yaml.safe_load is `\L`/`\P` (the YAML line/paragraph separators, U+2028/U+2029):
# they are normalized to a plain space, since a raw separator would break this
# tool's one-line-per-entry output contract. That case is unreachable in this
# corpus (no description uses them), so the flat==PyYAML parity test stays green.
_DQ_ESCAPES = {
    "0": "\x00", "a": "\x07", "b": "\x08", "t": "\t", "\t": "\t",
    "n": "\n", "v": "\x0b", "f": "\x0c", "r": "\r", "e": "\x1b",
    " ": " ", '"': '"', "/": "/", "\\": "\\",
    "N": "\x85", "_": "\xa0", "L": " ", "P": " ",
}


def _unescape_double_quoted(s: str) -> str:
    """Decode a YAML double-quoted scalar's body the way yaml.safe_load does.

    A malformed `\\x`/`\\u`/`\\U` sequence, or an unknown escape, is kept
    literally (PyYAML would raise; the flat fallback stays lossless rather than
    crash on an input the suite would already reject upstream).
    """
    out: list[str] = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == "\\" and i + 1 < n:
            nxt = s[i + 1]
            try:
                if nxt == "x" and i + 4 <= n:
                    out.append(chr(int(s[i + 2:i + 4], 16))); i += 4; continue
                if nxt == "u" and i + 6 <= n:
                    out.append(chr(int(s[i + 2:i + 6], 16))); i += 6; continue
                if nxt == "U" and i + 10 <= n:
                    out.append(chr(int(s[i + 2:i + 10], 16))); i += 10; continue
            except ValueError:
                out.append(c); i += 1; continue
            if nxt in _DQ_ESCAPES:
                out.append(_DQ_ESCAPES[nxt]); i += 2; continue
            out.append(c); i += 1; continue
        out.append(c); i += 1
    return "".join(out)


def _split_frontmatter(text: str) -> Optional[str]:
    """Return the raw frontmatter block text, or None when the file has none."""
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    return parts[1]


def _flat_keys(fm_text: str) -> dict[str, str]:
    """Tolerant column-0 `key: value` extraction (never raises).

    Values are single-line in this corpus, so a flat parse is sufficient. When
    PyYAML is importable and parses the block into a mapping, its values win
    (it handles every quoting edge); otherwise the flat scan is the fallback,
    exactly as `tests/helpers/frontmatter.py` does.
    """
    flat: dict[str, str] = {}
    for raw in fm_text.splitlines():
        if not raw or raw[0] in " \t#":
            continue  # indented continuation / comment / blank — not a top-level key
        m = _RE_FM_KEY.match(raw)
        if not m:
            continue
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] == '"':
            val = _unescape_double_quoted(val[1:-1])
        elif len(val) >= 2 and val[0] == val[-1] == "'":
            val = val[1:-1].replace("''", "'")  # YAML single-quote escaping
        flat[m.group(1)] = val

    if HAS_YAML:
        try:
            parsed = yaml.safe_load(fm_text)
        except Exception:  # yaml.YAMLError and subclasses — keep the flat read
            parsed = None
        if isinstance(parsed, dict):
            for key, value in parsed.items():
                if isinstance(key, str) and isinstance(value, str):
                    flat[key] = value
    return flat


def _first_sentence(description: str) -> str:
    """The first sentence of a description, whitespace-collapsed.

    "First sentence" ends at the first period that is followed by whitespace or
    the end of the string — so mid-token dots (`.md`, `e.g.`, `v3.32.0`) never cut
    it short. When no such period exists, the whole (collapsed) description is the
    sentence.
    """
    collapsed = " ".join(description.split())
    m = re.search(r"\.(?=\s|$)", collapsed)
    sentence = collapsed[: m.start()] if m else collapsed
    return sentence.strip()


def _summary(description: str, limit: int = SUMMARY_MAX_CHARS) -> str:
    """The catalog summary: first sentence, truncated at a word boundary."""
    sentence = _first_sentence(description)
    if not sentence:
        return ""
    # textwrap.shorten collapses whitespace and truncates at a word boundary,
    # keeping the result <= `limit` including the placeholder — deterministic.
    # break_on_hyphens=False keeps hyphenated identifiers (e.g. `bug-fix-pipeline`)
    # whole rather than cutting them mid-token.
    return textwrap.shorten(
        sentence, width=limit, placeholder=" " + _ELLIPSIS, break_on_hyphens=False
    )


def _read_summary(path: Path, fallback_name: str) -> tuple[str, str]:
    """Return (display_name, summary) for one capability file.

    The display name is the frontmatter `name` when present (skills + agents),
    otherwise the on-disk identifier (`fallback_name`) — commands carry no `name`
    field, so their filename stem is their identity. The identity is what the
    suite pins name==dir / name==stem elsewhere, so the two never disagree.
    """
    text = path.read_text(encoding="utf-8")
    fm_text = _split_frontmatter(text)
    keys = _flat_keys(fm_text) if fm_text is not None else {}
    name = keys.get("name") or fallback_name
    summary = _summary(keys.get("description", ""))
    return name, summary


def build_inventory(root: Union[str, Path]) -> dict[str, list[tuple[str, str]]]:
    """The plugin's three capability inventories, each a name-sorted (name, summary)."""
    root = Path(root)

    skills: list[tuple[str, str]] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.glob("*")):
            sk = d / "SKILL.md"
            if sk.exists():
                skills.append(_read_summary(sk, d.name))

    commands: list[tuple[str, str]] = []
    commands_dir = root / "commands"
    if commands_dir.is_dir():
        for p in sorted(commands_dir.glob("*.md")):
            commands.append(_read_summary(p, p.stem))

    agents: list[tuple[str, str]] = []
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for p in sorted(agents_dir.glob("*.md")):
            agents.append(_read_summary(p, p.stem))

    return {
        "skills": sorted(skills),
        "commands": sorted(commands),
        "agents": sorted(agents),
    }


def _render_section(title: str, entries: list[tuple[str, str]]) -> list[str]:
    lines = [f"## {title} ({len(entries)})", ""]
    for name, summary in entries:
        lines.append(f"- **{name}** — {summary}" if summary else f"- **{name}**")
    lines.append("")
    return lines


def render_index(root: Union[str, Path]) -> str:
    """Render the exact, byte-stable contents of docs/CAPABILITY_INDEX.md."""
    inv = build_inventory(root)
    lines: list[str] = [
        "# Capability Index",
        "",
        "<!-- GENERATED FILE — do not edit by hand.",
        f"     Regenerate: {REGEN_COMMAND}",
        "     Drift from the live skills/ commands/ agents/ frontmatter is caught",
        "     by tests/test_capability_index.py. -->",
        "",
        "Every capability CLAUDE TEAM SIX ships, one line each, derived from the "
        "`name` +",
        "`description` frontmatter of every skill, command, and agent. This file is",
        "generated, never hand-edited — after adding or renaming any skill, command,",
        f"or agent, regenerate it with `{REGEN_COMMAND}`.",
        "",
    ]
    lines += _render_section("Skills", inv["skills"])
    lines += _render_section("Commands", inv["commands"])
    lines += _render_section("Agents", inv["agents"])
    # Exactly one trailing newline, no trailing blank-line accumulation.
    return "\n".join(lines).rstrip("\n") + "\n"


def write_index(root: Union[str, Path]) -> Path:
    """Regenerate docs/CAPABILITY_INDEX.md in place; return its path."""
    root = Path(root)
    path = root / INDEX_REL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_index(root), encoding="utf-8")
    return path


def check_index(root: Union[str, Path]) -> dict[str, Any]:
    """Compare the committed docs/CAPABILITY_INDEX.md to a fresh render.

    Returns `{"ok": bool, "reason": str, "path": str}`. `ok` is False when the
    file is missing or has drifted from what the live frontmatter would render —
    i.e., a capability was added / renamed / re-described, or the file was
    hand-edited, without regenerating.
    """
    root = Path(root)
    path = root / INDEX_REL_PATH
    expected = render_index(root)
    if not path.exists():
        return {"ok": False, "reason": f"{INDEX_REL_PATH} is missing", "path": str(path)}
    actual = path.read_text(encoding="utf-8")
    if actual != expected:
        return {
            "ok": False,
            "reason": (
                f"{INDEX_REL_PATH} is stale — it does not match the live "
                f"skills/ commands/ agents/ frontmatter. Regenerate with "
                f"`{REGEN_COMMAND}`."
            ),
            "path": str(path),
        }
    return {"ok": True, "reason": "fresh", "path": str(path)}


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: regenerate (--write, default) or verify (--check) the capability index."""
    import argparse

    parser = argparse.ArgumentParser(description="Capability-index generator (REQ-003).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="regenerate the index (default)")
    mode.add_argument("--check", action="store_true", help="verify the committed index is fresh")
    parser.add_argument("root", nargs="?", default=".", help="repo root (default: cwd)")
    args = parser.parse_args(argv)

    if args.check:
        result = check_index(args.root)
        if result["ok"]:
            print(f"capability-index: fresh — {result['path']}")
            return 0
        print(f"capability-index: DRIFT — {result['reason']}")
        return 1

    path = write_index(args.root)
    inv = build_inventory(args.root)
    print(
        f"capability-index: wrote {path} "
        f"({len(inv['skills'])} skills / {len(inv['commands'])} commands / "
        f"{len(inv['agents'])} agents)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
