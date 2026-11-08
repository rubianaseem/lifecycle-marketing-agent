"""Optional model access with retry, backoff and a hard fallback.

- No ANTHROPIC_API_KEY: get_client() returns None and every caller uses templates.
- With a key: AnthropicClient is used. Errors are retried with exponential backoff and jitter;
  after the last attempt the caller falls back to templates and the audit log records why.
- Tests and evals inject FakeClient / ScriptedClient to simulate 429s, timeouts and a
  compromised model that echoes injected text.
"""
from __future__ import annotations

import os
import random
import time


class LLMError(Exception):
    def __init__(self, msg: str, retryable: bool = True, retry_after: float | None = None):
        super().__init__(msg)
        self.retryable = retryable
        self.retry_after = retry_after


class AnthropicClient:
    name = "claude"

    def __init__(self, model: str | None = None):
        import anthropic  # imported lazily so the offline path needs no package
        self._sdk = anthropic
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        try:
            msg = self._client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                               messages=[{"role": "user", "content": user}])
        except self._sdk.RateLimitError as exc:  # 429
            ra = None
            try:
                ra = float(exc.response.headers.get("retry-after"))
            except Exception:
                pass
            raise LLMError("rate_limited", True, ra) from exc
        except (self._sdk.APIConnectionError, self._sdk.APITimeoutError) as exc:
            raise LLMError("connection", True) from exc
        except self._sdk.APIStatusError as exc:
            raise LLMError(f"status_{exc.status_code}", exc.status_code >= 500) from exc
        return "".join(getattr(b, "text", "") for b in msg.content)


class ScriptedClient:
    """Test double. `script` is a list of outputs; an Exception instance is raised instead."""
    name = "scripted"

    def __init__(self, script: list, default: str | None = None):
        self.script = list(script)
        self.default = default
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, max_tokens: int = 600) -> str:
        self.calls.append({"system": system, "user": user})
        if self.script:
            item = self.script.pop(0)
        elif self.default is not None:
            item = self.default
        else:
            raise LLMError("script_exhausted", False)
        if isinstance(item, Exception):
            raise item
        return item(system, user) if callable(item) else item


def get_client():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return AnthropicClient()
    except Exception:  # package missing or misconfigured: stay offline, caller logs it
        return None


def call_with_retry(client, system: str, user: str, *, attempts: int = 3, base_delay: float = 1.0,
                    max_delay: float = 20.0, sleep=time.sleep, log=None) -> str | None:
    """Return model text, or None after the retry budget is spent. Never raises LLMError."""
    for attempt in range(1, attempts + 1):
        try:
            return client.complete(system, user)
        except LLMError as exc:
            if log:
                log({"event": "llm_error", "attempt": attempt, "error": str(exc), "retryable": exc.retryable})
            if not exc.retryable or attempt == attempts:
                return None
            delay = exc.retry_after if exc.retry_after else min(max_delay, base_delay * 2 ** (attempt - 1))
            sleep(delay + random.uniform(0, delay * 0.1))
    return None
