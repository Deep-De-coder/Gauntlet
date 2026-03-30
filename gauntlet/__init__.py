"""
Gauntlet — adversarial eval harness for multi-agent Claude API pipelines.

Quick start
-----------
from gauntlet import trace
from gauntlet.core.runner import run_eval
from gauntlet.core.models import EvalRequest, EvalMode

# 1. Decorate each agent in your workflow
@trace("Router")
async def router(input: str) -> str:
    ...

@trace("Writer")
async def writer(input: str) -> str:
    ...

# 2. Define your workflow normally
async def my_workflow(scenario: str) -> str:
    route = await router(scenario)
    result = await writer(route)
    return result

# 3. Run eval — tracing is automatic
request = EvalRequest(
    goal="Classify and respond to support tickets",
    agent_description="Router + Writer multi-agent pipeline",
    agent_api_key="sk-ant-...",
    mode=EvalMode.full,
    runs=5,
)
report = await run_eval(request, agent_fn=my_workflow)
print(f"Pass rate: {report.pass_rate:.0%}")
print(f"Bottleneck: {report.bottleneck_agent}")
"""

from gauntlet.tracing import trace, GauntletTracer

__all__ = ["trace", "GauntletTracer"]
__version__ = "0.1.3"