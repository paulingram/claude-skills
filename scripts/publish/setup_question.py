# -*- coding: utf-8 -*-
"""The one setup question: where should this project's shareable pages live?

Three callables `architect-team-setup` (scripts/setup/setup.py) wires in:

* ``detect_ecosystem(run=..., home=..., which=...)`` -- what the machine offers:
  is gcloud on PATH AND logged in, does the box have a globally routable
  address (from ``hostname -I``-like LOCAL info only -- no network call), and
  which ``Host`` aliases ``~/.ssh/config`` names. Every probe is injectable so
  the result is deterministic under test.
* ``question(ecosystem)`` -- the exact ``AskUserQuestion`` payload (text,
  header, the four options, the recommendation) WITH the security notes said
  out loud: the token sits in the URL, a local port is an attack surface, a
  cloud service costs money, plain HTTP leaks the token.
* ``write_config(answers, project_root, home=...)`` -- the ONE place a publish
  config is written: with the human's recorded answer, once; an existing
  project config is never overwritten unless ``overwrite=True`` (the human
  asked). The reader (hooks/publish_config.py) stays read-only.

Conditional-dependency posture (the setup.py CONDITIONAL_PLUGINS idea): gcloud
and ssh/scp are REPORTED present or absent with a remediation line, and never
gate setup -- a missing tool only changes which option is recommended.

Stdlib-only; ASCII-only source.
"""
from __future__ import annotations

import importlib.util
import ipaddress
import json
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "hooks" / "publish_config.py"


