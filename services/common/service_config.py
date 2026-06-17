# -*- coding: utf-8 -*-
"""Shared service-tier config + LLM adapter interface — stdlib-only.

Encodes the decided key model: ONE Anthropic API key serves BOTH as the
background LLM key (the Librarian's configurable Claude API, LIB-1/LIB-3) AND the
triage sign-up identity (SEC-2). The key is resolved from the config file or the
`ANTHROPIC_API_KEY` env var, and is NEVER written to logs (`redacted()` masks it).

The LLM itself is reached through an adapter (`LLMClient`) so the deterministic
service logic is testable with a `FakeLLMClient` and the real Anthropic call (SDK
+ network) is a documented boundary, not a hard dependency of the stdlib core.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Optional

DEFAULT_MODEL = "claude-opus-4-8"
STORAGE_MODES = ("mempalace", "file-folder")  # LIB-8 — vector store OR indexed file folder


class ServiceConfig:
    """Service-tier configuration. `anthropic_key` is the single shared key (LLM +
    sign-up). `storage_mode` selects the Librarian's store (LIB-8)."""

    def __init__(
        self,
        anthropic_key: Optional[str] = None,
        *,
        llm_model: str = DEFAULT_MODEL,
        storage_mode: str = "mempalace",
        extra: Optional[dict[str, Any]] = None,
    ):
        if storage_mode not in STORAGE_MODES:
            raise ValueError(f"storage_mode must be one of {STORAGE_MODES}")
        self.anthropic_key = anthropic_key
        self.llm_model = llm_model
        self.storage_mode = storage_mode
        self.extra = dict(extra or {})

    @property
    def has_key(self) -> bool:
        return bool(self.anthropic_key)

    # The LLM key and the sign-up key are the SAME key (the decided model).
    @property
    def llm_key(self) -> Optional[str]:
        return self.anthropic_key

    @property
    def signup_key(self) -> Optional[str]:
        return self.anthropic_key

    def redacted(self) -> dict[str, Any]:
        """A safe-to-log view — the key is masked to its last 4 chars."""
        k = self.anthropic_key
        masked = (("…" + k[-4:]) if k and len(k) >= 4 else ("set" if k else None))
        return {
            "anthropic_key": masked,
            "llm_model": self.llm_model,
            "storage_mode": self.storage_mode,
            "extra": self.extra,
        }

    def to_dict(self) -> dict[str, Any]:
        # WARNING: includes the RAW Anthropic key — for persistence only, NEVER
        # for logging. Use `redacted()` for any log / display / report output.
        return {
            "anthropic_key": self.anthropic_key,
            "llm_model": self.llm_model,
            "storage_mode": self.storage_mode,
            "extra": self.extra,
        }


def load_config(
    path: Optional[str | Path] = None,
    env: Optional[dict[str, str]] = None,
) -> ServiceConfig:
    """Load a `ServiceConfig`. The Anthropic key resolves from (in order) the
    config file's `anthropic_key`, then `ANTHROPIC_API_KEY` in `env` (defaults to
    `os.environ`). Other fields come from the file when present."""
    env = os.environ if env is None else env
    data: dict[str, Any] = {}
    if path is not None:
        p = Path(path)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
    key = data.get("anthropic_key") or env.get("ANTHROPIC_API_KEY")
    return ServiceConfig(
        anthropic_key=key,
        llm_model=data.get("llm_model", DEFAULT_MODEL),
        storage_mode=data.get("storage_mode", "mempalace"),
        extra=data.get("extra"),
    )


# --- LLM adapter (the background Claude API, behind an interface) ------------ #

class LLMClient:
    """Abstract background LLM client (LIB-1 — a configurable Claude API). The real
    Anthropic adapter (SDK + network) implements `complete`; the stdlib core uses
    `FakeLLMClient` in tests. Keeping this an interface means no network/SDK
    dependency leaks into the deterministic service logic."""

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        raise NotImplementedError


class FakeLLMClient(LLMClient):
    """Deterministic test/offline LLM: returns `responder(prompt)` (default echo).
    Lets the Librarian/Evaluator logic be exercised without a live model."""

    def __init__(self, responder: Optional[Callable[[str], str]] = None):
        self._responder = responder or (lambda p: f"[fake-llm] {p[:80]}")
        self.calls: list[str] = []

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        self.calls.append(prompt)
        return self._responder(prompt)


def anthropic_client(config: ServiceConfig):
    """Return a real Anthropic-backed `LLMClient` — or raise with an actionable
    message. HONEST BOUNDARY: this needs the `anthropic` SDK + network + a valid
    key, none guaranteed in a stdlib-only / offline context. The service logic
    accepts any `LLMClient`, so production injects this and tests inject
    `FakeLLMClient`."""
    if not config.has_key:
        raise RuntimeError("no Anthropic API key configured (set ANTHROPIC_API_KEY or the config)")
    try:
        import anthropic  # type: ignore  # noqa: F401
    except Exception as exc:  # pragma: no cover - SDK not installed in stdlib-only env
        raise RuntimeError(
            "the `anthropic` SDK is not installed — install it in the service's own "
            "environment (the service tier may carry its own deps, REPO-4), or inject "
            "a custom LLMClient"
        ) from exc

    class _AnthropicClient(LLMClient):  # pragma: no cover - exercised only with the SDK + network
        def __init__(self, key: str, model: str):
            self._client = anthropic.Anthropic(api_key=key)
            self._model = model

        def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
            msg = self._client.messages.create(
                model=self._model, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")

    return _AnthropicClient(config.anthropic_key, config.llm_model)
