"""Agent boilerplate guard -- v4.0.0 contract.

Until v3.67.0 this tool compiled five canonical boilerplate blocks (forbidden
git operations, checkpoint discipline, operating context, operating principles,
reporting and escalation) into every ``agents/*.md`` file and kept the 39 copies
byte-identical to ``agent_boilerplate_blocks.py``. v4.0.0 (proposal change 4)
moves the one canonical copy into ``skills/ct6-agent-core/SKILL.md`` -- rendered
there by ``compile_skills.py`` from the same source strings -- and every agent
PRELOADS it through its ``skills:`` frontmatter. The surface an agent receives is
unchanged; the maintenance duplication is gone.

So the contract this tool now holds is the inverse of the old one:

* no agent carries a canonical block heading in its own body any more
  (the three operating-context VARIANT agents keep their role-specific
  ``## Operating context`` section, which was never canonical text);
* every agent's frontmatter ``skills:`` list names ``ct6-agent-core``;
* ``skills/ct6-agent-core/SKILL.md`` is in sync with the canonical strings
  (``compile_skills.py --check`` owns that half; this tool reports it).

``--check`` exits non-zero on drift and names it; without ``--check`` the tool
performs the conversion (strips a stray canonical block, adds the preload).
Stdlib-only; no import-time side effects.
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Dict, List, Optional

try:
    from scripts.setup import agent_boilerplate_blocks as B
except ImportError:  # pragma: no cover - run as a script from scripts/setup
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import agent_boilerplate_blocks as B  # type: ignore[no-redef]

CORE_SKILL = "ct6-agent-core"
VARIANT_AGENTS = list(B.OPERATING_CONTEXT_VARIANT_AGENTS)
CANONICAL_HEADINGS = tuple(spec["heading"] for spec in B.BLOCKS.values())


def _default_agents_dir() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2] / "agents"


def _read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _frontmatter_bounds(text_lf: str) -> Optional[tuple[int, int]]:
    """(start, end) character offsets of the frontmatter body, or None."""
    if not text_lf.startswith("---\n"):
        return None
    end = text_lf.find("\n---", 4)
    if end == -1:
        return None
    return 4, end


def preloaded_skills(text_lf: str) -> List[str]:
    """The ``skills:`` list of an agent's frontmatter (inline or block form)."""
    bounds = _frontmatter_bounds(text_lf)
    if bounds is None:
        return []
    fm = text_lf[bounds[0]:bounds[1]]
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


def stray_blocks(stem: str, text_lf: str) -> List[str]:
    """Canonical block headings still present in the agent body."""
    found = []
    for heading in CANONICAL_HEADINGS:
        if heading == B.OPERATING_CONTEXT_HEADING and stem in VARIANT_AGENTS:
            continue
        if re.search(r"^" + re.escape(heading) + r"\s*$", text_lf, re.M):
            found.append(heading)
    return found


def classify_agents(agents_dir: pathlib.Path) -> Dict[str, List[str]]:
    """``standard`` agents preload the core and carry no canonical block;
    ``variant`` are the three operating-context variants (also preloading the
    core); ``other`` is everything that drifts from the contract."""
    result: Dict[str, List[str]] = {"standard": [], "variant": [], "other": []}
    for path in sorted(pathlib.Path(agents_dir).glob("*.md")):
        text = _read(path)
        ok = CORE_SKILL in preloaded_skills(text) and not stray_blocks(path.stem, text)
        if not ok:
            result["other"].append(path.stem)
        elif path.stem in VARIANT_AGENTS:
            result["variant"].append(path.stem)
        else:
            result["standard"].append(path.stem)
    return result


def drift_report(agents_dir: pathlib.Path) -> Dict[str, List[str]]:
    """stem -> list of drift reasons for every drifting agent."""
    report: Dict[str, List[str]] = {}
    for path in sorted(pathlib.Path(agents_dir).glob("*.md")):
        text = _read(path)
        reasons = []
        if CORE_SKILL not in preloaded_skills(text):
            reasons.append(f"frontmatter skills: does not preload {CORE_SKILL}")
        for heading in stray_blocks(path.stem, text):
            reasons.append(f"carries the canonical block {heading!r} in its body")
        if reasons:
            report[path.stem] = reasons
    return report


def find_drift(agents_dir: pathlib.Path) -> List[str]:
    """Sorted stems of agents that drift from the v4.0.0 contract."""
    return sorted(drift_report(agents_dir))


def _remove_section(text_lf: str, heading: str) -> str:
    lines = text_lf.split("\n")
    out: List[str] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip() == heading:
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def _add_preload(text_lf: str) -> str:
    bounds = _frontmatter_bounds(text_lf)
    if bounds is None:
        return text_lf
    skills = preloaded_skills(text_lf)
    if CORE_SKILL in skills:
        return text_lf
    fm = text_lf[bounds[0]:bounds[1]]
    if re.search(r"^skills:", fm, re.M):
        # append to an existing block list
        return text_lf.replace("skills:\n", f"skills:\n  - {CORE_SKILL}\n", 1)
    return text_lf[:bounds[1]] + f"\nskills:\n  - {CORE_SKILL}" + text_lf[bounds[1]:]


def sync(agents_dir: pathlib.Path) -> List[str]:
    """Convert drifting agents in place. Returns sorted changed stems."""
    changed = []
    for path in sorted(pathlib.Path(agents_dir).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        text = raw.replace("\r\n", "\n")
        new = text
        for heading in stray_blocks(path.stem, text):
            new = _remove_section(new, heading)
        new = _add_preload(new)
        if not new.endswith("\n"):
            new += "\n"
        if new != text:
            if "\r\n" in raw:
                new = new.replace("\n", "\r\n")
            path.write_text(new, encoding="utf-8", newline="")
            changed.append(path.stem)
    return sorted(changed)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Guard the v4.0.0 agent boilerplate contract: no compiled blocks in "
        "agents, every agent preloads ct6-agent-core."
    )
    parser.add_argument("--check", action="store_true",
                        help="Report drift without writing; exit non-zero on drift.")
    parser.add_argument("--agents-dir", default=None,
                        help="Path to the agents/ directory (defaults to the repo's agents/).")
    args = parser.parse_args(argv)

    agents_dir = pathlib.Path(args.agents_dir) if args.agents_dir else _default_agents_dir()
    if not agents_dir.is_dir():
        print(f"ERROR: agents directory not found: {agents_dir}", file=sys.stderr)
        return 2

    if args.check:
        report = drift_report(agents_dir)
        if report:
            print(f"DRIFT: {len(report)} agent file(s) off the v4.0.0 boilerplate contract:")
            for stem, reasons in report.items():
                for reason in reasons:
                    print(f"  - {stem}.md: {reason}")
            print("Run `python scripts/setup/sync_agent_boilerplate.py` to convert.")
            return 1
        print(f"IN SYNC: every agent preloads {CORE_SKILL} and carries no compiled block ({agents_dir}).")
        return 0

    changed = sync(agents_dir)
    if changed:
        print(f"Converted {len(changed)} agent file(s) to the v4.0.0 contract:")
        for stem in changed:
            print(f"  - {stem}.md")
    else:
        print("0 files changed (already in sync).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
