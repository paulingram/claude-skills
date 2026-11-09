# -*- coding: utf-8 -*-
"""Deterministic instruction-compliance lint (REQ-002).

Stdlib-only (PyYAML used only if importable, exactly as `tests/helpers/frontmatter.py`
does), no import-time side effects. The deterministic half of the instruction
compliance standard: it grades this repo's AI-facing instruction surfaces —
`skills/*/SKILL.md`, `agents/*.md`, `commands/*.md`, `CLAUDE.md`, and the two
`docs/*_MAP.md` maps — on the machine-checkable part of `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md`
dimension (a): frontmatter shape, required-field presence, section structure, and
cross-reference validity.

It is the machine; `docs/INSTRUCTION_COMPLIANCE_RUBRIC.md` is the written contract
(dimension (a) + cross-references are what this engine checks; dimensions (b)/(c)
are the rubric's LLM-judgment dimensions). It mirrors the established
`scripts/claude_md/claude_md_efficiency.py` engine shape: an `assess_*` function
returning a findings list, a `__main__` CLI, and no work at import time.

`assess_instruction_files(root)` returns::

    {"schema": "instruction-compliance/v1", "root": str, "files_checked": int,
     "findings": [{"file", "check", "issue", "evidence"}], "inventory_counts": {...}}

Each finding names the citing file (repo-relative), the `check` kind, a human
`issue`, and the specific `evidence` token/field.

The cross-reference grammar is deliberately NARROW — it resolves only unambiguous,
this-repo-inventory forms (`skills/<name>`, `agents/<name>.md`, `commands/<name>.md`,
`hooks|scripts|services/<path>.py|json`, and the two canonical `docs/` maps). The
colon-invocation form (`/architect-team:<cmd>`), per-codebase map names
(`docs/ROUTE_MAP.md` etc. produced in OTHER codebases), extensionless
`module.function` references, and multi-segment enumeration prose
(`skills/agents/commands`) are intentionally NOT machine-checked — they are the
rubric's documented LLM-judgment surface, so a false positive is a wording fix,
not an engine bug (see the rubric's "Recognized cross-reference forms").

Referencing-mandate checks (proposal change 9, conditions 2 + 3 of section 7 of
``docs/proposals/CT6_MODERNIZATION_PLAN.html``) -- three further finding classes:

* ``dead-pointer`` -- a backticked repo-relative path in a skill / command /
  agent body (or a ``references/*.md`` chapter) that does not exist on disk. The
  pointer grammar is a WHOLE backticked token of one of these shapes:
  ``skills/.../*.md``, ``docs/.../*.md``, ``agents/*.md``, ``commands/*.md``,
  ``hooks/*.py``, ``scripts/**/*.py`` (resolved against the repo root) and
  ``references/*.md`` (resolved against the citing skill's directory; from a
  non-skill file, against the file's own directory). A token the narrow
  cross-reference grammar above already flags is reported once, as
  ``cross-reference``, never twice.
* ``dead-heading`` -- a backticked ``## Heading`` literal that follows a
  RESOLVABLE markdown pointer in the same sentence of the same line must exist
  in that file as an exact heading line (case-sensitive, whitespace-trimmed; a
  version suffix or a trailing subtitle on the real heading is NOT stripped --
  cite the heading as written). Attribution ends at a sentence terminator
  (``.``, ``;``, ``?``, ``!`` + whitespace) or a table-cell bar, so a heading
  named later in the sentence's successor is never charged to the path.
* ``chapter-over-budget`` -- a ``skills/*/references/*.md`` chapter over the
  5,000-token re-attach budget (``bytes/4`` estimator: ``ceil(utf8_bytes / 4)``).

``scripts/compliance/pointer_allowlist.txt`` is the ONLY suppression: one entry
per line, a resolved repo-relative path (suppresses ``dead-pointer`` for that
target wherever it is cited) or ``<path>#<heading literal>`` (suppresses
``dead-heading`` for that heading of that target). It carries the dead pointers
that pre-dated the check, each with its classification; new entries need the
same justification. Chapters are pointer-scanned and budget-checked but are NOT
counted in ``files_checked`` (the in-scope set is unchanged); they are counted
in ``chapters_checked``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Union

try:
    import yaml  # type: ignore
    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False


# The required frontmatter fields per file class (the presence contract). Values
# are validated elsewhere (the existing structural pins); this engine checks
# presence + shape. `doc` (CLAUDE.md + the maps) carries no required frontmatter.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "skill": ("name", "description"),
    "agent": ("name", "description", "tools", "model", "color"),
    "command": ("description",),
    "doc": (),
}

# The description length cap — 1024 chars, applied UNIFORMLY to all three
# frontmatter classes (skills / agents / commands), measured on the RAW authored
# value (before a ' #' / ': ' truncation can mask an over-length value by silently
# cutting it under the cap). Evidence basis: for skills this is a real Agent Skills
# platform loader constraint — `tests/test_skills.py::SKILL_DESCRIPTION_MAX_CHARS =
# 1024` ("the Agent Skills platform caps a skill description at 1024 characters;
# a longer description is silently truncated (or rejected) by the loader"). For
# agents/commands there is no repo-proven loader cap, so 1024 is applied as the
# uniform house-style ceiling per docs/INSTRUCTION_COMPLIANCE_RUBRIC.md (a.4), which
# directs this engine to measure the raw description length for ALL THREE classes and
# emit a finding at > 1024 (otherwise a green lint could coexist with an over-cap
# agent/command description and the done-bar would be falsely green).
DESCRIPTION_MAX_CHARS = 1024

# --------------------------------------------------------------------------- #
# cross-reference grammar (narrow, this-repo-inventory only)
# --------------------------------------------------------------------------- #
# skills/<slug> or skills/<slug>/SKILL.md — trailing boundary rejects multi-segment
# enumeration prose ("skills/agents/commands"); leading boundary rejects vendored
# external paths (".claude/skills/openspec-propose/...").
_RE_SKILL = re.compile(r"(?<![A-Za-z0-9_/.-])skills/([a-z0-9][a-z0-9-]*)(?:/SKILL\.md)?(?![A-Za-z0-9/_.-])")
# agents/<slug>.md and commands/<slug>.md REQUIRE the extension so bare English
# prose ("agents/teams mode", "Skills/agents/commands") never matches.
_RE_AGENT = re.compile(r"(?<![A-Za-z0-9_/.-])agents/([a-z0-9][a-z0-9-]*)\.md(?![A-Za-z0-9])")
_RE_COMMAND = re.compile(r"(?<![A-Za-z0-9_/.-])commands/([a-z0-9][a-z0-9-]*)\.md(?![A-Za-z0-9])")
# hooks|scripts|services file paths REQUIRE a .py/.json extension so extensionless
# `module.function` references ("hooks/run_metrics.record_run_metrics") are skipped.
_RE_FILE = re.compile(r"(?<![A-Za-z0-9_-])((?:hooks|scripts|services)/[A-Za-z0-9_./-]+?\.(?:py|json))(?![A-Za-z0-9])")
# only the two canonical maps THIS repo actually owns; every other docs/*_MAP.md
# is a per-codebase artifact produced elsewhere, not a reference into this repo.
_RE_DOC = re.compile(r"(?<![A-Za-z0-9_-])(docs/(?:CODEBASE_MAP|INTEGRATION_MAP)\.md)(?![A-Za-z0-9])")

# A frontmatter key line at column 0 with a same-line plain-scalar value.
_RE_FM_KEY = re.compile(r"^([A-Za-z0-9_-]+):[ \t]+(\S.*)$")
# The two deterministic YAML hazards in an unquoted plain-scalar value, using
# ASCII whitespace only (yaml recognises ascii space/tab, not unicode nbsp):
#  - ': ' (colon + ascii space, or colon at end) -> ScannerError "mapping values
#    are not allowed here" (the house rule, memory `skill-frontmatter-no-colon-space`).
#  - ' #' (ascii space + hash) -> yaml reads an inline comment, SILENTLY truncating
#    the value at that point.
# Precedence is positional — whichever appears first in the value is what yaml does.
_RE_COLON_SPACE = re.compile(r":(?=[ \t]|$)")
_RE_SPACE_HASH = re.compile(r"(?<=[ \t])#")


# --------------------------------------------------------------------------- #
# referencing-mandate checks: pointer resolvability, heading existence, chapter
# budget (proposal change 9)
# --------------------------------------------------------------------------- #
# The token estimator shared with scripts/measure/instruction_budget.py: one
# token per four UTF-8 bytes, rounded up. Stated, not measured against a real
# tokenizer -- it is a budget yardstick, and every surface is measured with the
# same stick.
TOKEN_ESTIMATOR = "bytes/4"
# The re-attach budget for one reference chapter (the proposal's 5,000 tokens).
CHAPTER_TOKEN_BUDGET = 5000
POINTER_ALLOWLIST_PATH = "scripts/compliance/pointer_allowlist.txt"

# A WHOLE backticked token that is a repo-relative markdown / python pointer.
_RE_POINTER_TOKEN = re.compile(
    r"^(?:(?:skills|docs|agents|commands|references)/[A-Za-z0-9_./-]+\.md"
    r"|(?:hooks|scripts)/[A-Za-z0-9_./-]+\.py)$"
)
_RE_BACKTICK_TOKEN = re.compile(r"`([^`\n]+)`")
# A heading literal cited in backticks: `## Heading text`.
_RE_HEADING_TOKEN = re.compile(r"^#{1,6} \S.*$")
# What ends a sentence between a pointer and a heading literal: a terminator
# followed by whitespace / end, or a table-cell bar.
_RE_SENTENCE_BREAK = re.compile(r"[.;?!](?:\s|$)|\|")


def estimate_tokens(nbytes: int) -> int:
    """``ceil(nbytes / 4)`` -- the bytes/4 estimator."""
    return (int(nbytes) + 3) // 4


def load_pointer_allowlist(root: Union[str, Path]) -> dict[str, set[str]]:
    """``{"paths": {...}, "headings": {...}}`` from the allowlist file.

    One entry per line; ``#`` starts a comment ONLY at column 0 or after
    whitespace, because a heading entry is ``<path>#<heading literal>`` and the
    literal itself begins with ``#``. Blank lines are ignored. A missing file is
    an empty allowlist.
    """
    out: dict[str, set[str]] = {"paths": set(), "headings": set()}
    p = Path(root) / POINTER_ALLOWLIST_PATH
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if not line:
            continue
        if "#" in line:
            # `docs/X.md### Heading` -> path `docs/X.md`, literal `## Heading`;
            # the key is `<path>#<literal>`, exactly as the finding's evidence.
            path, _, heading = line.partition("#")
            out["headings"].add(f"{path.strip()}#{heading.strip()}")
        else:
            out["paths"].add(line.replace("\\", "/"))
    return out


def _skill_dir_for(path: Path, root: Path) -> Optional[Path]:
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return None
    if len(parts) >= 3 and parts[0] == "skills":
        return root / "skills" / parts[1]
    return None


def resolve_pointer_token(token: str, citing_file: Path, root: Path) -> tuple[Path, str]:
    """``(absolute, repo_relative_posix)`` for a pointer token as written."""
    token = token.strip()
    if token.startswith("references/"):
        base = _skill_dir_for(citing_file, root) or citing_file.parent
        absolute = base / token
    else:
        absolute = root / token
    try:
        rel = absolute.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = token.replace("\\", "/")
    return absolute, rel


def _headings_of(path: Path, cache: dict[str, set[str]]) -> set[str]:
    key = str(path)
    if key not in cache:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            lines = []
        cache[key] = {ln.rstrip() for ln in lines if ln.startswith("#")}
    return cache[key]


def _pointer_findings(
    text: str,
    path: Path,
    root: Path,
    *,
    allowlist: dict[str, set[str]],
    skip_evidence: set[str],
    hits: list[dict[str, str]],
    heading_cache: Optional[dict[str, set[str]]] = None,
) -> list[tuple[str, str, str]]:
    """``(check, issue, evidence)`` for every dead pointer / dead heading in
    ``text`` per the module docstring's referencing-mandate rules."""
    cache = heading_cache if heading_cache is not None else {}
    rel_file = path.resolve().relative_to(root.resolve()).as_posix()
    out: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(check: str, issue: str, evidence: str) -> None:
        if (check, evidence) not in seen:
            seen.add((check, evidence))
            out.append((check, issue, evidence))

    for line in text.splitlines():
        last_md: Optional[tuple[Path, str, int]] = None  # (absolute, rel, end offset)
        for m in _RE_BACKTICK_TOKEN.finditer(line):
            token = m.group(1).strip()
            if _RE_POINTER_TOKEN.match(token):
                absolute, rel = resolve_pointer_token(token, path, root)
                if absolute.is_file():
                    last_md = (absolute, rel, m.end()) if token.endswith(".md") else None
                    continue
                last_md = None
                if rel in allowlist["paths"]:
                    hits.append({"file": rel_file, "kind": "path", "entry": rel, "pointer": token})
                    continue
                if token in skip_evidence:
                    continue  # already reported as a cross-reference finding
                add("dead-pointer",
                    f"pointer '{token}' resolves to '{rel}', which does not exist on disk",
                    token)
                continue
            if _RE_HEADING_TOKEN.match(token):
                if last_md is None:
                    continue
                absolute, rel, end = last_md
                if _RE_SENTENCE_BREAK.search(line[end:m.start()]):
                    last_md = None  # a new sentence; the heading is not this pointer's
                    continue
                if token in _headings_of(absolute, cache):
                    continue
                key = f"{rel}#{token}"
                if key in allowlist["headings"]:
                    hits.append({"file": rel_file, "kind": "heading", "entry": key, "pointer": token})
                    continue
                add("dead-heading",
                    f"heading '{token}' is cited for '{rel}' but no line of that file is "
                    f"exactly that heading (cite the heading as written; suffixes are not stripped)",
                    key)
    return out


