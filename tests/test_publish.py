# -*- coding: utf-8 -*-
"""Tests for private-URL page publishing: hooks/publish_config.py, the
scripts/publish engine + adapters, and the setup question.

Every test sandboxes ``home`` to tmp_path (the registry, pages store, pidfile
and access log live under ``<home>/.architect-team/publish/``), so nothing
touches the developer's real ``~/.architect-team``. The local-port server runs
IN-PROCESS on 127.0.0.1 with an ephemeral port (a thread), never as the
detached background process; the gcloud / scp adapters run against a fake
``run`` seam, so no real network and no real subprocess. The TLS branch runs
only when ``openssl`` is on PATH to mint a self-signed certificate.

ASCII-only module; every file read passes encoding="utf-8".
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
import ssl
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from hooks import publish_config as pc
from tests.helpers.module_loader import load_module

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PAGE = ROOT / "tests" / "fixtures" / "publish" / "page.html"

engine = load_module(ROOT / "scripts" / "publish" / "publish.py", "ct6_test_publish_engine")
setup_q = load_module(ROOT / "scripts" / "publish" / "setup_question.py", "ct6_test_publish_setup")
local_port = engine.local_port()
gcp_signed = engine.adapter_module("gcp-signed-url")
cloud_run = engine.adapter_module("gcp-cloud-run")
nominated = engine.adapter_module("nominated-host")

NOW = dt.datetime(2026, 11, 8, 12, 0, 0, tzinfo=dt.timezone.utc)


def _ok_run(calls):
    def run(cmd, timeout=300):
        calls.append(list(cmd))
        return {"returncode": 0, "stdout": "", "stderr": ""}
    return run


@pytest.fixture
def home(tmp_path: Path) -> Path:
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def project(tmp_path: Path) -> Path:
    p = tmp_path / "My Repo"
    p.mkdir()
    return p


# --------------------------------------------------------------------------- #
# hooks/publish_config.py -- merge, defaults, fail-safe
# --------------------------------------------------------------------------- #


def test_absent_config_resolves_to_claude_defaults(project: Path, home: Path) -> None:
    cfg = pc.load_publish_config(project, home=home)
    assert cfg["schema"] == pc.SCHEMA
    assert cfg["mode"] == "claude" and cfg["adapter"] == "local-port"
    assert cfg["token_ttl_hours"] == 72
    assert cfg["bind"] == {"host": "0.0.0.0", "port": 8787, "external_ip": None,
                           "tls_cert": None, "tls_key": None}
    assert cfg["project_slug"] == "my-repo"  # the repo dir name, slugified
    assert pc.is_private_url(project, home=home) is False
    assert pc.publish_config_sources(project, home=home) == {"user": None, "project": None}


def test_user_level_then_project_level_merge_key_by_key(project: Path, home: Path) -> None:
    user = pc.user_config_path(home)
    user.parent.mkdir(parents=True)
    user.write_text(json.dumps({"base_url": "https://pages.example.com/", "adapter": "gcp-signed-url",
                                "gcp": {"project": "proj-1", "bucket": "shared-bucket"},
                                "bind": {"external_ip": "203.0.113.7"}}), encoding="utf-8")
    pc.project_config_path(project).write_text(json.dumps({
        "mode": "private-url", "gcp": {"bucket": "repo-bucket", "project": None},
        "bind": {"port": 9000}, "base_url": None, "token_ttl_hours": 4,
        "_comment": "ignored"}), encoding="utf-8")
    cfg = pc.load_publish_config(project, home=home)
    assert cfg["mode"] == "private-url" and cfg["adapter"] == "gcp-signed-url"
    assert cfg["gcp"]["bucket"] == "repo-bucket"       # project wins
    assert cfg["gcp"]["project"] == "proj-1"           # a project-level null inherits
    assert cfg["bind"]["port"] == 9000 and cfg["bind"]["external_ip"] == "203.0.113.7"
    assert cfg["base_url"] == "https://pages.example.com"  # trailing slash stripped, null inherits
    assert cfg["token_ttl_hours"] == 4
    assert pc.mode(project, home=home) == "private-url"
    assert pc.adapter(project, home=home) == "gcp-signed-url"
    assert pc.base_url(project, home=home) == "https://pages.example.com"
    sources = pc.publish_config_sources(project, home=home)
    assert sources["user"] and sources["project"]


def test_malformed_or_unknown_values_fail_safe_to_claude(project: Path, home: Path) -> None:
    pc.project_config_path(project).write_text("{ not json", encoding="utf-8")
    assert pc.mode(project, home=home) == "claude"
    pc.project_config_path(project).write_text(json.dumps(["a", "list"]), encoding="utf-8")
    assert pc.is_private_url(project, home=home) is False
    pc.project_config_path(project).write_text(json.dumps({
        "mode": "PUBLIC", "adapter": "ftp", "token_ttl_hours": -3,
        "bind": {"port": 99999, "host": ""}, "project_slug": "  "}), encoding="utf-8")
    cfg = pc.load_publish_config(project, home=home)
    assert cfg["mode"] == "claude" and cfg["adapter"] == "local-port"
    assert cfg["token_ttl_hours"] == 72 and cfg["bind"]["port"] == 8787 and cfg["bind"]["host"] == "0.0.0.0"
    assert cfg["project_slug"] == "my-repo"


def test_dict_readers_and_slugify() -> None:
    cfg = {"mode": "private-url", "adapter": "nominated-host", "project_slug": "Ops Dash!"}
    assert pc.is_private_url(cfg) is True
    assert pc.adapter(cfg) == "nominated-host"
    assert pc.project_slug(cfg) == "ops-dash"
    assert pc.slugify("  ") is None and pc.slugify(None) is None
    normalized = pc.normalize_config(None)
    assert normalized["mode"] == "claude" and normalized["project_slug"]


def test_example_template_is_schema_valid_and_resolves_to_claude(tmp_path: Path) -> None:
    template = json.loads((ROOT / pc.PUBLISH_EXAMPLE_FILENAME).read_text(encoding="utf-8"))
    assert template["schema"] == pc.SCHEMA and template["mode"] == "claude"
    for key in ("mode", "adapter", "token_ttl_hours", "bind", "gcp", "nominated_host", "base_url"):
        assert key in template
    assert "IMMUTABLE TO AGENTS" in template["_comment"] and "token" in template["_comment"].lower()
    for note in ("TLS", "port", "cost"):
        assert note.lower() in template["_comment"].lower(), note
    proj = tmp_path / "repo"
    proj.mkdir()
    shutil.copyfile(ROOT / pc.PUBLISH_EXAMPLE_FILENAME, pc.project_config_path(proj))
    assert pc.mode(proj, home=tmp_path / "h") == "claude"


def test_reader_module_declares_immutability_and_never_writes() -> None:
    src = (ROOT / "hooks" / "publish_config.py").read_text(encoding="utf-8")
    assert "IMMUTABILITY" in src and "READ-ONLY" in src
    assert "write_text" not in src and "open(" not in src.replace("_read_json_object", "")
    assert pc.PUBLISH_CONFIG_FILENAME == ".architect-team-publish.json"


# --------------------------------------------------------------------------- #
# page contract check
# --------------------------------------------------------------------------- #


def test_fixture_page_passes_the_contract() -> None:
    result = engine.check_page(FIXTURE_PAGE)
    assert result["ok"] is True, result["findings"]
    assert result["findings"] == []


def test_contract_refuses_external_hosts_unpinned_libraries_and_secrets(tmp_path: Path) -> None:
    page = tmp_path / "bad.html"
    page.write_text(
        '<!doctype html><html><head><script src="https://evil.example/x.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/react@18/umd/react.js"></script>'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">'
        "</head><body>key sk-ant-abcdefghijklmnop fetch('/x')</body></html>", encoding="utf-8")
    result = engine.check_page(page)
    kinds = {f["kind"] for f in result["findings"]}
    assert result["ok"] is False
    assert {"external-script-host", "unpinned-cdn-library", "secret-like-string",
            "network-call-present", "no-color-scheme", "no-viewport-meta"} <= kinds
    assert "external-style-host" not in kinds  # Google Fonts is an allowed stylesheet host
    not_html = tmp_path / "notes.txt"
    not_html.write_text("hello", encoding="utf-8")
    assert engine.check_page(not_html)["ok"] is False
    assert engine.check_page(tmp_path / "missing.html")["findings"][0]["kind"] == "missing-file"


def test_publish_refuses_contract_errors_and_never_force_publishes_a_secret(
        tmp_path: Path, home: Path, project: Path) -> None:
    page = tmp_path / "p.html"
    page.write_text('<!doctype html><html><head><script src="https://evil.example/x.js"></script>'
                    "</head><body></body></html>", encoding="utf-8")
    refused = engine.publish(page, {"mode": "claude"}, home, project_root=project)
    assert refused["ok"] is False and refused["url"] is None and "page contract" in refused["error"]
    forced = engine.publish(page, {"mode": "claude"}, home, project_root=project, force=True)
    assert forced["ok"] is True
    page.write_text("<!doctype html><html><body>-----BEGIN RSA PRIVATE KEY-----</body></html>",
                    encoding="utf-8")
    still = engine.publish(page, {"mode": "claude"}, home, project_root=project, force=True)
    assert still["ok"] is False and "secret" in still["remediation"]


# --------------------------------------------------------------------------- #
# claude mode -- the outbox, no URL
# --------------------------------------------------------------------------- #


def test_claude_mode_writes_outbox_and_mints_no_url(home: Path, project: Path) -> None:
    result = engine.publish(FIXTURE_PAGE, None, home, project_root=project)
    assert result["ok"] is True and result["mode"] == "claude"
    assert result["url"] is None and result["token"] is None and result["expires_at"] is None
    assert result["adapter"] is None
    outbox = project / ".architect-team" / "publish" / "outbox" / "page.html"
    assert Path(result["record_path"]) == outbox and outbox.is_file()
    assert outbox.read_bytes() == FIXTURE_PAGE.read_bytes()
    assert "Artifact tool" in result["instructions"]
    assert not local_port.state_paths(home)["registry"].exists()  # nothing recorded, nothing listens
    assert result["project_slug"] == "my-repo"
    named = engine.publish(FIXTURE_PAGE, None, home, project_root=project, name="Run Summary")
    assert Path(named["record_path"]).name == "Run-Summary.html"


def test_page_name_sanitization() -> None:
    assert engine.page_name("/x/report.html") == "report.html"
    assert engine.page_name("/x/report.html", "index") == "index.html"
    assert engine.page_name("/x/report.html", "../../etc/passwd") == "etc-passwd.html"
    assert engine.page_name("/x/a.htm", "weird name.htm") == "weird-name.html"


# --------------------------------------------------------------------------- #
# private-url + local-port -- the in-process server
# --------------------------------------------------------------------------- #

LOCAL_CFG = {"mode": "private-url", "adapter": "local-port", "token_ttl_hours": 2,
             "bind": {"host": "127.0.0.1", "port": 8799}}


class _Clock:
    def __init__(self, start: dt.datetime) -> None:
        self.now = start

    def __call__(self) -> dt.datetime:
        return self.now


@pytest.fixture
def server(home: Path):
    clock = _Clock(NOW)
    srv = local_port.make_server("127.0.0.1", 0, home=home, now_fn=clock)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    port = srv.server_address[1]

    def fetch(path: str, method: str = "GET"):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read(), dict(resp.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    yield {"server": srv, "fetch": fetch, "clock": clock, "port": port}
    srv.shutdown()
    srv.server_close()


def test_local_port_serves_only_live_tokens(home: Path, project: Path, server) -> None:
    fetch, clock = server["fetch"], server["clock"]
    result = engine.publish(FIXTURE_PAGE, LOCAL_CFG, home, project_root=project,
                            start_server=False, now=NOW)
    assert result["ok"] is True and result["mode"] == "private-url" and result["adapter"] == "local-port"
    token = result["token"]
    assert len(token) >= 32 and result["url"] == f"http://127.0.0.1:8799/my-repo/p/{token}/page.html"
    assert result["expires_at"] == "2026-11-08T14:00:00+00:00"
    assert Path(result["record_path"]) == local_port.state_paths(home)["registry"]
    assert any("plain HTTP" in w for w in result["warnings"])
    assert any("no comments routed to Claude" in b for b in result["boundary"])
    assert any("clear text" in b for b in result["boundary"])

    good_path = f"/my-repo/p/{token}/page.html"
    status, body, headers = fetch(good_path)
    assert status == 200 and body == FIXTURE_PAGE.read_bytes()
    assert headers["Referrer-Policy"] == "no-referrer" and headers["Cache-Control"] == "no-store"
    assert headers["X-Robots-Tag"].startswith("noindex")
    assert fetch(good_path, method="HEAD")[0] == 200

    # wrong token / other page in the token dir / traversal / directory URLs / root
    assert fetch(f"/my-repo/p/{'x' * len(token)}/page.html")[0] == 404
    assert fetch(f"/my-repo/p/{token}/other.html")[0] == 404
    assert fetch(f"/my-repo/p/{token}/../../registry.json")[0] == 404
    assert fetch(f"/my-repo/p/{token}/%2e%2e/%2e%2e/registry.json")[0] == 404
    assert fetch(f"/my-repo/p/{token}/")[0] == 404          # a non-homepage token dir
    assert fetch("/my-repo/p/")[0] == 404
    assert fetch("/my-repo/")[0] == 404
    assert fetch("/")[0] == 404
    status, body, _ = fetch("/my-repo/p/")
    assert b"<a href" not in body and b"Directory listing" not in body  # never a listing
    assert fetch(good_path, method="POST")[0] == 404

    # expiry: the clock passes expires_at -> 404; registry list reports expired
    clock.now = NOW + dt.timedelta(hours=2, seconds=1)
    assert fetch(good_path)[0] == 404
    assert engine.list_tokens(home, now=clock.now)[0]["status"] == "expired"
    clock.now = NOW
    assert fetch(good_path)[0] == 200

    # revoke -> 404 at once, file removed, registry says revoked
    revoked = engine.revoke(token, home, config=LOCAL_CFG, project_root=project, now=NOW)
    assert revoked["ok"] is True and revoked["removal"]["removed"] is True
    assert fetch(good_path)[0] == 404
    rows = engine.list_tokens(home, now=NOW)
    assert rows[0]["status"] == "revoked" and rows[0]["revoked_at"]
    again = engine.revoke(token, home, config=LOCAL_CFG, project_root=project)
    assert again["ok"] is True and again["already_revoked"] is True
    missing = engine.revoke("nope", home, config=LOCAL_CFG, project_root=project)
    assert missing["ok"] is False

    # the access log carries every request with the token redacted
    log = local_port.state_paths(home)["access_log"].read_text(encoding="utf-8")
    assert token not in log and token[:6] + "..." in log
    assert " 200\n" in log and " 404\n" in log


def test_homepage_lands_at_its_token_directory(home: Path, project: Path, server) -> None:
    fetch = server["fetch"]
    result = engine.publish(FIXTURE_PAGE, LOCAL_CFG, home, project_root=project,
                            start_server=False, now=NOW, name="index")
    token = result["token"]
    assert result["homepage"] is True
    assert result["url"] == f"http://127.0.0.1:8799/my-repo/p/{token}/"
    assert fetch(f"/my-repo/p/{token}/")[0] == 200
    assert fetch(f"/my-repo/p/{token}/index.html")[0] == 200
    assert fetch("/my-repo/")[0] == 404  # a token-free slug root is never served


def test_registry_shape_and_list(home: Path, project: Path) -> None:
    first = engine.publish(FIXTURE_PAGE, LOCAL_CFG, home, project_root=project,
                           start_server=False, now=NOW)
    second = engine.publish(FIXTURE_PAGE, LOCAL_CFG, home, project_root=project,
                            start_server=False, now=NOW, slug="Other Project")
    registry = json.loads(local_port.state_paths(home)["registry"].read_text(encoding="utf-8"))
    assert registry["schema"] == local_port.REGISTRY_SCHEMA
    assert [e["token"] for e in registry["tokens"]] == [first["token"], second["token"]]
    entry = registry["tokens"][1]
    for key in ("token", "slug", "page", "url", "created_at", "expires_at", "adapter", "revoked_at"):
        assert key in entry
    assert entry["slug"] == "other-project" and entry["revoked_at"] is None
    assert entry["path"] == f"/other-project/p/{second['token']}/page.html"
    assert Path(entry["page"]).is_file()
    assert [r["status"] for r in engine.list_tokens(home, now=NOW)] == ["live", "live"]


def test_prune_removes_expired_files_through_bg_runtime_scheduler(home: Path, project: Path) -> None:
    result = engine.publish(FIXTURE_PAGE, LOCAL_CFG, home, project_root=project,
                            start_server=False, now=NOW)
    stored = Path(result["stored_at"])
    assert stored.is_file()
    assert local_port.prune_expired(home, now=NOW) == []
    clock = _Clock(NOW)
    scheduler = local_port.build_scheduler(home, now_fn=clock)
    assert scheduler is not None, "bg_runtime must be the prune's scheduler in the checkout"
    assert scheduler.due(0) == ["prune-expired-pages"]
    assert scheduler.run_due(0) == {"prune-expired-pages": "ok"}  # nothing expired yet
    assert stored.is_file()
    assert scheduler.due(60) == []                      # the hourly interval holds
    clock.now = NOW + dt.timedelta(hours=3)
    assert scheduler.run_due(3600) == {"prune-expired-pages": "ok"}
    assert not stored.exists()                          # the scheduler's tick pruned it
    assert scheduler.health(3600)["healthy"] is True
    assert engine.list_tokens(home, now=clock.now)[0]["status"] == "expired"  # the record stays
    assert local_port.prune_expired(home, now=clock.now) == []  # idempotent


def test_base_url_derivation_and_serve_command(home: Path) -> None:
    warnings: list = []
    assert local_port.base_url_for({"bind": {"host": "127.0.0.1", "port": 8787}}, warnings) == "http://127.0.0.1:8787"
    assert local_port.base_url_for({"bind": {"host": "0.0.0.0", "port": 8787, "external_ip": "203.0.113.9"}}, warnings) == "http://203.0.113.9:8787"
    assert local_port.base_url_for({"bind": {"host": "0.0.0.0", "port": 443, "external_ip": "h.example",
                                             "tls_cert": "c.pem", "tls_key": "k.pem"}}, warnings) == "https://h.example"
    assert local_port.base_url_for({"base_url": "https://pages.example.com/", "bind": {}}, warnings) == "https://pages.example.com"
    assert warnings == []
    local_port.base_url_for({"bind": {"host": "0.0.0.0", "port": 8787}}, warnings)
    assert warnings and "wildcard" in warnings[0]
    cmd = local_port.build_serve_command(LOCAL_CFG, home, python="py")
    assert cmd[:3] == ["py", str((ROOT / "scripts/publish/adapters/local_port.py").resolve()), "serve"]
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1" and cmd[cmd.index("--port") + 1] == "8799"
    assert "--tls-cert" not in cmd
    status = engine.serve_status(home)
    assert status["running"] is False and status["pid"] is None
    assert engine.serve_stop(home) == {"stopped": False, "pid": None, "reason": "no pidfile"}


def test_stale_pidfile_is_reported_and_cleared(home: Path) -> None:
    paths = local_port.state_paths(home)
    paths["dir"].mkdir(parents=True)
    paths["pidfile"].write_text("999999999\n", encoding="utf-8")  # no such pid
    status = local_port.status(home)
    assert status["running"] is False and status["stale"] is True
    assert local_port.stop(home)["reason"] == "stale pidfile removed"
    assert not paths["pidfile"].exists()


def test_boot_descriptor_is_generated_not_installed(home: Path) -> None:
    desc = local_port.boot_descriptor(LOCAL_CFG, home, "linux")
    assert desc["ok"] is True and desc["kind"] == "systemd"
    assert "Restart=always" in desc["content"] and "local_port.py" in desc["content"]
    assert local_port.boot_descriptor(LOCAL_CFG, home, "darwin")["kind"] == "launchd"


@pytest.mark.skipif(shutil.which("openssl") is None,
                    reason="openssl is not on PATH: cannot mint a self-signed cert for the TLS branch")
def test_local_port_tls_branch_serves_https(tmp_path: Path, home: Path, project: Path) -> None:
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    minted = subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", str(key),
         "-out", str(cert), "-days", "1", "-subj", "/CN=localhost",
         "-addext", "subjectAltName=IP:127.0.0.1,DNS:localhost"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if minted.returncode != 0:
        pytest.skip(f"openssl could not mint a certificate: {minted.stderr[-200:]}")
    cfg = {"mode": "private-url", "adapter": "local-port",
           "bind": {"host": "127.0.0.1", "port": 8443, "tls_cert": str(cert), "tls_key": str(key)}}
    result = engine.publish(FIXTURE_PAGE, cfg, home, project_root=project, start_server=False, now=NOW)
    assert result["url"].startswith("https://127.0.0.1:8443/")
    assert not any("plain HTTP" in w for w in result["warnings"])
    assert not any("clear text" in b for b in result["boundary"])
    # The token was minted at the fixed NOW; the server must read the same
    # clock or the test expires with the calendar (it did, three days on).
    srv = local_port.make_server("127.0.0.1", 0, home=home, tls_cert=str(cert), tls_key=str(key), now_fn=lambda: NOW)
    assert srv.scheme == "https"
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        ctx = ssl.create_default_context(cafile=str(cert))
        url = f"https://127.0.0.1:{srv.server_address[1]}/my-repo/p/{result['token']}/page.html"
        with urllib.request.urlopen(url, context=ctx, timeout=5) as resp:
            assert resp.status == 200 and resp.read() == FIXTURE_PAGE.read_bytes()
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            urllib.request.urlopen(f"https://127.0.0.1:{srv.server_address[1]}/my-repo/p/bad/page.html",
                                   context=ctx, timeout=5)
        assert excinfo.value.code == 404
    finally:
        srv.shutdown()
        srv.server_close()


# --------------------------------------------------------------------------- #
# gcp-signed-url -- the monkeypatched run() seam
# --------------------------------------------------------------------------- #

GCP_CFG = {"mode": "private-url", "adapter": "gcp-signed-url", "token_ttl_hours": 48,
           "gcp": {"bucket": "ct6-pages", "project": "proj-1"}}


def test_gcp_signed_url_uploads_and_parses_the_signed_link(home: Path, project: Path, monkeypatch) -> None:
    calls: list = []

    def fake_run(cmd, timeout=300):
        calls.append(list(cmd))
        if "sign-url" in cmd:
            uri = cmd[3]
            return {"returncode": 0, "stderr": "",
                    "stdout": f"---\nexpiration: '2026-11-10'\nhttp_verb: GET\nresource: {uri}\n"
                              f"signed_url: {uri.replace('gs://', 'https://storage.googleapis.com/')}"
                              f"?X-Goog-Algorithm=GOOG4-RSA-SHA256&X-Goog-Signature=abc\n"}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    monkeypatch.setattr(gcp_signed, "run", fake_run)  # the module-level seam, through the engine's cache
    result = engine.publish(FIXTURE_PAGE, GCP_CFG, home, project_root=project, now=NOW)
    assert result["ok"] is True and result["adapter"] == "gcp-signed-url"
    token = result["token"]
    assert result["url"].startswith(f"https://storage.googleapis.com/ct6-pages/my-repo/p/{token}/page.html?")
    assert calls[0][:3] == ["gcloud", "storage", "cp"] and calls[0][3] == str(FIXTURE_PAGE)
    assert calls[0][4] == f"gs://ct6-pages/my-repo/p/{token}/page.html"
    assert "--project=proj-1" in calls[0] and "--project=proj-1" in calls[1]
    assert calls[1][:3] == ["gcloud", "storage", "sign-url"] and "--duration=48h" in calls[1]
    entry = engine.list_tokens(home)[0]
    assert entry["object_uri"] == f"gs://ct6-pages/my-repo/p/{token}/page.html"
    revoked = engine.revoke(token, home, config=GCP_CFG, project_root=project)
    assert revoked["removal"]["ok"] is True and calls[-1][:3] == ["gcloud", "storage", "rm"]


def test_gcp_signed_url_structured_errors_never_raise(home: Path, project: Path) -> None:
    missing = engine.publish(FIXTURE_PAGE, GCP_CFG, home, project_root=project,
                             run=lambda cmd, timeout=300: {"returncode": 127, "stdout": "",
                                                           "stderr": "gcloud: command not found"})
    assert missing["ok"] is False and "not installed" in missing["error"]
    assert "gcloud auth login" in missing["remediation"] and missing["url"] is None
    no_bucket = engine.publish(FIXTURE_PAGE, {"mode": "private-url", "adapter": "gcp-signed-url"},
                               home, project_root=project, run=_ok_run([]))
    assert no_bucket["ok"] is False and "gcp.bucket" in no_bucket["error"]

    def sign_fails(cmd, timeout=300):
        if "sign-url" in cmd:
            return {"returncode": 1, "stdout": "", "stderr": "ERROR: no service account key"}
        return {"returncode": 0, "stdout": "", "stderr": ""}

    unsigned = engine.publish(FIXTURE_PAGE, GCP_CFG, home, project_root=project, run=sign_fails)
    assert unsigned["ok"] is False and "sign-url failed" in unsigned["error"]
    assert "impersonate" in unsigned["remediation"]
    assert engine.list_tokens(home) == []  # nothing recorded on a failed publish
    assert gcp_signed.parse_signed_url("https://x.example/a?b=1\n") == "https://x.example/a?b=1"
    assert gcp_signed.parse_signed_url("nothing here") is None
    clamped = engine.publish(FIXTURE_PAGE, dict(GCP_CFG, token_ttl_hours=1000), home,
                             project_root=project, run=_ok_run([]))
    assert clamped["ok"] is False  # the ok-run returns no URL to parse -> structured error
    assert gcp_signed.publish_page(page_path=FIXTURE_PAGE, slug="s", token="t", name="n.html",
                                   config=dict(GCP_CFG, token_ttl_hours=1000),
                                   run=lambda c, timeout=300: {"returncode": 0, "stderr": "",
                                                               "stdout": "signed_url: https://s/x\n"}
                                   )["warnings"][0].startswith("token_ttl_hours 1000 exceeds")


def test_real_run_seam_reports_a_missing_binary_as_127() -> None:
    result = gcp_signed.run(["ct6-definitely-not-a-binary-xyz", "--version"])
    assert result["returncode"] == 127 and "command not found" in result["stderr"]
    result = nominated.run(["ct6-definitely-not-a-binary-xyz"])
    assert result["returncode"] == 127


# --------------------------------------------------------------------------- #
# gcp-cloud-run -- generates, deploys nothing
# --------------------------------------------------------------------------- #


def test_cloud_run_generates_files_and_deploys_nothing(home: Path, project: Path) -> None:
    calls: list = []
    cfg = {"mode": "private-url", "adapter": "gcp-cloud-run",
           "gcp": {"project": "proj-1", "region": "europe-west1", "service": "pages"}}
    result = engine.publish(FIXTURE_PAGE, cfg, home, project_root=project, run=_ok_run(calls), now=NOW)
    assert result["ok"] is True and calls == []  # NOTHING shelled out
    assert result["url_is_pattern"] is True
    assert result["url"] == f"https://pages-<project-hash>-europe-west1.a.run.app/my-repo/p/{result['token']}/page.html"
    gen_dir = project / ".architect-team" / "publish" / "cloud-run"
    names = sorted(Path(f).name for f in result["generated"])
    assert names == [".dockerignore", "Dockerfile", "README.md", "deploy.sh", "server.py"]
    dockerfile = (gen_dir / "Dockerfile").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in dockerfile and '"serve"' in dockerfile and "8080" in dockerfile
    deploy = (gen_dir / "deploy.sh").read_text(encoding="utf-8")
    assert "gcloud run deploy pages" in deploy and "--project proj-1" in deploy
    assert "--region europe-west1" in deploy and "A HUMAN runs this" in deploy
    assert (gen_dir / "server.py").read_text(encoding="utf-8") == \
        (ROOT / "scripts/publish/adapters/local_port.py").read_text(encoding="utf-8")
    assert any("deployed NOTHING" in w for w in result["warnings"])
    assert any("Nothing was deployed" in b for b in result["boundary"])
    assert Path(result["stored_at"]).is_file()
    assert (gen_dir / "README.md").read_text(encoding="utf-8").count("deployed") >= 1
    concrete = engine.publish(FIXTURE_PAGE, dict(cfg, base_url="https://pages-abc-ew.a.run.app"), home,
                              project_root=project, now=NOW)
    assert concrete["url_is_pattern"] is False
    assert concrete["url"].startswith("https://pages-abc-ew.a.run.app/my-repo/p/")
    no_project = engine.publish(FIXTURE_PAGE, {"mode": "private-url", "adapter": "gcp-cloud-run"},
                                home, project_root=project)
    assert no_project["ok"] is False and "gcp.project" in no_project["error"]
    revoked = engine.revoke(result["token"], home, config=cfg, project_root=project)
    assert revoked["removal"]["removed"] is True and "snapshot" in revoked["removal"]["warnings"][0]


# --------------------------------------------------------------------------- #
# nominated-host -- the scp command through run()
# --------------------------------------------------------------------------- #

HOST_CFG = {"mode": "private-url", "adapter": "nominated-host",
            "nominated_host": {"ssh": "deploy@web01", "web_root": "/var/www/pages/",
                               "public_base_url": "https://pages.example.com/"}}


def test_nominated_host_builds_mkdir_then_scp(home: Path, project: Path) -> None:
    calls: list = []
    result = engine.publish(FIXTURE_PAGE, HOST_CFG, home, project_root=project, run=_ok_run(calls), now=NOW)
    token = result["token"]
    assert result["ok"] is True
    assert result["url"] == f"https://pages.example.com/my-repo/p/{token}/page.html"
    assert len(calls) == 2
    assert calls[0][0] == "ssh" and calls[0][-2] == "deploy@web01"
    assert calls[0][-1] == f"mkdir -p /var/www/pages/my-repo/p/{token}"
    assert calls[1][0] == "scp" and calls[1][-2] == str(FIXTURE_PAGE)
    assert calls[1][-1] == f"deploy@web01:/var/www/pages/my-repo/p/{token}/page.html"
    built = nominated.build_commands(page_path="/tmp/x y.html", ssh="h", web_root="/srv/w w",
                                     slug="s", token="t", name="n.html")
    assert built["scp"][-1] == "h:'/srv/w w/s/p/t/n.html'"  # remote paths are shell-quoted
    assert built["mkdir"][-1] == "mkdir -p '/srv/w w/s/p/t'"
    revoked = engine.revoke(token, home, config=HOST_CFG, project_root=project, run=_ok_run(calls))
    assert revoked["removal"]["ok"] is True and calls[-1][-1] == f"rm -f /var/www/pages/my-repo/p/{token}/page.html"


def test_nominated_host_structured_errors(home: Path, project: Path) -> None:
    missing_cfg = engine.publish(FIXTURE_PAGE, {"mode": "private-url", "adapter": "nominated-host"},
                                 home, project_root=project, run=_ok_run([]))
    assert missing_cfg["ok"] is False and "nominated_host.ssh" in missing_cfg["error"]
    no_scp = engine.publish(FIXTURE_PAGE, HOST_CFG, home, project_root=project,
                            run=lambda cmd, timeout=300: {"returncode": 127, "stdout": "", "stderr": "x"})
    assert no_scp["ok"] is False and "not installed" in no_scp["error"]
    denied = engine.publish(FIXTURE_PAGE, HOST_CFG, home, project_root=project,
                            run=lambda cmd, timeout=300: {"returncode": 255, "stdout": "",
                                                          "stderr": "Permission denied (publickey)."})
    assert denied["ok"] is False and "Permission denied" in denied["detail"]
    assert engine.list_tokens(home) == []


# --------------------------------------------------------------------------- #
# the setup question
# --------------------------------------------------------------------------- #


def _fake_runner(gcloud_account: str = "me@example.com", ips: str = "10.0.0.5 34.120.1.2"):
    def run(cmd, timeout=20):
        if cmd[0] == "gcloud":
            return {"returncode": 0, "stdout": gcloud_account + "\n", "stderr": ""}
        if cmd[0] == "hostname":
            return {"returncode": 0, "stdout": ips + "\n", "stderr": ""}
        return {"returncode": 127, "stdout": "", "stderr": "command not found"}
    return run


def test_detect_ecosystem_with_everything_present(home: Path) -> None:
    (home / ".ssh").mkdir()
    (home / ".ssh" / "config").write_text(
        "# comment\nHost web01 web02\n  HostName w.example\nHost *\n  User me\nHost !bastion\n",
        encoding="utf-8")
    eco = setup_q.detect_ecosystem(run=_fake_runner(), home=home, which=lambda n: f"/usr/bin/{n}",
                                   platform_name="linux")
    assert eco["gcloud"] is True and eco["gcloud_account"] == "me@example.com"
    assert eco["public_ip"] == "34.120.1.2"            # the private 10/8 address is skipped
    assert eco["ssh_hosts"] == ["web01", "web02"]      # wildcards and negations skipped
    assert eco["ssh"] is True and eco["scp"] is True
    assert eco["remediation"] == {"gcloud": None, "ssh": None}


def test_detect_ecosystem_with_nothing_present(home: Path) -> None:
    eco = setup_q.detect_ecosystem(run=_fake_runner(gcloud_account="", ips="192.168.1.20 127.0.0.1"),
                                   home=home, which=lambda n: None, platform_name="linux")
    assert eco["gcloud"] is False and eco["gcloud_on_path"] is False and eco["gcloud_account"] is None
    assert eco["public_ip"] is None and eco["ssh_hosts"] == []
    assert "install the Google Cloud CLI" in eco["remediation"]["gcloud"]
    assert "OpenSSH" in eco["remediation"]["ssh"]
    installed_not_logged_in = setup_q.detect_ecosystem(
        run=_fake_runner(gcloud_account=""), home=home,
        which=lambda n: "/usr/bin/gcloud" if n == "gcloud" else None, platform_name="linux")
    assert installed_not_logged_in["gcloud"] is False and installed_not_logged_in["gcloud_on_path"] is True
    assert "gcloud auth login" in installed_not_logged_in["remediation"]["gcloud"]


def test_question_text_options_and_recommendation(home: Path) -> None:
    rich = setup_q.detect_ecosystem(run=_fake_runner(), home=home, which=lambda n: f"/usr/bin/{n}",
                                    platform_name="linux")
    q = setup_q.question(rich)
    labels = [o["label"] for o in q["options"]]
    assert labels == ["Claude artifacts only (default)",
                      "GCP signed URL (recommended when gcloud is present)",
                      "A port on this machine", "A host I nominate"]
    assert q["recommended"] == labels[1] and q["multiSelect"] is False and q["header"]
    assert "Where should this project's shareable pages live?" in q["question"]
    for phrase in ("token", "browser history", "attack surface" if False else "listening service",
                   "costs money", "clear text", "Nothing is opened"):
        assert phrase in q["question"], phrase
    assert "34.120.1.2" in q["options"][2]["description"]
    bare = setup_q.question(setup_q.detect_ecosystem(run=_fake_runner(gcloud_account=""), home=home,
                                                     which=lambda n: None, platform_name="linux"))
    assert bare["recommended"] == labels[0]
    assert "NOT ready" in bare["options"][1]["description"]
    assert setup_q.resolve_choice("A host I nominate") == ("private-url", "nominated-host")
    assert setup_q.resolve_choice("gcp-cloud-run") == ("private-url", "gcp-cloud-run")
    assert setup_q.resolve_choice("teleport") is None


def test_write_config_records_once_and_the_reader_sees_it(home: Path, project: Path) -> None:
    answers = {"choice": "GCP signed URL (recommended when gcloud is present)",
               "gcp": {"bucket": "ct6-pages"}, "token_ttl_hours": 24}
    written = setup_q.write_config(answers, project, home, user_level={"gcp": {"project": "proj-1"},
                                                                      "base_url": None})
    assert written["written"] is True and written["mode"] == "private-url"
    assert written["adapter"] == "gcp-signed-url"
    assert Path(written["path"]) == pc.project_config_path(project)
    assert Path(written["user_path"]) == pc.user_config_path(home)
    assert written["gitignore_ok"] is False and ".architect-team-publish.json" in written["gitignore_hint"]
    cfg = pc.load_publish_config(project, home=home)
    assert cfg["mode"] == "private-url" and cfg["adapter"] == "gcp-signed-url"
    assert cfg["gcp"] == {"project": "proj-1", "bucket": "ct6-pages", "service": None, "region": None}
    assert cfg["token_ttl_hours"] == 24
    doc = json.loads(pc.project_config_path(project).read_text(encoding="utf-8"))
    assert doc["schema"] == pc.SCHEMA and "IMMUTABLE TO AGENTS" in doc["_comment"]
    # asked once: a second write is refused unless the human asks for overwrite
    second = setup_q.write_config({"choice": "claude"}, project, home)
    assert second["written"] is False and second["reason"] == "exists"
    assert pc.mode(project, home=home) == "private-url"
    forced = setup_q.write_config({"choice": "Claude artifacts only (default)"}, project, home, overwrite=True)
    assert forced["written"] is True and pc.mode(project, home=home) == "claude"
    (project / ".gitignore").write_text(".architect-team-publish.json\n", encoding="utf-8")
    assert setup_q.write_config({"choice": "port"}, project, home, overwrite=True)["gitignore_ok"] is True
    assert setup_q.write_config({"choice": "nope"}, project, home, overwrite=True)["reason"] == "unknown choice"


# --------------------------------------------------------------------------- #
# the CLI
# --------------------------------------------------------------------------- #


def test_cli_publish_list_revoke_and_exit_codes(home: Path, project: Path, capsys) -> None:
    pc.project_config_path(project).write_text(json.dumps(LOCAL_CFG), encoding="utf-8")
    common = ["--home", str(home), "--project-root", str(project)]
    assert engine.main(common + ["publish", str(FIXTURE_PAGE), "--no-server-start", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is True and result["url"].startswith("http://127.0.0.1:8799/my-repo/p/")
    assert engine.main(common + ["publish", str(FIXTURE_PAGE), "--no-server-start"]) == 0
    out = capsys.readouterr().out
    assert "Honest boundary:" in out and "url: http://127.0.0.1:8799" in out and "WARNING: plain HTTP" in out
    assert engine.main(common + ["list"]) == 0
    assert capsys.readouterr().out.count("[live   ]") == 2
    assert engine.main(common + ["revoke", result["token"]]) == 0
    assert "revoked" in capsys.readouterr().out
    assert engine.main(common + ["revoke", "nope"]) == 1
    capsys.readouterr()
    assert engine.main(common + ["check", str(FIXTURE_PAGE)]) == 0
    assert "page contract: ok" in capsys.readouterr().out
    assert engine.main(common + ["serve-status"]) == 0
    assert json.loads(capsys.readouterr().out)["running"] is False
    assert engine.main(common + ["serve-stop"]) == 1
    capsys.readouterr()
    assert engine.main(["bogus-verb"]) == 2
    missing = tmp = project / "nope.html"
    assert engine.main(common + ["publish", str(missing)]) == 1
    assert "REFUSED" in capsys.readouterr().out


def test_cli_claude_mode_prints_the_handoff_instruction(home: Path, project: Path, capsys) -> None:
    assert engine.main(["--home", str(home), "--project-root", str(project), "publish", str(FIXTURE_PAGE)]) == 0
    out = capsys.readouterr().out
    assert "mode: claude" in out and "Artifact tool" in out and "url:" not in out


# --------------------------------------------------------------------------- #
# shipped surfaces
# --------------------------------------------------------------------------- #


def test_skill_command_and_reference_exist_with_the_contract_vocabulary() -> None:
    skill = (ROOT / "skills" / "page-publishing" / "SKILL.md").read_text(encoding="utf-8")
    assert skill.startswith("---\nname: page-publishing\n")
    assert "user-invocable: false" in skill.split("---", 2)[1]
    assert len(skill.splitlines()) < 250
    for phrase in ("references/page-contract.md", "scripts/publish/publish.py", "Artifact tool",
                   "private-url", "<base_url>/<project_slug>/p/<token>/<page-name>.html",
                   "Claude artifacts only (default)", "GCP signed URL (recommended when gcloud is present)",
                   "A port on this machine", "A host I nominate", "revoke", "no comments routed to Claude",
                   "deploys NOTHING"):
        assert phrase in skill, phrase
    contract = (ROOT / "skills" / "page-publishing" / "references" / "page-contract.md").read_text(encoding="utf-8")
    for phrase in ("prefers-color-scheme", "data-theme", "inline SVG", "400px", "16px", "cdnjs",
                   "jsdelivr", "unpkg", "No data leaves the page", "No secrets", "16 MB"):
        assert phrase in contract, phrase
    command = (ROOT / "commands" / "publish.md").read_text(encoding="utf-8")
    assert "# /architect-team:publish" in command
    for flag in ("--revoke", "--list", "--status", "--name"):
        assert flag in command, flag
    assert "page-publishing" in command


def test_python_surfaces_are_ascii_only() -> None:
    for rel in ("hooks/publish_config.py", "scripts/publish/publish.py", "scripts/publish/setup_question.py",
                "scripts/publish/adapters/local_port.py", "scripts/publish/adapters/gcp_signed_url.py",
                "scripts/publish/adapters/gcp_cloud_run.py", "scripts/publish/adapters/nominated_host.py"):
        raw = (ROOT / rel).read_bytes()
        assert all(b < 128 for b in raw), f"{rel} carries a non-ASCII byte"
