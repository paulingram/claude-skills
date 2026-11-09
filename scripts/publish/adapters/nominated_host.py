# -*- coding: utf-8 -*-
"""The `nominated-host` adapter: scp the page into a web root the user's own
server already serves; link it under their public base URL.

Remote layout: ``<web_root>/<slug>/p/<token>/<name>`` ->
``<public_base_url>/<slug>/p/<token>/<name>``. The token directory is created
with ``ssh <host> mkdir -p`` first (scp does not create parents). Both calls go
through the single ``run(cmd)`` seam; a missing ssh/scp returns a structured
error with remediation, never an exception.

The remote server does NOT check expiry (it is a plain web root): expiry is
enforced by the revoke verb removing the file, so a nominated host's TTL is
advisory until `publish --revoke` or the prune runs. Stated in the result.

Stdlib-only; ASCII-only source.
"""
from __future__ import annotations

import shlex
import subprocess
from typing import Any, Dict, List

DEFAULT_TIMEOUT = 300


def run(cmd: List[str], timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """The single subprocess seam (same contract as gcp_signed_url.run)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"{cmd[0]}: command not found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": f"{cmd[0]}: timed out after {timeout}s"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": f"{cmd[0]}: {type(exc).__name__}: {exc}"}
    return {"returncode": proc.returncode, "stdout": proc.stdout or "", "stderr": proc.stderr or ""}


def remote_paths(web_root: str, slug: str, token: str, name: str) -> Dict[str, str]:
    root = web_root.rstrip("/")
    directory = f"{root}/{slug}/p/{token}"
    return {"dir": directory, "file": f"{directory}/{name}"}


def build_commands(*, page_path, ssh: str, web_root: str, slug: str, token: str,
                   name: str) -> Dict[str, List[str]]:
    paths = remote_paths(web_root, slug, token, name)
    return {
        "mkdir": ["ssh", "-o", "BatchMode=yes", ssh, "mkdir -p " + shlex.quote(paths["dir"])],
        "scp": ["scp", "-q", "-o", "BatchMode=yes", str(page_path),
                f"{ssh}:{shlex.quote(paths['file'])}"],
        "rm": ["ssh", "-o", "BatchMode=yes", ssh, "rm -f " + shlex.quote(paths["file"])],
    }


def _required(block: Dict[str, Any], key: str) -> str:
    value = block.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else ""


def publish_page(*, page_path, slug: str, token: str, name: str, config: Dict[str, Any],
                 home=None, start_server: bool = True, run=None, now=None) -> Dict[str, Any]:
    del home, start_server, now
    runner = run or globals()["run"]
    block = config.get("nominated_host") or {}
    missing = [k for k in ("ssh", "web_root", "public_base_url") if not _required(block, k)]
    if missing:
        return {"ok": False, "error": f"nominated_host.{', nominated_host.'.join(missing)} not configured",
                "remediation": "set nominated_host.ssh (an `ssh` destination such as user@host or a "
                               "~/.ssh/config Host alias), nominated_host.web_root (the directory the "
                               "host already serves) and nominated_host.public_base_url (the https:// "
                               "base that serves that root) in .architect-team-publish.json"}
    ssh, web_root = _required(block, "ssh"), _required(block, "web_root")
    base = _required(block, "public_base_url").rstrip("/")
    cmds = build_commands(page_path=page_path, ssh=ssh, web_root=web_root, slug=slug,
                          token=token, name=name)
    for step in ("mkdir", "scp"):
        result = runner(cmds[step])
        if result["returncode"] == 127:
            return {"ok": False, "error": f"{cmds[step][0]} is not installed or not on PATH",
                    "remediation": "install an OpenSSH client (ssh + scp) or switch adapter to "
                                   "local-port / gcp-signed-url", "commands": [cmds[step]]}
        if result["returncode"] != 0:
            return {"ok": False, "error": f"{step} failed (exit {result['returncode']})",
                    "detail": (result.get("stderr") or "").strip()[-600:],
                    "remediation": f"check `ssh -o BatchMode=yes {ssh} true` works without a prompt "
                                   f"(key-based auth), and that {web_root} is writable",
                    "commands": [cmds[step]]}
    path = f"/{slug}/p/{token}/{name}"
    return {"ok": True, "url": base + path, "path": path, "base_url": base,
            "scheme": "https" if base.startswith("https://") else "http",
            "remote_file": remote_paths(web_root, slug, token, name)["file"],
            "warnings": ["the nominated host serves a plain web root: expiry is enforced only by "
                         "`publish --revoke <token>` (or the prune) removing the file"]
                        + ([] if base.startswith("https://") else
                           ["public_base_url is not https: the token travels in clear text"]),
            "commands": [cmds["mkdir"], cmds["scp"]]}


def revoke_page(entry: Dict[str, Any], config: Dict[str, Any], home=None, run=None) -> Dict[str, Any]:
    del home
    runner = run or globals()["run"]
    block = config.get("nominated_host") or {}
    ssh = _required(block, "ssh")
    remote = entry.get("remote_file")
    if not ssh or not isinstance(remote, str) or not remote:
        return {"ok": False, "error": "no ssh destination / remote_file to remove"}
    cmd = ["ssh", "-o", "BatchMode=yes", ssh, "rm -f " + shlex.quote(remote)]
    result = runner(cmd)
    if result["returncode"] != 0:
        return {"ok": False, "error": f"remote rm failed (exit {result['returncode']})",
                "detail": (result.get("stderr") or "").strip()[-400:], "command": cmd}
    return {"ok": True, "removed": remote, "command": cmd}
