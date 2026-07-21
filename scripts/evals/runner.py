# -*- coding: utf-8 -*-
"""Non-interactive ``claude`` CLI runner + stream-json transcript parser.

Stdlib-only, ASCII-safe, NO import-time side effects.

This module drives ``claude -p <prompt> --output-format stream-json`` as a
subprocess with a HARD wall-clock timeout and parses the emitted NDJSON stream
into a structured :class:`Transcript`.

Flag portability
----------------
The set of bounding flags a given ``claude`` build accepts varies by version
(for example, ``--max-turns`` is present in some builds and absent in others).
The runner never assumes a flag exists: :func:`supported_flags` parses
``claude -p --help`` ONCE and :func:`build_command` includes an optional
bounding flag only when the build advertises it. The guaranteed hard bound is
therefore the subprocess wall-clock timeout, which is always applied; the
CLI-level bounds (``--max-turns`` / ``--max-budget-usd`` / an allowed-tools
list) are best-effort tighteners layered on top when supported.

Robustness contract
--------------------
The stream parser is robust to unknown event shapes: any line that is not
valid JSON is skipped, and any event whose shape the parser does not recognise
is retained verbatim in ``events`` but never crashes extraction. A non-zero
exit or a timeout is RECORDED on the transcript, never raised.
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# The subprocess wall-clock ceiling applied when a config does not name one.
# This is the always-on hard bound; CLI-level bounds are layered on top when
# the build supports them.
DEFAULT_TIMEOUT_S = 900.0

# The flag-token grammar in ``claude -p --help``. Case-insensitive because the
# CLI advertises mixed-case aliases such as ``--allowedTools``.
_FLAG_RE = re.compile(r"--[A-Za-z][A-Za-z0-9-]*")

# Cache of parsed help-advertised flags, keyed by the ``claude`` binary name so
# a test that points at a fake binary does not poison the real cache.
_FLAG_CACHE: Dict[str, frozenset] = {}


def supported_flags(claude_bin: str = "claude", *, use_cache: bool = True) -> frozenset:
    """Return the set of ``--flag`` tokens advertised by ``<bin> -p --help``.

    Returns an empty set when the help probe cannot be run (missing binary,
    non-zero exit, timeout). Callers treat the empty set as "unknown" and fall
    back to a documented stable subset (see :func:`build_command`).
    """
    if use_cache and claude_bin in _FLAG_CACHE:
        return _FLAG_CACHE[claude_bin]
    flags: frozenset = frozenset()
    try:
        proc = subprocess.run(
            [claude_bin, "-p", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        flags = frozenset(_FLAG_RE.findall(text))
    except (OSError, subprocess.SubprocessError):
        flags = frozenset()
    if use_cache:
        _FLAG_CACHE[claude_bin] = flags
    return flags


# The bounding flags the runner adds only when the build both advertises them
# AND the config requests them. Everything not in this list that a caller needs
# goes through ``extra_args`` verbatim.
_OPTIONAL_FLAGS_STABLE = frozenset(
    {
        "--model",
        "--max-turns",
        "--max-budget-usd",
        "--allowedTools",
        "--verbose",
    }
)


@dataclass
class RunnerConfig:
    """Bounds + selectors for one ``claude`` invocation.

    Only ``timeout_s`` is guaranteed to take effect; the rest are applied when
    the target ``claude`` build advertises the corresponding flag.
    """

    model: Optional[str] = None
    max_turns: Optional[int] = None
    max_budget_usd: Optional[float] = None
    allowed_tools: Optional[Sequence[str]] = None
    cwd: Optional[str] = None
    timeout_s: float = DEFAULT_TIMEOUT_S
    output_format: str = "stream-json"
    claude_bin: str = "claude"
    # Verbatim trailing args (e.g. ``--permission-mode bypassPermissions``).
    extra_args: Optional[Sequence[str]] = None


@dataclass
class Transcript:
    """Structured view of one ``claude`` run.

    ``events`` holds every parsed NDJSON object verbatim; the remaining fields
    are extracted best-effort and default to empty/None when the stream did not
    carry them.
    """

    events: List[Dict[str, Any]] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    texts: List[str] = field(default_factory=list)
    final_text: str = ""
    usage: Optional[Dict[str, Any]] = None
    cost_usd: Optional[float] = None
    num_turns: Optional[int] = None
    duration_s: Optional[float] = None
    result_subtype: Optional[str] = None
    is_error: Optional[bool] = None
    returncode: Optional[int] = None
    timed_out: bool = False
    stderr: str = ""

    @property
    def tool_count(self) -> int:
        return len(self.tool_calls)

    @property
    def tool_names(self) -> List[str]:
        return [tc.get("name", "") for tc in self.tool_calls]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_calls": list(self.tool_calls),
            "tool_count": self.tool_count,
            "tool_names": self.tool_names,
            "final_text": self.final_text,
            "usage": self.usage,
            "cost_usd": self.cost_usd,
            "num_turns": self.num_turns,
            "duration_s": self.duration_s,
            "result_subtype": self.result_subtype,
            "is_error": self.is_error,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "n_events": len(self.events),
        }


def build_command(
    prompt: str,
    config: Optional[RunnerConfig] = None,
    *,
    available_flags: Optional[frozenset] = None,
    model: Optional[str] = None,
) -> List[str]:
    """Assemble the ``claude`` argv for ``prompt`` under ``config``.

    ``available_flags`` is injectable for deterministic testing; when omitted
    it is probed from the build. When the probe yields nothing (unknown build)
    the runner falls back to the documented stable optional subset so a
    well-known flag is still passed rather than silently dropped.

    ``model`` pins the model for this call; when None it falls back to
    ``config.model``. The effective model is passed as ``--model`` ONLY when the
    build advertises the flag. Pinning a model matters because the subprocess
    otherwise inherits the parent session's default model - which may be an
    alias an older ``claude`` build cannot resolve (a `404 model: <alias>`).
    """
    cfg = config or RunnerConfig()
    if available_flags is None:
        probed = supported_flags(cfg.claude_bin)
        available = probed if probed else _OPTIONAL_FLAGS_STABLE
    else:
        available = available_flags

    effective_model = model if model is not None else cfg.model

    cmd: List[str] = [cfg.claude_bin, "-p", prompt, "--output-format", cfg.output_format]

    # stream-json output is emitted incrementally and, on several builds, is
    # gated behind --verbose; add it only when advertised.
    if cfg.output_format == "stream-json" and "--verbose" in available:
        cmd.append("--verbose")

    if effective_model and "--model" in available:
        cmd += ["--model", effective_model]
    if cfg.max_turns is not None and "--max-turns" in available:
        cmd += ["--max-turns", str(cfg.max_turns)]
    if cfg.max_budget_usd is not None and "--max-budget-usd" in available:
        cmd += ["--max-budget-usd", str(cfg.max_budget_usd)]
    if cfg.allowed_tools and "--allowedTools" in available:
        cmd += ["--allowedTools", ",".join(cfg.allowed_tools)]

    if cfg.extra_args:
        cmd += list(cfg.extra_args)
    return cmd


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_content_blocks(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the content-block list of an assistant/user message event.

    Tolerant of both the ``{"message": {"content": [...]}}`` envelope and a
    bare ``{"content": [...]}`` shape; returns [] for anything else.
    """
    message = event.get("message")
    if isinstance(message, dict):
        content = message.get("content")
    else:
        content = event.get("content")
    if isinstance(content, list):
        return [b for b in content if isinstance(b, dict)]
    return []