def _chapter_files(root: Path) -> list[Path]:
    """Every ``skills/*/references/*.md`` chapter (INDEX.md files included)."""
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(skills_dir.glob("*/references/*.md"))


def assess_chapters(
    root: Path,
    *,
    allowlist: dict[str, set[str]],
    hits: list[dict[str, str]],
    heading_cache: Optional[dict[str, set[str]]] = None,
) -> tuple[list[dict[str, Any]], int]:
    """``(findings, chapters_checked)`` -- chapter budget + pointer scan over
    every reference chapter. Chapters are outside the in-scope file count."""
    findings: list[dict[str, Any]] = []
    chapters = _chapter_files(root)
    for chapter in chapters:
        rel = chapter.resolve().relative_to(root.resolve()).as_posix()
        data = chapter.read_bytes()
        tokens = estimate_tokens(len(data))
        if tokens > CHAPTER_TOKEN_BUDGET:
            findings.append({
                "file": rel,
                "check": "chapter-over-budget",
                "issue": (
                    f"reference chapter is {tokens} tokens ({TOKEN_ESTIMATOR}), over the "
                    f"{CHAPTER_TOKEN_BUDGET}-token re-attach budget; split it or move "
                    "procedure that is not read together into its own chapter"
                ),
                "evidence": f"{tokens} tokens",
            })
        text = data.decode("utf-8", errors="replace")
        for check, issue, evidence in _pointer_findings(
            text, chapter, root, allowlist=allowlist, skip_evidence=set(),
            hits=hits, heading_cache=heading_cache,
        ):
            findings.append({"file": rel, "check": check, "issue": issue, "evidence": evidence})
    return findings, len(chapters)


