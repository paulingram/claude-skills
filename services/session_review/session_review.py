# -*- coding: utf-8 -*-
"""The Session Review agent (SR-1…3) — stdlib + an LLM adapter.

A service of similar design to the Librarian (SR-1): if activated, it sits on the
server or laptop and reviews agentic output at the SESSION level. As it works
through a session it performs a simple outbound PUSH summarizing the session's
output (SR-2), and it identifies the issues the agents ran into — specifically the
ones they were NOT competent enough to solve on the first attempt (SR-3).

Reuse-first: the unsolved issues are normalized with the triage `issue` record and
filed through the triage `sink`, so they follow the SAME triage process as the
automatic evaluator (EVAL) and the manual helpdesk (HD) paths. The LLM is the
injected adapter; the prompt + the string-aware parse are deterministic + testable
with `FakeLLMClient`. Runs on the shared `bg_runtime` (SR-1 / BG-1…2).

HONEST BOUNDARY: design + a runnable stdlib-only core + tests, NOT a live-deployed
service. The real LLM, the live outbound-push target (the triage server — a real
pusher signs the payload via `services/common/handshake.py` and POSTs it), and
persistence are adapters / operator-provided.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Callable, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here.parent / "triage"))     # issue, sink (reuse the triage record + sink)
sys.path.insert(0, str(_here.parent / "common"))      # bg_runtime (shared substrate)
import issue as _issue  # noqa: E402
try:  # bg_runtime is optional at import time (scheduling is opt-in)
    import bg_runtime as _bg  # noqa: E402
except Exception:  # pragma: no cover
    _bg = None


def build_session_review_prompt(session_logs: str, *, version: str) -> str:
    """SR-1/2/3 prompt: review a session's agentic output AT THE SESSION LEVEL.
    Return a session SUMMARY (SR-2) and the issues the agents hit — flagging, per
    issue, whether it was solved on the FIRST attempt (SR-3 keeps the ones that were
    NOT). Asks for one JSON object so the output is machine-parseable."""
    return (
        "You are a session-review agent reviewing a full coding-agent SESSION at the "
        "session level. Produce: (1) a concise SUMMARY of what the session "
        "accomplished; and (2) the ISSUES the agents ran into — for each, whether it "
        "was solved on the FIRST attempt, and how many attempts it took. Focus on the "
        "issues the agents were NOT competent enough to solve on the first try.\n"
        f"Plugin version: {version}.\n"
        'Respond with ONLY a JSON object: {"summary": "...", "issues": '
        '[{"category": "...", "what": "...", "what_happened": "...", '
        '"solved_on_first_attempt": false, "attempts": 2}]}\n\nSESSION LOG:\n'
        + (session_logs or "")
    )


def parse_session_review(output: str) -> dict[str, Any]:
    """Parse the session-review JSON reply robustly (string-aware `raw_decode` over
    each `{`). Returns `{summary, issues}` with safe defaults; an unparseable reply
    or a non-list `issues` yields empty, never raises."""
    text = output or ""
    decoder = json.JSONDecoder()
    idx = text.find("{")
    data: dict[str, Any] = {}
    attempts = 0
    while idx != -1 and attempts < 4096:   # cap candidate starts: bounds pathological brace-heavy input
        attempts += 1
        try:
            parsed, _end = decoder.raw_decode(text, idx)
            if isinstance(parsed, dict):
                data = parsed
                break
        except ValueError:
            pass
        idx = text.find("{", idx + 1)
    issues = data.get("issues")
    return {
        "summary": str(data.get("summary", "")).strip(),
        "issues": [x for x in issues if isinstance(x, dict)] if isinstance(issues, list) else [],
    }


def _solved_on_first_attempt(v: Any) -> bool:
    """Coerce the LLM's `solved_on_first_attempt` to a real boolean. ONLY a genuine
    affirmative counts as solved — `True`, an affirmative string (`true`/`yes`/`y`/`1`),
    or the number 1. Everything else (missing, `False`, the STRING `"false"`/`"no"`,
    0, null, a list/dict) is NOT affirmative, so SR-3 default-KEEPS the issue (errs
    toward surfacing). Plain truthiness would wrongly drop a stringified `"false"`."""
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "yes", "y", "1"}
    if isinstance(v, (int, float)):
        return v == 1
    return False


def review_session(
    session_logs: str,
    llm: Any,
    *,
    version: str,
    privacy_level: str = "off",
) -> dict[str, Any]:
    """SR-1/2/3: review a session. Returns `{summary, unsolved_issues}` where
    `unsolved_issues` are normalized triage issue records (reuse) for ONLY the issues
    the agents did NOT solve on the first attempt (SR-3). `summary` is the SR-2 push
    payload text. `privacy_level` defaults to `off` (the EVAL-17 posture)."""
    if not version:
        raise ValueError("session review must record the version (EVAL-8)")
    review = parse_session_review(llm.complete(build_session_review_prompt(session_logs, version=version)))
    unsolved: list[dict[str, Any]] = []
    for item in review["issues"]:
        if _solved_on_first_attempt(item.get("solved_on_first_attempt")):
            continue  # SR-3: keep ONLY the issues NOT solved on the first attempt
        category = str(item.get("category", "")).strip()
        what = str(item.get("what", "")).strip()
        if not (category and what):
            continue
        wh = str(item.get("what_happened", "")).strip()
        ev = [{"category": category, "what_happened": wh,
               "agent_could_not_solve": True, "attempts": item.get("attempts")}]
        unsolved.append(_issue.make_issue(
            category, what, wh, version=version, source="auto",
            evidence=ev, privacy_level=privacy_level,
        ))
    return {"summary": review["summary"], "unsolved_issues": unsolved}


class SessionReview:
    """Ties the LLM + the triage issue sink + a summary pusher together (SR-1…3).
    Runs on the shared BG runtime, like the Librarian (SR-1)."""

    def __init__(self, llm: Any, sink: Any, *, version: str,
                 summary_pusher: Optional[Callable[[dict[str, Any]], Any]] = None):
        if not version:
            raise ValueError("session review must record the version (EVAL-8)")
        self.llm = llm
        self.sink = sink
        self.version = version
        # SR-2: the "simple outbound push" of the session summary. The real target
        # (the triage server) is the operator's; a real pusher signs the payload via
        # services/common/handshake.py and POSTs it. With no pusher the summary is
        # returned but NOT transmitted (honest — `pushed: False`).
        self.summary_pusher = summary_pusher

    def review_and_push(self, session_logs: str, *, privacy_level: str = "off") -> dict[str, Any]:
        """SR-1/2/3: review the session, PUSH the summary (SR-2), and file each
        unsolved issue through the triage sink (SR-3 — the same triage path). Returns
        `{summary, summary_payload, pushed, tickets, unsolved_issues}`.

        EVAL-17 (off by default): under `privacy_level == "off"` NOTHING is
        transmitted off-machine — neither the (free-text, possibly identifiable)
        summary push NOR the issue tickets; the review is produced LOCALLY only and
        the caller opts in to `summary`/`full` to transmit. (Consistent with the
        triage server's `off` behavior.) At `summary`/`full` the summary text is sent
        as-is (the model is asked for a non-identifiable summary; the same
        retained-free-text caveat as the helpdesk `summary` posture); issue evidence
        is already redacted per level by `make_issue`."""
        result = review_session(session_logs, self.llm, version=self.version, privacy_level=privacy_level)
        summary_payload = {
            "schema": "session-summary/v1",
            "version": self.version,
            "summary": result["summary"],
            "unsolved_count": len(result["unsolved_issues"]),
        }
        if privacy_level == "off":
            return {"summary": result["summary"], "summary_payload": summary_payload,
                    "pushed": False, "tickets": [],
                    "unsolved_issues": result["unsolved_issues"]}
        pushed = False
        if self.summary_pusher is not None:
            try:
                self.summary_pusher(summary_payload)
                pushed = True
            except Exception:
                pushed = False  # best-effort, like notify.py — never crash the review
        tickets = []
        for iss in result["unsolved_issues"]:
            try:
                tickets.append(self.sink.create_ticket(iss))
            except Exception:
                pass  # best-effort, symmetric with the push — a sink fault never crashes the review
        return {"summary": result["summary"], "summary_payload": summary_payload,
                "pushed": pushed, "tickets": tickets,
                "unsolved_issues": result["unsolved_issues"]}

    def build_review_task(self, collect_session_logs: Callable[[], str],
                          *, interval_seconds: int = 1800, privacy_level: str = "off"):
        """SR-1: a BG task that reviews the latest session + pushes, on a schedule
        (like the Librarian). Returns a `bg_runtime.ServiceTask`."""
        if _bg is None:
            raise RuntimeError("bg_runtime is unavailable")

        def _run() -> dict[str, Any]:
            rep = self.review_and_push(collect_session_logs(), privacy_level=privacy_level)
            return {"pushed": rep["pushed"], "unsolved": len(rep["tickets"])}

        return _bg.ServiceTask("session-review", interval_seconds, fn=_run)

    def install_descriptor(self, platform: str, command: str, **kwargs) -> dict[str, str]:
        """The per-OS boot/restart install descriptor for the session-review daemon
        (SR-1 / BG-1…3), via the shared BG runtime."""
        if _bg is None:
            raise RuntimeError("bg_runtime is unavailable")
        return _bg.install_descriptor(platform, "ct6-session-review", command, **kwargs)
