# -*- coding: utf-8 -*-
"""The read-only source-adapter seam (KS-2) — stdlib-only, dependency-free.

`Tool` + `SourceAdapter` + `ContractError` live here (not in `server.py`) so the
server core AND the `DictionarySource` / `MapSource` adapters share ONE definition
by bare name — `adapter_base` is a unique stem, so every module resolves the same
`sys.modules['adapter_base']`, keeping class identity consistent without any
module bare-importing the (non-unique) `server` stem. This module imports only the
standard library, so it is trivially `check_separation`-clean.
"""
from __future__ import annotations

from typing import Any, Callable, Optional


class ContractError(Exception):
    """A tool handler produced a payload that violates its closed output contract
    (KS-6). The server never emits an unvalidated structured result."""


class Tool:
    """A registered tool: a name, an input schema (for `tools/list`), a handler
    `(arguments: dict) -> payload dict`, and — when set — a closed output contract
    the payload is validated against before it is returned."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: Callable[[dict], dict],
        *,
        output_contract: Optional[dict[str, Any]] = None,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler
        self.output_contract = output_contract


class SourceAdapter:
    """The pluggable READ-ONLY source-adapter seam (KS-2).

    An adapter reads a repo-committed sidecar and registers tools; it NEVER writes
    the artifacts it serves. `tools()` returns the tool bindings; `refresh()`
    re-indexes when the backing sidecar changed (KS-7) and returns whether it did;
    `scheduler_task()` optionally exposes that refresh as a `bg_runtime.ServiceTask`.
    Handlers read the adapter's CURRENT state at call time, so a rebuild after a
    refresh reflects new content.
    """

    def tools(self) -> list:
        raise NotImplementedError

    def tools_by_name(self) -> dict:
        return {t.name: t for t in self.tools()}

    def refresh(self) -> bool:
        return False

    def scheduler_task(self, interval_seconds: int = 300):  # pragma: no cover - overridden
        return None
