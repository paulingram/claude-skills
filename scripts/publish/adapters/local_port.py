# -*- coding: utf-8 -*-
"""The `local-port` adapter: a stdlib token-checking page server on this machine.

Serves ONLY request paths that match a live (unrevoked, unexpired) token in the
publish registry; everything else is 404 -- never a directory listing, never a
file outside the pages store. Access is appended to
``<home>/.architect-team/publish/access.log`` with the token redacted. TLS when
``bind.tls_cert`` + ``bind.tls_key`` are set (``ssl.SSLContext``), plain HTTP
otherwise with a printed warning.

The server runs as a DETACHED background process (``start_detached``) so it
outlives the Claude Code session; a pidfile + state file under the publish dir
back ``status`` / ``stop``. The hourly expired-page prune rides on
``services/common/bg_runtime.Scheduler`` when that module is present (the
plugin checkout), and on a plain timer thread otherwise (the Cloud Run image,
which copies this file alone as ``server.py``).

SELF-CONTAINED BY DESIGN: this module imports nothing from the plugin at import
time. The registry helpers (``load_registry`` / ``save_registry`` /
``live_entry_for_path``) live here because the server is the consumer that must
run without the rest of the repo; the engine reuses them.

Stdlib-only; ASCII-only source.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import importlib.util
import json
import os
import shlex
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

REGISTRY_SCHEMA = "architect-team-publish-registry/v1"
PUBLISH_DIRNAME = Path(".architect-team") / "publish"
SERVICE_NAME = "ct6-publish-local-port"
PRUNE_INTERVAL_SECONDS = 3600
_WILDCARD_HOSTS = {"0.0.0.0", "::", "", "*"}

# --------------------------------------------------------------------------- #
# paths + time
# --------------------------------------------------------------------------- #


def state_paths(home=None) -> Dict[str, Path]:
    """Every on-disk location the adapter touches, under ``<home>``."""
    base = (Path(home) if home is not None else Path.home()) / PUBLISH_DIRNAME
    return {
        "dir": base,
        "registry": base / "registry.json",
        "pages": base / "pages",
        "access_log": base / "access.log",
        "pidfile": base / "local-port.pid",
        "statefile": base / "local-port.json",
        "server_log": base / "local-port.log",
    }


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def iso(ts: _dt.datetime) -> str:
    return ts.isoformat()


def parse_ts(value: Any) -> Optional[_dt.datetime]:
    """An aware UTC datetime from an ISO 8601 string, or ``None`` when it does
    not parse (a caller treats ``None`` as already expired -- fail-safe)."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        ts = _dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)
    return ts.astimezone(_dt.timezone.utc)


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #


def load_registry(home=None) -> Dict[str, Any]:
    """The registry object (``{"schema", "tokens": [...]}``); an empty one when
    the file is absent or unreadable. Never raises."""
    path = state_paths(home)["registry"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("tokens"), list):
        return {"schema": REGISTRY_SCHEMA, "tokens": []}
    data.setdefault("schema", REGISTRY_SCHEMA)
    return data


def save_registry(registry: Dict[str, Any], home=None) -> Path:
    """Atomic write (tmp + replace) of the registry."""
    path = state_paths(home)["registry"]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def entry_status(entry: Dict[str, Any], now: Optional[_dt.datetime] = None) -> str:
    """``live`` / ``revoked`` / ``expired`` (an unparseable expiry is expired)."""
    if entry.get("revoked_at"):
        return "revoked"
    expires = parse_ts(entry.get("expires_at"))
    if expires is None or expires <= (now or utcnow()):
        return "expired"
    return "live"


def _clean_request_path(raw: str) -> Optional[str]:
    """The decoded request path, or ``None`` when it carries anything a page
    path never does (traversal, backslashes, empty segments, control chars)."""
    path = raw.split("?", 1)[0].split("#", 1)[0]
    try:
        decoded = urllib.parse.unquote(path, errors="strict")
    except UnicodeDecodeError:
        return None
    if not decoded.startswith("/"):
        return None
    if ".." in decoded or "\\" in decoded or "//" in decoded or "\x00" in decoded:
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded):
        return None
    return decoded


