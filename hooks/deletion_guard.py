#!/usr/bin/env python3
"""Deletion recoverability guard -- the PreToolUse[Bash] arm + the soft-delete verbs.

WHAT IT CLOSES
    An agent that deletes a file decides, in that instant, whether the file's
    content exists anywhere else. Until this guard the decision was taken from
    memory: `rm -rf` on an untracked directory, `git checkout -- .` over an
    hour of uncommitted work, `git clean -fd` from the repo root wiping the
    per-run state of every teammate. None of those is recoverable, and none of
    them looked different from `rm -rf __pycache__` at the moment it ran.

    This guard makes RECOVERABILITY the classifier. Before a deletion-shaped
    Bash command runs, every target path is classified by what git knows about
    it, and the decision follows from the class:

        temp / cache / run-state scratch       -> allow (nothing to recover)
        gitignored                             -> allow (not under version control by design)
        tracked AND clean                      -> allow, naming the restore command
        tracked WITH uncommitted changes       -> ask   (those lines exist nowhere else)
        untracked and not ignored              -> ask   (the only copy)
        outside any repo / unparsable target   -> ask   (cannot prove recoverability)
        shared-state git op (teammate rules)   -> deny inside an ACTIVE run, ask outside

    The soft-delete path is the default the discipline asks for: the `trash`
    verb moves a path into `<workspace>/.architect-team/trash/<run-id>/<rel>`
    (per-run scratch state, which the guard itself classifies as deletable), so
    "delete" becomes "recoverable until prune".

HOOK CONTRACT (PreToolUse, matcher "Bash")
    stdin:  {"hook_event_name": "PreToolUse", "tool_name": "Bash",
             "tool_input": {"command": "..."}, "cwd": "...", ...}
    stdout: ONE JSON object when a decision is needed --
            {"hookSpecificOutput": {"hookEventName": "PreToolUse",
             "permissionDecision": "allow" | "ask" | "deny",
             "permissionDecisionReason": "...", "additionalContext": "..."}}
            NOTHING for a non-Bash tool or a non-deletion command (so the hook
            never slows ordinary commands).
    exit:   ALWAYS 0. An internal exception emits an "ask" whose reason carries
            "deletion guard could not classify" -- fail-SAFE, never a crash and
            never a silent allow.
    Kill-switch: CT6_DELETION_GUARD_DISABLED=1 (the human's lever).

MOST RESTRICTIVE WINS: with several targets, deny > ask > allow, and the reason
lists every path with its class.

CLI VERBS (soft delete + inspection)
    deletion_guard.py trash <path>... [--cwd X] [--run-id R]
    deletion_guard.py prune [--run-id R] [--all] [--older-than-days N] [--cwd X]
    deletion_guard.py classify <path>... [--cwd X] [--json]
    deletion_guard.py check "<command>" [--cwd X]

The six shared-state git operations are IMPORTED from
``hooks/shared_rule_constants.py`` (FORBIDDEN_GIT_OPERATIONS) -- never
re-declared here. The active-run marker is read through
``hooks/run_continuity.py`` exactly as ``pretool_skill_gate.py`` reads it.

Stdlib-only. ASCII-only source (the suite runs under Windows cp1252).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:  # package shape (repo root on sys.path)
    from hooks.shared_rule_constants import FORBIDDEN_GIT_OPERATIONS
except ImportError:  # pragma: no cover - bare-module shape (hooks/ on sys.path)
    from shared_rule_constants import FORBIDDEN_GIT_OPERATIONS

try:  # package shape
    from hooks.shared_util import _utc_now_iso
except ImportError:  # pragma: no cover - bare-module shape
    from shared_util import _utc_now_iso

# Module-object import on purpose (the circular-import-safe shape the gate uses).
try:  # package shape
    from hooks import run_continuity as _rc
except ImportError:  # pragma: no cover - bare-module shape
    try:
        import run_continuity as _rc  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - substrate unavailable
        _rc = None  # type: ignore[assignment]


DISABLE_ENV = "CT6_DELETION_GUARD_DISABLED"
STATE_DIRNAME = ".architect-team"
TRASH_DIRNAME = "trash"
MANIFEST_FILENAME = ".trash-manifest.jsonl"
DEFAULT_RUN_ID = "manual"
COULD_NOT_CLASSIFY = "deletion guard could not classify"
REFERENCE_DOC = "skills/common-pipeline-conventions/references/deletion-discipline.md"

#: `.architect-team/<dir>` subtrees that ARE per-run scratch state (deletable).
#: Everything else under `.architect-team/` -- git-identity.json, decisions.jsonl,
#: principles.json, timings.jsonl, active-run.json, locks/, openspec/ -- is run
#: state that exists nowhere else and is NOT temp.
RUN_STATE_DIRS: frozenset[str] = frozenset({"reviews", "teammates", "handoffs", "trash", "run-history"})

#: Path components that mark build / cache output. A TRACKED path under one of
#: these names is never treated as temp (a repo may legitimately track `build/`).
TEMP_DIR_NAMES: frozenset[str] = frozenset({
    "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache",
    ".tox", ".nox", "htmlcov", "coverage", ".nyc_output", "dist", "build",
})
TEMP_FILE_NAMES: frozenset[str] = frozenset({".coverage"})
TEMP_FILE_SUFFIXES: tuple[str, ...] = (".pyc", ".pyo", ".egg-info")

RM_COMMANDS: frozenset[str] = frozenset({"rm", "rmdir", "unlink", "shred"})
#: v4.1.3 -- the cheap pre-screen a segment must pass before a tokenizer failure
#: is worth asking about. A heredoc'd commit message with an apostrophe ("the
#: engine's config") used to fail `shlex` and ask as "unparsable" although the
#: command deleted nothing (field report). Only a segment that LOOKS like a
#: deletion may ask when it cannot be tokenized; everything else is allowed.
_DELETION_SHAPED_RE = re.compile(
    r"(?<![\w.-])(rm|rmdir|unlink|shred|del|erase|rd|remove-item|ri|xargs|find)(?![\w-])"
    r"|\bgit\b[^\n]*\b(rm|clean|checkout|restore|reset|branch|stash|worktree|push|update-ref|reflog|filter-branch)\b"
    r"|shutil\.rmtree|os\.remove\b|os\.unlink\b|\.unlink\(|rmdir\(|os\.removedirs|send2trash",
    re.IGNORECASE,
)
_HEREDOC_OPEN_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def strip_heredocs(command: str) -> str:
    """Return ``command`` with every here-document BODY removed (the opener
    stays, the terminator line goes). A heredoc body is data fed to the
    command -- a commit message, a file's content -- never a command of its
    own, so it must not be segmented or tokenized as one. Unterminated
    heredocs drop everything after the opener's line."""
    lines = (command or "").split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = _HEREDOC_OPEN_RE.search(line)
        i += 1
        if not m:
            continue
        terminator = m.group(2)
        while i < len(lines):
            body = lines[i]
            i += 1
            if body.strip() == terminator or (line.count("<<-") and body.lstrip("\t") == terminator):
                break
    return "\n".join(out)
