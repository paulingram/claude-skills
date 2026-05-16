"""Minimal YAML frontmatter parser for SKILL.md / agent.md / command.md files.

We avoid a hard dependency on PyYAML for the simple cases by accepting either:
- PyYAML if available (preferred — handles every YAML edge case)
- a tiny built-in fallback for flat key:value frontmatter

Returns (frontmatter_dict, body_str) or raises ValueError.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
    _HAS_YAML = True
except ImportError:  # pragma: no cover
    _HAS_YAML = False


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


def _flat_yaml(text: str) -> dict[str, Any]:
    """Fallback: parse `key: value` lines and `key: [a, b, c]` lists."""
    out: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unparseable frontmatter line: {raw!r}")
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            items = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
            out[key] = items
        elif val in {"true", "false"}:
            out[key] = (val == "true")
        elif val.startswith(("'", '"')) and val.endswith(("'", '"')):
            out[key] = val[1:-1]
        else:
            out[key] = val
    return out