def build_inventory(root: Union[str, Path]) -> dict[str, set[str]]:
    """The plugin's own skill/agent/command inventory, resolved on disk."""
    root = Path(root)
    skills = {d.name for d in (root / "skills").glob("*") if (d / "SKILL.md").exists()} \
        if (root / "skills").is_dir() else set()
    agents = {p.stem for p in (root / "agents").glob("*.md")} if (root / "agents").is_dir() else set()
    commands = {p.stem for p in (root / "commands").glob("*.md")} if (root / "commands").is_dir() else set()
    return {"skills": skills, "agents": agents, "commands": commands}


def _split_frontmatter(text: str) -> tuple[Optional[str], str, Optional[str]]:
    """Return (frontmatter_text, body, error).

    `error` is a non-None reason string when the delimited block is malformed
    (missing opening/closing `---`). A file with no leading `---` returns
    (None, text, None) — that is "no frontmatter", not an error.
    """
    if not text.startswith("---"):
        return None, text, None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text, "malformed frontmatter: no closing '---' delimiter"
    return parts[1], parts[2].lstrip("\n"), None


def _value_hazards(fm_text: str) -> list[tuple[str, str]]:
    """(field, kind) for every UNQUOTED plain-scalar frontmatter value that yaml
    would break or truncate — kind is 'colon-space' (': ' -> ScannerError) or
    'comment' (' #' -> silent inline-comment truncation).

    Only column-0 `key: value` lines with a same-line plain scalar are inspected;
    quoted values, block scalars (`>`/`|`), flow collections (`[`/`{`), and other
    YAML indicators are skipped, and indented continuation lines are never keys —
    so a folded `note: >-` block (the maps use one) cannot false-positive. When
    both hazards are present, the one that appears FIRST wins, matching yaml's
    actual behaviour (a ' #' before a ': ' turns the ': ' into harmless comment
    text; a ': ' before a ' #' raises before the comment is ever reached).
    """
    out: list[tuple[str, str]] = []
    for raw in fm_text.splitlines():
        m = _RE_FM_KEY.match(raw)
        if not m:
            continue
        key, val = m.group(1), m.group(2)
        if val[:1] in ("\"", "'", ">", "|", "[", "{", "&", "*", "!", "#"):
            continue  # quoted / block / flow / indicator — not a plain scalar
        colon = _RE_COLON_SPACE.search(val)
        comment = _RE_SPACE_HASH.search(val)
        if colon is not None and (comment is None or colon.start() < comment.start()):
            out.append((key, "colon-space"))
        elif comment is not None:
            out.append((key, "comment"))
    return out


