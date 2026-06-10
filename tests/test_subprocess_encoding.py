"""A7 (review-remediation): every text-mode subprocess call in the four named
files carries `encoding="utf-8"` (+ `errors="replace"`), and the network git
ops carry a bounded `timeout=`.

`text=True` (or `universal_newlines=True`) without `encoding=` decodes child
output with the implicit locale codec, which mojibakes / `UnicodeDecodeError`s
on a non-ASCII branch or worktree path under Windows cp1252. The fix is to make
the decoding explicit. Template: scripts/setup/install_mempalace.py:71-78.

This is a SOURCE-STRUCTURAL assertion implemented over the AST, so it inspects
exactly `subprocess.run` / `subprocess.Popen` / `subprocess.check_output` /
`subprocess.call` calls (and never false-matches a `read_text(encoding=...)`
or an unrelated `text=True` in prose).

Network git ops (`git push`, `git push --delete`) additionally must carry a
`timeout=` so a hung credential prompt cannot hang the run forever.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

A7_FILES = [
    REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py",
    REPO_ROOT / "scripts" / "setup" / "worktree_paths.py",
    REPO_ROOT / "scripts" / "setup" / "setup.py",
    REPO_ROOT / "hooks" / "pipeline-completion-audit.py",
]

_SUBPROCESS_FUNCS = {"run", "Popen", "check_output", "call", "check_call"}


def _kw(call: ast.Call, name: str) -> ast.keyword | None:
    for k in call.keywords:
        if k.arg == name:
            return k
    return None

def _kw_is_truthy_constant(call: ast.Call, name: str) -> bool:
    k = _kw(call, name)
    return k is not None and isinstance(k.value, ast.Constant) and bool(k.value.value)


def _kw_str_value(call: ast.Call, name: str) -> str | None:
    k = _kw(call, name)
    if k is not None and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
        return k.value.value
    return None


def _is_subprocess_call(call: ast.Call) -> bool:
    """True iff `call` is subprocess.<run|Popen|check_output|call|check_call>(...)."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in _SUBPROCESS_FUNCS:
        base = func.value
        if isinstance(base, ast.Name) and base.id == "subprocess":
            return True
    return False


def _text_mode(call: ast.Call) -> bool:
    """True iff the call requests text-mode decoding (text=True or
    universal_newlines=True)."""
    return _kw_is_truthy_constant(call, "text") or _kw_is_truthy_constant(
        call, "universal_newlines"
    )


def _collect_subprocess_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_subprocess_call(node)
    ]


@pytest.mark.parametrize("path", A7_FILES, ids=lambda p: p.name)
def test_file_exists(path: Path) -> None:
    assert path.exists(), f"{path} missing"


@pytest.mark.parametrize("path", A7_FILES, ids=lambda p: p.name)
def test_every_text_mode_subprocess_call_has_encoding(path: Path) -> None:
    calls = _collect_subprocess_calls(path)
    assert calls, f"no subprocess calls found in {path.name} (unexpected)"
    offenders: list[int] = []
    for call in calls:
        if not _text_mode(call):
            continue
        enc = _kw_str_value(call, "encoding")
        if enc is None:
            offenders.append(getattr(call, "lineno", -1))
            continue
        assert enc.lower() in {"utf-8", "utf8"}, (
            f"{path.name}:{call.lineno} subprocess encoding is {enc!r}, "
            f"expected utf-8"
        )
        # errors='replace' guarantees the decode never raises.
        err = _kw_str_value(call, "errors")
        assert err == "replace", (
            f"{path.name}:{call.lineno} text-mode subprocess call must carry "
            f"errors='replace' (got {err!r})"
        )
    assert not offenders, (
        f"{path.name}: text-mode subprocess call(s) at line(s) {offenders} "
        f"lack encoding='utf-8' — they decode with the locale codec and "
        f"mojibake under cp1252 (A7)."
    )


def test_worktree_lifecycle_network_pushes_carry_timeout() -> None:
    """The two network git ops (`git push`, `git push --delete`) must carry a
    bounded timeout so a hung credential prompt cannot hang the run forever.

    In worktree_lifecycle.py these route through the `_git_run` helper, which is
    called with `timeout=_NETWORK_GIT_TIMEOUT` for the push ops. We assert that
    every `_git_run(...)` whose command list contains the literal "push" passes
    a `timeout=` keyword.
    """
    path = REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    def _calls_named(name: str) -> list[ast.Call]:
        return [
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == name
        ]

    push_calls = []
    for call in _calls_named("_git_run"):
        if not call.args:
            continue
        first = call.args[0]
        if isinstance(first, ast.List):
            literals = [
                el.value
                for el in first.elts
                if isinstance(el, ast.Constant) and isinstance(el.value, str)
            ]
            if "push" in literals:
                push_calls.append(call)
    assert push_calls, "expected at least one `_git_run([... 'push' ...])` network call"
    for call in push_calls:
        assert _kw(call, "timeout") is not None, (
            f"worktree_lifecycle.py:{call.lineno} network `_git_run([...push...])` "
            f"call must carry a timeout= (A7 — hung credential prompt guard)."
        )


def test_git_run_helper_sets_encoding_and_timeout() -> None:
    """The `_git_run` helper itself (the single real subprocess.run in
    worktree_lifecycle.py) must carry encoding='utf-8', errors='replace', and a
    timeout= so the whole module is covered by one place."""
    path = REPO_ROOT / "scripts" / "setup" / "worktree_lifecycle.py"
    calls = _collect_subprocess_calls(path)
    # Exactly one real subprocess.run survives (inside _git_run).
    run_calls = [c for c in calls if isinstance(c.func, ast.Attribute) and c.func.attr == "run"]
    assert len(run_calls) == 1, (
        f"expected exactly one subprocess.run in worktree_lifecycle.py (inside "
        f"_git_run); found {len(run_calls)} at lines "
        f"{[c.lineno for c in run_calls]}"
    )
    call = run_calls[0]
    assert _kw_str_value(call, "encoding") in {"utf-8", "utf8"}
    assert _kw_str_value(call, "errors") == "replace"
    assert _kw(call, "timeout") is not None, "_git_run must pass timeout= through"
