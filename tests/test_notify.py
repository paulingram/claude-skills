"""Unit + structural tests for scripts/notify/notify.py — the project email notifier.

The notifier lives outside the package layout (it is a path-addressed script,
exactly like scripts/setup/setup.py), so it is loaded directly via importlib and
the shared `plugin_root` conftest fixture. Only the two genuinely external,
non-deterministic transports are mocked — `smtplib.SMTP` and
`urllib.request.urlopen`. Every other layer (config parse/validate, recipient
filtering, message rendering, secret resolution, error handling, the CLI) runs
for real.

Coverage maps 1:1 to the scenarios in
openspec/changes/project-email-notifications/specs/project-email-notifications/spec.md
for requirements REQ-001..REQ-004 and the REQ-006 structural scenarios.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# --- module loading -----------------------------------------------------------


@pytest.fixture(scope="module")
def notify(plugin_root: Path) -> ModuleType:
    """Load scripts/notify/notify.py directly (it is out-of-package, like setup.py)."""
    path = plugin_root / "scripts" / "notify" / "notify.py"
    assert path.exists(), f"notify.py missing at {path}"
    spec = importlib.util.spec_from_file_location("notify_module", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def notify_path(plugin_root: Path) -> Path:
    return plugin_root / "scripts" / "notify" / "notify.py"


# --- config builders ----------------------------------------------------------


def _gmail_config() -> dict:
    return {
        "provider": "gmail",
        "from_address": "ci@example.com",
        "from_name": "Architect CI",
        "gmail": {"username": "ci@example.com", "app_password_env": "GMAIL_APP_PASSWORD"},
        "recipients": [
            {"email": "lead@example.com", "events": ["all"]},
            {"email": "qa@example.com", "events": ["phase_complete", "deploy"]},
        ],
    }


def _sendgrid_config() -> dict:
    return {
        "provider": "sendgrid",
        "from_address": "ci@example.com",
        "from_name": "Architect CI",
        "sendgrid": {"api_key_env": "SENDGRID_API_KEY"},
        "recipients": [
            {"email": "lead@example.com", "events": ["all"]},
        ],
    }


def _write_config(directory: Path, raw: dict) -> Path:
    path = directory / ".architect-team-notify.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


# =============================================================================
# REQ-001 — Per-project recipient configuration
# =============================================================================


def test_valid_config_is_loaded(notify: ModuleType, tmp_path: Path) -> None:
    """Scenario: Valid config is loaded."""
    path = _write_config(tmp_path, _gmail_config())
    cfg = notify.load_config(path)
    cfg = notify.validate_config(cfg)
    assert cfg["provider"] == "gmail"
    assert cfg["from_address"] == "ci@example.com"
    assert cfg["from_name"] == "Architect CI"
    assert len(cfg["recipients"]) == 2
    assert cfg["recipients"][0]["events"] == ["all"]
    assert cfg["recipients"][1]["events"] == ["phase_complete", "deploy"]


def test_find_config_locates_default_in_cwd(notify: ModuleType, tmp_path: Path) -> None:
    """find_config with no explicit path resolves the default-named file in cwd."""
    path = _write_config(tmp_path, _gmail_config())
    found = notify.find_config(None, cwd=tmp_path)
    assert found == path


def test_find_config_returns_none_when_absent(notify: ModuleType, tmp_path: Path) -> None:
    """find_config returns None when no default-located file exists (drives the no-op)."""
    assert notify.find_config(None, cwd=tmp_path) is None


def test_find_config_uses_explicit_path(notify: ModuleType, tmp_path: Path) -> None:
    """An explicit --config path is honoured verbatim."""
    explicit = tmp_path / "custom-notify.json"
    explicit.write_text(json.dumps(_gmail_config()), encoding="utf-8")
    assert notify.find_config(str(explicit), cwd=tmp_path) == explicit


def test_absent_config_is_silent_noop(notify: ModuleType, tmp_path: Path, capsys) -> None:
    """Scenario: Absent config is a silent no-op — exit 0, NO stderr output."""
    rc = notify.notify(["phase_start", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""


def test_malformed_config_invalid_json_warns_and_exits_zero(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Malformed config (invalid JSON) does not break the run."""
    (tmp_path / ".architect-team-notify.json").write_text("{not json", encoding="utf-8")
    rc = notify.notify(["phase_start", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().err.strip() != ""


def test_malformed_config_missing_required_field_warns(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Malformed config (missing required field) does not break the run."""
    bad = _gmail_config()
    del bad["from_address"]
    _write_config(tmp_path, bad)
    rc = notify.notify(["phase_start", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert "from_address" in err


def test_validate_config_rejects_unknown_provider(notify: ModuleType) -> None:
    """A provider outside the known set is a NotifyError."""
    bad = _gmail_config()
    bad["provider"] = "mailchimp"
    with pytest.raises(notify.NotifyError):
        notify.validate_config(bad)


def test_validate_config_rejects_empty_recipients(notify: ModuleType) -> None:
    """An empty recipients[] is a NotifyError."""
    bad = _gmail_config()
    bad["recipients"] = []
    with pytest.raises(notify.NotifyError):
        notify.validate_config(bad)


def test_validate_config_rejects_recipient_without_email(notify: ModuleType) -> None:
    """A recipient missing `email` is a NotifyError."""
    bad = _gmail_config()
    bad["recipients"] = [{"events": ["all"]}]
    with pytest.raises(notify.NotifyError):
        notify.validate_config(bad)


def test_validate_config_rejects_recipient_without_events(notify: ModuleType) -> None:
    """A recipient missing `events` is a NotifyError."""
    bad = _gmail_config()
    bad["recipients"] = [{"email": "x@example.com"}]
    with pytest.raises(notify.NotifyError):
        notify.validate_config(bad)


def test_shipped_example_config_is_valid(notify: ModuleType, plugin_root: Path) -> None:
    """Scenario: Shipped example config is itself valid — parses + passes validate_config."""
    example = plugin_root / ".architect-team-notify.example.json"
    assert example.exists(), "example config must ship at the repo root"
    raw = json.loads(example.read_text(encoding="utf-8"))
    validated = notify.validate_config(raw)
    assert validated["provider"] in notify.VALID_PROVIDERS
    assert validated["from_address"]
    assert len(validated["recipients"]) >= 2


def test_shipped_example_has_both_provider_blocks_and_differing_events(
    plugin_root: Path,
) -> None:
    """The example carries BOTH a gmail and a sendgrid block + two recipients
    with differing `events` (one ["all"], one a custom subset)."""
    raw = json.loads(
        (plugin_root / ".architect-team-notify.example.json").read_text(encoding="utf-8")
    )
    assert "gmail" in raw and "sendgrid" in raw
    events_lists = [r["events"] for r in raw["recipients"]]
    assert ["all"] in events_lists
    assert any(ev != ["all"] for ev in events_lists)


def test_shipped_example_env_values_are_names_not_secrets(plugin_root: Path) -> None:
    """The *_env fields hold env-var NAMES (upper-snake identifiers), never secrets."""
    raw = json.loads(
        (plugin_root / ".architect-team-notify.example.json").read_text(encoding="utf-8")
    )
    app_pw_env = raw["gmail"]["app_password_env"]
    api_key_env = raw["sendgrid"]["api_key_env"]
    for name in (app_pw_env, api_key_env):
        assert name.replace("_", "").isalnum()
        assert name == name.upper()
        assert " " not in name


# =============================================================================
# REQ-002 — Email provider abstraction
# =============================================================================


def test_select_provider_dispatches_gmail(notify: ModuleType) -> None:
    """Scenario: provider selection driven by config — gmail."""
    provider = notify.select_provider(notify.validate_config(_gmail_config()))
    assert isinstance(provider, notify.GmailProvider)


def test_select_provider_dispatches_sendgrid(notify: ModuleType) -> None:
    """Scenario: provider selection driven by config — sendgrid."""
    provider = notify.select_provider(notify.validate_config(_sendgrid_config()))
    assert isinstance(provider, notify.SendGridProvider)


def test_gmail_build_message_structure(notify: ModuleType) -> None:
    """Gmail message is RFC-822 with configured sender, subject, body, recipients."""
    provider = notify.GmailProvider(notify.validate_config(_gmail_config()))
    msg = provider.build_message("A subject", "A body", ["a@example.com", "b@example.com"])
    assert msg["Subject"] == "A subject"
    assert "ci@example.com" in msg["From"]
    assert "a@example.com" in msg["To"]
    assert "b@example.com" in msg["To"]
    assert msg.get_content().strip() == "A body"


def test_gmail_send_uses_starttls_and_login(notify: ModuleType) -> None:
    """Scenario: Gmail provider builds an authenticated SMTP message over STARTTLS."""
    config = notify.validate_config(_gmail_config())
    provider = notify.GmailProvider(config)
    smtp_instance = MagicMock()
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_ctx.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_ctx) as m_smtp, \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "app-pw-secret"}, clear=False):
        provider.send("Subj", "Body", ["dest@example.com"])
    # connected to smtp.gmail.com:587
    args, kwargs = m_smtp.call_args
    assert args[0] == notify.GMAIL_HOST
    assert args[1] == notify.GMAIL_PORT
    smtp_instance.starttls.assert_called_once()
    smtp_instance.login.assert_called_once_with("ci@example.com", "app-pw-secret")
    smtp_instance.send_message.assert_called_once()


def test_sendgrid_build_payload_structure(notify: ModuleType) -> None:
    """Scenario: SendGrid v3 payload — personalizations, from, subject, content."""
    provider = notify.SendGridProvider(notify.validate_config(_sendgrid_config()))
    payload = provider.build_payload("Subj", "Body", ["x@example.com", "y@example.com"])
    assert payload["from"]["email"] == "ci@example.com"
    assert payload["from"]["name"] == "Architect CI"
    assert payload["subject"] == "Subj"
    assert payload["content"][0]["type"] == "text/plain"
    assert payload["content"][0]["value"] == "Body"
    to_emails = [t["email"] for t in payload["personalizations"][0]["to"]]
    assert to_emails == ["x@example.com", "y@example.com"]


def test_sendgrid_send_posts_with_bearer_auth(notify: ModuleType) -> None:
    """Scenario: SendGrid provider builds an authenticated API request."""
    config = notify.validate_config(_sendgrid_config())
    provider = notify.SendGridProvider(config)
    fake_resp = MagicMock()
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.status = 202
    with patch("urllib.request.urlopen", return_value=fake_resp) as m_open, \
         patch.dict("os.environ", {"SENDGRID_API_KEY": "sg-key-secret"}, clear=False):
        provider.send("Subj", "Body", ["dest@example.com"])
    req = m_open.call_args[0][0]
    assert req.full_url == notify.SENDGRID_URL
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer sg-key-secret"
    assert req.get_header("Content-type") == "application/json"
    body = json.loads(req.data.decode("utf-8"))
    assert body["subject"] == "Subj"


def test_missing_gmail_secret_skips_send_and_warns(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Missing provider secret is handled gracefully (gmail)."""
    _write_config(tmp_path, _gmail_config())
    with patch.dict("os.environ", {}, clear=True), \
         patch("smtplib.SMTP") as m_smtp:
        rc = notify.notify(
            ["phase_start", "--project", "Demo", "--phase", "Phase 1"], cwd=tmp_path
        )
    assert rc == 0
    m_smtp.assert_not_called()
    err = capsys.readouterr().err
    assert "GMAIL_APP_PASSWORD" in err


def test_missing_sendgrid_secret_skips_send_and_warns(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Missing provider secret is handled gracefully (sendgrid)."""
    _write_config(tmp_path, _sendgrid_config())
    with patch.dict("os.environ", {}, clear=True), \
         patch("urllib.request.urlopen") as m_open:
        rc = notify.notify(
            ["phase_start", "--project", "Demo", "--phase", "Phase 1"], cwd=tmp_path
        )
    assert rc == 0
    m_open.assert_not_called()
    assert "SENDGRID_API_KEY" in capsys.readouterr().err


def test_resolve_secret_raises_when_unset(notify: ModuleType) -> None:
    """_resolve_secret raises NotifyError for an unset variable."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(notify.NotifyError):
            notify._resolve_secret("DEFINITELY_UNSET_VAR_XYZ")


def test_resolve_secret_raises_when_empty(notify: ModuleType) -> None:
    """_resolve_secret raises NotifyError for an empty-string variable."""
    with patch.dict("os.environ", {"EMPTY_SECRET": ""}, clear=False):
        with pytest.raises(notify.NotifyError):
            notify._resolve_secret("EMPTY_SECRET")


def test_resolve_secret_returns_value_when_set(notify: ModuleType) -> None:
    """_resolve_secret returns the value when the variable is populated."""
    with patch.dict("os.environ", {"PRESENT_SECRET": "the-value"}, clear=False):
        assert notify._resolve_secret("PRESENT_SECRET") == "the-value"


def test_secret_value_never_disclosed_in_output(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Secret value is never disclosed.

    With a SENTINEL secret in the environment and the SMTP transport raising a
    realistic auth failure, the captured stdout+stderr must not contain the
    sentinel anywhere.
    """
    sentinel = "S3CR3T-SENTINEL-c0ffee-DO-NOT-LEAK"
    _write_config(tmp_path, _gmail_config())
    import smtplib

    smtp_instance = MagicMock()
    smtp_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad creds")
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_ctx.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_ctx), \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": sentinel}, clear=False):
        rc = notify.notify(
            ["phase_complete", "--project", "Demo", "--phase", "Phase 3"], cwd=tmp_path
        )
    assert rc == 0
    captured = capsys.readouterr()
    assert sentinel not in captured.out
    assert sentinel not in captured.err


def test_module_imports_only_standard_library(notify_path: Path) -> None:
    """REQ-002 acceptance: scripts/notify/notify.py imports ONLY the stdlib.

    Parses the module with `ast` and checks every top-level import root against
    sys.stdlib_module_names — zero third-party dependencies allowed.
    """
    tree = ast.parse(notify_path.read_text(encoding="utf-8"))
    stdlib = sys.stdlib_module_names
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    third_party = {r for r in roots if r not in stdlib}
    assert not third_party, f"non-stdlib imports found: {sorted(third_party)}"


def test_module_contains_no_notimplementederror_token(notify_path: Path) -> None:
    """Approved ruling 1: the NotImplementedError token must not appear at all."""
    source = notify_path.read_text(encoding="utf-8")
    assert "NotImplementedError" not in source


def test_provider_base_has_no_abstract_send(notify: ModuleType) -> None:
    """Approved ruling 1: the base EmailProvider defines no `send` (only concretes do)."""
    assert "send" not in notify.EmailProvider.__dict__
    assert "send" in notify.GmailProvider.__dict__
    assert "send" in notify.SendGridProvider.__dict__


# =============================================================================
# REQ-003 — Notification event types and per-recipient filtering
# =============================================================================


def test_exactly_ten_event_types(notify: ModuleType) -> None:
    """Scenario foundation: exactly the ten recognized event types.

    v3.10.0 (R6c) added the `heartbeat` unbounded-run liveness signal.
    v3.34.0 (informative run notifications) adds the run-level bookends
    (`run_start` — the kickoff email that embeds the architecture + solution
    plan; `run_complete` — the run's final notification) and the
    dispatch-wait pair (`waiting_on_agents` / `agents_complete`).
    """
    assert set(notify.EVENT_TYPES) == {
        "run_start",
        "phase_start",
        "phase_complete",
        "waiting_on_agents",
        "agents_complete",
        "issue_discovered",
        "git_commit",
        "deploy",
        "run_complete",
        "heartbeat",
    }
    assert len(notify.EVENT_TYPES) == 10


def test_event_reaches_only_subscribed_recipients(notify: ModuleType) -> None:
    """Scenario: Event reaches only subscribed recipients."""
    recipients = [
        {"email": "a@example.com", "events": ["phase_complete"]},
        {"email": "b@example.com", "events": ["phase_start", "phase_complete"]},
    ]
    matched = notify.filter_recipients(recipients, "phase_start")
    emails = [r["email"] for r in matched]
    assert emails == ["b@example.com"]


def test_all_shorthand_subscribes_to_every_event(notify: ModuleType) -> None:
    """Scenario: The "all" shorthand subscribes to every event."""
    recipients = [{"email": "everything@example.com", "events": ["all"]}]
    for event in notify.EVENT_TYPES:
        matched = notify.filter_recipients(recipients, event)
        assert [r["email"] for r in matched] == ["everything@example.com"], event


def test_unknown_event_rejected_without_sending(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Unknown event type is rejected without sending."""
    _write_config(tmp_path, _gmail_config())
    with patch("smtplib.SMTP") as m_smtp, \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}, clear=False):
        rc = notify.notify(["not_a_real_event", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    m_smtp.assert_not_called()
    assert capsys.readouterr().err.strip() != ""


def test_render_email_phase_start_includes_phase_name(notify: ModuleType) -> None:
    """Scenario: Event context appears in the email — phase name."""
    subject, body = notify.render_email(
        "phase_start", {"project": "Acme", "phase": "Phase 2"}
    )
    assert "Phase 2" in subject or "Phase 2" in body
    assert "Acme" in subject or "Acme" in body


def test_render_email_git_commit_includes_sha(notify: ModuleType) -> None:
    """Scenario: Event context appears in the email — commit SHA."""
    subject, body = notify.render_email(
        "git_commit", {"project": "Acme", "commit": "deadbeef1234"}
    )
    assert "deadbeef1234" in subject or "deadbeef1234" in body


def test_render_email_issue_discovered_includes_summary(notify: ModuleType) -> None:
    """Scenario: Event context appears in the email — issue summary."""
    subject, body = notify.render_email(
        "issue_discovered", {"project": "Acme", "summary": "auth contract regressed"}
    )
    assert "auth contract regressed" in body


def test_render_email_deploy_includes_layer(notify: ModuleType) -> None:
    """Scenario: Event context appears in the email — deploy layer."""
    subject, body = notify.render_email(
        "deploy", {"project": "Acme", "layer": "backend"}
    )
    assert "backend" in subject or "backend" in body


# =============================================================================
# v3.34.0 — Informative run notifications (run bookends, dispatch-wait pair,
# universal informative blocks, plan embedding)
# =============================================================================


def test_render_run_start_embeds_plan_files_in_one_email(
    notify: ModuleType, tmp_path: Path
) -> None:
    """The run_start email carries the architecture + solution plan ITSELF —
    every --plan-file artifact embedded under its own filename header, in the
    one kickoff email."""
    (tmp_path / "proposal.md").write_text("# Proposal\nBuild SSO login.", encoding="utf-8")
    (tmp_path / "design.md").write_text("# Design\nHexagonal architecture.", encoding="utf-8")
    subject, body = notify.render_email(
        "run_start",
        {
            "project": "Acme",
            "run_id": "run-42",
            "plan_files": [str(tmp_path / "proposal.md"), str(tmp_path / "design.md")],
        },
    )
    assert "Run started" in subject
    assert "run-42" in body
    assert "Architecture & solution plan" in body
    assert "proposal.md" in body and "Build SSO login." in body
    assert "design.md" in body and "Hexagonal architecture." in body


def test_render_run_start_truncates_oversized_plan_file(
    notify: ModuleType, tmp_path: Path
) -> None:
    """A plan artifact beyond PLAN_FILE_MAX_CHARS is embedded truncated, with
    an explicit truncation marker — a huge design doc cannot balloon the email."""
    big = tmp_path / "design.md"
    big.write_text("x" * (notify.PLAN_FILE_MAX_CHARS + 5000), encoding="utf-8")
    _, body = notify.render_email(
        "run_start", {"project": "Acme", "plan_files": [str(big)]}
    )
    assert "[truncated for email]" in body
    assert len(body) < notify.PLAN_FILE_MAX_CHARS + 2000


def test_render_run_start_missing_plan_file_degrades_to_note(
    notify: ModuleType, tmp_path: Path
) -> None:
    """A missing/unreadable --plan-file NEVER raises — it degrades to a
    one-line could-not-be-read note (best-effort contract)."""
    missing = tmp_path / "not-there.md"
    subject, body = notify.render_email(
        "run_start", {"project": "Acme", "plan_files": [str(missing)]}
    )
    assert "Run started" in subject
    assert "could not be read" in body
    assert str(missing) in body


def test_render_run_start_caps_plan_file_count(
    notify: ModuleType, tmp_path: Path
) -> None:
    """More than MAX_PLAN_FILES artifacts: the extras are acknowledged with an
    omission note rather than embedded."""
    paths = []
    for i in range(notify.MAX_PLAN_FILES + 2):
        p = tmp_path / f"part-{i}.md"
        p.write_text(f"content {i}", encoding="utf-8")
        paths.append(str(p))
    _, body = notify.render_email("run_start", {"project": "Acme", "plan_files": paths})
    assert f"part-{notify.MAX_PLAN_FILES - 1}.md" in body
    assert f"content {notify.MAX_PLAN_FILES}" not in body
    assert "additional plan file(s) omitted" in body


def test_render_waiting_on_agents_includes_roster_and_phase(
    notify: ModuleType,
) -> None:
    """waiting_on_agents names the phase and the per-agent roster so the
    reader knows exactly WHO is being waited on and WHAT each is doing."""
    subject, body = notify.render_email(
        "waiting_on_agents",
        {
            "project": "Acme",
            "phase": "Phase 3",
            "agents": "backend-auth — JWT middleware; frontend-dash — dashboard UI",
        },
    )
    assert "Waiting on agents" in subject
    assert "Phase 3" in subject or "Phase 3" in body
    assert "backend-auth" in body and "frontend-dash" in body


def test_render_agents_complete_includes_roster(notify: ModuleType) -> None:
    """agents_complete reports the dispatched agents (with outcomes) returned."""
    subject, body = notify.render_email(
        "agents_complete",
        {
            "project": "Acme",
            "phase": "Phase 3",
            "agents": "backend-auth — done (12 tests green); frontend-dash — done",
        },
    )
    assert "Agents complete" in subject
    assert "backend-auth" in body
    assert "12 tests green" in body


def test_render_run_complete_includes_run_elapsed_and_commit(
    notify: ModuleType,
) -> None:
    """run_complete carries the run id, elapsed time, and the final commit."""
    subject, body = notify.render_email(
        "run_complete",
        {"project": "Acme", "run_id": "run-42", "elapsed": "2h 14m", "commit": "abc1234"},
    )
    assert "Run complete" in subject
    assert "run-42" in body
    assert "2h 14m" in body
    assert "abc1234" in body


def test_render_run_complete_omits_absent_optional_lines(
    notify: ModuleType,
) -> None:
    """run_complete omits the Elapsed / Final commit lines when not provided
    (no '(unknown ...)' placeholder noise in the final email)."""
    _, body = notify.render_email("run_complete", {"project": "Acme", "run_id": "r-1"})
    assert "Elapsed:" not in body
    assert "Final commit:" not in body


@pytest.mark.parametrize("event", ["phase_start", "phase_complete", "heartbeat"])
def test_universal_informative_blocks_render_on_any_event(
    notify: ModuleType, event: str
) -> None:
    """The v3.34.0 informative-content contract: --details / --progress /
    --next-step render as their own body blocks on EVERY event."""
    _, body = notify.render_email(
        event,
        {
            "project": "Acme",
            "phase": "Phase 2",
            "details": "About to spawn 2 teams against the auth slice.",
            "progress": "4 of 12 phases complete",
            "next_step": "Phase 3 — implementation review gates",
        },
    )
    assert "Details:" in body and "About to spawn 2 teams" in body
    assert "Where the run stands:" in body and "4 of 12 phases complete" in body
    assert "Up next:" in body and "Phase 3" in body


def test_universal_informative_blocks_omitted_when_absent(
    notify: ModuleType,
) -> None:
    """Without the informative flags, the legacy bodies render without the
    Details / Where-the-run-stands / Up-next blocks (backward compatible)."""
    _, body = notify.render_email("phase_start", {"project": "Acme", "phase": "Phase 2"})
    assert "Details:" not in body
    assert "Where the run stands:" not in body
    assert "Up next:" not in body


def test_validate_config_accepts_new_event_subscriptions(notify: ModuleType) -> None:
    """A recipient may subscribe to the four v3.34.0 events without tripping
    the unknown-event validation guard."""
    config = _gmail_config()
    config["recipients"] = [
        {
            "email": "lead@example.com",
            "events": ["run_start", "waiting_on_agents", "agents_complete", "run_complete"],
        }
    ]
    validated = notify.validate_config(config)
    assert validated["recipients"][0]["events"][0] == "run_start"


def test_dispatch_run_start_sends_plan_carrying_body(
    notify: ModuleType, tmp_path: Path
) -> None:
    """End-to-end dispatch of run_start: the provider receives ONE email whose
    body embeds the plan artifact content."""
    plan = tmp_path / "proposal.md"
    plan.write_text("## Solution plan\nAdd SSO via OIDC.", encoding="utf-8")
    config = notify.validate_config(_gmail_config())
    captured: list[tuple[str, str, list[str]]] = []

    class _RecordingProvider:
        def send(self, subject, body, recipients):
            captured.append((subject, body, list(recipients)))

    with patch.object(notify, "select_provider", return_value=_RecordingProvider()):
        sent = notify.dispatch(
            config,
            "run_start",
            {"project": "Demo", "run_id": "r-9", "plan_files": [str(plan)]},
        )
    assert sent == 1  # only the ["all"] recipient subscribes to run_start
    assert len(captured) == 1
    subject, body, recipients = captured[0]
    assert recipients == ["lead@example.com"]
    assert "Add SSO via OIDC." in body


def test_cli_run_start_with_plan_file_via_gmail(
    notify: ModuleType, tmp_path: Path
) -> None:
    """CLI end-to-end: `notify.py run_start --plan-file ...` builds a message
    whose payload embeds the plan content."""
    _write_config(tmp_path, _gmail_config())
    plan = tmp_path / "design.md"
    plan.write_text("Component diagram: A -> B", encoding="utf-8")
    smtp_instance = MagicMock()
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_ctx.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_ctx), \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}, clear=False):
        rc = notify.notify(
            [
                "run_start",
                "--project", "Demo",
                "--run-id", "r-7",
                "--details", "Requirement: SSO login.",
                "--plan-file", str(plan),
            ],
            cwd=tmp_path,
        )
    assert rc == 0
    smtp_instance.send_message.assert_called_once()
    message = smtp_instance.send_message.call_args[0][0]
    content = message.get_content()
    assert "Component diagram: A -> B" in content
    assert "Requirement: SSO login." in content


def test_dispatch_emails_only_matching_recipients(notify: ModuleType) -> None:
    """dispatch() sends to exactly the filtered recipient set, one provider call."""
    config = notify.validate_config(_gmail_config())  # lead=all, qa=phase_complete+deploy
    sent: list[list[str]] = []

    class _RecordingProvider:
        def send(self, subject, body, recipients):
            sent.append(list(recipients))

    with patch.object(notify, "select_provider", return_value=_RecordingProvider()):
        notify.dispatch(config, "phase_start", {"project": "Demo", "phase": "P1"})
    # only the ["all"] recipient matches phase_start
    assert sent == [["lead@example.com"]]


def test_dispatch_no_matching_recipients_is_informational_noop(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Approved ruling 3: a valid config with zero matching recipients exits 0
    with ONE concise informational stderr line (distinct from no-config silence)."""
    config = {
        "provider": "gmail",
        "from_address": "ci@example.com",
        "gmail": {"username": "ci@example.com", "app_password_env": "GMAIL_APP_PASSWORD"},
        "recipients": [{"email": "narrow@example.com", "events": ["deploy"]}],
    }
    _write_config(tmp_path, config)
    with patch("smtplib.SMTP") as m_smtp, \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}, clear=False):
        rc = notify.notify(["phase_start", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    m_smtp.assert_not_called()
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert len(err.strip().splitlines()) == 1


# =============================================================================
# REQ-004 — Notifier CLI and best-effort failure isolation
# =============================================================================


def test_build_parser_accepts_all_options(notify: ModuleType) -> None:
    """build_parser exposes the positional event + every documented option."""
    parser = notify.build_parser()
    ns = parser.parse_args(
        [
            "deploy",
            "--project", "Demo",
            "--phase", "Phase 5",
            "--summary", "a summary",
            "--commit", "abc123",
            "--layer", "frontend",
            "--details", "what happened",
            "--progress", "5 of 12",
            "--next-step", "Phase 6",
            "--agents", "backend-auth; frontend-dash",
            "--config", "x.json",
        ]
    )
    assert ns.event == "deploy"
    assert ns.project == "Demo"
    assert ns.phase == "Phase 5"
    assert ns.summary == "a summary"
    assert ns.commit == "abc123"
    assert ns.layer == "frontend"
    assert ns.details == "what happened"
    assert ns.progress == "5 of 12"
    assert ns.next_step == "Phase 6"
    assert ns.agents == "backend-auth; frontend-dash"
    assert ns.config == "x.json"


def test_build_parser_plan_file_is_repeatable(notify: ModuleType) -> None:
    """--plan-file appends: the run_start kickoff email can embed proposal +
    design + tasks as one email."""
    parser = notify.build_parser()
    ns = parser.parse_args(
        ["run_start", "--plan-file", "proposal.md", "--plan-file", "design.md"]
    )
    assert ns.event == "run_start"
    assert ns.plan_files == ["proposal.md", "design.md"]
    # Absent flag -> None (renderer treats it as no plan section).
    ns2 = notify.build_parser().parse_args(["phase_start"])
    assert ns2.plan_files is None


def test_build_parser_rejects_unknown_event_choice(notify: ModuleType) -> None:
    """The positional event is constrained to choices=EVENT_TYPES."""
    parser = notify.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["not_an_event"])


def test_cli_successful_emission_via_gmail(
    notify: ModuleType, tmp_path: Path
) -> None:
    """Scenario: Successful event emission via the CLI."""
    _write_config(tmp_path, _gmail_config())
    smtp_instance = MagicMock()
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_ctx.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_ctx), \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}, clear=False):
        rc = notify.notify(
            ["phase_start", "--project", "Demo", "--phase", "Phase 2"], cwd=tmp_path
        )
    assert rc == 0
    smtp_instance.send_message.assert_called_once()


def test_cli_provider_error_never_escalates(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Scenario: Provider/network error never escalates."""
    _write_config(tmp_path, _gmail_config())
    smtp_instance = MagicMock()
    smtp_instance.send_message.side_effect = OSError("network down")
    smtp_ctx = MagicMock()
    smtp_ctx.__enter__ = MagicMock(return_value=smtp_instance)
    smtp_ctx.__exit__ = MagicMock(return_value=False)
    with patch("smtplib.SMTP", return_value=smtp_ctx), \
         patch.dict("os.environ", {"GMAIL_APP_PASSWORD": "pw"}, clear=False):
        rc = notify.notify(
            ["phase_start", "--project", "Demo", "--phase", "Phase 2"], cwd=tmp_path
        )
    assert rc == 0
    assert capsys.readouterr().err.strip() != ""


def test_cli_sendgrid_network_error_never_escalates(
    notify: ModuleType, tmp_path: Path
) -> None:
    """Scenario: Provider/network error never escalates — SendGrid HTTP path."""
    import urllib.error

    _write_config(tmp_path, _sendgrid_config())
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ), patch.dict("os.environ", {"SENDGRID_API_KEY": "key"}, clear=False):
        rc = notify.notify(
            ["deploy", "--project", "Demo", "--layer", "backend"], cwd=tmp_path
        )
    assert rc == 0


def test_main_invalid_arguments_exit_zero(notify: ModuleType, capsys) -> None:
    """Scenario: Invalid CLI arguments do not block the pipeline.

    argparse normally raises SystemExit(2); main() must swallow it and return 0.
    """
    rc = notify.main(["not_an_event"])
    assert rc == 0


def test_main_no_arguments_exit_zero(notify: ModuleType) -> None:
    """A bare invocation with no event still yields exit 0 (argparse error swallowed)."""
    assert notify.main([]) == 0


def test_main_returns_zero_on_unexpected_internal_error(
    notify: ModuleType, tmp_path: Path
) -> None:
    """main() catches EVERY exception — even an unexpected non-NotifyError."""
    with patch.object(notify, "dispatch", side_effect=RuntimeError("boom")), \
         patch.object(notify, "find_config", return_value=tmp_path / "x.json"), \
         patch.object(
             notify, "load_config", return_value=_gmail_config()
         ), patch.object(
             notify, "validate_config", return_value=notify.validate_config(_gmail_config())
         ):
        rc = notify.main(["phase_start", "--project", "Demo"])
    assert rc == 0


def test_main_returns_zero_with_valid_run(notify: ModuleType, tmp_path: Path) -> None:
    """Scenario: main() with a valid run returns 0."""
    _write_config(tmp_path, _sendgrid_config())
    fake_resp = MagicMock()
    fake_resp.__enter__ = MagicMock(return_value=fake_resp)
    fake_resp.__exit__ = MagicMock(return_value=False)
    fake_resp.status = 202
    import os as _os

    cwd = _os.getcwd()
    try:
        _os.chdir(tmp_path)
        with patch("urllib.request.urlopen", return_value=fake_resp), \
             patch.dict("os.environ", {"SENDGRID_API_KEY": "key"}, clear=False):
            rc = notify.main(["phase_complete", "--project", "Demo", "--phase", "P4"])
    finally:
        _os.chdir(cwd)
    assert rc == 0


def test_module_is_importable_without_running_cli(notify: ModuleType) -> None:
    """Scenario: Module is importable for testing — entry points are callable.

    Reaching this test means the module imported without executing the CLI; we
    additionally assert the documented entry points are present and callable.
    """
    for name in (
        "find_config",
        "load_config",
        "validate_config",
        "select_provider",
        "dispatch",
        "notify",
        "main",
        "render_email",
        "filter_recipients",
        "build_parser",
    ):
        assert callable(getattr(notify, name)), name


def test_notify_entry_swallows_notifyerror(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """notify() catches NotifyError, warns to stderr, and returns 0."""
    bad = _gmail_config()
    del bad["provider"]
    _write_config(tmp_path, bad)
    rc = notify.notify(["phase_start", "--project", "Demo"], cwd=tmp_path)
    assert rc == 0
    assert capsys.readouterr().err.strip() != ""


def test_explicit_missing_config_path_warns_not_silent(
    notify: ModuleType, tmp_path: Path, capsys
) -> None:
    """Approved ruling 2: a missing EXPLICIT --config path warns to stderr (exit 0),
    unlike a missing default-located file which is silent."""
    missing = tmp_path / "does-not-exist.json"
    rc = notify.notify(
        ["phase_start", "--project", "Demo", "--config", str(missing)], cwd=tmp_path
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert err.strip() != ""
    assert len(err.strip().splitlines()) == 1


def test_module_has_main_guard(notify_path: Path) -> None:
    """The module carries the `if __name__ == "__main__"` guard with sys.exit(main(...))."""
    source = notify_path.read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in source or "__name__ == '__main__'" in source
    assert "sys.exit(main(" in source


def test_module_has_no_stub_tokens(notify_path: Path) -> None:
    """Implementation discipline: no TODO / FIXME / pass-stub placeholders."""
    source = notify_path.read_text(encoding="utf-8")
    assert "TODO" not in source
    assert "FIXME" not in source
    assert "raise NotImplementedError" not in source