def _raw_description(fm_text: str) -> Optional[str]:
    """The RAW `description` value as authored on its column-0 line, before yaml
    processing (quotes stripped for a same-line quoted value). None if absent or a
    block scalar (`>`/`|`, whose content lives on following lines)."""
    for raw in fm_text.splitlines():
        m = _RE_FM_KEY.match(raw)
        if m and m.group(1) == "description":
            val = m.group(2)
            if val[:1] in (">", "|"):
                return None
            if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                val = val[1:-1]
            return val
    return None


def _flat_keys(fm_text: str) -> dict[str, str]:
    """Tolerant column-0 `key: value` extraction (never raises).

    Used for required-field presence + name/filename matching. Values are
    single-line in this corpus, so a flat parse is sufficient and yaml-independent.
    """
    out: dict[str, str] = {}
    for raw in fm_text.splitlines():
        if not raw or raw[0] in " \t#":
            continue  # indented continuation / comment / blank — not a top-level key
        m = re.match(r"^([A-Za-z0-9_-]+):(.*)$", raw)
        if not m:
            continue
        val = m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[m.group(1)] = val
    return out


def _yaml_error(fm_text: str) -> Optional[str]:
    """A yaml.safe_load error string when PyYAML is present and rejects the block."""
    if not HAS_YAML:
        return None
    try:
        yaml.safe_load(fm_text)
    except Exception as exc:  # yaml.YAMLError and subclasses
        return f"yaml.safe_load failed: {type(exc).__name__}"
    return None


