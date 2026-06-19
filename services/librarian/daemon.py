# -*- coding: utf-8 -*-
"""The Librarian daemon entry point + the real `urllib` data source (REQ-003/004).

This is the runnable glue the boot descriptor targets. It wires the already-built
reused pieces — `LibraryIndex` (sqlite), the LLM adapter (`anthropic_client` when a
key resolves, else `FakeLLMClient`), the `Source` (the new `UrlSource` over a
topic->URL registry, else an injected one), and a `Librarian` (fetch -> extract ->
index -> metadata) — onto a `bg_runtime.Scheduler` and calls `run_forever()`.

HONEST BOUNDARY (per services/README.md): `UrlSource` does real network I/O at
RUNTIME, but it is an adapter behind the existing `Source` interface — tests inject
`StaticSource` + `FakeLLMClient` so the suite stays offline + stdlib-only. The
`anthropic` SDK stays a LAZY import behind `service_config.anthropic_client`; this
module imports only stdlib + in-repo siblings at module load, so
`services/separation.py::check_separation()` still passes.

Runnable as a PATH script (services/ has no __init__.py; do NOT rely on `python -m`):
    python <abs>/services/librarian/daemon.py --base-dir <state-dir>
The same sibling-import sys.path bootstrap as librarian.py is used so the in-repo
reuse points resolve by bare name.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any, Optional

_here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_here))                       # librarian, library_index, extract (siblings)
sys.path.insert(0, str(_here.parent / "common"))     # bg_runtime, service_config (shared substrate)

import bg_runtime as _bg  # noqa: E402
import librarian as _librarian  # noqa: E402
import library_index as _library_index  # noqa: E402
import service_config as _service_config  # noqa: E402

# Defaults — kept here so the installer and the daemon agree on the layout.
DEFAULT_INTERVAL_SECONDS = 3600
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_BYTES = 1024 * 1024  # 1 MB body cap — guard against runaway reads
_USER_AGENT = "ct6-librarian/1.0 (+https://github.com/architect-team)"

CONFIG_NAME = "config.json"
TOPICS_NAME = "topics.json"
INDEX_NAME = "index.sqlite"
BODIES_DIR = "bodies"
METADATA_DIR = "metadata"
LOG_NAME = "librarian.log.jsonl"


def _doc_id_for_url(url: str) -> str:
    """A stable, path-safe doc id derived from the URL (the Librarian re-sanitizes
    it before using it as a body filename, so this only needs to be stable)."""
    import hashlib

    return "url-" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


class UrlSource(_librarian.Source):
    """A stdlib-`urllib` concrete `Source` over a topic->URL registry (REQ-004).

    `fetch(topic)` requests each URL mapped to `topic`, returning one
    `{doc_id, text, source}` record per URL that fetched successfully. On ANY
    network / HTTP / decode error for a URL it logs the failure (to the optional
    `FileLogShipper`) and SKIPS that URL — it NEVER raises, so a single bad URL
    cannot crash a scheduler tick. The body is capped at `max_bytes` to avoid a
    pathological read.
    """

    def __init__(
        self,
        registry: dict[str, list[str]],
        *,
        log_shipper: Optional[Any] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ):
        self._registry = {k: list(v) for k, v in (registry or {}).items()}
        self._log = log_shipper
        self._timeout = float(timeout)
        self._max_bytes = int(max_bytes)

    def _ship(self, record: dict[str, Any]) -> None:
        if self._log is not None:
            try:
                self._log.ship(record)
            except Exception:  # logging must never break a fetch
                pass

    def _fetch_one(self, topic: str, url: str) -> Optional[dict[str, Any]]:
        req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                # read one byte beyond the cap so we can tell when we truncated.
                raw = resp.read(self._max_bytes + 1)
            if len(raw) > self._max_bytes:
                raw = raw[: self._max_bytes]
            text = raw.decode("utf-8", errors="replace")
            return {"doc_id": _doc_id_for_url(url), "text": text, "source": url}
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                ValueError, UnicodeError) as exc:
            self._ship({
                "event": "fetch-error", "topic": topic, "url": url,
                "error": repr(exc),
            })
            return None

    def fetch(self, topic: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for url in self._registry.get(topic, []):
            rec = self._fetch_one(topic, url)
            if rec is not None:
                out.append(rec)
        return out


# --------------------------------------------------------------------------- #
# state loading
# --------------------------------------------------------------------------- #

def _load_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _resolve_llm(config: "_service_config.ServiceConfig") -> Any:
    """The real Anthropic adapter when a key resolves, else `FakeLLMClient`. Never
    silently fakes a key — the caller surfaces the mode."""
    if config.has_key:
        try:
            return _service_config.anthropic_client(config)
        except Exception:
            # key set but SDK/network unavailable: fall back honestly to fake.
            return _service_config.FakeLLMClient()
    return _service_config.FakeLLMClient()


def build_daemon(
    base_dir: str | pathlib.Path,
    *,
    source: Optional[Any] = None,
    llm: Optional[Any] = None,
) -> tuple["_bg.Scheduler", "_librarian.Librarian"]:
    """Construct the scheduler + librarian from persisted state under `base_dir`.

    Loads `config.json` + `topics.json`, builds the `LibraryIndex` over
    `index.sqlite`, resolves the LLM (injected `llm` wins; else Anthropic-or-fake),
    constructs the `Source` (injected `source` wins; else a `UrlSource` over the
    topic registry with a `FileLogShipper`), builds a `Librarian` (file-folder body
    store + metadata dir), registers every topic, and registers one scheduler task
    per topic. Returns `(scheduler, librarian)`; the caller runs the loop.
    """
    base = pathlib.Path(base_dir)
    config = _service_config.load_config(base / CONFIG_NAME)
    registry: dict[str, list[str]] = _load_json(base / TOPICS_NAME, {})
    interval = int(config.extra.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))

    index = _library_index.LibraryIndex(str(base / INDEX_NAME))
    resolved_llm = llm if llm is not None else _resolve_llm(config)
    if source is not None:
        resolved_source: Any = source
    else:
        shipper = _bg.FileLogShipper(base / LOG_NAME)
        resolved_source = UrlSource(registry, log_shipper=shipper)

    librarian = _librarian.Librarian(
        index, resolved_llm, resolved_source,
        metadata_dir=base / METADATA_DIR, body_dir=base / BODIES_DIR,
    )
    for topic in registry:
        librarian.register_topic(topic)

    scheduler = _bg.Scheduler()
    for task in librarian.build_scheduler_tasks(interval_seconds=interval):
        scheduler.register(task)
    return scheduler, librarian


def main(
    argv: Optional[list[str]] = None,
    *,
    source: Optional[Any] = None,
    llm: Optional[Any] = None,
) -> int:
    """Daemon entry point (the boot descriptor's program-arguments target).

    `--base-dir <state>` selects the state layout. `--max-ticks N` bounds the loop
    for tests (production omits it => `run_forever()` runs unbounded). The injected
    `source`/`llm` keep tests offline; production resolves the real adapters.
    """
    parser = argparse.ArgumentParser(description="CT6 Librarian background daemon")
    parser.add_argument("--base-dir", required=True,
                        help="the librarian state directory")
    parser.add_argument("--max-ticks", type=int, default=None,
                        help="bound the scheduler loop (tests); omit for forever")
    parser.add_argument("--tick-seconds", type=float, default=1.0,
                        help="seconds to sleep between scheduler ticks")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    scheduler, _librarian_obj = build_daemon(args.base_dir, source=source, llm=llm)
    # Production: run_forever() unbounded. Tests pass --max-ticks for a bounded run.
    if args.max_ticks is not None:
        scheduler.run_forever(
            sleep_fn=lambda _s: None, tick_seconds=args.tick_seconds,
            max_ticks=args.max_ticks)
    else:  # pragma: no cover - the unbounded production loop is not run in tests
        scheduler.run_forever(tick_seconds=args.tick_seconds)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a path script
    sys.exit(main(sys.argv[1:]))