def live_entry_for_path(registry: Dict[str, Any], raw_path: str,
                        now: Optional[_dt.datetime] = None) -> Optional[Dict[str, Any]]:
    """The live registry entry whose URL path matches ``raw_path`` exactly --
    or, for a homepage entry (``index.html``), whose token directory matches
    the trailing-slash form. Anything else is ``None`` (a 404)."""
    path = _clean_request_path(raw_path)
    if path is None:
        return None
    now = now or utcnow()
    for entry in registry.get("tokens", []):
        if not isinstance(entry, dict):
            continue
        entry_path = entry.get("path")
        if not isinstance(entry_path, str):
            continue
        matches = path == entry_path
        if not matches and entry.get("homepage") and entry_path.endswith("/index.html"):
            matches = path == entry_path[: -len("index.html")]
        if matches and entry_status(entry, now) == "live":
            return entry
    return None


def _redact_token(path: str) -> str:
    parts = path.split("/")
    for i, seg in enumerate(parts[:-1]):
        if seg == "p" and i + 1 < len(parts) and parts[i + 1]:
            tok = parts[i + 1]
            parts[i + 1] = tok[:6] + "..." if len(tok) > 6 else "..."
    return "/".join(parts)


# --------------------------------------------------------------------------- #
# the server
# --------------------------------------------------------------------------- #