def parse_stream(text: Any) -> Transcript:
    """Parse an NDJSON ``claude`` stream (str or line iterable) into a Transcript.

    Never raises on malformed input: non-JSON lines and unrecognised event
    shapes are skipped/retained without aborting extraction.
    """
    if isinstance(text, str):
        lines = text.splitlines()
    else:
        lines: List[str] = []
        for chunk in text or []:
            lines.extend(str(chunk).splitlines())

    tr = Transcript()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        tr.events.append(event)
        etype = event.get("type")

        if etype == "assistant":
            for block in _extract_content_blocks(event):
                btype = block.get("type")
                if btype == "tool_use":
                    tr.tool_calls.append(
                        {"name": block.get("name", ""), "input": block.get("input", {})}
                    )
                elif btype == "text":
                    txt = block.get("text")
                    if isinstance(txt, str) and txt:
                        tr.texts.append(txt)
        elif etype == "result":
            # Terminal event: authoritative for cost / turns / final text.
            tr.result_subtype = event.get("subtype")
            if "is_error" in event:
                tr.is_error = bool(event.get("is_error"))
            result_text = event.get("result")
            if isinstance(result_text, str):
                tr.final_text = result_text
            usage = event.get("usage")
            if isinstance(usage, dict):
                tr.usage = usage
            cost = event.get("total_cost_usd", event.get("cost_usd"))
            cost_f = _coerce_float(cost)
            if cost_f is not None:
                tr.cost_usd = cost_f
            turns = _coerce_int(event.get("num_turns"))
            if turns is not None:
                tr.num_turns = turns
            dur_ms = _coerce_float(event.get("duration_ms"))
            if dur_ms is not None:
                tr.duration_s = dur_ms / 1000.0
        # Any other event type (system/init, user/tool-result, unknown) is
        # retained in ``events`` and otherwise ignored.

    if not tr.final_text and tr.texts:
        tr.final_text = tr.texts[-1]
    return tr