def _body_opens_ok(file_class: str, body: str) -> bool:
    """Section-structure: the conventional opening line per class.

    - skills / commands open with an H1 title (`# `).
    - agents open with an H1 title OR a `You are` / `You're` role statement
      (both are attested in the corpus).
    - docs (CLAUDE.md + the maps) are not structurally uniform → no check.
    """
    first = ""
    for line in body.splitlines():
        if line.strip():
            first = line
            break
    if file_class in ("skill", "command"):
        return first.startswith("# ")
    if file_class == "agent":
        low = first.lower()
        return first.startswith("# ") or low.startswith(("you are", "you're", "you will"))
    return True  # doc


def _cross_reference_findings(text: str, inventory: dict[str, set[str]], root: Path) -> list[tuple[str, str]]:
    """(evidence, issue) pairs for every unresolved narrow-grammar reference."""
    out: list[tuple[str, str]] = []
    for m in _RE_SKILL.finditer(text):
        if m.group(1) not in inventory["skills"]:
            out.append((m.group(0), f"skill reference '{m.group(0)}' does not resolve to a known skill"))
    for m in _RE_AGENT.finditer(text):
        if m.group(1) not in inventory["agents"] and not (root / "agents" / f"{m.group(1)}.md").exists():
            out.append((m.group(0), f"agent reference '{m.group(0)}' does not resolve to a known agent"))
    for m in _RE_COMMAND.finditer(text):
        if m.group(1) not in inventory["commands"] and not (root / "commands" / f"{m.group(1)}.md").exists():
            out.append((m.group(0), f"command reference '{m.group(0)}' does not resolve to a known command"))
    for m in _RE_FILE.finditer(text):
        if not (root / m.group(1)).exists():
            out.append((m.group(1), f"file path reference '{m.group(1)}' does not resolve on disk"))
    for m in _RE_DOC.finditer(text):
        if not (root / m.group(1)).exists():
            out.append((m.group(1), f"doc reference '{m.group(1)}' does not resolve on disk"))
    # de-dup, preserve first-seen order
    seen: set[tuple[str, str]] = set()
    uniq: list[tuple[str, str]] = []
    for pair in out:
        if pair not in seen:
            seen.add(pair)
            uniq.append(pair)
    return uniq