class TokenPageServer(ThreadingHTTPServer):
    """``ThreadingHTTPServer`` carrying the publish-dir paths + an injectable
    clock. ``allow_reuse_address`` so a restart does not wait on TIME_WAIT."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, *, home, now_fn: Optional[Callable[[], _dt.datetime]] = None):
        self.home = home
        self.paths = state_paths(home)
        self.now_fn = now_fn or utcnow
        self.scheme = "http"
        self._log_lock = threading.Lock()
        super().__init__(address, handler)

    def log_access(self, client: str, method: str, path: str, status: int) -> None:
        line = f"{iso(self.now_fn())} {client} {method} {_redact_token(path)} {status}\n"
        try:
            with self._log_lock:
                self.paths["access_log"].parent.mkdir(parents=True, exist_ok=True)
                with self.paths["access_log"].open("a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError:
            pass  # logging must never take the page down

    def resolve(self, raw_path: str) -> Optional[Path]:
        """The on-disk page for a live-token request, else ``None``."""
        entry = live_entry_for_path(load_registry(self.home), raw_path, self.now_fn())
        if entry is None:
            return None
        pages_root = self.paths["pages"].resolve()
        candidate = (pages_root / entry["path"].lstrip("/")).resolve()
        try:
            candidate.relative_to(pages_root)
        except ValueError:
            return None  # defence in depth: never outside the store
        return candidate if candidate.is_file() else None


class TokenPageHandler(BaseHTTPRequestHandler):
    server_version = "ct6-publish/1"
    sys_version = ""

    def _deny(self) -> None:
        body = b"not found\n"
        self.send_response(404)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)
        self.server.log_access(self.client_address[0], self.command, self.path, 404)

    def _serve(self, head_only: bool) -> None:
        target = self.server.resolve(self.path)
        if target is None:
            self._deny()
            return
        try:
            body = target.read_bytes()
        except OSError:
            self._deny()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Robots-Tag", "noindex, nofollow")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)
        self.server.log_access(self.client_address[0], self.command, self.path, 200)

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        self._serve(head_only=False)

    def do_HEAD(self) -> None:  # noqa: N802
        self._serve(head_only=True)

    def do_POST(self) -> None:  # noqa: N802
        self._deny()

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST

    def log_message(self, *_args) -> None:  # the access log is the record
        return


def make_server(host: str, port: int, *, home, tls_cert: Optional[str] = None,
                tls_key: Optional[str] = None,
                now_fn: Optional[Callable[[], _dt.datetime]] = None) -> TokenPageServer:
    """A bound (not yet serving) server. ``port=0`` picks an ephemeral port
    (``server.server_address[1]``). TLS when both cert and key are given."""
    server = TokenPageServer((host, int(port)), TokenPageHandler, home=home, now_fn=now_fn)
    if tls_cert and tls_key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile=str(tls_cert), keyfile=str(tls_key))
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        server.scheme = "https"
    return server


# --------------------------------------------------------------------------- #
# expired-page prune (the bg_runtime consumer)
# --------------------------------------------------------------------------- #


def prune_expired(home=None, now: Optional[_dt.datetime] = None) -> List[str]:
    """Delete the stored file of every expired or revoked entry; return the
    removed paths. The registry entries themselves stay (the audit trail)."""
    now = now or utcnow()
    paths = state_paths(home)
    removed: List[str] = []
    pages_root = paths["pages"]
    for entry in load_registry(home).get("tokens", []):
        if not isinstance(entry, dict) or entry_status(entry, now) == "live":
            continue
        rel = entry.get("path")
        if not isinstance(rel, str):
            continue
        target = pages_root / rel.lstrip("/")
        if target.is_file():
            try:
                target.unlink()
                removed.append(str(target))
            except OSError:
                continue
            # drop the now-empty token directory
            try:
                target.parent.rmdir()
            except OSError:
                pass
    return removed


def _load_bg_runtime():
    """``services/common/bg_runtime`` when this file sits in the plugin checkout,
    else ``None`` (the Cloud Run image carries this file alone)."""
    candidate = Path(__file__).resolve().parents[3] / "services" / "common" / "bg_runtime.py"
    if not candidate.is_file():
        return None
    spec = importlib.util.spec_from_file_location("ct6_publish_bg_runtime", candidate)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_scheduler(home=None, now_fn: Optional[Callable[[], _dt.datetime]] = None):
    """A ``bg_runtime.Scheduler`` with the hourly prune task registered, or
    ``None`` when bg_runtime is unavailable. ``now_fn`` is the clock the prune
    judges expiry by (the server's clock; the real UTC clock by default)."""
    bg = _load_bg_runtime()
    if bg is None:
        return None
    clock = now_fn or utcnow
    scheduler = bg.Scheduler()
    scheduler.register(bg.ServiceTask("prune-expired-pages", PRUNE_INTERVAL_SECONDS,
                                      lambda: prune_expired(home, now=clock())))
    return scheduler


def _start_prune_thread(home, now_fn: Optional[Callable[[], _dt.datetime]] = None) -> threading.Thread:
    scheduler = build_scheduler(home, now_fn)
    clock = now_fn or utcnow

    def _loop() -> None:
        if scheduler is not None:
            scheduler.run_forever(tick_seconds=60.0)
        else:  # plain timer fallback (no bg_runtime on disk)
            while True:
                prune_expired(home, now=clock())
                time.sleep(PRUNE_INTERVAL_SECONDS)

    thread = threading.Thread(target=_loop, name="ct6-publish-prune", daemon=True)
    thread.start()
    return thread


# --------------------------------------------------------------------------- #
# process management (pidfile + state file)
# --------------------------------------------------------------------------- #


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":  # os.kill(pid, 0) would TERMINATE on Windows
        try:
            import ctypes  # noqa: WPS433 - stdlib, Windows only
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            code = ctypes.c_ulong()
            ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            kernel32.CloseHandle(handle)
            return bool(ok) and code.value == 259  # STILL_ACTIVE
        except Exception:  # noqa: BLE001 - a probe failure reads as "not running"
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    # A terminated child nobody reaped is a zombie: kill(pid, 0) still succeeds,
    # but it serves nothing. Linux exposes the state in /proc.
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="utf-8", errors="replace") as fh:
            fields = fh.read().rsplit(")", 1)
        if len(fields) == 2 and fields[1].split()[:1] == ["Z"]:
            return False
    except (OSError, IndexError, ValueError):
        pass
    return True


def _reap(pid: int) -> None:
    """Reap ``pid`` when it is our own child (a detached server started from
    this process); a no-op for anyone else's process."""
    if os.name == "nt":
        return
    try:
        os.waitpid(pid, os.WNOHANG)
    except (ChildProcessError, OSError):
        pass


