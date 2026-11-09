# -*- coding: utf-8 -*-
"""Page-publishing engine + CLI -- the mechanism under the `page-publishing` skill.

    python scripts/publish/publish.py publish <file> [--slug S] [--name N] [--json]
    python scripts/publish/publish.py revoke <token> [--json]
    python scripts/publish/publish.py list [--json]
    python scripts/publish/publish.py serve-status [--json]
    python scripts/publish/publish.py serve-stop   [--json]
    python scripts/publish/publish.py check <file> [--json]

Two modes, read from the human-owned config (`hooks/publish_config.py`):

* ``claude`` (default) -- the page is copied to
  ``<workspace>/.architect-team/publish/outbox/<name>.html`` and the result
  carries INSTRUCTIONS: hand that file to the Claude Artifact tool. No URL is
  minted, nothing listens, nothing is uploaded.
* ``private-url`` -- a token is minted with ``secrets.token_urlsafe(24)``, the
  configured adapter places the page at ``<base_url>/<slug>/p/<token>/<name>``
  (a ``--name index`` homepage lands at ``<base_url>/<slug>/p/<token>/``), and
  the link is recorded in ``~/.architect-team/publish/registry.json`` with its
  expiry so `revoke` / `list` / the local server agree on what is live.

Every private link is printed WITH its honest boundary (``boundary_lines``):
no comments routed to Claude, no shared database, no organization share list,
and -- for a plain-HTTP local port -- the token travels in clear text.

The page contract (``skills/page-publishing/references/page-contract.md``) is
machine-checked by ``check_page`` before any publish: one self-contained HTML
file under 16 MB, libraries only from pinned cdnjs / jsdelivr / unpkg URLs, no
secret-shaped strings. Errors refuse the publish (``--force`` overrides the
contract findings, never the secret finding).

Exit codes: 0 ok, 1 the publish/revoke was refused (a structured error), 2 a
usage error, 3 an unexpected internal failure. Stdlib-only; ASCII-only source.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_CONFIG_PATH = _REPO / "hooks" / "publish_config.py"
_ADAPTER_FILES = {
    "local-port": _HERE / "adapters" / "local_port.py",
    "gcp-signed-url": _HERE / "adapters" / "gcp_signed_url.py",
    "gcp-cloud-run": _HERE / "adapters" / "gcp_cloud_run.py",
    "nominated-host": _HERE / "adapters" / "nominated_host.py",
}

MAX_PAGE_BYTES = 16 * 1024 * 1024
TOKEN_BYTES = 24
OUTBOX_RELDIR = Path(".architect-team") / "publish" / "outbox"

ALLOWED_SCRIPT_HOSTS = ("cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com")
ALLOWED_STYLE_HOSTS = ALLOWED_SCRIPT_HOSTS + ("fonts.googleapis.com", "fonts.gstatic.com")

_RE_SCRIPT_SRC = re.compile(r"<script\b[^>]*\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_RE_LINK_HREF = re.compile(r"<link\b[^>]*\bhref\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_RE_PINNED = {
    "cdnjs.cloudflare.com": re.compile(r"/ajax/libs/[^/]+/\d+\.\d+"),
    "cdn.jsdelivr.net": re.compile(r"/(?:npm|gh)/[^/@]+(?:/[^/@]+)?@\d+\.\d+\.\d+"),
    "unpkg.com": re.compile(r"^https://unpkg\.com/(?:@[^/]+/)?[^/@]+@\d+\.\d+\.\d+"),
}
_RE_SECRETS = (
    ("anthropic-api-key", re.compile(r"sk-ant-[A-Za-z0-9_-]{8,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
)
_RE_NETWORK = re.compile(r"\bfetch\s*\(|XMLHttpRequest|navigator\.sendBeacon|new\s+WebSocket\s*\(", re.IGNORECASE)
_RE_NAME_BAD = re.compile(r"[^A-Za-z0-9._-]+")


# --------------------------------------------------------------------------- #
# module loading (the scripts/ tier's house idiom)
# --------------------------------------------------------------------------- #


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish_config = _load(_CONFIG_PATH, "ct6_publish_config")
_ADAPTERS: Dict[str, Any] = {}


def adapter_module(name: str):
    """The adapter module for ``name`` (cached, so a test can monkeypatch its
    ``run`` seam through this same object)."""
    if name not in _ADAPTER_FILES:
        raise ValueError(f"unknown adapter {name!r} (one of {', '.join(sorted(_ADAPTER_FILES))})")
    if name not in _ADAPTERS:
        _ADAPTERS[name] = _load(_ADAPTER_FILES[name], "ct6_publish_adapter_" + name.replace("-", "_"))
    return _ADAPTERS[name]


def local_port():
    return adapter_module("local-port")


# --------------------------------------------------------------------------- #
# page contract check
# --------------------------------------------------------------------------- #


def _host_of(url: str) -> Optional[str]:
    m = re.match(r"^(?:https?:)?//([^/]+)", url.strip(), re.IGNORECASE)
    return m.group(1).lower() if m else None


def check_page(page_path) -> Dict[str, Any]:
    """Lint the page against the contract. ``{"ok", "findings": [{"severity",
    "kind", "detail"}], "bytes"}``; ``ok`` is False when any finding is an
    error. Never raises."""
    path = Path(page_path)
    findings: List[Dict[str, str]] = []

    def err(kind: str, detail: str) -> None:
        findings.append({"severity": "error", "kind": kind, "detail": detail})

    def warn(kind: str, detail: str) -> None:
        findings.append({"severity": "warning", "kind": kind, "detail": detail})

    if not path.is_file():
        err("missing-file", f"{path} is not a file")
        return {"ok": False, "findings": findings, "bytes": 0}
    if path.suffix.lower() not in (".html", ".htm"):
        err("not-html", f"{path.name} does not end in .html")
    size = path.stat().st_size
    if size > MAX_PAGE_BYTES:
        err("too-large", f"{size} bytes exceeds the 16 MB page limit")
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        err("unreadable", f"{type(exc).__name__}: {exc}")
        return {"ok": False, "findings": findings, "bytes": size}
    low = text.lower()
    if "<html" not in low:
        err("not-html", "no <html> element")
    for src in _RE_SCRIPT_SRC.findall(text):
        host = _host_of(src)
        if host is None:
            continue  # a relative src is not external
        if host not in ALLOWED_SCRIPT_HOSTS:
            err("external-script-host", f"script from {host} (allowed: {', '.join(ALLOWED_SCRIPT_HOSTS)})")
        elif not _RE_PINNED[host].search(src):
            err("unpinned-cdn-library", f"{src} names no exact version")
    for href in _RE_LINK_HREF.findall(text):
        host = _host_of(href)
        if host is None:
            continue
        if host not in ALLOWED_STYLE_HOSTS:
            err("external-style-host", f"stylesheet/link from {host} (allowed: {', '.join(ALLOWED_STYLE_HOSTS)})")
        elif host in _RE_PINNED and not _RE_PINNED[host].search(href):
            err("unpinned-cdn-library", f"{href} names no exact version")
    for kind, rx in _RE_SECRETS:
        if rx.search(text):
            err("secret-like-string", f"{kind} pattern present -- a page never renders a secret")
    if "prefers-color-scheme" not in low:
        warn("no-color-scheme", "no prefers-color-scheme media query (light + dark tokens expected)")
    if 'name="viewport"' not in low and "name='viewport'" not in low:
        warn("no-viewport-meta", "no viewport meta (responsive at phone width expected)")
    if _RE_NETWORK.search(text):
        warn("network-call-present", "fetch/XHR/beacon/WebSocket present -- verify no data leaves the page")
    ok = not any(f["severity"] == "error" for f in findings)
    return {"ok": ok, "findings": findings, "bytes": size}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def page_name(page_path, name: Optional[str] = None) -> str:
    """The served file name: ``--name`` (or the file stem), sanitized to
    ``[A-Za-z0-9._-]``, always ending in ``.html``; ``index`` -> ``index.html``."""
    raw = (name or Path(page_path).stem or "page").strip()
    raw = _RE_NAME_BAD.sub("-", raw).strip("-.") or "page"
    if raw.lower().endswith(".htm"):
        raw = raw[:-4]
    if not raw.lower().endswith(".html"):
        raw += ".html"
    return raw


def mint_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def _now(now) -> _dt.datetime:
    if callable(now):
        now = now()
    if isinstance(now, _dt.datetime):
        return now if now.tzinfo else now.replace(tzinfo=_dt.timezone.utc)
    return local_port().utcnow()


def boundary_lines(result: Dict[str, Any]) -> List[str]:
    """The honest boundary printed with every private link."""
    lines = [
        "This link is a private URL, not a Claude artifact: no comments routed to Claude, "
        "no shared database, no organization share list, no host theme detection.",
        "The token in the URL IS the secret: anyone holding the link can open the page until "
        f"it expires ({result.get('expires_at')}) or you run `publish.py revoke {result.get('token')}`.",
    ]
    url = str(result.get("url") or "")
    if url.startswith("http://"):
        lines.append("Served over plain HTTP (no certificate configured): the token travels in "
                     "clear text on the wire.")
    if result.get("url_is_pattern"):
        lines.append("Nothing was deployed: the URL is a pattern until a human runs the generated "
                     "deploy.sh and records base_url.")
    return lines


# --------------------------------------------------------------------------- #
# the engine
# --------------------------------------------------------------------------- #


def _registry_entry(*, token: str, slug: str, name: str, adapter: str, source: str,
                    adapted: Dict[str, Any], created: _dt.datetime, expires: _dt.datetime) -> Dict[str, Any]:
    entry = {
        "token": token, "slug": slug, "name": name,
        "path": adapted.get("path") or f"/{slug}/p/{token}/{name}",
        "page": adapted.get("stored_at"), "source": source, "url": adapted.get("url"),
        "created_at": local_port().iso(created), "expires_at": local_port().iso(expires),
        "adapter": adapter, "revoked_at": None, "homepage": name == "index.html",
    }
    for key in ("object_uri", "remote_file", "url_is_pattern"):
        if key in adapted:
            entry[key] = adapted[key]
    return entry


def publish(page_path, config: Optional[Dict[str, Any]] = None, home=None, *,
            project_root=None, name: Optional[str] = None, slug: Optional[str] = None,
            start_server: bool = True, run: Optional[Callable] = None, now=None,
            force: bool = False) -> Dict[str, Any]:
    """Publish ``page_path`` per ``config`` (loaded from disk when ``None``).

    Returns ``{"ok", "mode", "adapter", "url", "token", "expires_at",
    "project_slug", "record_path", ...}`` -- ``url``/``token``/``expires_at``
    are ``None`` in claude mode, whose ``instructions`` say what to do next.
    A refused publish is ``{"ok": False, "error", "remediation", ...}``; this
    function never raises for a user-facing condition."""
    root = Path(project_root) if project_root is not None else Path.cwd()
    cfg = (publish_config.load_publish_config(root, home=home) if config is None
           else publish_config.normalize_config(config, root))
    page = Path(page_path)
    served_name = page_name(page, name)
    project = publish_config.slugify(slug) or cfg["project_slug"]
    mode = cfg["mode"]

    lint = check_page(page)
    errors = [f for f in lint["findings"] if f["severity"] == "error"]
    secret_hits = [f for f in errors if f["kind"] == "secret-like-string"]
    if secret_hits or (errors and not force):
        return {"ok": False, "mode": mode, "adapter": cfg["adapter"] if mode == "private-url" else None,
                "url": None, "token": None, "expires_at": None, "project_slug": project,
                "record_path": None, "error": "the page fails the page contract",
                "findings": lint["findings"],
                "remediation": ("remove the secret-shaped string; a page never renders a secret"
                                if secret_hits else
                                "fix the error findings (see skills/page-publishing/references/"
                                "page-contract.md) or pass --force to publish anyway")}

    if mode == "claude":
        outbox = root / OUTBOX_RELDIR
        outbox.mkdir(parents=True, exist_ok=True)
        target = outbox / served_name
        shutil.copyfile(str(page), str(target))
        return {"ok": True, "mode": "claude", "adapter": None, "url": None, "token": None,
                "expires_at": None, "project_slug": project, "record_path": str(target),
                "findings": lint["findings"],
                "instructions": (f"Hand this file to the Claude Artifact tool (publish {target}); "
                                 "no URL was minted -- the artifact's private link is the share link.")}

    adapter_name = cfg["adapter"]
    module = adapter_module(adapter_name)
    token = mint_token()
    created = _now(now)
    expires = created + _dt.timedelta(hours=int(cfg["token_ttl_hours"]))
    kwargs: Dict[str, Any] = dict(page_path=page, slug=project, token=token, name=served_name,
                                  config=cfg, home=home, start_server=start_server, run=run, now=created)
    if adapter_name == "gcp-cloud-run":
        kwargs["workspace"] = root
    adapted = module.publish_page(**kwargs)
    if not adapted.get("ok"):
        return {"ok": False, "mode": mode, "adapter": adapter_name, "url": None, "token": None,
                "expires_at": None, "project_slug": project, "record_path": None,
                "error": adapted.get("error"), "remediation": adapted.get("remediation"),
                "detail": adapted.get("detail"), "findings": lint["findings"]}

    registry = local_port().load_registry(home)
    entry = _registry_entry(token=token, slug=project, name=served_name, adapter=adapter_name,
                            source=str(page), adapted=adapted, created=created, expires=expires)
    registry["tokens"].append(entry)
    record_path = local_port().save_registry(registry, home)
    result = {"ok": True, "mode": mode, "adapter": adapter_name, "url": adapted["url"], "token": token,
              "expires_at": entry["expires_at"], "created_at": entry["created_at"],
              "project_slug": project, "record_path": str(record_path), "name": served_name,
              "homepage": entry["homepage"], "stored_at": adapted.get("stored_at"),
              "url_is_pattern": bool(adapted.get("url_is_pattern")),
              "warnings": list(adapted.get("warnings") or []), "findings": lint["findings"],
              "server": adapted.get("server"), "generated": adapted.get("generated"),
              "deploy_script": adapted.get("deploy_script")}
    result["boundary"] = boundary_lines(result)
    return result


def list_tokens(home=None, now=None) -> List[Dict[str, Any]]:
    """Every registry entry with a computed ``status`` (live/expired/revoked)."""
    lp = local_port()
    current = _now(now)
    out = []
    for entry in lp.load_registry(home).get("tokens", []):
        if isinstance(entry, dict):
            row = dict(entry)
            row["status"] = lp.entry_status(entry, current)
            out.append(row)
    return out


def revoke(token: str, home=None, *, config: Optional[Dict[str, Any]] = None, project_root=None,
           run: Optional[Callable] = None, now=None) -> Dict[str, Any]:
    """Mark ``token`` revoked in the registry and ask its adapter to remove the
    stored/uploaded file (best effort -- the registry mark alone makes the
    local server refuse it)."""
    lp = local_port()
    registry = lp.load_registry(home)
    for entry in registry.get("tokens", []):
        if isinstance(entry, dict) and entry.get("token") == token:
            if entry.get("revoked_at"):
                return {"ok": True, "token": token, "already_revoked": True,
                        "revoked_at": entry["revoked_at"]}
            entry["revoked_at"] = lp.iso(_now(now))
            lp.save_registry(registry, home)
            root = Path(project_root) if project_root is not None else Path.cwd()
            cfg = (publish_config.load_publish_config(root, home=home) if config is None
                   else publish_config.normalize_config(config, root))
            adapter_name = entry.get("adapter") or "local-port"
            try:
                removal = adapter_module(adapter_name).revoke_page(entry, cfg, home, run=run)
            except Exception as exc:  # noqa: BLE001 - removal is best effort
                removal = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            return {"ok": True, "token": token, "revoked_at": entry["revoked_at"],
                    "adapter": adapter_name, "removal": removal}
    return {"ok": False, "token": token, "error": "token not found in the registry",
            "remediation": "run `publish list` to see the recorded tokens"}


def serve_status(home=None) -> Dict[str, Any]:
    return local_port().status(home)


def serve_stop(home=None) -> Dict[str, Any]:
    return local_port().stop(home)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(enc, "replace").decode(enc, "replace"))


def _emit_publish(result: Dict[str, Any]) -> None:
    if not result.get("ok"):
        _print(f"REFUSED: {result.get('error')}")
        if result.get("detail"):
            _print(f"  detail: {result['detail']}")
        if result.get("remediation"):
            _print(f"  remediation: {result['remediation']}")
        for f in result.get("findings") or []:
            if f["severity"] == "error":
                _print(f"  [error] {f['kind']}: {f['detail']}")
        return
    for f in result.get("findings") or []:
        _print(f"[{f['severity']}] {f['kind']}: {f['detail']}")
    if result["mode"] == "claude":
        _print(f"mode: claude -- wrote {result['record_path']}")
        _print(result["instructions"])
        return
    _print(f"mode: private-url ({result['adapter']})")
    _print(f"url: {result['url']}")
    _print(f"token: {result['token']}  expires: {result['expires_at']}")
    _print(f"registry: {result['record_path']}")
    for w in result.get("warnings") or []:
        _print(f"WARNING: {w}")
    if result.get("deploy_script"):
        _print(f"deploy script (human runs it): {result['deploy_script']}")
    _print("Honest boundary:")
    for line in result.get("boundary") or []:
        _print(f"  - {line}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish a self-contained HTML page (claude mode "
                                                 "or a private URL).")
    parser.add_argument("--home", default=None, help="override ~ (the registry/server root)")
    parser.add_argument("--project-root", default=None, help="the workspace (default: cwd)")
    parser.add_argument("--json", action="store_true", default=False)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def _sub(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text)
        # accepted after the verb too; SUPPRESS keeps the global value when absent
        p.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        return p

    pub = _sub("publish", "Publish one page.")
    pub.add_argument("file")
    pub.add_argument("--slug", default=None, help="override the project slug")
    pub.add_argument("--name", default=None, help="served page name ('index' = the homepage)")
    pub.add_argument("--no-server-start", action="store_true",
                     help="local-port: do not start the background server")
    pub.add_argument("--force", action="store_true", help="publish despite contract errors "
                                                         "(never despite a secret-like string)")
    rev = _sub("revoke", "Revoke a token.")
    rev.add_argument("token")
    _sub("list", "List recorded tokens with status.")
    _sub("serve-status", "Local-port server status.")
    _sub("serve-stop", "Stop the local-port server.")
    chk = _sub("check", "Lint a page against the page contract.")
    chk.add_argument("file")
    return parser


def _dispatch(args: argparse.Namespace) -> int:
    home = Path(args.home) if args.home else None
    root = Path(args.project_root) if args.project_root else None
    if args.cmd == "publish":
        result = publish(args.file, None, home, project_root=root, name=args.name, slug=args.slug,
                         start_server=not args.no_server_start, force=args.force)
        if args.json:
            _print(json.dumps(result, indent=2, sort_keys=True, default=str))
        else:
            _emit_publish(result)
        return 0 if result.get("ok") else 1
    if args.cmd == "revoke":
        result = revoke(args.token, home, project_root=root)
        _print(json.dumps(result, indent=2, sort_keys=True, default=str) if args.json
               else (f"revoked {args.token} at {result.get('revoked_at')}" if result.get("ok")
                     else f"REFUSED: {result.get('error')}"))
        return 0 if result.get("ok") else 1
    if args.cmd == "list":
        rows = list_tokens(home)
        if args.json:
            _print(json.dumps(rows, indent=2, sort_keys=True, default=str))
        else:
            if not rows:
                _print("(no tokens recorded)")
            for row in rows:
                _print(f"[{row['status']:7s}] {row['token']}  {row.get('slug')}/{row.get('name')}  "
                       f"expires {row.get('expires_at')}  {row.get('adapter')}  {row.get('url')}")
        return 0
    if args.cmd == "serve-status":
        _print(json.dumps(serve_status(home), indent=2, sort_keys=True))
        return 0
    if args.cmd == "serve-stop":
        result = serve_stop(home)
        _print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("stopped") else 1
    result = check_page(args.file)
    if args.json:
        _print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for f in result["findings"]:
            _print(f"[{f['severity']}] {f['kind']}: {f['detail']}")
        _print("page contract: " + ("ok" if result["ok"] else "FAILED"))
    return 0 if result["ok"] else 1


def main(argv: Optional[List[str]] = None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code in (0, None) else 2
    try:
        return _dispatch(args)
    except Exception as exc:  # noqa: BLE001 - a crash must never read as a refusal
        _print(f"internal error: {type(exc).__name__}: {exc}")
        return 3


if __name__ == "__main__":
    sys.exit(main())
