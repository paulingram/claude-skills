"""Minimal YAML frontmatter parser for SKILL.md / agent.md / command.md files.

We avoid a hard dependency on PyYAML for the simple cases by accepting either:
- PyYAML if available (preferred - handles every YAML edge case)
- a tiny built-in fallback for flat key:value frontmatter PLUS block scalars

The fallback additionally understands YAML block scalars (`>`, `>-`, `>+`, `|`,
`|-`, `|+`), so a folded `note: >-` field (used by the maps' frontmatter) parses
to the same value PyYAML produces WITHOUT requiring PyYAML on the box. Folding and
chomping match `yaml.safe_load` for the block shapes that occur in this repo
(uniform-indent bodies, no more-indented continuation lines) - the parity is
asserted against the real in-scope files in tests/test_frontmatter_helper.py.

Returns (frontmatter_dict, body_str) or raises ValueError.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


# A block-scalar header value: a `|` or `>` indicator optionally followed by a
# chomping indicator (`-`/`+`) and/or an explicit indent digit, then optional
# trailing whitespace / comment. It matches ONLY when the indicator is alone on
# the line (a quoted value or a plain scalar starting with other text never
# matches), so ordinary `key: value` frontmatter is untouched.
_BLOCK_SCALAR_RE = re.compile(r"^([|>])([+\-0-9]*)[ \t]*(#.*)?$")


def parse(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: missing frontmatter (must start with '---')")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"{path}: malformed frontmatter (no closing '---')")
    fm_text, body = parts[1], parts[2]
    if _HAS_YAML:
        fm = yaml.safe_load(fm_text) or {}
    else:
        fm = _flat_yaml(fm_text)
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: frontmatter is not a mapping")
    return fm, body.lstrip("\n")


def _parse_inline(val: str) -> Any:
    """Parse a single-line scalar / flow value (the historical fallback behavior)."""
    if val.startswith("[") and val.endswith("]"):
        return [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
    if val in {"true", "false"}:
        return val == "true"
    if len(val) >= 2 and val.startswith(("'", '"')) and val.endswith(("'", '"')):
        return val[1:-1]
    return val


def _render_block_scalar(body_lines: list[str], style: str, chomp: str) -> str:
    """Assemble a block scalar's value the way yaml.safe_load does.

    `body_lines` are the raw lines under the header (blank lines are ""). `style`
    is `>` (folded) or `|` (literal); `chomp` is `-` (strip), `+` (keep), or ""
    (clip). Folding matches PyYAML for uniform-indent bodies: consecutive
    non-empty lines join with a single space, each blank line yields one newline;
    a literal body joins every line with a newline. More-indented continuation
    lines (which PyYAML keeps verbatim) do not occur in this repo's frontmatter.
    """
    indent = None
    for line in body_lines:
        if line.strip():
            indent = len(line) - len(line.lstrip(" "))
            break
    if indent is None:
        return ""  # an all-blank / empty block

    dedented = ["" if not line.strip() else line[indent:] for line in body_lines]

    trailing_blanks = 0
    while dedented and dedented[-1] == "":
        dedented.pop()
        trailing_blanks += 1

    if style == "|":
        body = "\n".join(dedented)
    else:  # folded
        parts: list[str] = []
        i = 0
        while i < len(dedented):
            if dedented[i] == "":
                parts.append("\n")
                i += 1
            else:
                run: list[str] = []
                while i < len(dedented) and dedented[i] != "":
                    run.append(dedented[i])
                    i += 1
                parts.append(" ".join(run))
        body = "".join(parts)

    if chomp == "-":            # strip: no trailing newline
        return body
    if chomp == "+":            # keep: every trailing line break preserved
        return body + "\n" * (trailing_blanks + 1)
    return body + "\n" if body else ""   # clip (default): a single trailing newline


def _flat_yaml(text: str) -> dict[str, Any]:
    """Fallback parser: `key: value`, `key: [a, b, c]`, and block scalars.

    Iterates line-by-line so a `key: >-` / `key: |` header can consume the
    following more-indented (and blank) lines as its scalar body. Top-level lines
    are at column 0; a blank or `#`-comment line at that level is skipped.
    """
    out: dict[str, Any] = {}
    lines = text.splitlines()
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        if raw[0] in (" ", "\t"):
            raise ValueError(f"unparseable frontmatter line: {raw!r}")
        if ":" not in raw:
            raise ValueError(f"unparseable frontmatter line: {raw!r}")

        key, _, val = raw.partition(":")
        key, val = key.strip(), val.strip()

        m = _BLOCK_SCALAR_RE.match(val)
        if m:
            suffix = m.group(2)
            chomp = "-" if "-" in suffix else ("+" if "+" in suffix else "")
            i += 1
            body_lines: list[str] = []
            while i < n:
                bl = lines[i]
                if bl.strip() == "":
                    body_lines.append("")
                    i += 1
                elif bl[0] in (" ", "\t"):
                    body_lines.append(bl)
                    i += 1
                else:
                    break  # a new column-0 key ends the block
            out[key] = _render_block_scalar(body_lines, m.group(1), chomp)
            continue

        out[key] = _parse_inline(val)
        i += 1
    return out