def assess_file(
    path: Path,
    *,
    root: Path,
    file_class: str,
    inventory: dict[str, set[str]],
    expected_name: Optional[str] = None,
    allowlist: Optional[dict[str, set[str]]] = None,
    hits: Optional[list[dict[str, str]]] = None,
    heading_cache: Optional[dict[str, set[str]]] = None,
) -> list[dict[str, Any]]:
    """Grade one instruction file; return its findings (possibly empty).

    ``allowlist`` / ``hits`` / ``heading_cache`` feed the referencing-mandate
    pointer check (skill / agent / command classes only); when ``allowlist`` is
    None it is loaded from ``POINTER_ALLOWLIST_PATH`` under ``root``.
    """
    rel = str(path.relative_to(root)).replace("\\", "/")
    text = path.read_text(encoding="utf-8")
    findings: list[dict[str, Any]] = []

    def add(check: str, issue: str, evidence: str) -> None:
        findings.append({"file": rel, "check": check, "issue": issue, "evidence": evidence})

    fm_text, body, fm_error = _split_frontmatter(text)
    frontmatter_expected = file_class in ("skill", "agent", "command")

    if fm_error is not None:
        add("frontmatter-unparseable", fm_error, "frontmatter block")
    elif frontmatter_expected and fm_text is None:
        add("frontmatter-missing",
            f"{file_class} file must open with a '---' YAML frontmatter block",
            "missing frontmatter")
    elif fm_text is not None:
        hazards = _value_hazards(fm_text)
        for field, kind in hazards:
            if kind == "colon-space":
                add("frontmatter-colon-space",
                    "unquoted frontmatter value contains ': ' which breaks yaml.safe_load "
                    "(house rule); quote the value or reword",
                    f"field '{field}'")
            else:  # comment
                add("frontmatter-comment",
                    "unquoted frontmatter value contains ' #' which yaml.safe_load reads as an "
                    "inline comment, silently truncating the value; quote the value or remove the ' #'",
                    f"field '{field}'")
        if not hazards:
            yaml_err = _yaml_error(fm_text)
            if yaml_err is not None:
                add("frontmatter-unparseable", yaml_err, "frontmatter block")
        # required-field presence + name/filename match (keys via tolerant parse)
        keys = _flat_keys(fm_text)
        for field in REQUIRED_FIELDS.get(file_class, ()):
            if field not in keys:
                add("required-field",
                    f"{file_class} frontmatter is missing the required '{field}' field",
                    f"field '{field}'")
        if expected_name is not None and "name" in keys and keys["name"] != expected_name:
            add("name-mismatch",
                f"frontmatter name '{keys['name']}' does not match the filename '{expected_name}'",
                keys["name"])
        if frontmatter_expected:
            raw_desc = _raw_description(fm_text)
            if raw_desc is not None and len(raw_desc) > DESCRIPTION_MAX_CHARS:
                add("frontmatter-description-too-long",
                    f"raw description is {len(raw_desc)} chars, over the "
                    f"{DESCRIPTION_MAX_CHARS}-char Agent Skills cap (measured before any "
                    "' #'/': ' truncation) — rewrite trigger-first, move detail to the body",
                    f"{len(raw_desc)} chars")

    if not _body_opens_ok(file_class, body):
        add("section-structure",
            f"{file_class} body does not open with the conventional heading/role line",
            "opening line")

    xref = _cross_reference_findings(text, inventory, root)
    for evidence, issue in xref:
        add("cross-reference", issue, evidence)

    if file_class in ("skill", "agent", "command"):
        allow = allowlist if allowlist is not None else load_pointer_allowlist(root)
        sink = hits if hits is not None else []
        for check, issue, evidence in _pointer_findings(
            text, path, root, allowlist=allow,
            skip_evidence={ev for ev, _ in xref}, hits=sink, heading_cache=heading_cache,
        ):
            add(check, issue, evidence)

    return findings


