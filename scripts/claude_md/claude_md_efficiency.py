# -*- coding: utf-8 -*-
"""Deterministic Claude.md-efficiency engine (CMD-1 … CMD-4).

Stdlib-only, no import-time side effects. The deterministic half of the
**claude-md-efficiency** discipline: when (and only when) MemPalace is installed,
`CLAUDE.md` should be a thin POINTER document — it tells the agent WHERE to find
things (load context on demand) rather than CONTAINING the full context, and it
stays very small (CMD-1 … CMD-3). It carries two parts (CMD-4): (a) standards
that point to a reference DB / reference MemPalace, and (b) customizations that
can be toggled on/off.

This module:
- `assess_claude_md(text)` — score an existing CLAUDE.md for pointer-shape + size
  and emit advisory signals (the auditor).
- `generate_pointer_claude_md(...)` — emit a minimal, correctly-shaped pointer
  CLAUDE.md (the generator).

It is the machine; `skills/claude-md-efficiency/SKILL.md` is the contract +
LLM-judgment workflow. The pointer-style mandate is CONDITIONAL on MemPalace
being installed (CMD-1) — the assessor reports shape/size; whether the mandate
APPLIES is the skill's precondition, not the engine's to decide.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

# A pointer-style CLAUDE.md should be tiny — it points, it does not contain.
# (CMD-3 "keep Claude.md very small.") Bytes, UTF-8.
CLAUDE_MD_POINTER_BUDGET_BYTES = 2048

# Substrings that indicate load-on-demand POINTER shape (CMD-2) rather than a
# self-contained context container.
POINTER_MARKERS: tuple[str, ...] = (
    "located at", "read your", "read the", "see ", "wake-up", "wake up",
    "mempalace", "load on demand", "on demand", "pointer", "reference database",
    "reference mempalace", "fetch", "look up", "->", "→",
)
# Heading/word hints for the two CMD-4 parts.
STANDARDS_HINTS: tuple[str, ...] = ("standard", "reference")
CUSTOMIZATION_HINTS: tuple[str, ...] = (
    "customization", "customisation", "toggle", "opt-in", "opt in", "preference",
)


def assess_claude_md(text: str) -> dict[str, Any]:
    """Assess a CLAUDE.md's pointer-shape + size (CMD-1 … CMD-4).

    Returns the size, whether it reads as a pointer doc, and advisory `signals`:
    `over-budget` (too large to be a pointer), `no-pointers` (reads as a
    container), `missing-standards-pointer`, `missing-customizations`.
    `is_pointer_style` is True only when it both carries pointers AND fits the
    size budget. The signals are advisory and only MANDATORY when MemPalace is
    installed (CMD-1) — that precondition is the skill's, not the engine's.
    """
    text = text or ""
    size = len(text.encode("utf-8"))
    lines = text.splitlines()
    lower = text.lower()

    pointers_found = sorted({m for m in POINTER_MARKERS if m in lower})
    has_standards = any(h in lower for h in STANDARDS_HINTS)
    has_customizations = any(h in lower for h in CUSTOMIZATION_HINTS)
    over_budget = size > CLAUDE_MD_POINTER_BUDGET_BYTES

    signals: list[dict[str, Any]] = []
    if over_budget:
        signals.append({
            "signal": "over-budget",
            "severity": "high",
            "detail": (
                f"CLAUDE.md is {size} bytes, over the "
                f"{CLAUDE_MD_POINTER_BUDGET_BYTES}-byte pointer budget — it likely "
                "CONTAINS context that should live in MemPalace and be pointed to"
            ),
        })
    if not pointers_found:
        signals.append({
            "signal": "no-pointers",
            "severity": "high",
            "detail": (
                "no load-on-demand pointer markers found — CLAUDE.md reads as a "
                "self-contained container rather than a pointer to where context lives"
            ),
        })
    if not has_standards:
        signals.append({
            "signal": "missing-standards-pointer",
            "severity": "medium",
            "detail": "no standards section pointing to the reference DB / MemPalace (CMD-4a)",
        })
    if not has_customizations:
        signals.append({
            "signal": "missing-customizations",
            "severity": "low",
            "detail": "no toggleable customizations section (CMD-4b)",
        })

    is_pointer_style = bool(pointers_found) and not over_budget
    return {
        "schema": "claude-md-assessment/v1",
        "size_bytes": size,
        "line_count": len(lines),
        "budget_bytes": CLAUDE_MD_POINTER_BUDGET_BYTES,
        "over_budget": over_budget,
        "pointers_found": pointers_found,
        "has_standards": has_standards,
        "has_customizations": has_customizations,
        "is_pointer_style": is_pointer_style,
        "signals": signals,
    }


def generate_pointer_claude_md(
    project_name: str,
    *,
    mempalace_palace: Optional[str] = None,
    wakeup_pointer: Optional[str] = None,
    standards_pointers: Optional[Iterable[str]] = None,
    customizations: Optional[Iterable[tuple[str, bool]]] = None,
) -> str:
    """Emit a minimal, correctly-shaped POINTER CLAUDE.md (CMD-2/CMD-3/CMD-4).

    `wakeup_pointer` — where the agent reads its wake-up script first (the CMD-2
    example). `standards_pointers` — lines pointing to the reference DB/MemPalace.
    `customizations` — (label, enabled) pairs rendered as on/off toggles (CMD-4b).
    The output is deliberately tiny: it points, it does not contain.
    """
    palace = mempalace_palace or "<your-palace>"
    wake = wakeup_pointer or f"`mempalace --palace {palace} wake-up`"
    std = list(standards_pointers or [
        f"Standards live in the reference MemPalace `{palace}` — query it on demand "
        "rather than inlining standards here.",
    ])
    custom = list(customizations or [("example-customization", False)])

    out: list[str] = [
        f"# {project_name}",
        "",
        "> **Pointer-style CLAUDE.md (CMD-1…CMD-4).** MemPalace is installed, so this",
        "> file is a POINTER, not a container: it tells you WHERE to find things and",
        "> you load context ON DEMAND. Do NOT internalize this whole file — follow the",
        "> pointers. Keep this file very small.",
        "",
        "## First step — wake up (load on demand)",
        "",
        f"Before doing anything else, read your wake-up context: {wake}.",
        "",
        "## Standards (point to the reference MemPalace, do not inline)",
        "",
    ]
    for line in std:
        out.append(f"- {line}")
    out += [
        "",
        "## Customizations (toggle on/off at your discretion)",
        "",
    ]
    for label, enabled in custom:
        mark = "x" if enabled else " "
        out.append(f"- [{mark}] {label}")
    out.append("")
    return "\n".join(out)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: assess an existing CLAUDE.md, or generate a pointer-style one.

    Usage:
      claude_md_efficiency.py assess <path> [--json]
      claude_md_efficiency.py generate --project <name> [--palace <p>] [--out <file>]
    `assess` exits 0 if the file is pointer-style, 1 otherwise (advisory).
    """
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Claude.md-efficiency assessor + generator (CMD-1…4).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("assess", help="assess an existing CLAUDE.md")
    pa.add_argument("path")
    pa.add_argument("--json", action="store_true")

    pg = sub.add_parser("generate", help="emit a minimal pointer-style CLAUDE.md")
    pg.add_argument("--project", required=True)
    pg.add_argument("--palace", default=None)
    pg.add_argument("--out", default=None)

    args = parser.parse_args(argv)

    if args.cmd == "assess":
        text = Path(args.path).read_text(encoding="utf-8")
        result = assess_claude_md(text)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            if result["is_pointer_style"]:
                print(f"claude-md: pointer-style ✓ ({result['size_bytes']} bytes).")
            else:
                print(f"claude-md: NOT pointer-style ({result['size_bytes']} bytes) —")
                for sig in result["signals"]:
                    print(f"  [{sig['severity']}] {sig['signal']}: {sig['detail']}")
        return 0 if result["is_pointer_style"] else 1

    # generate
    content = generate_pointer_claude_md(args.project, mempalace_palace=args.palace)
    if args.out:
        Path(args.out).write_text(content, encoding="utf-8")
        print(f"wrote {args.out} ({len(content.encode('utf-8'))} bytes)")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