def _read_state(paths: Dict[str, Path]) -> Dict[str, Any]:
    try:
        data = json.loads(paths["statefile"].read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_pid(paths: Dict[str, Path]) -> Optional[int]:
    try:
        return int(paths["pidfile"].read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def _write_state(paths: Dict[str, Path], state: Dict[str, Any]) -> None:
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["pidfile"].write_text(f"{state['pid']}\n", encoding="utf-8")
    paths["statefile"].write_text(json.dumps(state, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8", newline="\n")


def _clear_state(paths: Dict[str, Path]) -> None:
    for key in ("pidfile", "statefile"):
        try:
            paths[key].unlink()
        except OSError:
            pass


def status(home=None) -> Dict[str, Any]:
    """``{"running", "pid", "host", "port", "scheme", "stale", "pidfile", ...}``."""
    paths = state_paths(home)
    pid = _read_pid(paths)
    state = _read_state(paths)
    running = pid is not None and _pid_alive(pid)
    return {
        "running": running,
        "pid": pid,
        "stale": pid is not None and not running,
        "host": state.get("host"),
        "port": state.get("port"),
        "scheme": state.get("scheme"),
        "started_at": state.get("started_at"),
        "pidfile": str(paths["pidfile"]),
        "statefile": str(paths["statefile"]),
        "server_log": str(paths["server_log"]),
        "access_log": str(paths["access_log"]),
    }


def stop(home=None, wait_seconds: float = 3.0) -> Dict[str, Any]:
    """Terminate the detached server named by the pidfile; clear the state."""
    paths = state_paths(home)
    pid = _read_pid(paths)
    if pid is None:
        return {"stopped": False, "pid": None, "reason": "no pidfile"}
    if not _pid_alive(pid):
        _clear_state(paths)
        return {"stopped": False, "pid": pid, "reason": "stale pidfile removed"}
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        return {"stopped": False, "pid": pid, "reason": f"signal failed: {type(exc).__name__}"}
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        _reap(pid)
        if not _pid_alive(pid):
            break
        time.sleep(0.05)
    _reap(pid)
    _clear_state(paths)
    return {"stopped": not _pid_alive(pid), "pid": pid, "reason": "terminated"}


def build_serve_command(config: Dict[str, Any], home=None, python: Optional[str] = None) -> List[str]:
    """The argv that runs this module's ``serve`` verb for ``config``."""
    bind = config.get("bind") or {}
    argv = [python or sys.executable, str(Path(__file__).resolve()), "serve",
            "--home", str(Path(home) if home is not None else Path.home()),
            "--host", str(bind.get("host") or "0.0.0.0"),
            "--port", str(bind.get("port") or 8787)]
    if bind.get("tls_cert") and bind.get("tls_key"):
        argv += ["--tls-cert", str(bind["tls_cert"]), "--tls-key", str(bind["tls_key"])]
    return argv


def start_detached(config: Dict[str, Any], home=None, *, python: Optional[str] = None,
                   wait_seconds: float = 3.0) -> Dict[str, Any]:
    """Launch the server as a detached background process (new session on
    POSIX, detached process group on Windows) and wait for its state file."""
    paths = state_paths(home)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    argv = build_serve_command(config, home, python)
    popen_kwargs: Dict[str, Any] = {"stdin": subprocess.DEVNULL, "close_fds": True}
    if os.name == "nt":
        popen_kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True
    try:
        log_fh = paths["server_log"].open("ab")
    except OSError:
        log_fh = None
    try:
        proc = subprocess.Popen(argv, stdout=log_fh or subprocess.DEVNULL,
                                stderr=log_fh or subprocess.DEVNULL, **popen_kwargs)
    except OSError as exc:
        return {"started": False, "error": f"could not launch the server: {type(exc).__name__}: {exc}",
                "command": argv}
    finally:
        if log_fh is not None:
            log_fh.close()
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        state = _read_state(paths)
        if state.get("pid") == proc.pid:
            return {"started": True, "pid": proc.pid, "host": state.get("host"),
                    "port": state.get("port"), "scheme": state.get("scheme"),
                    "server_log": str(paths["server_log"]), "command": argv}
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    tail = ""
    try:
        tail = paths["server_log"].read_text(encoding="utf-8", errors="replace")[-800:]
    except OSError:
        pass
    return {"started": False, "pid": proc.pid, "returncode": proc.poll(),
            "error": "the server did not come up (see server_log)", "server_log_tail": tail,
            "server_log": str(paths["server_log"]), "command": argv}


def ensure_running(config: Dict[str, Any], home=None) -> Dict[str, Any]:
    """The running server's status, starting it when nothing is listening."""
    current = status(home)
    bind = config.get("bind") or {}
    if current["running"] and current.get("port") == int(bind.get("port") or 8787):
        current["started"] = False
        return current
    if current["stale"]:
        _clear_state(state_paths(home))
    launched = start_detached(config, home)
    launched["running"] = bool(launched.get("started"))
    return launched


def serve(home, host: str, port: int, *, tls_cert: Optional[str] = None,
          tls_key: Optional[str] = None, now_fn=None, write_state: bool = True,
          prune: bool = True) -> int:
    """Run the server in the FOREGROUND (the detached child's body). Writes the
    pidfile + state file, starts the prune thread, serves until SIGTERM/^C."""
    paths = state_paths(home)
    server = make_server(host, port, home=home, tls_cert=tls_cert, tls_key=tls_key, now_fn=now_fn)
    bound_host, bound_port = server.server_address[0], server.server_address[1]
    if write_state:
        _write_state(paths, {"pid": os.getpid(), "host": bound_host, "port": bound_port,
                             "scheme": server.scheme, "started_at": iso(utcnow()),
                             "pages": str(paths["pages"]), "registry": str(paths["registry"])})
    if prune:
        _start_prune_thread(home, server.now_fn)

    def _term(*_a) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    try:
        signal.signal(signal.SIGTERM, _term)
    except (ValueError, OSError):  # not the main thread / unsupported platform
        pass
    if server.scheme == "http":
        print(f"WARNING: serving plain HTTP on {bound_host}:{bound_port} -- the token "
              f"travels in clear text; set bind.tls_cert + bind.tls_key for HTTPS.", flush=True)
    print(f"{SERVICE_NAME} listening on {server.scheme}://{bound_host}:{bound_port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if write_state:
            _clear_state(paths)
    return 0


# --------------------------------------------------------------------------- #
# URL derivation + the adapter interface
# --------------------------------------------------------------------------- #


def _guess_local_ip() -> Optional[str]:
    """The interface address the OS would route out of -- a UDP ``connect``
    sends NO packet; it only resolves a route. ``None`` when unavailable."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("192.0.2.1", 9))  # TEST-NET-1: never actually sent
            return sock.getsockname()[0]
    except OSError:
        return None


def base_url_for(config: Dict[str, Any], warnings: Optional[List[str]] = None) -> str:
    """``base_url`` when the user stated one; else scheme + (external_ip | bind
    host | guessed local address) + port."""
    warnings = warnings if warnings is not None else []
    stated = config.get("base_url")
    if isinstance(stated, str) and stated.strip():
        return stated.strip().rstrip("/")
    bind = config.get("bind") or {}
    scheme = "https" if (bind.get("tls_cert") and bind.get("tls_key")) else "http"
    host = bind.get("external_ip") or None
    if not host:
        bound = str(bind.get("host") or "")
        if bound not in _WILDCARD_HOSTS:
            host = bound
        else:
            host = _guess_local_ip()
            if host:
                warnings.append(f"bind.host is a wildcard and bind.external_ip is unset; "
                                f"links use the guessed interface address {host}")
            else:
                host = "127.0.0.1"
                warnings.append("bind.host is a wildcard and no interface address could be "
                                "guessed; links use 127.0.0.1 -- set bind.external_ip")
    port = int(bind.get("port") or 8787)
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    return f"{scheme}://{host}" if default_port else f"{scheme}://{host}:{port}"


def url_path_for(slug: str, token: str, name: str) -> str:
    return f"/{slug}/p/{token}/{name}"


def store_page(page_path, slug: str, token: str, name: str, home=None) -> Path:
    """Copy the page into the pages store at ``<slug>/p/<token>/<name>``."""
    paths = state_paths(home)
    target = paths["pages"] / slug / "p" / token / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(page_path), str(target))
    return target


def publish_page(*, page_path, slug: str, token: str, name: str, config: Dict[str, Any],
                 home=None, start_server: bool = True, run=None, now=None) -> Dict[str, Any]:
    """Store the page and make sure the server is up. Returns the adapter result
    (``ok`` / ``url`` / ``stored_at`` / ``warnings`` / ``server``)."""
    del run, now  # the local adapter shells out to nothing
    warnings: List[str] = []
    stored = store_page(page_path, slug, token, name, home)
    base = base_url_for(config, warnings)
    path = url_path_for(slug, token, name)
    homepage = name == "index.html"
    url = base + (path[: -len("index.html")] if homepage else path)
    bind = config.get("bind") or {}
    scheme = "https" if (bind.get("tls_cert") and bind.get("tls_key")) else "http"
    if scheme == "http" and not str(base).startswith("https://"):
        warnings.append("plain HTTP: no bind.tls_cert + bind.tls_key configured -- the token "
                        "travels in clear text on the wire")
    server_state: Dict[str, Any] = {"running": None, "started": False}
    if start_server:
        server_state = ensure_running(config, home)
        if not server_state.get("running"):
            return {"ok": False, "error": server_state.get("error") or "the local server is not running",
                    "remediation": f"inspect {state_paths(home)['server_log']} and run "
                                   f"`python {Path(__file__).name} serve --home <home> --host "
                                   f"{bind.get('host')} --port {bind.get('port')}` by hand",
                    "stored_at": str(stored), "url": url, "warnings": warnings, "server": server_state}
    return {"ok": True, "url": url, "path": path, "stored_at": str(stored), "base_url": base,
            "scheme": "https" if url.startswith("https://") else "http", "homepage": homepage,
            "warnings": warnings, "server": server_state}


def revoke_page(entry: Dict[str, Any], config: Dict[str, Any], home=None, run=None) -> Dict[str, Any]:
    """Remove the stored file; the registry's ``revoked_at`` does the refusing."""
    del config, run
    rel = entry.get("path")
    if not isinstance(rel, str):
        return {"ok": False, "error": "entry has no path"}
    target = state_paths(home)["pages"] / rel.lstrip("/")
    removed = False
    if target.is_file():
        try:
            target.unlink()
            removed = True
            target.parent.rmdir()
        except OSError:
            pass
    return {"ok": True, "removed": removed, "stored_at": str(target)}


def boot_descriptor(config: Dict[str, Any], home=None, platform_name: Optional[str] = None) -> Dict[str, Any]:
    """A boot-start/restart descriptor (systemd / launchd / schtasks) for the
    serve command via ``bg_runtime.install_descriptor`` -- generated, never
    installed (registering it is the operator's step)."""
    bg = _load_bg_runtime()
    if bg is None:
        return {"ok": False, "error": "services/common/bg_runtime.py is not available here",
                "remediation": "run this from the plugin checkout"}
    plat = (platform_name or sys.platform).lower()
    plat = "windows" if plat.startswith("win") else ("darwin" if plat.startswith("darwin") else "linux")
    argv = build_serve_command(config, home)
    command = " ".join(shlex.quote(a) for a in argv) if plat != "windows" else subprocess.list2cmdline(argv)
    try:
        desc = bg.install_descriptor(plat, SERVICE_NAME, command)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    desc["ok"] = True
    return desc


# --------------------------------------------------------------------------- #
# CLI (the detached child runs ``serve``)
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CT6 local-port page server.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    srv = sub.add_parser("serve", help="Run the token-checking server in the foreground.")
    srv.add_argument("--home", default=None)
    srv.add_argument("--host", default="0.0.0.0")
    srv.add_argument("--port", type=int, default=8787)
    srv.add_argument("--tls-cert", default=None)
    srv.add_argument("--tls-key", default=None)
    srv.add_argument("--no-prune", action="store_true")
    for verb in ("status", "stop", "prune"):
        p = sub.add_parser(verb)
        p.add_argument("--home", default=None)
    desc = sub.add_parser("descriptor", help="Print a boot-start descriptor (never installs it).")
    desc.add_argument("--home", default=None)
    desc.add_argument("--platform", default=None, choices=["linux", "darwin", "windows"])
    desc.add_argument("--host", default="0.0.0.0")
    desc.add_argument("--port", type=int, default=8787)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    home = Path(args.home) if args.home else None
    if args.cmd == "serve":
        return serve(home, args.host, args.port, tls_cert=args.tls_cert, tls_key=args.tls_key,
                     prune=not args.no_prune)
    if args.cmd == "status":
        print(json.dumps(status(home), indent=2, sort_keys=True))
        return 0
    if args.cmd == "stop":
        result = stop(home)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["stopped"] else 1
    if args.cmd == "prune":
        print(json.dumps({"removed": prune_expired(home)}, indent=2))
        return 0
    cfg = {"bind": {"host": args.host, "port": args.port}}
    result = boot_descriptor(cfg, home, args.platform)
    print(result.get("content") if result.get("ok") else json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
