"""Tests for the knowledge server core (KS-1, KS-6) — services/knowledge_server/server.py.

The hand-rolled JSON-RPC-2.0-over-stdio loop (newline-delimited framing):
initialize / tools/list / tools/call, driven in-process against StringIO
stdin/stdout — the structural refusal of a launch-dead `main()` (an entry point
no test exercises). No `mcp` SDK, no third-party import (check_separation green).
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from tests.helpers.module_loader import load_module

REPO_ROOT = Path(__file__).resolve().parents[1]

srv = load_module(REPO_ROOT / "services" / "knowledge_server" / "server.py", "ct6_ks_server")
oc = load_module(REPO_ROOT / "scripts" / "mcp_design" / "output_contract.py", "ct6_ks_oc")
sep = load_module(REPO_ROOT / "services" / "separation.py", "ct6_ks_sep")


class _FakeAdapter(srv.SourceAdapter):
    """A trivial read-only adapter registering an unshaped `echo` tool and a
    contract-shaped `shaped` tool whose handler deliberately returns a malformed
    payload — so the server's runtime contract enforcement can be exercised."""

    def __init__(self) -> None:
        self.calls: list = []
        self._shaped_contract = oc.build_output_contract(
            "shaped",
            [{"name": "value", "type": "string"}, {"name": "freshness", "type": "object"}],
        )

    def tools(self) -> list:
        def echo(args: dict) -> dict:
            self.calls.append(args)
            return {"echo": args.get("text", ""),
                    "freshness": {"verdict": "current", "basis": ["fake"]}}

        def shaped(args: dict) -> dict:
            return {}  # malformed on purpose: missing required 'value' + 'freshness'

        return [
            srv.Tool("echo", "echo text back", {"type": "object",
                     "properties": {"text": {"type": "string"}}}, echo),
            srv.Tool("shaped", "always malformed", {"type": "object", "properties": {}},
                     shaped, output_contract=self._shaped_contract),
        ]


def _drive(requests: list) -> dict:
    stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
    stdout = io.StringIO()
    server = srv.KnowledgeServer([_FakeAdapter()])
    srv.serve(stdin, stdout, server)
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    return {r.get("id"): r for r in responses}


def test_stdio_loop_initialize_list_call_end_to_end() -> None:
    by_id = _drive([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},  # notification: no reply
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "echo", "arguments": {"text": "hi"}}},
    ])
    # initialize handshake
    init = by_id[1]["result"]
    assert "protocolVersion" in init
    assert init["serverInfo"]["name"]
    assert "tools" in init["capabilities"]
    # tools/list enumerates registered tools with an input schema
    tools = {t["name"]: t for t in by_id[2]["result"]["tools"]}
    assert "echo" in tools and "inputSchema" in tools["echo"]
    # tools/call returns an MCP result carrying the structured payload
    call = by_id[3]["result"]
    assert call["structuredContent"]["echo"] == "hi"
    assert call["content"][0]["type"] == "text"
    assert json.loads(call["content"][0]["text"])["echo"] == "hi"


def test_notification_produces_no_response() -> None:
    stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    stdout = io.StringIO()
    srv.serve(stdin, stdout, srv.KnowledgeServer([_FakeAdapter()]))
    assert stdout.getvalue().strip() == ""  # a notification is never answered


def test_unknown_method_and_parse_error_are_jsonrpc_errors() -> None:
    stdin = io.StringIO(
        "this is not json\n"
        + json.dumps({"jsonrpc": "2.0", "id": 9, "method": "no/such"}) + "\n"
    )
    stdout = io.StringIO()
    srv.serve(stdin, stdout, srv.KnowledgeServer([_FakeAdapter()]))
    responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    parse_err = next(r for r in responses if r.get("id") is None)
    assert parse_err["error"]["code"] == -32700  # Parse error
    method_err = next(r for r in responses if r.get("id") == 9)
    assert method_err["error"]["code"] == -32601  # Method not found


def test_tools_call_validates_against_output_contract() -> None:
    # runtime contract enforcement: a handler that returns a malformed payload
    # surfaces as an MCP tool error, never a silently-wrong structured result.
    by_id = _drive([
        {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
         "params": {"name": "shaped", "arguments": {}}},
    ])
    result = by_id[7]["result"]
    assert result["isError"] is True
    assert "contract" in result["content"][0]["text"].lower()


def test_unknown_tool_is_rejected() -> None:
    by_id = _drive([
        {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
         "params": {"name": "nope", "arguments": {}}},
    ])
    assert by_id[5]["error"]["code"] == -32602  # invalid params: unknown tool


def test_duplicate_tool_name_across_adapters_is_rejected() -> None:
    try:
        srv.KnowledgeServer([_FakeAdapter(), _FakeAdapter()])
    except ValueError as exc:
        assert "echo" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate tool name must raise")


def test_package_is_import_clean_check_separation_green() -> None:
    # KS-1: the new package must not break the REPO-4 separability invariant.
    result = sep.check_separation()
    assert result["clean"] is True, f"non-separable imports: {result['violations']}"
    # and specifically none of the violations (if the suite ever regresses) are ours
    assert not any("knowledge_server" in str(v) for v in result["violations"])