def run(
    prompt: str,
    config: Optional[RunnerConfig] = None,
    *,
    model: Optional[str] = None,
) -> Transcript:
    """Execute ``claude`` for ``prompt`` and return the parsed Transcript.

    The subprocess wall-clock timeout is the hard bound. A timeout or a
    non-zero exit is recorded on the returned transcript, never raised; on
    timeout, whatever partial stdout was buffered is still parsed.

    Model pinning: ``model`` (falling back to ``config.model``) pins the model
    for this call. When an explicit model is in effect, the model-forcing child
    env var (``ANTHROPIC_MODEL``) is ALSO scrubbed from the child environment,
    so a parent-session model alias cannot leak past the ``--model`` flag and
    produce a `404 model: <alias>` on an older ``claude`` build. When no model
    is in effect, the child inherits the environment unchanged.

    Process-tree reaping: the ``claude`` CLI can spawn grandchildren (its own
    subprocesses / tools). On POSIX the child is launched in a new session
    (``start_new_session=True``) so a timeout can SIGKILL the whole process
    group, not just the direct child - otherwise a killed parent can orphan a
    still-running grandchild that keeps consuming resources. Where process
    groups are unavailable (Windows), the direct child is killed as a fallback.
    """
    cfg = config or RunnerConfig()
    effective_model = model if model is not None else cfg.model
    cmd = build_command(prompt, cfg, model=model)
    stdout = ""
    stderr = ""
    returncode: Optional[int] = None
    timed_out = False

    popen_kwargs: Dict[str, Any] = {
        "cwd": cfg.cwd,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
    }
    # Own session/process group so the timeout path can reap the whole tree.
    if hasattr(os, "setsid"):
        popen_kwargs["start_new_session"] = True
    # Scrub the model-forcing env when a model is pinned, so an inherited
    # session alias cannot override the explicit --model selection.
    if effective_model is not None:
        popen_kwargs["env"] = _child_env_without_model_override()

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except OSError as exc:
        tr = parse_stream("")
        tr.returncode = None
        tr.timed_out = False
        tr.stderr = f"runner: failed to launch claude: {exc}"
        return tr

    try:
        stdout, stderr = proc.communicate(timeout=cfg.timeout_s)
        returncode = proc.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        # Reap the killed process and collect whatever partial output buffered.
        try:
            stdout, stderr = proc.communicate(timeout=10)
        except (subprocess.SubprocessError, OSError, ValueError):
            pass
        returncode = proc.returncode

    tr = parse_stream(_as_text(stdout))
    tr.returncode = returncode
    tr.timed_out = timed_out
    tr.stderr = _as_text(stderr)
    return tr


# Env vars that force a specific model on the child ``claude`` and would
# override an explicit --model selection if inherited from the parent session.
_MODEL_FORCING_ENV_VARS = ("ANTHROPIC_MODEL",)


def _child_env_without_model_override() -> Dict[str, str]:
    """Copy of the current environment with model-forcing vars removed."""
    env = dict(os.environ)
    for var in _MODEL_FORCING_ENV_VARS:
        env.pop(var, None)
    return env


def _kill_process_tree(proc: "subprocess.Popen") -> None:
    """SIGKILL the child's whole process group; fall back to the direct child.

    On POSIX the child was started in its own session, so ``killpg`` on the
    child's process-group id reaps grandchildren too. If the group cannot be
    resolved or the platform lacks process groups (Windows), the direct child
    is killed instead. Never raises.
    """
    try:
        if hasattr(os, "killpg") and hasattr(os, "getpgid"):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
    except (OSError, ValueError):
        pass  # fall through to the direct-child kill
    try:
        proc.kill()
    except (OSError, ValueError):
        pass


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)