WINDOWS_DELETE_COMMANDS: frozenset[str] = frozenset({"del", "erase", "rd", "remove-item", "ri"})
_PYTHON_WORD_RE = re.compile(r"^(python|python3|py|pythonw)(\d+(\.\d+)*)?$")
_PYTHON_DELETE_RE = re.compile(
    r"shutil\.rmtree|os\.remove\b|os\.unlink\b|\.unlink\(|rmdir\(|os\.removedirs|send2trash"
)
_STRING_LITERAL_RE = re.compile(r"'([^'\\]*)'|\"([^\"\\]*)\"")
_PREFIX_WORDS: frozenset[str] = frozenset({"sudo", "doas", "command", "exec", "builtin", "nice", "time", "env", "nohup"})
_PREFIX_VALUE_FLAGS: frozenset[str] = frozenset({"-u", "-g", "-n", "-C"})
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_REDIRECT_TOKEN_RE = re.compile(r"^\d*(>>?|<|&>|>&|<&)\S*$")
_REDIRECT_BARE_RE = re.compile(r"^\d*(>>?|<|&>|>&|<&)$")
_WINDOWS_SWITCH_RE = re.compile(r"^/[A-Za-z](:\S*)?$")
_GIT_GLOBAL_VALUE_OPTS: frozenset[str] = frozenset({
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env",
})
_SHRED_VALUE_FLAGS: frozenset[str] = frozenset({"-n", "-s", "--iterations", "--size", "--random-source"})
_XARGS_VALUE_FLAGS: frozenset[str] = frozenset({"-I", "-i", "-n", "-P", "-d", "-L", "-s", "-a", "-E"})

_DECISION_RANK = {"allow": 0, "ask": 1, "deny": 2}
_GIT_TIMEOUT_SECONDS = 15


# --------------------------------------------------------------------------- #
# small shared plumbing
# --------------------------------------------------------------------------- #

def guard_disabled() -> bool:
    """Truthy per the house kill-switch rule: anything but unset / 0 / false / no."""
    v = os.environ.get(DISABLE_ENV, "").strip().lower()
    return v not in ("", "0", "false", "no")


def _read_stdin_utf8() -> str:
    """Read the hook payload as UTF-8 (cp1252-safe); StringIO fallback for tests."""
    buffer = getattr(sys.stdin, "buffer", None)
    if buffer is not None:
        return buffer.read().decode("utf-8", "replace")
    return sys.stdin.read()


def _git(args: list[str], cwd: Path | str) -> subprocess.CompletedProcess | None:
    """Run git in ``cwd``; ``None`` on any OS / timeout error. Optional locks are
    OFF so a classification never writes an index lock under a teammate."""
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            env=env,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def git_toplevel(start_dir: Path | str) -> Path | None:
    """The work-tree root containing ``start_dir`` (realpath), or ``None``."""
    proc = _git(["rev-parse", "--show-toplevel"], start_dir)
    if proc is None or proc.returncode != 0:
        return None
    out = (proc.stdout or "").strip()
    return Path(os.path.realpath(out)) if out else None


def _temp_roots() -> tuple[Path, ...]:
    """The OS temp roots (realpath). Applied ONLY to paths outside any git work
    tree -- a repository that happens to live under /tmp still holds real work."""
    roots: list[Path] = []
    for cand in (tempfile.gettempdir(), "/tmp", "/var/tmp", os.environ.get("TEMP"), os.environ.get("TMP")):
        if cand:
            try:
                roots.append(Path(os.path.realpath(cand)))
            except (OSError, ValueError):
                continue
    return tuple(roots)


def _under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _existing_dir(path: Path) -> Path:
    """The nearest existing directory at or above ``path``."""
    p = path
    while not p.is_dir():
        if p.parent == p:
            break
        p = p.parent
    return p


