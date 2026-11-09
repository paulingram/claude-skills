"""Instruction-surface readers for the structural tests (v4.0.0).

v4.0.0 moves most discipline text out of the big SKILL.md bodies into
``references/*.md`` chapters behind STOP pointers, and moves the five compiled
agent boilerplate blocks into the ``ct6-agent-core`` skill that every agent
preloads through its ``skills:`` frontmatter. The invariant the wording-pin
tests protect is "the surface an agent actually receives carries this rule", so
these helpers return that surface: the file PLUS the chapters it points at.

* ``skill_surface(name)``   -> ``skills/<name>/SKILL.md`` + every
  ``skills/<name>/references/**/*.md`` (sorted, each prefixed by a marker line).
* ``agent_surface(name)``   -> ``agents/<name>.md`` + ``agents/references/<name>.md``
  when present + the ``SKILL.md`` of every skill named in the agent's ``skills:``
  frontmatter (the preloaded skills).
* ``command_surface(name)`` -> ``commands/<name>.md`` (commands carry no chapters).

Every helper is pure and reads only from ``root`` (default: the repo root), so a
test that copies the plugin into a tmp dir passes ``root=`` and sees that copy.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]

_MARKER = "\n\n<!-- surface: {rel} -->\n"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _references(dir_path: Path) -> List[Path]:
    ref_dir = dir_path / "references"
    if not ref_dir.is_dir():
        return []
    return sorted(p for p in ref_dir.rglob("*.md") if p.is_file())


_POINTER_RE = re.compile(r"`((?:skills/[a-z0-9-]+/|agents/)?references/[A-Za-z0-9_./-]+\.md)`")


def _strip_h1(text: str) -> str:
    """Drop the chapter's ``# Title`` line (wherever it sits before the first
    ``## ``, since some chapters open with a STOP line) so the chapter sits
    under its stub's heading without adding a second H1 to the surface."""
    lines = text.lstrip("\n").split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## "):
            break
        if line.startswith("# "):
            del lines[i]
            break
    return "\n".join(lines).strip("\n")


def _expand_pointers(text: str, base_dir: Path, root: Path) -> tuple[str, set[Path]]:
    """Splice each referenced chapter in right after the line that points at it.

    A STOP pointer stands where the full section used to be, so the surface an
    agent receives when it follows the pointer is the section in place. Tests
    that slice a section by its ``## `` heading therefore keep seeing the whole
    section. Returns the expanded text and the set of chapter paths spliced.
    """
    out: list[str] = []
    seen: set[Path] = set()
    pending: list[tuple[str, Path]] = []

    def flush() -> None:
        # Splice the section's chapters at the END of the section (just before
        # the next ``## `` heading), so a pointer that sits inside a table or
        # mid-paragraph never breaks the table or the paragraph it sits in.
        while pending:
            rel, cand = pending.pop(0)
            out.append(_MARKER.format(rel=rel).rstrip("\n"))
            out.append(_strip_h1(_read(cand)))

    for line in text.split("\n"):
        if line.startswith("## "):
            flush()
        out.append(line)
        for rel in _POINTER_RE.findall(line):
            cand = (root / rel) if rel.startswith(("skills/", "agents/")) else (base_dir / rel)
            cand = cand.resolve()
            if cand in seen or not cand.is_file():
                continue
            seen.add(cand)
            pending.append((rel, cand))
    flush()
    return "\n".join(out), seen


def skill_surface(name: str, root: Path | str = REPO_ROOT) -> str:
    """SKILL.md with every pointed-at chapter spliced in place, plus any
    remaining ``references/**/*.md`` chapter appended at the end."""
    root = Path(root)
    skill_dir = root / "skills" / name
    text, spliced = _expand_pointers(_read(skill_dir / "SKILL.md"), skill_dir, root)
    for ref in _references(skill_dir):
        if ref.resolve() in spliced:
            continue
        rel = ref.relative_to(skill_dir).as_posix()
        text += _MARKER.format(rel=rel) + _read(ref)
    return text


def _frontmatter_skills(text: str) -> List[str]:
    """The ``skills:`` list of an agent's frontmatter (inline or block form)."""
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end == -1:
        return []
    fm = text[3:end]
    m = re.search(r"^skills:[ \t]*(.*)$", fm, re.M)
    if not m:
        return []
    inline = m.group(1).strip()
    if inline.startswith("["):
        return [s.strip().strip("'\"") for s in inline.strip("[]").split(",") if s.strip()]
    if inline:
        return [inline.strip("'\"")]
    out: List[str] = []
    for line in fm[m.end():].splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s+-\s+", line):
            out.append(re.sub(r"^\s+-\s+", "", line).strip().strip("'\""))
            continue
        break
    return out


def agent_surface(name: str, root: Path | str = REPO_ROOT) -> str:
    """agents/<name>.md plus its reference chapter and its preloaded skills."""
    root = Path(root)
    stem = name[:-3] if name.endswith(".md") else name
    agent_path = root / "agents" / f"{stem}.md"
    text, spliced = _expand_pointers(_read(agent_path), root / "agents", root)
    ref = root / "agents" / "references" / f"{stem}.md"
    if ref.is_file() and ref.resolve() not in spliced:
        text += _MARKER.format(rel=f"agents/references/{stem}.md") + _read(ref)
    for skill in _frontmatter_skills(text):
        skill_md = root / "skills" / skill / "SKILL.md"
        if skill_md.is_file():
            # The compiler's fence comments are not part of what an agent reads
            # as a block, so they are dropped from the surface.
            body = re.sub(r"^<!-- ct6:block:[a-z0-9-]+:(?:begin|end) -->\n?", "", _read(skill_md), flags=re.M)
            text += _MARKER.format(rel=f"skills/{skill}/SKILL.md") + body
    return text


def command_surface(name: str, root: Path | str = REPO_ROOT) -> str:
    """commands/<name>.md (commands have no chapters; kept for symmetry)."""
    root = Path(root)
    stem = name[:-3] if name.endswith(".md") else name
    return _read(root / "commands" / f"{stem}.md")


def surface_read(path: Path | str) -> str:
    """Read ``path`` as the surface an agent receives: an ``agents/<x>.md`` file
    becomes ``agent_surface``, a ``skills/<x>/SKILL.md`` becomes
    ``skill_surface``, anything else is read verbatim. Use this where a test
    reads a path held in a variable, so the surface follows the variable."""
    p = Path(path)
    parts = p.resolve().parts
    if len(parts) >= 2 and parts[-2] == "agents" and p.suffix == ".md":
        root = p.resolve().parents[1]
        if (root / "skills").is_dir():
            return agent_surface(p.stem, root=root)
    if p.name == "SKILL.md" and len(parts) >= 3 and parts[-3] == "skills":
        return skill_surface(p.resolve().parent.name, root=p.resolve().parents[2])
    return p.read_text(encoding="utf-8")
