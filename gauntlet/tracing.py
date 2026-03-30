"""
gauntlet/tracing.py

Automatic tracing for multi-agent workflows via the @trace decorator.

Usage
-----
from gauntlet import trace

@trace("Router")
async def router(input: str) -> str:
    # your agent logic
    return result

@trace("Writer")
async def writer(input: str) -> str:
    return result

@trace("Validator")
async def validator(input: str) -> str:
    return result

async def my_workflow(scenario: str) -> str:
    route  = await router(scenario)
    draft  = await writer(route)
    result = await validator(draft)
    return result

# Run eval normally — tracing is automatic
report = await run_eval(request, agent_fn=my_workflow)

What happens internally
-----------------------
Each @trace decorator registers the function under its agent name.
When the workflow runs, every decorated call is intercepted:
  - Input and output are recorded
  - Latency is measured
  - Errors are caught and stored (not swallowed)
  - The call chain is preserved in order

The runner reads these spans after each scenario and judges
each step individually, producing per-agent pass rates and
pinpointing exactly where in the chain failures originate.
"""

from __future__ import annotations

import asyncio
import functools
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any


# --------------------------------------------------------------------------- #
# Global span store — one per eval run, reset between scenarios
# --------------------------------------------------------------------------- #

@dataclass
class AgentSpan:
    """One recorded call to a traced agent function."""
    agent_name:  str
    input:       str
    output:      str
    latency_ms:  int
    error:       str | None = None
    skipped:     bool = False   # True if upstream failure prevented this agent from running


class _SpanStore:
    """
    Thread-local span storage.
    Stores spans in the order agents were called so the flow can be
    reconstructed exactly as it happened.
    """
    def __init__(self):
        self._spans: list[AgentSpan] = []
        self._active: bool = False

    def start(self):
        """Called by the runner before each scenario."""
        self._spans.clear()
        self._active = True

    def stop(self):
        """Called by the runner after each scenario."""
        self._active = False

    def record(self, span: AgentSpan):
        if self._active:
            self._spans.append(span)

    def get_spans(self) -> list[AgentSpan]:
        return list(self._spans)

    def has_spans(self) -> bool:
        return len(self._spans) > 0

    def agent_names(self) -> list[str]:
        """Return agent names in the order they were first called."""
        seen = []
        for span in self._spans:
            if span.agent_name not in seen:
                seen.append(span.agent_name)
        return seen


# Module-level singleton — shared across all decorated functions
_store = _SpanStore()


def get_store() -> _SpanStore:
    """Used by the runner to access recorded spans."""
    return _store


# --------------------------------------------------------------------------- #
# @trace decorator
# --------------------------------------------------------------------------- #

def trace(agent_name: str) -> Callable:
    """
    Decorator that automatically records every call to an agent function.

    Parameters
    ----------
    agent_name:
        Human-readable name shown in the report e.g. "Router", "Writer".
        Keep it short and descriptive.

    Example
    -------
    @trace("Router")
    async def router(input: str) -> str:
        response = await client.messages.create(...)
        return response.content[0].text
    """
    def decorator(fn: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> str:
            # Extract the input — first positional arg or 'input' kwarg
            raw_input = args[0] if args else kwargs.get("input", "")
            input_str = str(raw_input)[:2000]

            t0 = time.time()
            try:
                result = await fn(*args, **kwargs)
                latency_ms = int((time.time() - t0) * 1000)
                output_str = str(result)[:2000]

                _store.record(AgentSpan(
                    agent_name=agent_name,
                    input=input_str,
                    output=output_str,
                    latency_ms=latency_ms,
                ))
                return result

            except Exception as exc:
                latency_ms = int((time.time() - t0) * 1000)
                _store.record(AgentSpan(
                    agent_name=agent_name,
                    input=input_str,
                    output="[error]",
                    latency_ms=latency_ms,
                    error=str(exc),
                ))
                # Re-raise so the workflow can handle it
                raise

        # Tag the wrapper so the runner can detect traced workflows
        wrapper._is_gauntlet_traced = True
        wrapper._gauntlet_agent_name = agent_name
        return wrapper

    return decorator


# --------------------------------------------------------------------------- #
# GauntletTracer — kept for backwards compatibility with manual tracing
# --------------------------------------------------------------------------- #

class GauntletTracer:
    """
    Legacy manual tracer. Use @trace decorator instead for new workflows.

    Kept so existing code using tracer.log() still works.
    """
    def log(
        self,
        agent_name: str,
        input: str,
        output: str,
        error: str | None = None,
    ) -> None:
        _store.record(AgentSpan(
            agent_name=agent_name,
            input=str(input)[:2000],
            output=str(output)[:2000],
            latency_ms=0,
            error=error,
        ))

    def reset(self) -> None:
        _store.start()

    def has_spans(self) -> bool:
        return _store.has_spans()

    def get_spans(self) -> list[AgentSpan]:
        return _store.get_spans()