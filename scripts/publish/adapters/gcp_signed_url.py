# -*- coding: utf-8 -*-
"""The `gcp-signed-url` adapter: upload with `gcloud storage cp`, link with a
time-limited signed URL. No server to run; HTTPS for free.

Every subprocess goes through ONE ``run(cmd)`` seam so tests monkeypatch it (or
pass ``run=`` explicitly). A missing or unauthenticated gcloud never raises to
the user: the adapter returns ``{"ok": False, "error", "remediation"}``.

Object layout: ``gs://<bucket>/<slug>/p/<token>/<name>`` -- the same
``<base>/<slug>/p/<token>/<page>`` shape every adapter uses, so the registry,
the revoke verb and the printed links read the same regardless of host.

Stdlib-only; ASCII-only source.
"""
from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List, Optional

GCLOUD = "gcloud"
STORAGE_HOST = "https://storage.googleapis.com"
MAX_SIGNED_URL_HOURS = 168  # V4 signed URLs: 7 days
DEFAULT_TIMEOUT = 300

_URL_RE = re.compile(r"https://\S+")


def run(cmd: List[str], timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """The single subprocess seam: ``{"returncode", "stdout", "stderr"}``.
    A missing binary reads as returncode 127 (never an exception)."""
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


def _missing_gcloud(result: Dict[str, Any]) -> bool:
    return result.get("returncode") == 127 or "command not found" in (result.get("stderr") or "")


def object_uri(bucket: str, slug: str, token: str, name: str) -> str:
    return f"gs://{bucket}/{slug}/p/{token}/{name}"


def parse_signed_url(stdout: str) -> Optional[str]:
    """`gcloud storage sign-url` prints YAML-ish ``signed_url: https://...``;
    older builds print the bare URL. Take the ``signed_url:`` line first, else
    the first https token."""
    for line in (stdout or "").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("signed_url:"):
            value = stripped.split(":", 1)[1].strip().strip("'\"")
            if value.startswith("https://"):
                return value
    match = _URL_RE.search(stdout or "")
    return match.group(0).strip("'\"") if match else None


def build_commands(*, page_path, bucket: str, slug: str, token: str, name: str,
                   ttl_hours: int, project: Optional[str] = None,
                   impersonate: Optional[str] = None) -> Dict[str, List[str]]:
    uri = object_uri(bucket, slug, token, name)
    cp = [GCLOUD, "storage", "cp", str(page_path), uri,
          "--content-type=text/html; charset=utf-8", "--cache-control=no-store"]
    sign = [GCLOUD, "storage", "sign-url", uri, f"--duration={int(ttl_hours)}h", "--http-verb=GET"]
    rm = [GCLOUD, "storage", "rm", uri]
    if project:
        for cmd in (cp, sign, rm):
            cmd.append(f"--project={project}")
    if impersonate:
        sign.append(f"--impersonate-service-account={impersonate}")
    return {"cp": cp, "sign": sign, "rm": rm, "uri": [uri]}


def publish_page(*, page_path, slug: str, token: str, name: str, config: Dict[str, Any],
                 home=None, start_server: bool = True, run=None, now=None) -> Dict[str, Any]:
    del home, start_server, now
    runner = run or globals()["run"]
    gcp = config.get("gcp") or {}
    bucket = gcp.get("bucket")
    if not isinstance(bucket, str) or not bucket.strip():
        return {"ok": False, "error": "gcp.bucket is not configured",
                "remediation": "set gcp.bucket in .architect-team-publish.json (a bucket you own; "
                               "create one with `gcloud storage buckets create gs://<name>`)"}
    warnings: List[str] = []
    ttl = int(config.get("token_ttl_hours") or 72)
    if ttl > MAX_SIGNED_URL_HOURS:
        warnings.append(f"token_ttl_hours {ttl} exceeds the signed-URL maximum; clamped to "
                        f"{MAX_SIGNED_URL_HOURS}h")
        ttl = MAX_SIGNED_URL_HOURS
    cmds = build_commands(page_path=page_path, bucket=bucket.strip(), slug=slug, token=token,
                          name=name, ttl_hours=ttl, project=gcp.get("project"),
                          impersonate=gcp.get("impersonate_service_account"))
    uploaded = runner(cmds["cp"])
    if uploaded["returncode"] != 0:
        if _missing_gcloud(uploaded):
            return {"ok": False, "error": "gcloud is not installed or not on PATH",
                    "remediation": "install the Google Cloud CLI (https://cloud.google.com/sdk/docs/install) "
                                   "and run `gcloud auth login`; or switch adapter to local-port / "
                                   "nominated-host", "commands": [cmds["cp"]]}
        return {"ok": False, "error": f"gcloud storage cp failed (exit {uploaded['returncode']})",
                "detail": (uploaded.get("stderr") or "").strip()[-600:],
                "remediation": "check `gcloud auth list`, that the bucket exists and your account "
                               "can write to it (roles/storage.objectCreator), and the project flag",
                "commands": [cmds["cp"]]}
    signed = runner(cmds["sign"])
    url = parse_signed_url(signed.get("stdout", "")) if signed["returncode"] == 0 else None
    if url is None:
        return {"ok": False, "error": f"gcloud storage sign-url failed (exit {signed['returncode']})",
                "detail": (signed.get("stderr") or signed.get("stdout") or "").strip()[-600:],
                "remediation": "signing needs a service-account key or impersonation: run "
                               "`gcloud auth activate-service-account` or set "
                               "gcp.impersonate_service_account (roles/iam.serviceAccountTokenCreator); "
                               "the object was uploaded and can be removed with "
                               + " ".join(cmds["rm"]),
                "uploaded": cmds["uri"][0], "commands": [cmds["cp"], cmds["sign"]]}
    return {"ok": True, "url": url, "object_uri": cmds["uri"][0],
            "base_url": f"{STORAGE_HOST}/{bucket.strip()}", "path": f"/{slug}/p/{token}/{name}",
            "scheme": "https", "ttl_hours": ttl, "warnings": warnings,
            "commands": [cmds["cp"], cmds["sign"]]}


def revoke_page(entry: Dict[str, Any], config: Dict[str, Any], home=None, run=None) -> Dict[str, Any]:
    """Delete the object -- the signed URL then 404s regardless of its expiry."""
    del home
    runner = run or globals()["run"]
    uri = entry.get("object_uri")
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        return {"ok": False, "error": "entry carries no object_uri"}
    cmd = [GCLOUD, "storage", "rm", uri]
    project = (config.get("gcp") or {}).get("project")
    if project:
        cmd.append(f"--project={project}")
    result = runner(cmd)
    if result["returncode"] != 0:
        return {"ok": False, "error": f"gcloud storage rm failed (exit {result['returncode']})",
                "detail": (result.get("stderr") or "").strip()[-400:], "command": cmd}
    return {"ok": True, "removed": uri, "command": cmd}