def active_run_marker(cwd: str | None) -> dict[str, Any] | None:
    """The ACTIVE, non-stale run marker for ``cwd`` -- read exactly as the
    skill gate reads it (run_continuity), with a minimal reader when that
    substrate is unavailable. ``None`` when no run is active."""
    if not isinstance(cwd, str) or not cwd.strip():
        return None
    if _rc is not None:
        try:
            marker = _rc.read_marker(cwd)
            if isinstance(marker, dict) and marker.get("status") == "active" and not _rc.marker_is_stale(marker):
                return marker
            return None
        except Exception:
            return None
    try:  # pragma: no cover - exercised only without run_continuity on the path
        data = json.loads((Path(cwd) / STATE_DIRNAME / "active-run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("status") == "active" else None


# --------------------------------------------------------------------------- #
# command parsing
# --------------------------------------------------------------------------- #

def split_segments(command: str) -> list[str]:
    """Split a command line into simple commands on UNQUOTED ``&&`` / ``||`` /
    ``;`` / ``|`` / ``&`` / newline. Quote-aware, so ``python -c "a; b"`` stays
    one segment. Subshell braces/parens around a segment are stripped."""
    segments: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(command or "")
    while i < n:
        ch = command[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < n:
                buf.append(command[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "\\" and i + 1 < n:
            buf.append(ch)
            buf.append(command[i + 1])
            i += 2
            continue
        if ch == "&" and buf and buf[-1] in "<>":
            buf.append(ch)  # `2>&1` / `&>` redirections are not separators
            i += 1
            continue
        if ch in ("\n", ";", "|", "&"):
            segments.append("".join(buf))
            buf = []
            if ch in "|&" and i + 1 < n and command[i + 1] == ch:
                i += 1
            i += 1
            continue
        buf.append(ch)
        i += 1
    segments.append("".join(buf))
    out: list[str] = []
    for seg in segments:
        s = seg.strip().lstrip("({").rstrip(")}").strip()
        if s:
            out.append(s)
    return out


def _tokenize(segment: str) -> list[str] | None:
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return None


def _tokenize_windows(segment: str) -> list[str] | None:
    try:
        toks = shlex.split(segment, posix=False)
    except ValueError:
        return None
    return [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in toks]


_SHELL_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _record_assignments(tokens: list[str], assigns: dict[str, str]) -> None:
    """v4.1.3 -- remember ``NAME=value`` assignments that lead a segment (a
    bare ``W=/tmp/lanes/x`` segment, or ``FOO=bar cmd ...``) when the value
    is a literal: a later ``git -C $W`` or ``rm $W/build`` in the SAME command
    is then resolvable. A value that itself carries ``$`` or a backtick stays
    unknown, so the unexpanded-variable rule still applies to it."""
    for t in tokens:
        m = _ENV_ASSIGN_RE.match(t)
        if not m:
            break
        name, _, value = t.partition("=")
        # A chain (`S=/tmp/x; W=$S/lanes/y`) resolves through the names already
        # known; only a value that STILL carries a variable or a backtick after
        # that expansion is unknown.
        value = _expand_known_vars([value], assigns)[0]
        if "$" in value or "`" in value:
            assigns.pop(name, None)
        else:
            assigns[name] = value


def _expand_known_vars(tokens: list[str], assigns: dict[str, str]) -> list[str]:
    """Substitute ``$NAME`` / ``${NAME}`` for names assigned earlier in the same
    command; unknown names are left as written (and later reported as
    unexpanded). Tokens arrive already unquoted by the tokenizer."""
    if not assigns:
        return tokens
    def sub(m: "re.Match[str]") -> str:
        name = m.group(1) or m.group(2)
        return assigns.get(name, m.group(0))
    return [_SHELL_VAR_RE.sub(sub, t) for t in tokens]


def _strip_prefixes(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if _ENV_ASSIGN_RE.match(t):
            i += 1
            continue
        if os.path.basename(t).lower() in _PREFIX_WORDS:
            i += 1
            while i < len(tokens) and tokens[i].startswith("-"):
                i += 2 if tokens[i] in _PREFIX_VALUE_FLAGS and i + 1 < len(tokens) else 1
            continue
        break
    return tokens[i:]


def _strip_redirections(tokens: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for t in tokens:
        if skip:
            skip = False
            continue
        if _REDIRECT_TOKEN_RE.match(t):
            if _REDIRECT_BARE_RE.match(t):
                skip = True  # a bare operator -- the next token is its file
            continue
        out.append(t)
    return out


def _command_word(tokens: list[str]) -> str:
    if not tokens:
        return ""
    word = os.path.basename(tokens[0]).lower()
    return word[:-4] if word.endswith(".exe") else word


def _hit(kind: str, segment: str, targets: list[str], base: str | None,
         unresolvable: str | None = None, label: str | None = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "segment": segment,
        "targets": list(targets),
        "base": base,
        "unresolvable": unresolvable,
        "label": label,
    }


def _positional(tokens: list[str], value_flags: frozenset[str] = frozenset()) -> list[str]:
    """Non-flag tokens; everything after ``--`` is positional."""
    out: list[str] = []
    end_opts = False
    skip = False
    for t in tokens:
        if skip:
            skip = False
            continue
        if end_opts:
            out.append(t)
            continue
        if t == "--":
            end_opts = True
            continue
        if t.startswith("-") and len(t) > 1:
            if t in value_flags:
                skip = True
            continue
        out.append(t)
    return out


def _apply_cd(tokens: list[str], base: str | None) -> str | None:
    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return os.path.expanduser("~")
    target = args[0]
    if target == "-" or "$" in target or "`" in target or any(c in target for c in "*?["):
        return None
    target = os.path.expanduser(target)
    if os.path.isabs(target):
        return os.path.normpath(target)
    if base is None:
        return None
    return os.path.normpath(os.path.join(base, target))


def _git_subcommand(tokens: list[str], base: str | None) -> tuple[str | None, list[str], str | None]:
    """``(subcommand, tokens_after_it, effective_base)`` -- honours ``-C <dir>``."""
    j = 1
    eff_base = base
    while j < len(tokens):
        t = tokens[j]
        if not t.startswith("-"):
            return t, tokens[j + 1:], eff_base
        if t in _GIT_GLOBAL_VALUE_OPTS and j + 1 < len(tokens):
            if t == "-C":
                d = tokens[j + 1]
                if os.path.isabs(d):
                    eff_base = os.path.normpath(d)
                elif eff_base is not None and "$" not in d:
                    eff_base = os.path.normpath(os.path.join(eff_base, d))
                else:
                    eff_base = None
            j += 2
        else:
            j += 1
    return None, [], eff_base


def _git_hit(tokens: list[str], segment: str, base: str | None) -> dict[str, Any] | None:
    # The six shared-state operations first -- imported, never re-declared.
    for label, pattern in FORBIDDEN_GIT_OPERATIONS:
        if pattern.search(segment):
            return _hit("shared-state", segment, [], base, label=label)
    sub, rest, eff_base = _git_subcommand(tokens, base)
    if sub == "clean":
        if "-n" in rest or "--dry-run" in rest:
            return None
        paths = _positional(rest, frozenset({"-e", "--exclude"}))
        return _hit("git-clean", segment, paths or ["."], eff_base)
    if sub == "checkout":
        if "--" in rest:
            paths = rest[rest.index("--") + 1:]
            return _hit("git-restore", segment, paths, eff_base) if paths else None
        # v4.1.5 -- `git checkout -b|-B|--orphan <name> [<start>]` creates a
        # branch and `--detach` moves HEAD; neither restores a path. The
        # positionals are a branch name and a start point (a sha, a ref),
        # not files. Field report: the start-point sha was read as a path.
        if any(t in ("-b", "-B", "--orphan", "--detach") or t.startswith(("--orphan=",)) for t in rest):
            return None
        positional = [t for t in rest if not t.startswith("-")]
        if len(positional) >= 2:  # `git checkout HEAD <path>...`
            return _hit("git-restore", segment, positional[1:], eff_base)
        return None
    if sub == "restore":
        staged = "--staged" in rest or "-S" in rest
        worktree = "--worktree" in rest or "-W" in rest
        if staged and not worktree:
            return None  # index-only: the working tree keeps its content
        paths = _positional(rest, frozenset({"-s", "--source"}))
        if not paths:
            return _hit("git-restore", segment, [], eff_base, "git restore with no resolvable pathspec")
        return _hit("git-restore", segment, paths, eff_base)
    if sub == "rm":
        if "--cached" in rest:
            return None  # index-only
        paths = _positional(rest)
        if not paths:
            return _hit("git-rm", segment, [], eff_base, "git rm with no resolvable pathspec")
        return _hit("git-rm", segment, paths, eff_base)
    return None


def _is_temp_predicate(value: str) -> bool:
    v = value.strip().strip("'\"")
    if v in TEMP_DIR_NAMES or v in TEMP_FILE_NAMES:
        return True
    if v.startswith("*") and v[1:] in TEMP_FILE_SUFFIXES:
        return True
    return v.endswith(".egg-info")


def _find_hit(tokens: list[str], segment: str, base: str | None) -> dict[str, Any] | None:
    rest = tokens[1:]
    i = 0
    while i < len(rest) and rest[i] in ("-H", "-L", "-P"):
        i += 1
    roots: list[str] = []
    while i < len(rest) and not rest[i].startswith("-") and rest[i] not in ("(", "!", ","):
        roots.append(rest[i])
        i += 1
    expr = rest[i:]
    deletes = "-delete" in expr
    for j, t in enumerate(expr):
        if t in ("-exec", "-execdir", "-ok", "-okdir") and j + 1 < len(expr):
            if _command_word([expr[j + 1]]) in RM_COMMANDS:
                deletes = True
    if not deletes:
        return None
    names = [expr[j + 1] for j, t in enumerate(expr)
             if t in ("-name", "-iname", "-path", "-ipath", "-wholename") and j + 1 < len(expr)]
    if names and all(_is_temp_predicate(v) for v in names):
        return _hit("find-temp", segment, roots or ["."], base, label=", ".join(names))
    return _hit("find", segment, roots or ["."], base)


def _python_literals(code: str) -> list[str]:
    return [a or b for a, b in _STRING_LITERAL_RE.findall(code) if (a or b).strip()]


def _python_hit(tokens: list[str], segment: str, base: str | None) -> dict[str, Any] | None:
    if "-c" not in tokens:
        return None
    idx = tokens.index("-c")
    code = tokens[idx + 1] if idx + 1 < len(tokens) else ""
    if not _PYTHON_DELETE_RE.search(code):
        return None
    literals = _python_literals(code)
    if not literals:
        return _hit("python", segment, [], base, "the deletion target is not a string literal")
    return _hit("python", segment, literals, base)


def _xargs_hit(tokens: list[str], segment: str, base: str | None) -> dict[str, Any] | None:
    rest = tokens[1:]
    skip = False
    for t in rest:
        if skip:
            skip = False
            continue
        if t.startswith("-"):
            skip = t in _XARGS_VALUE_FLAGS
            continue
        if _command_word([t]) in RM_COMMANDS:
            return _hit("xargs", segment, [], base, "deletion targets arrive on stdin and cannot be enumerated")
        return None
    return None


def _windows_hit(tokens: list[str], segment: str, base: str | None) -> dict[str, Any]:
    if "\\" in segment:
        tokens = _tokenize_windows(segment) or tokens
    targets = [t for t in tokens[1:] if not _WINDOWS_SWITCH_RE.match(t) and not t.startswith("-")]
    if not targets:
        return _hit("windows", segment, [], base, "no target path on the command line")
    return _hit("windows", segment, targets, base)


def detect_deletions(command: str, cwd: str | None) -> list[dict[str, Any]]:
    """Every deletion-shaped simple command in ``command`` -> a hit dict with
    its raw targets (resolved later against the tracked ``cd`` / ``git -C``
    base). An EMPTY list means the command deletes nothing the guard knows of."""
    hits: list[dict[str, Any]] = []
    base = cwd if isinstance(cwd, str) and cwd.strip() else None
    saw_python = False
    assigns: dict[str, str] = {}
    # Heredoc bodies are data (a commit message, a file's content), never
    # commands: segment the command with them removed. The python-heredoc
    # check below still reads the FULL text, so `python - <<EOF` bodies that
    # call shutil.rmtree are not lost.
    for seg in split_segments(strip_heredocs(command or "")):
        tokens = _tokenize(seg)
        if tokens is None:
            if _DELETION_SHAPED_RE.search(seg):
                hits.append(_hit("unparsable", seg, [], base, "the command could not be tokenized (unbalanced quotes)"))
            # A segment that is not deletion-shaped and cannot be tokenized
            # deletes nothing the guard knows of -- a prose line, an odd quote
            # in an argument to a non-deleting tool. Silence, not ask.
            continue
        # Same-command variables (`W=/tmp/x; git -C $W checkout -- f`): the
        # value is right there, so the base and the targets are resolvable.
        _record_assignments(tokens, assigns)
        tokens = _expand_known_vars(tokens, assigns)
        tokens = _strip_redirections(_strip_prefixes(tokens))
        if not tokens:
            continue
        word = _command_word(tokens)
        if word == "cd":
            base = _apply_cd(tokens, base)
            continue
        hit: dict[str, Any] | None = None
        if word == "git":
            hit = _git_hit(tokens, seg, base)
        elif word in RM_COMMANDS:
            targets = _positional(tokens[1:], _SHRED_VALUE_FLAGS if word == "shred" else frozenset())
            hit = _hit(word, seg, targets, base,
                       None if targets else "no target path on the command line (stdin, a variable, or an empty glob)")
        elif word == "find":
            hit = _find_hit(tokens, seg, base)
        elif word == "xargs":
            hit = _xargs_hit(tokens, seg, base)
        elif _PYTHON_WORD_RE.match(word):
            saw_python = True
            hit = _python_hit(tokens, seg, base)
        elif word in WINDOWS_DELETE_COMMANDS:
            hit = _windows_hit(tokens, seg, base)
        if hit is not None:
            hits.append(hit)
    if not hits and saw_python and _PYTHON_DELETE_RE.search(command or ""):
        # A heredoc body (`python - <<EOF ... EOF`) arrives as separate lines;
        # the literals in the whole text are the best available targets.
        literals = _python_literals(command)
        hits.append(_hit("python", command.strip()[:120], literals, base,
                         None if literals else "the deletion target is not a string literal"))
    return hits


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #

def resolve_target(raw: str, base: str | None) -> tuple[Path | None, str | None]:
    """``(absolute path, None)`` or ``(None, why it cannot be resolved)``."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty target"
    if "$" in raw or "`" in raw:
        return None, "unexpanded shell variable or substitution in the path"
    if any(c in raw for c in "*?["):
        return None, "unexpanded glob in the path"
    expanded = os.path.expanduser(raw)
    p = Path(expanded)
    if not p.is_absolute():
        if not base:
            return None, "relative path with no known working directory"
        p = Path(base) / p
    norm = Path(os.path.normpath(str(p)))
    if not norm.name:
        return norm, None
    return Path(os.path.realpath(str(norm.parent))) / norm.name, None


def _verdict(path: str, cls: str, decision: str, reason: str, **extra: Any) -> dict[str, Any]:
    out: dict[str, Any] = {"path": path, "class": cls, "decision": decision, "reason": reason}
    out.update(extra)
    return out


class Classifier:
    """Classifies target paths by recoverability. Caches the per-repo facts."""

    def __init__(self) -> None:
        self._toplevels: dict[str, Path | None] = {}
        self._remote: dict[str, str | None] = {}

    # -- git facts -----------------------------------------------------------
    def toplevel(self, start_dir: Path) -> Path | None:
        key = str(start_dir)
        if key not in self._toplevels:
            self._toplevels[key] = git_toplevel(start_dir)
        return self._toplevels[key]

    def head_on_remote(self, toplevel: Path) -> str | None:
        key = str(toplevel)
        if key not in self._remote:
            proc = _git(["branch", "-r", "--contains", "HEAD"], toplevel)
            name: str | None = None
            if proc is not None and proc.returncode == 0:
                names = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip() and "->" not in ln]
                name = names[0] if names else None
            self._remote[key] = name
        return self._remote[key]

    def _ignored(self, toplevel: Path, path: Path) -> bool:
        proc = _git(["check-ignore", "-q", "--", str(path)], toplevel)
        return proc is not None and proc.returncode == 0

    def _tracked_files(self, toplevel: Path, path: Path) -> list[str]:
        proc = _git(["ls-files", "--", str(path)], toplevel)
        if proc is None or proc.returncode != 0:
            return []
        return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]

    def _porcelain(self, toplevel: Path, path: Path) -> list[str] | None:
        proc = _git(["status", "--porcelain", "--untracked-files=all", "--", str(path)], toplevel)
        if proc is None or proc.returncode != 0:
            return None
        return [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]

    def _changed_lines(self, toplevel: Path, path: Path) -> int | None:
        proc = _git(["diff", "--numstat", "HEAD", "--", str(path)], toplevel)
        if proc is None or proc.returncode != 0:
            return None
        total = 0
        for ln in (proc.stdout or "").splitlines():
            parts = ln.split("\t")
            if len(parts) < 2:
                continue
            for cell in parts[:2]:
                if cell.strip().isdigit():
                    total += int(cell)
        return total

    def _restore_hint(self, toplevel: Path, path: Path, base: str | None) -> str:
        shown = str(path)
        if base:
            try:
                shown = Path(path).relative_to(Path(os.path.realpath(base))).as_posix()
            except ValueError:
                shown = str(path)
        remote = self.head_on_remote(toplevel)
        tail = (
            f"also on {remote}" if remote
            else "the commit may not be on the remote -- no remote branch contains HEAD"
        )
        return f"Restore with: git checkout HEAD -- {shown} [recoverable from local HEAD; {tail}]"

    # -- the classifier ------------------------------------------------------
    def classify(self, raw: str, base: str | None) -> dict[str, Any]:
        path, why = resolve_target(raw, base)
        if path is None:
            return _verdict(raw, "unparsable", "ask", f"{why} -- cannot classify what would be deleted")
        parts = path.parts
        if ".git" in parts:
            return _verdict(raw, "repo-metadata", "ask", "inside the repository's own .git metadata -- not a working-tree file")
        if STATE_DIRNAME in parts:
            rest = parts[parts.index(STATE_DIRNAME) + 1:]
            if rest and rest[0] in RUN_STATE_DIRS:
                return _verdict(raw, "run-state", "allow", f"CT6 per-run scratch state ({STATE_DIRNAME}/{rest[0]}) -- nothing to recover")
            return _verdict(raw, "protected-state", "ask", f"CT6 run state under {STATE_DIRNAME}/ that exists nowhere else (not temp, not recoverable from git)")
        start = _existing_dir(path)
        toplevel = self.toplevel(start)
        rel_parts = parts
        if toplevel is not None and _under(path, toplevel):
            rel_parts = path.relative_to(toplevel).parts
        temp_name = self._temp_name(rel_parts)
        if temp_name is not None:
            if toplevel is None or not self._tracked_files(toplevel, path):
                return _verdict(raw, "temp", "allow", f"build/cache artifact ({temp_name}) -- nothing to recover")
        if toplevel is None:
            if any(_under(path, root) for root in _temp_roots()):
                return _verdict(raw, "temp", "allow", "under the OS temp directory -- nothing to recover")
            return _verdict(raw, "no-repo", "ask", "outside any git repository -- no history to restore from")
        if not path.exists() and not path.is_symlink():
            return _verdict(raw, "absent", "allow", "does not exist -- nothing to delete")
        if self._ignored(toplevel, path):
            return _verdict(raw, "ignored", "allow", "gitignored -- not under version control by design")
        if path.is_dir() and not path.is_symlink():
            return self._classify_dir(raw, path, toplevel, base)
        return self._classify_file(raw, path, toplevel, base)

    @staticmethod
    def _temp_name(rel_parts: tuple[str, ...]) -> str | None:
        for part in rel_parts:
            if part in TEMP_DIR_NAMES:
                return part
        if rel_parts:
            name = rel_parts[-1]
            if name in TEMP_FILE_NAMES or name.endswith(TEMP_FILE_SUFFIXES):
                return name
        return None

    def _classify_file(self, raw: str, path: Path, toplevel: Path, base: str | None) -> dict[str, Any]:
        proc = _git(["ls-files", "--error-unmatch", "--", str(path)], toplevel)
        if proc is None:
            return _verdict(raw, "unparsable", "ask", "git could not be consulted -- cannot classify what would be deleted")
        if proc.returncode != 0:
            return _verdict(raw, "untracked", "ask", "untracked and not ignored -- this working tree holds the only copy")
        porcelain = self._porcelain(toplevel, path)
        if porcelain is None:
            return _verdict(raw, "unparsable", "ask", "git status failed -- cannot classify what would be deleted")
        if not porcelain:
            return _verdict(raw, "tracked-clean", "allow", "tracked and clean -- recoverable from local HEAD",
                            restore=self._restore_hint(toplevel, path, base))
        changed = self._changed_lines(toplevel, path)
        count = f"{changed} changed line(s)" if changed is not None else "an uncounted number of changed lines (no HEAD commit)"
        return _verdict(raw, "tracked-dirty", "ask",
                        f"tracked with uncommitted changes ({count} vs HEAD) -- those lines exist nowhere else",
                        changed_lines=changed)

    def _classify_dir(self, raw: str, path: Path, toplevel: Path, base: str | None) -> dict[str, Any]:
        tracked = self._tracked_files(toplevel, path)
        porcelain = self._porcelain(toplevel, path)
        if porcelain is None:
            return _verdict(raw, "unparsable", "ask", "git status failed -- cannot classify what would be deleted")
        untracked = [ln for ln in porcelain if ln.startswith("??")]
        modified = [ln for ln in porcelain if not ln.startswith("??")]
        if untracked or modified:
            bits: list[str] = []
            changed: int | None = None
            if modified:
                changed = self._changed_lines(toplevel, path)
                bits.append(f"{changed if changed is not None else 'uncounted'} changed line(s) vs HEAD")
            if untracked:
                bits.append(f"{len(untracked)} untracked file(s) that exist nowhere else")
            cls = "tracked-dirty" if tracked else "untracked"
            return _verdict(raw, cls, "ask", "directory holds " + " and ".join(bits) + " -- the only copies",
                            changed_lines=changed, untracked_files=len(untracked))
        if tracked:
            return _verdict(raw, "tracked-clean", "allow",
                            f"directory of {len(tracked)} tracked file(s), all clean -- recoverable from local HEAD",
                            restore=self._restore_hint(toplevel, path, base))
        return _verdict(raw, "empty-or-ignored", "allow", "directory holds no tracked or untracked files (empty or only ignored content)")


# --------------------------------------------------------------------------- #
# the decision
# --------------------------------------------------------------------------- #

def _shared_state_verdict(hit: dict[str, Any], run_cwd: str | None) -> dict[str, Any]:
    label = hit.get("label") or "shared-state git operation"
    shown = hit["segment"].strip()[:80]
    marker = active_run_marker(run_cwd)
    if marker is not None:
        slug = marker.get("slug") or marker.get("run_id") or "<unnamed>"
        return _verdict(shown, "shared-state-git-op", "deny",
                        f"'{label}' rewrites git state shared by every teammate of the ACTIVE run '{slug}' (teammate git discipline) -- never run inside a run")
    return _verdict(shown, "shared-state-git-op", "ask",
                    f"'{label}' rewrites shared git state (teammate git discipline); no active run here, so the human decides")


def _hit_verdicts(hit: dict[str, Any], clf: Classifier, run_cwd: str | None) -> list[dict[str, Any]]:
    kind = hit["kind"]
    if kind == "shared-state":
        return [_shared_state_verdict(hit, run_cwd)]
    if kind == "find-temp":
        return [_verdict(hit["segment"].strip()[:80], "temp", "allow",
                         f"find predicate names only build/cache artifacts ({hit.get('label')}) -- nothing to recover")]
    if hit.get("unresolvable"):
        return [_verdict(hit["segment"].strip()[:80], "unparsable", "ask",
                         f"{hit['unresolvable']} -- cannot classify what would be deleted")]
    return [clf.classify(raw, hit.get("base")) for raw in hit["targets"]]


def make_decision(decision: str, reason: str, context: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }
    if context:
        out["additionalContext"] = context
    return {"hookSpecificOutput": out}


def _soft_delete_hint() -> str:
    return (
        "Soft-delete instead: $(command -v python3 || command -v python) "
        "\"${CLAUDE_PLUGIN_ROOT}/hooks/deletion_guard.py\" trash <path> "
        f"(moves it under {STATE_DIRNAME}/trash/; see {REFERENCE_DOC})."
    )


def build_decision(verdicts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Most restrictive wins (deny > ask > allow); the reason lists each path."""
    if not verdicts:
        return None
    decision = max((v["decision"] for v in verdicts), key=lambda d: _DECISION_RANK.get(d, 1))
    items: list[str] = []
    seen: set[str] = set()
    for v in verdicts:
        line = f"{v['path']}: {v['class']} -- {v['reason']}"
        if line not in seen:
            seen.add(line)
            items.append(line)
    reason = f"CT6 deletion guard [{decision.upper()}]: " + "; ".join(items)
    hints = [v["restore"] for v in verdicts if v.get("restore")]
    context_bits: list[str] = []
    seen_hints: set[str] = set()
    for h in hints:
        if h not in seen_hints:
            seen_hints.add(h)
            context_bits.append(h)
    if decision != "allow" and any(
        v["decision"] != "allow" and v["class"] != "shared-state-git-op" for v in verdicts
    ):
        context_bits.append(_soft_delete_hint())  # a path can be trashed; a git op cannot
    return make_decision(decision, reason, " ".join(context_bits))


def check_command(command: str, cwd: str | None) -> dict[str, Any] | None:
    """The guard's decision for one Bash command line, or ``None`` when the
    command deletes nothing the guard recognises. Pure apart from git reads."""
    hits = detect_deletions(command, cwd)
    if not hits:
        return None
    clf = Classifier()
    verdicts: list[dict[str, Any]] = []
    for hit in hits:
        verdicts.extend(_hit_verdicts(hit, clf, cwd))
    return build_decision(verdicts)


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """PreToolUse payload -> decision dict or ``None`` (non-Bash / no deletion)."""
    tool = str(payload.get("tool_name") or payload.get("tool") or "").strip()
    if tool != "Bash":
        return None
    inp = payload.get("tool_input") or payload.get("input") or {}
    command = inp.get("command") if isinstance(inp, dict) else None
    if not isinstance(command, str) or not command.strip():
        return None
    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd.strip() else None
    return check_command(command, cwd)


def _hook_main() -> int:
    if guard_disabled():
        return 0
    payload: dict[str, Any] = {}
    try:
        raw = "" if sys.stdin.isatty() else _read_stdin_utf8()
        parsed = json.loads(raw) if raw.strip() else {}
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}
    tool = str(payload.get("tool_name") or payload.get("tool") or "").strip()
    if tool != "Bash":
        return 0
    try:
        decision = evaluate_payload(payload)
    except Exception as exc:  # fail SAFE: an unclassifiable deletion is asked, never allowed
        decision = make_decision(
            "ask",
            f"CT6 deletion guard: {COULD_NOT_CLASSIFY} ({type(exc).__name__}: {exc}) -- asking instead of allowing",
            _soft_delete_hint(),
        )
    if decision is not None:
        sys.stdout.write(json.dumps(decision) + "\n")
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- #
# CLI verbs: trash / prune / classify / check
# --------------------------------------------------------------------------- #

def workspace_root(cwd: str | None) -> Path:
    """The git toplevel of ``cwd`` (realpath), else ``cwd`` itself."""
    base = Path(os.path.realpath(cwd or os.getcwd()))
    start = base if base.is_dir() else base.parent
    return git_toplevel(start) or base


def _safe_run_id(run_id: str | None) -> str:
    rid = (run_id or "").strip()
    if not rid or not re.fullmatch(r"[A-Za-z0-9._-]+", rid) or rid in (".", ".."):
        return DEFAULT_RUN_ID
    return rid


def _resolve_cli_path(raw: str, base: Path) -> Path:
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = base / p
    norm = Path(os.path.normpath(str(p)))
    return Path(os.path.realpath(str(norm.parent))) / norm.name if norm.name else norm


def cmd_trash(paths: list[str], cwd: str | None, run_id: str | None) -> tuple[int, dict[str, Any]]:
    ws = workspace_root(cwd)
    base = Path(os.path.realpath(cwd or os.getcwd()))
    rid = _safe_run_id(run_id)
    run_dir = ws / STATE_DIRNAME / TRASH_DIRNAME / rid
    moves: list[dict[str, Any]] = []
    failures = 0
    for raw in paths:
        entry: dict[str, Any] = {"path": raw}
        p = _resolve_cli_path(raw, base)
        try:
            rel = p.relative_to(ws)
        except ValueError:
            entry.update(status="refused", reason="outside the workspace -- the trash never reaches past the git toplevel")
            moves.append(entry)
            failures += 1
            continue
        if not rel.parts:
            entry.update(status="refused", reason="the workspace root itself")
            moves.append(entry)
            failures += 1
            continue
        if rel.parts[0] == STATE_DIRNAME and (len(rel.parts) == 1 or rel.parts[1] == TRASH_DIRNAME):
            entry.update(status="refused", reason=f"the {STATE_DIRNAME}/ state dir or something already in the trash")
            moves.append(entry)
            failures += 1
            continue
        if not p.exists() and not p.is_symlink():
            entry.update(status="missing", reason="no such path")
            moves.append(entry)
            failures += 1
            continue
        dest = run_dir / rel
        n = 0
        while dest.exists() or dest.is_symlink():
            n += 1
            dest = run_dir / rel.parent / f"{rel.name}.{n}"
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
        except (OSError, shutil.Error) as exc:
            entry.update(status="failed", reason=f"{type(exc).__name__}: {exc}")
            moves.append(entry)
            failures += 1
            continue
        rel_to = dest.relative_to(ws).as_posix()
        entry.update(status="moved", to=rel_to, restore=f"mv {rel_to} {rel.as_posix()}")
        moves.append(entry)
        try:
            with open(run_dir / MANIFEST_FILENAME, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"from": rel.as_posix(), "to": rel_to, "at": _utc_now_iso()}) + "\n")
        except OSError:
            pass
    result = {
        "workspace": str(ws),
        "run_id": rid,
        "trash_dir": (run_dir.relative_to(ws)).as_posix(),
        "moves": moves,
    }
    return (0 if failures == 0 else 2), result


def _trash_dir_age_marker(d: Path) -> float:
    stamps = [d.stat().st_mtime]
    manifest = d / MANIFEST_FILENAME
    if manifest.exists():
        stamps.append(manifest.stat().st_mtime)
    return max(stamps)


def cmd_prune(cwd: str | None, run_id: str | None, all_runs: bool, older_than_days: float | None) -> tuple[int, dict[str, Any]]:
    ws = workspace_root(cwd)
    trash_root = ws / STATE_DIRNAME / TRASH_DIRNAME
    if not run_id and not all_runs:
        return 2, {"error": "prune needs --run-id <id> or --all", "workspace": str(ws)}
    pruned: list[str] = []
    kept: list[dict[str, Any]] = []
    if trash_root.is_dir():
        if run_id:
            candidates = [trash_root / _safe_run_id(run_id)]
        else:
            candidates = sorted(d for d in trash_root.iterdir() if d.is_dir())
        cutoff = time.time() - float(older_than_days) * 86400.0 if older_than_days is not None else None
        for d in candidates:
            if not d.is_dir():
                kept.append({"run_id": d.name, "reason": "no such trash dir"})
                continue
            if cutoff is not None and _trash_dir_age_marker(d) > cutoff:
                kept.append({"run_id": d.name, "reason": f"newer than {older_than_days} day(s)"})
                continue
            try:
                shutil.rmtree(d)
                pruned.append(d.name)
            except OSError as exc:
                kept.append({"run_id": d.name, "reason": f"{type(exc).__name__}: {exc}"})
    return 0, {"workspace": str(ws), "trash_root": trash_root.relative_to(ws).as_posix(), "pruned": pruned, "kept": kept}


def cmd_classify(paths: list[str], cwd: str | None) -> list[dict[str, Any]]:
    base = os.path.realpath(cwd or os.getcwd())
    clf = Classifier()
    return [clf.classify(raw, base) for raw in paths]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deletion_guard.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="verb")
    t = sub.add_parser("trash", help="soft-delete paths into .architect-team/trash/<run-id>/")
    t.add_argument("paths", nargs="+")
    t.add_argument("--cwd", default=None)
    t.add_argument("--run-id", default=None)
    p = sub.add_parser("prune", help="hard-delete trash dirs")
    p.add_argument("--cwd", default=None)
    p.add_argument("--run-id", default=None)
    p.add_argument("--all", action="store_true")
    p.add_argument("--older-than-days", type=float, default=None)
    c = sub.add_parser("classify", help="classify paths by recoverability")
    c.add_argument("paths", nargs="+")
    c.add_argument("--cwd", default=None)
    c.add_argument("--json", action="store_true")
    k = sub.add_parser("check", help="show the guard's decision for a command line")
    k.add_argument("command")
    k.add_argument("--cwd", default=None)
    return parser


def _cli(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    if args.verb == "trash":
        code, result = cmd_trash(args.paths, args.cwd, args.run_id)
        print(json.dumps(result, indent=2))
        return code
    if args.verb == "prune":
        code, result = cmd_prune(args.cwd, args.run_id, args.all, args.older_than_days)
        print(json.dumps(result, indent=2))
        return code
    if args.verb == "classify":
        results = cmd_classify(args.paths, args.cwd)
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"{r['path']}\t{r['class']}\t{r['decision']}\t{r['reason']}")
        return 0
    if args.verb == "check":
        decision = check_command(args.command, args.cwd or os.getcwd())
        print(json.dumps(decision if decision is not None else {"decision": None, "note": "not a deletion-shaped command"}, indent=2))
        return 0
    _build_parser().print_help()
    return 2


def main(argv: list[str] | None = None) -> int:
    """With arguments: a CLI verb. Without: the PreToolUse hook (payload on stdin)."""
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    if argv:
        return _cli(argv)
    try:
        return _hook_main()
    except Exception as exc:  # pragma: no cover - the last-resort fail-safe
        try:
            sys.stdout.write(json.dumps(make_decision(
                "ask", f"CT6 deletion guard: {COULD_NOT_CLASSIFY} ({type(exc).__name__}: {exc}) -- asking instead of allowing")) + "\n")
        except Exception:
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
