# -*- coding: utf-8 -*-
"""The CT6 knowledge server (KS-1) — a stdlib-only MCP server, JSON-RPC 2.0 over
stdio, hand-implemented (no `mcp` SDK, no third-party import, no LLM, no network).

Framing: NEWLINE-DELIMITED JSON-RPC — one JSON object per line in, one per line
out. This is what the MCP stdio transport uses (messages carry no embedded
newlines) and it makes the ENTRY POINT itself suite-testable: a test drives
`serve(stdin, stdout, server)` with `io.StringIO` end-to-end — the structural
refusal of deng-toolkit's launch-dead `main()` (an entry point no test exercises).

Three methods are implemented — `initialize` / `tools/list` / `tools/call` —
exactly what the tools need, not a general MCP implementation. Tools come from
pluggable READ-ONLY `SourceAdapter`s (the `DictionarySource` / `MapSource` seam);
each tool's response is validated against its closed output contract (KS-6) before
it leaves the server, so a malformed payload surfaces as an MCP tool error rather
than a silently-wrong result.

Runnable as a PATH script (services/ has no __init__.py — do NOT rely on
`python -m`): `python <repo>/services/knowledge_server/server.py --dictionary
<sidecar> --graph <lineage.json> [--map <MAP.md> ...]`. The same sibling-import
`sys.path` bootstrap the Librarian daemon uses lets the in-repo reuse points
resolve by bare name.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable, Optional

_HERE = Path(__file__).resolve().parent
for _rel in (_HERE, _HERE.parent / "common"):   # package siblings + bg_runtime
    _s = str(_rel)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import contracts as _contracts  # noqa: E402  (package sibling — separation-clean)
from adapter_base import ContractError, SourceAdapter, Tool  # noqa: E402,F401  (re-exported)

SERVER_NAME = "ct6-knowledge-server"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"

# JSON-RPC 2.0 error codes (the subset this server emits).
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Notification methods that expect NO response even though they carry a method.
_NOTIFICATION_METHODS = frozenset({
    "notifications/initialized", "initialized", "notifications/cancelled",
})


class KnowledgeServer:
    """The tool registry + JSON-RPC dispatcher. Adapters contribute tools; a
    duplicate tool name across adapters is a wiring error and is rejected."""

    def __init__(self, adapters: list, *, name: str = SERVER_NAME,
                 version: str = SERVER_VERSION) -> None:
        self.name = name
        self.version = version
        self.adapters = list(adapters)
        self._tools: dict[str, Tool] = {}
        for adapter in self.adapters:
            for tool in adapter.tools():
                if tool.name in self._tools:
                    raise ValueError(f"duplicate tool name across adapters: {tool.name!r}")
                self._tools[tool.name] = tool

    # -- registry -------------------------------------------------------------- #

    def tool_list(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                for t in self._tools.values()]

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Invoke a tool and validate its payload against the tool's contract."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(name)
        payload = tool.handler(arguments or {})
        if tool.output_contract is not None:
            result = _contracts.validate_payload(payload, tool.output_contract)
            if not result["valid"]:
                raise ContractError(
                    f"tool {name!r} produced a response violating its output "
                    f"contract: {result['errors']}")
        return payload

    # -- JSON-RPC dispatch ----------------------------------------------------- #

    def handle(self, request: Any) -> Optional[dict]:
        """Dispatch one parsed JSON-RPC request. Returns the response dict, or
        `None` for a notification (a request with no `id`)."""
        if not isinstance(request, dict):
            return self._error(None, INVALID_REQUEST, "Invalid Request: not an object")
        # A request with no "id" member is a notification — never answered.
        if "id" not in request:
            return None
        req_id = request.get("id")
        method = request.get("method")
        if method == "initialize":
            return self._ok(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": self.name, "version": self.version},
            })
        if method == "tools/list":
            return self._ok(req_id, {"tools": self.tool_list()})
        if method == "tools/call":
            return self._tools_call(req_id, request.get("params") or {})
        if method == "ping":
            return self._ok(req_id, {})
        if method in _NOTIFICATION_METHODS:
            # a client that (wrongly) attaches an id to a notification method still
            # gets a benign empty ack rather than a method-not-found.
            return self._ok(req_id, {})
        return self._error(req_id, METHOD_NOT_FOUND, f"Method not found: {method!r}")

    def _tools_call(self, req_id: Any, params: dict) -> dict:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            payload = self.call_tool(name, arguments)
        except KeyError:
            return self._error(req_id, INVALID_PARAMS, f"unknown tool: {name!r}")
        except ContractError as exc:
            # a contract violation is an execution error, surfaced as an MCP tool
            # error result (isError) — a wrong shape must never leave silently.
            return self._ok(req_id, self._tool_error(str(exc)))
        except Exception as exc:  # a tool execution failure is an MCP result, not transport error
            return self._ok(req_id, self._tool_error(f"tool error: {exc}"))
        return self._ok(req_id, {
            "content": [{"type": "text",
                         "text": json.dumps(payload, sort_keys=True, ensure_ascii=False)}],
            "structuredContent": payload,
            "isError": False,
        })

    @staticmethod
    def _tool_error(message: str) -> dict:
        return {"content": [{"type": "text", "text": message}], "isError": True}

    @staticmethod
    def _ok(req_id: Any, result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: Any, code: int, message: str, data: Any = None) -> dict:
        err: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return {"jsonrpc": "2.0", "id": req_id, "error": err}


def _write(stdout, obj: Any) -> None:
    stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    stdout.flush()


def serve(stdin, stdout, server: KnowledgeServer, *, max_messages: Optional[int] = None) -> int:
    """The stdio loop — read newline-delimited JSON-RPC from `stdin`, write
    responses to `stdout`. Returns the number of messages processed. `max_messages`
    bounds the loop for tests; a real daemon omits it and runs until EOF.
    """
    processed = 0
    for line in stdin:
        if max_messages is not None and processed >= max_messages:
            break
        stripped = line.strip()
        if not stripped:
            continue
        processed += 1
        try:
            request = json.loads(stripped)
        except (ValueError, TypeError):
            _write(stdout, server._error(None, PARSE_ERROR, "Parse error"))
            continue
        if isinstance(request, list):  # tolerate a JSON-RPC batch
            batch = [r for r in (server.handle(x) for x in request) if r is not None]
            if batch:
                _write(stdout, batch)
            continue
        response = server.handle(request)
        if response is not None:
            _write(stdout, response)
    return processed


def discover_sidecars(repo_root: Optional[str]) -> dict:
    """Discover the conventional CT6 sidecars under a repo root (stdlib globbing).

    The 'where CT6 sidecars conventionally live' knowledge belongs in the server,
    so the installer can register a portable `server.py --repo-root <repo>` instead
    of hardcoded absolute paths. Returns a dict with only the keys that EXIST — a
    missing sidecar is reported by OMISSION (source absent), never a crash:

      * ``dictionary``  -> ``<root>/docs/data-dictionary.json``
      * ``annotations`` -> ``<root>/docs/data-annotations/`` (dir)
      * ``graph``       -> ``<root>/lineage-graph.json``
      * ``map_files``   -> sorted ``<root>/docs/*_MAP.md``
    """
    if not repo_root:
        return {}
    root = Path(repo_root)
    found: dict = {}
    dictionary = root / "docs" / "data-dictionary.json"
    if dictionary.is_file():
        found["dictionary"] = str(dictionary)
    annotations = root / "docs" / "data-annotations"
    if annotations.is_dir():
        found["annotations"] = str(annotations)
    graph = root / "lineage-graph.json"
    if graph.is_file():
        found["graph"] = str(graph)
    docs = root / "docs"
    if docs.is_dir():
        maps = sorted(str(p) for p in docs.glob("*_MAP.md"))
        if maps:
            found["map_files"] = maps
    return found


def build_adapters_from_paths(
    *,
    dictionary: Optional[str] = None,
    annotations: Optional[str] = None,
    graph: Optional[str] = None,
    map_files: Optional[list] = None,
    repo_root: Optional[str] = None,
    changed_paths_provider: Optional[Callable] = None,
    discover: bool = True,
) -> list:
    """Construct the configured source adapters. The adapters are imported LAZILY
    (they are package siblings; a module-load import would also make `server.py`
    un-loadable before they exist).

    When `repo_root` is set, the conventional CT6 sidecars under it are discovered
    and fill in every source NOT named explicitly (per-source precedence: an
    explicit `--dictionary`/`--graph`/`--map`/`--annotations` overrides its
    discovered counterpart; discovery augments the rest). With neither an explicit
    path nor a discoverable sidecar, the clear no-source ValueError stands.
    """
    import dictionary_source  # noqa: E402  lazy package siblings
    import map_source  # noqa: E402
    discovered = discover_sidecars(repo_root) if discover else {}
    dictionary = dictionary or discovered.get("dictionary")
    annotations = annotations or discovered.get("annotations")
    graph = graph or discovered.get("graph")
    map_files = map_files or discovered.get("map_files") or []
    adapters: list = []
    if dictionary:
        adapters.append(dictionary_source.DictionarySource(
            dictionary, annotations_dir=annotations, repo_root=repo_root,
            changed_paths_provider=changed_paths_provider))
    if graph:
        adapters.append(map_source.MapSource(
            graph, map_files=map_files, repo_root=repo_root,
            changed_paths_provider=changed_paths_provider))
    if not adapters:
        raise ValueError(
            "no source configured: pass --dictionary and/or --graph, or "
            "--repo-root pointing at a repo with docs/data-dictionary.json and/or "
            "lineage-graph.json")
    return adapters


def build_scheduler(adapters: list, *, interval_seconds: int = 300):
    """Compose a `bg_runtime.Scheduler` that re-indexes each adapter on a tick
    (KS-7). `bg_runtime` is a services sibling; imported lazily to keep server.py's
    module-load surface minimal."""
    import bg_runtime  # noqa: E402  (services/common sibling)
    scheduler = bg_runtime.Scheduler()
    for adapter in adapters:
        task = adapter.scheduler_task(interval_seconds)
        if task is not None:
            scheduler.register(task)
    return scheduler


def main(argv: Optional[list] = None, *, stdin=None, stdout=None) -> int:
    """Entry point (the MCP registration's program target). Builds the configured
    adapters and serves stdio. `stdin`/`stdout` are injectable so the suite drives
    the real entry point end-to-end (the launch-dead-main refusal)."""
    import argparse
    parser = argparse.ArgumentParser(
        description="CT6 knowledge server — stdlib MCP (JSON-RPC over stdio)")
    parser.add_argument("--dictionary", help="path to data-dictionary.json")
    parser.add_argument("--annotations", help="path to a docs/data-annotations/ dir")
    parser.add_argument("--graph", help="path to lineage-graph.json")
    parser.add_argument("--map", action="append", default=[],
                        help="path to a *_MAP.md (repeatable)")
    parser.add_argument("--repo-root", default=None,
                        help="repo root for git-drift freshness AND conventional-sidecar "
                             "auto-discovery (docs/data-dictionary.json, lineage-graph.json, "
                             "docs/*_MAP.md) when explicit --dictionary/--graph are omitted")
    parser.add_argument("--max-messages", type=int, default=None,
                        help="bound the stdio loop (tests); omit for a real daemon")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    adapters = build_adapters_from_paths(
        dictionary=args.dictionary, annotations=args.annotations,
        graph=args.graph, map_files=args.map, repo_root=args.repo_root)
    server = KnowledgeServer(adapters)
    serve(stdin if stdin is not None else sys.stdin,
          stdout if stdout is not None else sys.stdout,
          server, max_messages=args.max_messages)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised in-process via serve()/main()
    sys.exit(main(sys.argv[1:]))
