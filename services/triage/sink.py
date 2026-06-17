# -*- coding: utf-8 -*-
"""Issue sink adapters (EVAL-2) — stdlib-only.

EVAL-2's preferred mechanism: log each categorized issue as a GitHub issue, then
pull those into the project's own server. The sink is an ADAPTER interface so the
triage core never assumes a network: `InMemorySink` backs the tests, and
`GitHubIssueSink` BUILDS the GitHub-issue payload (title/body/labels) from an issue
record and posts it via an INJECTED `poster` callable — the real HTTP POST (token +
network) is the operator's, mirroring the best-effort `scripts/notify/notify.py`
pattern. With no poster the ticket is recorded locally and marked not-transmitted
(honest: nothing was actually sent). The reverse direction (PULL GitHub issues back
into the project's own server) needs the live GitHub API and is the operator's.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


class IssueSink:
    """Abstract issue sink (EVAL-2). `create_ticket(issue) -> ticket` records the
    issue as a ticket; `list_tickets()` returns them."""

    def create_ticket(self, issue: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def list_tickets(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class InMemorySink(IssueSink):
    """Deterministic test/offline sink: keeps tickets in a list."""

    def __init__(self) -> None:
        self._tickets: list[dict[str, Any]] = []

    def create_ticket(self, issue: dict[str, Any]) -> dict[str, Any]:
        ticket = {"ticket_id": f"t-{len(self._tickets) + 1}", "issue": issue,
                  "state": "open", "transmitted": False}
        self._tickets.append(ticket)
        return ticket

    def list_tickets(self) -> list[dict[str, Any]]:
        return list(self._tickets)


def github_issue_payload(issue: dict[str, Any]) -> dict[str, Any]:
    """Build the GitHub-issue REST payload from an issue record (EVAL-2). Title =
    category + a short what; body = the structured fields; labels = category /
    version / source. Privacy is ALREADY applied on the issue (EVAL-15…17) — this
    only formats what the record carries (it adds no new identifiable data)."""
    what = str(issue.get("what", "")).strip()
    title = f"[{issue.get('category', 'issue')}] {what[:80]}".strip()
    body = (
        f"**What:** {what}\n\n"
        f"**What happened:** {issue.get('what_happened', '')}\n\n"
        f"**Version:** {issue.get('version', '?')}  \n"
        f"**Source:** {issue.get('source', '?')}  \n"
        f"**Fingerprint:** `{issue.get('fingerprint', '')}`\n"
    )
    labels = [f"category:{issue.get('category', 'issue')}",
              f"version:{issue.get('version', '?')}",
              f"source:{issue.get('source', '?')}"]
    return {"title": title, "body": body, "labels": labels}


class GitHubIssueSink(IssueSink):
    """EVAL-2 GitHub sink. Builds the GitHub-issue payload and posts it via the
    injected `poster(payload) -> ticket_id | None`. The real poster (a token + an
    HTTP POST to the GitHub issues API) is the operator's — the separated service
    tier's own dependency (REPO-4); with `poster=None` nothing is sent and the ticket
    is recorded as not-transmitted (honest: no network here). A poster that raises is
    swallowed best-effort (like `notify.py`) and the ticket is marked not-transmitted."""

    def __init__(self, poster: Optional[Callable[[dict[str, Any]], Optional[str]]] = None):
        self._poster = poster
        self._tickets: list[dict[str, Any]] = []

    def create_ticket(self, issue: dict[str, Any]) -> dict[str, Any]:
        payload = github_issue_payload(issue)
        ticket_id: Optional[str] = None
        transmitted = False
        if self._poster is not None:
            try:
                ticket_id = self._poster(payload)
                transmitted = ticket_id is not None
            except Exception:
                transmitted = False  # best-effort, like notify.py — never crash the loop
        ticket = {"ticket_id": ticket_id, "payload": payload, "issue": issue,
                  "state": "open", "transmitted": transmitted}
        self._tickets.append(ticket)
        return ticket

    def list_tickets(self) -> list[dict[str, Any]]:
        return list(self._tickets)