def _load_config_module():
    spec = importlib.util.spec_from_file_location("ct6_publish_config_for_setup", _CONFIG_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError(f"cannot load {_CONFIG_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish_config = _load_config_module()

OPTION_CLAUDE = "Claude artifacts only (default)"
OPTION_GCP = "GCP signed URL (recommended when gcloud is present)"
OPTION_PORT = "A port on this machine"
OPTION_HOST = "A host I nominate"

# label / short key / adapter name -> (mode, adapter)
CHOICES: Dict[str, tuple] = {
    OPTION_CLAUDE: ("claude", "local-port"),
    "claude": ("claude", "local-port"),
    OPTION_GCP: ("private-url", "gcp-signed-url"),
    "gcp": ("private-url", "gcp-signed-url"),
    "gcp-signed-url": ("private-url", "gcp-signed-url"),
    "gcp-cloud-run": ("private-url", "gcp-cloud-run"),
    OPTION_PORT: ("private-url", "local-port"),
    "port": ("private-url", "local-port"),
    "local-port": ("private-url", "local-port"),
    OPTION_HOST: ("private-url", "nominated-host"),
    "host": ("private-url", "nominated-host"),
    "nominated-host": ("private-url", "nominated-host"),
}

SECURITY_NOTES = [
    "A private link carries its token IN THE URL: anyone holding the link opens the page until "
    "it expires (default 72h) or is revoked; it leaks through browser history, chat logs and "
    "referrers.",
    "A port on this machine is a listening service on your dev box (plain HTTP unless you "
    "supply a certificate -- the token then travels in clear text).",
    "A GCP bucket or Cloud Run service costs money and needs IAM; it gets HTTPS for free, "
    "which is why it is recommended when gcloud is present.",
    "Nothing is opened, uploaded or deployed until this answer is recorded, and the recorded "
    "file is human-owned: agents read it, never change it.",
]


def run(cmd: List[str], timeout: int = 20) -> Dict[str, Any]:
    """The subprocess seam (same contract as the adapters' ``run``)."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": f"{cmd[0]}: command not found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": f"{cmd[0]}: timed out"}
    except OSError as exc:
        return {"returncode": 126, "stdout": "", "stderr": f"{cmd[0]}: {type(exc).__name__}"}
    return {"returncode": proc.returncode, "stdout": proc.stdout or "", "stderr": proc.stderr or ""}


def _public_candidates(runner: Callable, platform_name: str) -> List[str]:
    """Interface addresses from LOCAL info: ``hostname -I`` on Linux, else the
    resolver's view of the local hostname (hosts file / mDNS; no remote call
    is made on purpose and any failure yields an empty list)."""
    addresses: List[str] = []
    if platform_name.startswith("linux"):
        result = runner(["hostname", "-I"])
        if result.get("returncode") == 0:
            addresses.extend(result.get("stdout", "").split())
    if not addresses:
        try:
            _, _, addrs = socket.gethostbyname_ex(socket.gethostname())
            addresses.extend(addrs)
        except (socket.gaierror, socket.herror, OSError, UnicodeError):
            pass
    return addresses


def public_ip_from(addresses: List[str]) -> Optional[str]:
    """The first globally routable address, or ``None``."""
    for raw in addresses:
        try:
            ip = ipaddress.ip_address(raw.strip())
        except ValueError:
            continue
        if ip.is_global:
            return str(ip)
    return None


def ssh_hosts_from(config_text: str) -> List[str]:
    """``Host`` aliases from an ssh config, wildcards and negations skipped."""
    hosts: List[str] = []
    for line in config_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "host":
            for alias in parts[1].split():
                if any(ch in alias for ch in "*?!") or alias in hosts:
                    continue
                hosts.append(alias)
    return hosts


def detect_ecosystem(run: Optional[Callable] = None, home=None, which: Optional[Callable] = None,
                     platform_name: Optional[str] = None) -> Dict[str, Any]:
    """What the machine offers, with every probe injectable."""
    runner = run or globals()["run"]
    which_fn = which or shutil.which
    plat = (platform_name or sys.platform).lower()
    home_path = Path(home) if home is not None else Path.home()

    gcloud_on_path = bool(which_fn("gcloud"))
    account: Optional[str] = None
    if gcloud_on_path:
        auth = runner(["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
        if auth.get("returncode") == 0:
            first = (auth.get("stdout") or "").strip().splitlines()
            account = first[0].strip() if first and first[0].strip() else None

    ssh_config = home_path / ".ssh" / "config"
    try:
        ssh_text = ssh_config.read_text(encoding="utf-8", errors="replace")
    except OSError:
        ssh_text = ""

    return {
        "gcloud": gcloud_on_path and account is not None,
        "gcloud_on_path": gcloud_on_path,
        "gcloud_account": account,
        "public_ip": public_ip_from(_public_candidates(runner, plat)),
        "ssh_hosts": ssh_hosts_from(ssh_text),
        "ssh": bool(which_fn("ssh")),
        "scp": bool(which_fn("scp")),
        "remediation": {
            "gcloud": None if gcloud_on_path and account else (
                "install the Google Cloud CLI and run `gcloud auth login` (optional: only the "
                "GCP adapters need it)" if not gcloud_on_path else
                "run `gcloud auth login` (gcloud is installed but no account is active)"),
            "ssh": None if which_fn("ssh") and which_fn("scp") else
            "install an OpenSSH client (optional: only the nominated-host adapter needs it)",
        },
    }


def question(ecosystem: Dict[str, Any]) -> Dict[str, Any]:
    """The exact AskUserQuestion payload for the one setup question."""
    gcloud = bool(ecosystem.get("gcloud"))
    public_ip = ecosystem.get("public_ip")
    hosts = list(ecosystem.get("ssh_hosts") or [])
    detected = []
    detected.append("gcloud: " + (f"logged in as {ecosystem.get('gcloud_account')}" if gcloud else
                                  ("installed, not logged in" if ecosystem.get("gcloud_on_path")
                                   else "not found")))
    detected.append("public address: " + (public_ip or "none detected (private/NAT only)"))
    detected.append("ssh hosts in ~/.ssh/config: " + (", ".join(hosts) if hosts else "none"))
    options = [
        {"label": OPTION_CLAUDE,
         "description": "Pages go to the Claude Artifact tool as today; no URL, no port, no upload. "
                        "Viewers need a Claude login."},
        {"label": OPTION_GCP,
         "description": ("A signed Google Cloud Storage link (HTTPS, no server to run, expires with "
                         "the TTL). Needs gcloud logged in and a bucket you own. ") +
                        ("gcloud is ready on this machine." if gcloud else
                         "gcloud is NOT ready here -- install + `gcloud auth login` first.")},
        {"label": OPTION_PORT,
         "description": ("A stdlib token-checking server on this machine" +
                         (f" (reachable at {public_ip})" if public_ip else
                          " (no public address detected: LAN-only unless you forward a port)") +
                         "; plain HTTP unless you supply a certificate.")},
        {"label": OPTION_HOST,
         "description": "scp into a web root your own server already serves" +
                        (f" (ssh hosts found: {', '.join(hosts[:4])})" if hosts else
                         " (no ~/.ssh/config hosts found; you will name the destination)") + "."},
    ]
    recommended = OPTION_GCP if gcloud else OPTION_CLAUDE
    text = ("Where should this project's shareable pages live? CT6 builds self-contained HTML pages "
            "(reports, dashboards, explainers). By default they go to the Claude Artifact tool. A "
            "private URL lets someone WITHOUT a Claude login open them through a tokened link.\n"
            "Detected: " + "; ".join(detected) + ".\n"
            "Security, said plainly: " + " ".join(SECURITY_NOTES) + "\n"
            f"Recommended here: {recommended}.")
    return {"question": text, "header": "Pages", "options": options, "recommended": recommended,
            "multiSelect": False, "notes": list(SECURITY_NOTES), "detected": detected}


def resolve_choice(choice: Any) -> Optional[tuple]:
    """``(mode, adapter)`` for a label, short key or adapter name; ``None`` if unknown."""
    if not isinstance(choice, str):
        return None
    key = choice.strip()
    if key in CHOICES:
        return CHOICES[key]
    low = key.lower()
    for label, pair in CHOICES.items():
        if label.lower() == low:
            return pair
    return None


def _gitignore_ok(project_root: Path) -> bool:
    try:
        text = (project_root / ".gitignore").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return any(line.strip() == publish_config.PUBLISH_CONFIG_FILENAME for line in text.splitlines())


def write_config(answers: Dict[str, Any], project_root, home=None, *, overwrite: bool = False,
                 user_level: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Write the project config from the recorded answer (and optionally merge
    machine-wide defaults into the user-level file). Never overwrites an
    existing project config unless ``overwrite`` is True."""
    root = Path(project_root)
    pair = resolve_choice((answers or {}).get("choice"))
    if pair is None:
        return {"written": False, "reason": "unknown choice",
                "valid_choices": [OPTION_CLAUDE, OPTION_GCP, OPTION_PORT, OPTION_HOST]}
    mode, adapter = pair
    path = publish_config.project_config_path(root)
    if path.exists() and not overwrite:
        return {"written": False, "reason": "exists", "path": str(path),
                "hint": "the answer is already recorded; edit the file by hand or pass overwrite"}

    doc: Dict[str, Any] = {"schema": publish_config.SCHEMA, "mode": mode, "adapter": adapter}
    slug = publish_config.slugify(answers.get("project_slug"))
    doc["project_slug"] = slug
    ttl = answers.get("token_ttl_hours")
    doc["token_ttl_hours"] = int(ttl) if isinstance(ttl, int) and not isinstance(ttl, bool) and ttl > 0 \
        else publish_config.DEFAULT_TOKEN_TTL_HOURS
    for block in ("bind", "gcp", "nominated_host"):
        merged = dict(publish_config.DEFAULTS[block])
        given = answers.get(block)
        if isinstance(given, dict):
            merged.update(given)
        doc[block] = merged
    base = answers.get("base_url")
    doc["base_url"] = base.strip().rstrip("/") if isinstance(base, str) and base.strip() else None
    doc["_comment"] = ("Written once by architect-team-setup from your answer. Human-owned and "
                       "IMMUTABLE TO AGENTS -- see " + publish_config.PUBLISH_EXAMPLE_FILENAME +
                       " for every field and the security notes.")
    root.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")

    user_path = None
    if isinstance(user_level, dict) and user_level:
        upath = publish_config.user_config_path(home)
        upath.parent.mkdir(parents=True, exist_ok=True)
        existing: Dict[str, Any] = {}
        try:
            loaded = json.loads(upath.read_text(encoding="utf-8"))
            existing = loaded if isinstance(loaded, dict) else {}
        except (OSError, ValueError):
            existing = {}
        existing.setdefault("schema", publish_config.SCHEMA)
        for key, value in user_level.items():
            if key in ("bind", "gcp", "nominated_host") and isinstance(value, dict):
                block = dict(existing.get(key) or {})
                block.update(value)
                existing[key] = block
            else:
                existing[key] = value
        upath.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8", newline="\n")
        user_path = str(upath)

    gitignore_ok = _gitignore_ok(root)
    return {"written": True, "path": str(path), "mode": mode, "adapter": adapter,
            "user_path": user_path, "gitignore_ok": gitignore_ok,
            "gitignore_hint": None if gitignore_ok else
            f"add `{publish_config.PUBLISH_CONFIG_FILENAME}` to {root / '.gitignore'} -- the file is "
            f"local per checkout and may name a bucket, a host or a port"}


def main(argv: Optional[List[str]] = None) -> int:
    """``detect`` prints the ecosystem; ``question`` prints the AskUserQuestion
    payload for it (both JSON). Writing is left to setup.py, which holds the
    human's answer."""
    args = list(sys.argv[1:] if argv is None else argv)
    verb = args[0] if args else "question"
    eco = detect_ecosystem()
    if verb == "detect":
        print(json.dumps(eco, indent=2, sort_keys=True))
    elif verb == "question":
        print(json.dumps(question(eco), indent=2))
    else:
        print("usage: setup_question.py [detect|question]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