def _in_scope_files(root: Path) -> list[tuple[Path, str, Optional[str]]]:
    """Every in-scope file that exists: (path, file_class, expected_name)."""
    files: list[tuple[Path, str, Optional[str]]] = []
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.glob("*")):
            sk = d / "SKILL.md"
            if sk.exists():
                files.append((sk, "skill", d.name))
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        for p in sorted(agents_dir.glob("*.md")):
            files.append((p, "agent", p.stem))
    commands_dir = root / "commands"
    if commands_dir.is_dir():
        for p in sorted(commands_dir.glob("*.md")):
            files.append((p, "command", None))
    for rel in ("CLAUDE.md", "docs/CODEBASE_MAP.md", "docs/INTEGRATION_MAP.md"):
        p = root / rel
        if p.exists():
            files.append((p, "doc", None))
    return files


def assess_instruction_files(root: Union[str, Path]) -> dict[str, Any]:
    """Assess every in-scope instruction file under `root` (REQ-002).

    Walks the 47 SKILL.md + 39 agents + 23 commands + CLAUDE.md + the 2 maps that
    exist under `root`, grading each on frontmatter shape, required-field
    presence, section structure, and cross-reference validity. Returns the file
    count + the flat findings list; an empty `findings` is a clean pass.
    """
    root = Path(root)
    inventory = build_inventory(root)
    files = _in_scope_files(root)
    allowlist = load_pointer_allowlist(root)
    hits: list[dict[str, str]] = []
    heading_cache: dict[str, set[str]] = {}
    findings: list[dict[str, Any]] = []
    for path, file_class, expected_name in files:
        findings.extend(assess_file(
            path, root=root, file_class=file_class,
            inventory=inventory, expected_name=expected_name,
            allowlist=allowlist, hits=hits, heading_cache=heading_cache,
        ))
    chapter_findings, chapters_checked = assess_chapters(
        root, allowlist=allowlist, hits=hits, heading_cache=heading_cache,
    )
    findings.extend(chapter_findings)
    return {
        "schema": "instruction-compliance/v1",
        "root": str(root),
        "files_checked": len(files),
        "chapters_checked": chapters_checked,
        "findings": findings,
        "inventory_counts": {k: len(v) for k, v in inventory.items()},
        "token_estimator": TOKEN_ESTIMATOR,
        "chapter_token_budget": CHAPTER_TOKEN_BUDGET,
        "pointer_allowlist": sorted(allowlist["paths"]) + sorted(allowlist["headings"]),
        "pointer_allowlist_hits": hits,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: assess an in-scope tree and print findings.

    Usage:
      instruction_compliance.py [<root>] [--json]
    Exits 0 when there are zero findings, 1 otherwise.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Instruction-compliance lint (REQ-002).")
    parser.add_argument("root", nargs="?", default=".", help="repo root to assess (default: cwd)")
    parser.add_argument("--json", action="store_true", help="emit the full JSON result")
    args = parser.parse_args(argv)

    result = assess_instruction_files(args.root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        n = len(result["findings"])
        if n == 0:
            print(f"instruction-compliance: clean — {result['files_checked']} files, 0 findings.")
        else:
            print(f"instruction-compliance: {n} finding(s) across {result['files_checked']} files —")
            for f in result["findings"]:
                print(f"  {f['file']}: [{f['check']}] {f['evidence']} — {f['issue']}")
    return 0 if not result["findings"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
