#!/usr/bin/env python3
"""Best-effort per-project email notifier for the architect-team plugin.

Invoked as a path-addressed script during a pipeline run
(`python ".../scripts/notify/notify.py" <event> [options]`), exactly like
scripts/setup/setup.py. It reads an opt-in per-project recipient config
(`.architect-team-notify.json`), renders an event email, and sends it through
the configured provider — Gmail (SMTP) or SendGrid (HTTP API).

Design guarantees (per openspec change `project-email-notifications`):
  * Opt-in: with no config file the notifier is a silent no-op.
  * Best-effort: every failure path — missing config, missing secret, provider
    error, network error, malformed input — is caught and yields exit code 0.
    A notification failure can never block, fail, or alter a pipeline run.
  * Stdlib-only: zero third-party dependencies (smtplib/urllib transport).
  * Secrets via env-var indirection: the config names the environment variable
    holding the provider secret; the value is read at send time and never
    written into the config file or any logged/printed line.

Events (exactly ten): run_start, phase_start, phase_complete,
waiting_on_agents, agents_complete, issue_discovered, git_commit, deploy,
run_complete, heartbeat. The v3.10.0 `heartbeat` event (R6c) carries an
unbounded-run liveness signal — the run id, current phase, elapsed time, and
the QA-cycle / agents-dispatched counts — emitted during long phases and at
post-first-hour phase boundaries. The v3.34.0 quartet (informative run
notifications) adds the run-level bookends and the dispatch-wait pair:
`run_start` fires once per run at the moment the architecture + solution plan
first exists and embeds the plan artifacts themselves (repeatable
`--plan-file`) so stakeholders receive the plan in ONE email; `run_complete`
is the run's final notification; `waiting_on_agents` / `agents_complete`
bracket every dispatch-and-wait point with the agent roster (`--agents`).
Every event additionally renders the universal informative blocks when
provided — `--details` (what is about to happen / what was accomplished),
`--progress` (where the run stands), `--next-step` (what happens next) — so
an email is a meaningful update, not a bare status line. All ten honor the
identical opt-in/best-effort contract; none gates, blocks, or caps a run.

Exit:
  Always 0. main() catches every exception (including argparse SystemExit).
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import ssl
import sys
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path
from typing import Iterable


# ---- Constants ---------------------------------------------------------------

CONFIG_FILENAME = ".architect-team-notify.json"

EVENT_TYPES = (
    "run_start",  # v3.34.0 — run kickoff: architecture + solution plan in ONE email.
    "phase_start",
    "phase_complete",
    "waiting_on_agents",  # v3.34.0 — the Lead dispatched agents and is waiting.
    "agents_complete",  # v3.34.0 — every dispatched agent has returned.
    "issue_discovered",
    "git_commit",
    "deploy",
    "run_complete",  # v3.34.0 — the run finished end-to-end (final notification).
    "heartbeat",  # v3.10.0 (R6c) — unbounded-run liveness signal.
)
ALL_EVENTS = "all"

# Bounds for the run_start plan embedding (--plan-file). Each embedded artifact
# is capped so a huge design doc cannot balloon the email; extra files beyond
# the count cap are acknowledged with an omission note rather than embedded.
PLAN_FILE_MAX_CHARS = 20_000
MAX_PLAN_FILES = 8

VALID_PROVIDERS = ("gmail", "sendgrid")

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 587
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"

# Bounded socket timeout (seconds) — a send must fail fast, never hang a phase.
SOCKET_TIMEOUT = 15


# ---- Errors ------------------------------------------------------------------


class NotifyError(Exception):
    """An expected, recoverable notifier failure.

    Raised for malformed config, missing secrets, and provider/transport
    errors. The CLI catches it, writes one stderr line, and exits 0 — it never
    propagates into a pipeline run.
    """


# ---- Config ------------------------------------------------------------------


def find_config(explicit: str | None, cwd: Path | None = None) -> Path | None:
    """Resolve the notifier config path.

    Args:
        explicit: the value of ``--config``, or None.
        cwd: directory to search for the default-named file (defaults to the
            real process cwd).

    Returns:
        * The explicit path as a Path when ``--config`` was supplied (returned
          even if it does not exist — the caller distinguishes an explicitly
          requested-but-missing file from a default-location miss).
        * The default-located ``.architect-team-notify.json`` Path when it
          exists in ``cwd``.
        * None when no ``--config`` was given and no default-located file
          exists — this drives the silent no-op.
    """
    if explicit is not None:
        return Path(explicit)
    base = Path(cwd) if cwd is not None else Path.cwd()
    candidate = base / CONFIG_FILENAME
    return candidate if candidate.is_file() else None


def load_config(path: Path) -> dict:
    """Read and JSON-parse the config file.

    Raises:
        NotifyError: the file is missing or is not valid JSON.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise NotifyError(f"cannot read notifier config at {path}: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NotifyError(f"notifier config at {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise NotifyError(f"notifier config at {path} must be a JSON object")
    return data


def _require_str(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise NotifyError(f"notifier config: required field '{key}' is missing or empty")
    return value


def validate_config(raw: dict) -> dict:
    """Validate the config schema and return it unchanged on success.

    Required: ``provider`` (one of VALID_PROVIDERS), ``from_address``, and a
    non-empty ``recipients`` array in which each entry has a string ``email``
    and a non-empty list ``events``. Optional: ``from_name``, and the
    provider-settings objects ``gmail`` / ``sendgrid``.

    Raises:
        NotifyError: any required field is missing, mistyped, or invalid.
    """
    if not isinstance(raw, dict):
        raise NotifyError("notifier config must be a JSON object")

    provider = _require_str(raw, "provider")
    if provider not in VALID_PROVIDERS:
        raise NotifyError(
            f"notifier config: provider '{provider}' is not supported "
            f"(expected one of {', '.join(VALID_PROVIDERS)})"
        )

    _require_str(raw, "from_address")

    if "from_name" in raw and not isinstance(raw["from_name"], str):
        raise NotifyError("notifier config: 'from_name' must be a string")

    recipients = raw.get("recipients")
    if not isinstance(recipients, list) or not recipients:
        raise NotifyError("notifier config: 'recipients' must be a non-empty array")

    for index, recipient in enumerate(recipients):
        if not isinstance(recipient, dict):
            raise NotifyError(f"notifier config: recipients[{index}] must be an object")
        email = recipient.get("email")
        if not isinstance(email, str) or not email.strip():
            raise NotifyError(
                f"notifier config: recipients[{index}] is missing a valid 'email'"
            )
        events = recipient.get("events")
        if not isinstance(events, list) or not events:
            raise NotifyError(
                f"notifier config: recipients[{index}] needs a non-empty 'events' array"
            )
        for event in events:
            if event != ALL_EVENTS and event not in EVENT_TYPES:
                raise NotifyError(
                    f"notifier config: recipients[{index}] subscribes to unknown "
                    f"event '{event}'"
                )

    settings = raw.get(provider)
    if settings is not None and not isinstance(settings, dict):
        raise NotifyError(f"notifier config: '{provider}' settings must be an object")

    return raw


# ---- Secret resolution -------------------------------------------------------


def _resolve_secret(env_var_name: str) -> str:
    """Read a provider secret from the named environment variable.

    This is the ONLY place a provider secret is read. The returned value is
    never interpolated into a logged or printed string anywhere in this module.

    Raises:
        NotifyError: the variable is unset or empty. The message names the
            variable but never includes a secret value.
    """
    value = os.environ.get(env_var_name)
    if not value:
        raise NotifyError(
            f"provider secret environment variable '{env_var_name}' is not set; "
            f"skipping email send"
        )
    return value


# ---- Providers ---------------------------------------------------------------


class EmailProvider:
    """Shared base for the concrete email providers.

    Holds the validated config and a small set of sender-identity helpers.
    It deliberately does NOT declare an abstract ``send`` — each concrete
    provider (GmailProvider, SendGridProvider) defines its own, and
    ``select_provider`` is the sole dispatch point.
    """

    def __init__(self, config: dict) -> None:
        self.config = config

    @property
    def from_address(self) -> str:
        return self.config["from_address"]

    @property
    def from_name(self) -> str | None:
        name = self.config.get("from_name")
        return name if isinstance(name, str) and name.strip() else None

    def _from_header(self) -> str:
        """Render the RFC-822 From header value, with an optional display name."""
        name = self.from_name
        return f"{name} <{self.from_address}>" if name else self.from_address

    def _settings(self, provider_key: str) -> dict:
        settings = self.config.get(provider_key)
        return settings if isinstance(settings, dict) else {}


class GmailProvider(EmailProvider):
    """Send email through Gmail's SMTP endpoint over STARTTLS."""

    def build_message(
        self, subject: str, body: str, recipients: list[str]
    ) -> EmailMessage:
        """Build an RFC-822 message — From / To / Subject + plain-text content."""
        message = EmailMessage()
        message["From"] = self._from_header()
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
        return message

    def send(self, subject: str, body: str, recipients: list[str]) -> None:
        """Build the message and transmit it via smtp.gmail.com over STARTTLS.

        Raises:
            NotifyError: the app-password env var is unset, or the SMTP
                transport fails (auth, connection, send).
        """
        settings = self._settings("gmail")
        username = settings.get("username") or self.from_address
        app_password_env = settings.get("app_password_env")
        if not isinstance(app_password_env, str) or not app_password_env.strip():
            raise NotifyError(
                "notifier config: gmail.app_password_env must name an "
                "environment variable"
            )
        app_password = _resolve_secret(app_password_env)

        message = self.build_message(subject, body, recipients)
        try:
            with smtplib.SMTP(GMAIL_HOST, GMAIL_PORT, timeout=SOCKET_TIMEOUT) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
                smtp.login(username, app_password)
                smtp.send_message(message)
        except (smtplib.SMTPException, OSError) as exc:
            # Never let a secret reach the message: report the exception TYPE,
            # not str(exc) (an SMTP error string can echo the credential back).
            raise NotifyError(
                f"Gmail send failed ({type(exc).__name__})"
            ) from exc


class SendGridProvider(EmailProvider):
    """Send email through the SendGrid v3 mail-send HTTP API."""

    def build_payload(
        self, subject: str, body: str, recipients: list[str]
    ) -> dict:
        """Build the SendGrid v3 mail-send JSON body."""
        sender: dict[str, str] = {"email": self.from_address}
        name = self.from_name
        if name:
            sender["name"] = name
        return {
            "personalizations": [
                {"to": [{"email": address} for address in recipients]}
            ],
            "from": sender,
            "subject": subject,
            "content": [{"type": "text/plain", "value": body}],
        }

    def send(self, subject: str, body: str, recipients: list[str]) -> None:
        """Build the payload and POST it to the SendGrid mail-send endpoint.

        Raises:
            NotifyError: the API-key env var is unset, or the HTTP request
                fails (network error, non-2xx response).
        """
        settings = self._settings("sendgrid")
        api_key_env = settings.get("api_key_env")
        if not isinstance(api_key_env, str) or not api_key_env.strip():
            raise NotifyError(
                "notifier config: sendgrid.api_key_env must name an "
                "environment variable"
            )
        api_key = _resolve_secret(api_key_env)

        payload = self.build_payload(subject, body, recipients)
        request = urllib.request.Request(
            SENDGRID_URL,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT) as response:
                status = getattr(response, "status", None)
                if status is not None and not 200 <= status < 300:
                    raise NotifyError(
                        f"SendGrid API returned HTTP {status}"
                    )
        except urllib.error.HTTPError as exc:
            # Report the status code only — never the response body, which
            # could be reflected request content.
            raise NotifyError(f"SendGrid API returned HTTP {exc.code}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise NotifyError(
                f"SendGrid send failed ({type(exc).__name__})"
            ) from exc


def select_provider(config: dict) -> EmailProvider:
    """Construct the provider implementation named by ``config['provider']``.

    This is the sole provider-dispatch point.

    Raises:
        NotifyError: the provider value is not one of VALID_PROVIDERS.
    """
    provider = config.get("provider")
    if provider == "gmail":
        return GmailProvider(config)
    if provider == "sendgrid":
        return SendGridProvider(config)
    raise NotifyError(f"notifier config: unknown provider '{provider}'")


# ---- Events ------------------------------------------------------------------


def _project_label(context: dict) -> str:
    project = context.get("project")
    return str(project) if project else "the project"


def _read_plan_file(path_str: str) -> tuple[str, str]:
    """Read one ``--plan-file`` artifact for embedding.

    Returns ``(label, content)`` where content is the file text capped at
    PLAN_FILE_MAX_CHARS (with an explicit truncation marker), or a one-line
    could-not-be-read note. Never raises — a missing or unreadable plan file
    degrades to the note, honoring the best-effort contract.
    """
    path = Path(path_str)
    label = path.name or path_str
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return label, f"(plan file could not be read: {path_str})"
    if len(text) > PLAN_FILE_MAX_CHARS:
        text = text[:PLAN_FILE_MAX_CHARS] + "\n... [truncated for email]"
    return label, text


def render_plan_section(plan_files: Iterable[str]) -> str:
    """Render the embedded architecture-and-solution-plan block.

    Each ``--plan-file`` artifact (proposal.md / design.md / tasks.md / a fix
    proposal / a flow catalog) is embedded under its own filename header so the
    run_start email carries the actual plan, not a pointer to it. At most
    MAX_PLAN_FILES files are embedded; extras are acknowledged with an
    omission note. Returns "" when no plan files were provided.
    """
    paths = [str(p) for p in (plan_files or []) if p]
    if not paths:
        return ""
    lines = ["", "=== Architecture & solution plan ==="]
    for path_str in paths[:MAX_PLAN_FILES]:
        label, content = _read_plan_file(path_str)
        lines.append("")
        lines.append(f"--- {label} ---")
        lines.append(content.rstrip("\n"))
    omitted = len(paths) - MAX_PLAN_FILES
    if omitted > 0:
        lines.append("")
        lines.append(f"(... {omitted} additional plan file(s) omitted)")
    lines.append("")
    return "\n".join(lines)


def _context_trailer(context: dict) -> str:
    """Render the universal informative blocks every event body may carry.

    The v3.34.0 informative-content contract: an email should be a meaningful
    update, not a bare status line. When the orchestrator passes them, every
    event appends ``--details`` (what is about to happen / what was
    accomplished), ``--progress`` (where the run stands), and ``--next-step``
    (what happens next). Each block is omitted when absent.
    """
    parts: list[str] = []
    details = context.get("details")
    progress = context.get("progress")
    next_step = context.get("next_step")
    if details:
        parts.append(f"\nDetails:\n{details}\n")
    if progress:
        parts.append(f"\nWhere the run stands:\n{progress}\n")
    if next_step:
        parts.append(f"\nUp next:\n{next_step}\n")
    return "".join(parts)


def render_email(event: str, context: dict) -> tuple[str, str]:
    """Render the (subject, body) for an event from its context.

    Each event's subject and body embed the relevant context: the phase name
    for phase events, the commit SHA for git_commit, the issue summary for
    issue_discovered, the deploy layer for deploy, the agent roster for
    waiting_on_agents / agents_complete, the embedded plan artifacts for
    run_start, the run-id / elapsed / final-commit fields for run_complete,
    and the run-id / phase / elapsed / QA-cycle / agents-dispatched liveness
    fields for heartbeat. Every event additionally appends the universal
    informative blocks (details / progress / next-step) and the embedded plan
    section when the corresponding context fields are provided.

    Raises:
        NotifyError: the event is not one of the ten recognized types.
    """
    if event not in EVENT_TYPES:
        raise NotifyError(
            f"unknown event type '{event}' "
            f"(expected one of {', '.join(EVENT_TYPES)})"
        )

    project = _project_label(context)
    phase = context.get("phase") or "an unnamed phase"
    summary = context.get("summary") or "(no summary provided)"
    commit = context.get("commit") or "(unknown commit)"
    layer = context.get("layer") or "(unspecified layer)"
    agents = context.get("agents") or "(agent roster not provided)"
    run_id = context.get("run_id") or "(unknown run)"

    if event == "run_start":
        subject = f"[{project}] Run started — architecture & solution plan"
        body = (
            f"The architect-team run for {project} has kicked off.\n\n"
            f"Run: {run_id}\n"
        )
    elif event == "phase_start":
        subject = f"[{project}] {phase} started"
        body = (
            f"The architect-team pipeline for {project} has started {phase}.\n"
        )
    elif event == "phase_complete":
        subject = f"[{project}] {phase} complete"
        body = (
            f"The architect-team pipeline for {project} has completed {phase}.\n"
        )
    elif event == "waiting_on_agents":
        subject = f"[{project}] Waiting on agents — {phase}"
        body = (
            f"The architect-team run for {project} has dispatched agents "
            f"during {phase} and is now waiting on their results.\n\n"
            f"Waiting on: {agents}\n"
        )
    elif event == "agents_complete":
        subject = f"[{project}] Agents complete — {phase}"
        body = (
            f"Every agent dispatched during {phase} of the architect-team run "
            f"for {project} has returned.\n\n"
            f"Agents: {agents}\n"
        )
    elif event == "issue_discovered":
        subject = f"[{project}] Issue discovered"
        body = (
            f"An issue was discovered during the architect-team run for "
            f"{project}.\n\nSummary: {summary}\n"
        )
    elif event == "git_commit":
        subject = f"[{project}] Commit {commit}"
        body = (
            f"The architect-team pipeline for {project} created a git commit.\n\n"
            f"Commit: {commit}\n"
        )
    elif event == "deploy":
        subject = f"[{project}] Deploy ({layer})"
        body = (
            f"A deploy occurred during the architect-team run for {project}.\n\n"
            f"Layer: {layer}\n"
        )
    elif event == "run_complete":
        subject = f"[{project}] Run complete"
        body = (
            f"The architect-team run for {project} has completed "
            f"end-to-end.\n\n"
            f"Run: {run_id}\n"
        )
        elapsed = context.get("elapsed")
        if elapsed:
            body += f"Elapsed: {elapsed}\n"
        final_commit = context.get("commit")
        if final_commit:
            body += f"Final commit: {final_commit}\n"
    else:  # heartbeat
        elapsed = context.get("elapsed") or "(unknown elapsed)"
        qa_cycles = context.get("qa_cycles")
        agents_dispatched = context.get("agents_dispatched")
        qa_cycles_text = qa_cycles if qa_cycles is not None else "(unknown)"
        agents_text = (
            agents_dispatched if agents_dispatched is not None else "(unknown)"
        )
        subject = f"[{project}] Heartbeat — {phase}"
        body = (
            f"The architect-team run for {project} is alive and working.\n\n"
            f"Run: {run_id}\n"
            f"Phase: {phase}\n"
            f"Elapsed: {elapsed}\n"
            f"QA / dev-loop cycles: {qa_cycles_text}\n"
            f"Agents dispatched: {agents_text}\n"
        )

    body += _context_trailer(context)
    body += render_plan_section(context.get("plan_files") or [])

    return subject, body


def filter_recipients(recipients: Iterable[dict], event: str) -> list[dict]:
    """Select recipients subscribed to ``event``.

    A recipient matches when its ``events`` array contains the event type or
    the ``"all"`` shorthand.
    """
    matched: list[dict] = []
    for recipient in recipients:
        events = recipient.get("events") or []
        if ALL_EVENTS in events or event in events:
            matched.append(recipient)
    return matched


def dispatch(config: dict, event: str, context: dict) -> int:
    """Render and send ``event`` to every subscribed recipient.

    Returns:
        The number of recipients emailed (0 when none are subscribed).

    Raises:
        NotifyError: the event is unknown, or the provider send fails.
    """
    if event not in EVENT_TYPES:
        raise NotifyError(
            f"unknown event type '{event}' "
            f"(expected one of {', '.join(EVENT_TYPES)})"
        )

    matched = filter_recipients(config.get("recipients", []), event)
    if not matched:
        return 0

    subject, body = render_email(event, context)
    provider = select_provider(config)
    provider.send(subject, body, [recipient["email"] for recipient in matched])
    return len(matched)


# ---- CLI ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the notifier CLI."""
    parser = argparse.ArgumentParser(
        prog="notify.py",
        description="Best-effort architect-team project email notifier.",
    )
    parser.add_argument(
        "event",
        choices=EVENT_TYPES,
        help="the notification event type",
    )
    parser.add_argument("--project", help="the project name")
    parser.add_argument("--phase", help="the pipeline phase name")
    parser.add_argument("--summary", help="an issue summary (for issue_discovered)")
    parser.add_argument(
        "--commit", help="a git commit SHA (for git_commit / run_complete)"
    )
    parser.add_argument("--layer", help="a deploy layer, e.g. backend (for deploy)")
    # Universal informative blocks (v3.34.0). Optional on every event; each is
    # rendered as its own body block when provided and omitted when absent.
    parser.add_argument(
        "--details",
        help="meaningful detail block — what is about to happen / what was "
        "accomplished (rendered on every event)",
    )
    parser.add_argument(
        "--progress",
        help="where the run stands, e.g. '4 of 12 phases complete — ...' "
        "(rendered on every event)",
    )
    parser.add_argument(
        "--next-step",
        help="what happens next (rendered on every event)",
    )
    parser.add_argument(
        "--agents",
        help="the dispatched-agent roster with per-agent missions/outcomes "
        "(for waiting_on_agents / agents_complete)",
    )
    parser.add_argument(
        "--plan-file",
        action="append",
        dest="plan_files",
        metavar="PATH",
        help="path to a plan artifact (proposal.md / design.md / tasks.md) "
        "embedded verbatim in the email body; repeatable (for run_start)",
    )
    # Heartbeat context (v3.10.0, R6c). Optional everywhere; only the heartbeat
    # event renders them, and each gracefully degrades when omitted.
    parser.add_argument("--run-id", help="the run id (for heartbeat)")
    parser.add_argument(
        "--elapsed", help="elapsed time since run start (for heartbeat)"
    )
    parser.add_argument(
        "--qa-cycles", help="QA / dev-loop cycle count (for heartbeat)"
    )
    parser.add_argument(
        "--agents-dispatched", help="agents-dispatched count (for heartbeat)"
    )
    parser.add_argument(
        "--config",
        help=f"path to the notifier config (default: ./{CONFIG_FILENAME})",
    )
    return parser


def _context_from_args(args: argparse.Namespace) -> dict:
    return {
        "project": args.project,
        "phase": args.phase,
        "summary": args.summary,
        "commit": args.commit,
        "layer": args.layer,
        "run_id": getattr(args, "run_id", None),
        "elapsed": getattr(args, "elapsed", None),
        "qa_cycles": getattr(args, "qa_cycles", None),
        "agents_dispatched": getattr(args, "agents_dispatched", None),
        # v3.34.0 — informative run notifications.
        "details": getattr(args, "details", None),
        "progress": getattr(args, "progress", None),
        "next_step": getattr(args, "next_step", None),
        "agents": getattr(args, "agents", None),
        "plan_files": getattr(args, "plan_files", None),
    }


def notify(argv: list[str], cwd: Path | None = None) -> int:
    """Programmatic notifier entry point — parses ``argv`` and dispatches.

    This is the importable counterpart to the CLI: tests and the orchestrator
    can drive it directly. It resolves the config, renders the event, and
    sends it. A NotifyError (malformed config, missing secret, provider error)
    is caught here, reported as a single stderr warning, and yields 0.

    Behavioral rules:
      * No ``--config`` and no default-located config file -> silent no-op
        (exit 0, no output).
      * An explicit ``--config`` path that does not exist -> one-line stderr
        warning, exit 0.
      * A valid config with zero subscribed recipients -> one concise
        informational stderr line, exit 0.

    Returns:
        Always 0 — a notification failure never propagates.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse raises SystemExit on a bad/unknown argument (including an
        # event type outside EVENT_TYPES). A usage message was already written
        # to stderr; isolate the failure here so a direct caller of notify()
        # never sees a non-zero exit. This is the programmatic entry point, so
        # the unknown-event scenario must terminate here with exit 0.
        if exc.code not in (0, None):
            print(
                "notify: warning: invalid arguments; no notification sent",
                file=sys.stderr,
            )
        return 0

    try:
        config_path = find_config(args.config, cwd=cwd)

        if config_path is None:
            # No --config and no default-located file: opt-out, stay silent.
            return 0

        if args.config is not None and not config_path.is_file():
            # An explicit path was requested but is absent: warn, do not crash.
            raise NotifyError(
                f"notifier config '{config_path}' was specified but does not exist"
            )

        raw = load_config(config_path)
        config = validate_config(raw)

        context = _context_from_args(args)
        sent = dispatch(config, args.event, context)
        if sent == 0:
            print(
                f"notify: no recipients subscribed to '{args.event}'; "
                f"nothing sent",
                file=sys.stderr,
            )
    except NotifyError as exc:
        print(f"notify: warning: {exc}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Catches EVERY exception and always returns 0.

    A notification failure — malformed config, missing secret, provider error,
    network error, or invalid CLI arguments (argparse raises SystemExit) — must
    never block or fail a pipeline run.
    """
    # Ensure Unicode output works on Windows consoles (cp1252 default).
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - best-effort console tweak
            pass

    args = sys.argv[1:] if argv is None else argv
    try:
        return notify(list(args))
    except SystemExit as exc:
        # argparse exits the process on bad arguments — swallow it. A usage
        # message was already written to stderr by argparse.
        if exc.code not in (0, None):
            print(
                "notify: warning: invalid arguments; no notification sent",
                file=sys.stderr,
            )
        return 0
    except Exception as exc:  # noqa: BLE001 - best-effort: nothing may escape
        print(f"notify: warning: unexpected error ({type(exc).__name__})", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
