"""
Core eval runner — orchestrates all four agents.

Flow:
  1. ScenarioAgent    → generates test inputs from the goal
  2. AdversarialAgent → (if mode=adversarial|full) adds hostile inputs
  3. JudgeAgent       → scores each agent output pass/fail
  4. ReportAgent      → synthesises recommendations

Multi-agent tracing (automatic):
  If the agent_fn contains functions decorated with @trace, the runner
  automatically records every sub-agent call, judges each step, and
  reports per-agent pass rates so you can pinpoint the bottleneck.

  No tracer argument needed — just decorate your agent functions:

  from gauntlet import trace

  @trace("Router")
  async def router(input): ...

  @trace("Writer")
  async def writer(input): ...
"""
from __future__ import annotations
import time
import uuid
from collections import defaultdict
from typing import Callable, Awaitable

from gauntlet.core.models import (
    AgentPassRate,
    AgentStepResult,
    EvalMode,
    EvalReport,
    EvalRequest,
    ScenarioResult,
)
from gauntlet.agents.scenario    import ScenarioAgent
from gauntlet.agents.judge       import JudgeAgent
from gauntlet.agents.adversarial import AdversarialAgent
from gauntlet.agents.report      import ReportAgent
from gauntlet.storage.db         import save_report
from gauntlet.tracing            import get_store


# --------------------------------------------------------------------------- #
# Agent factory — builds real callable from request fields
# --------------------------------------------------------------------------- #

def _build_agent_fn(request: EvalRequest) -> Callable[[str], Awaitable[str]]:
    if request.agent_provider.value == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=request.agent_api_key)

        async def anthropic_agent(scenario_input: str) -> str:
            response = await client.messages.create(
                model=request.agent_model,
                max_tokens=1024,
                system=request.agent_system_prompt,
                messages=[{"role": "user", "content": scenario_input}],
            )
            return response.content[0].text

        return anthropic_agent

    elif request.agent_provider.value == "openai":
        try:
            import openai
        except ImportError:
            raise ImportError("openai not installed. Run: pip install openai")

        client = openai.AsyncOpenAI(api_key=request.agent_api_key)

        async def openai_agent(scenario_input: str) -> str:
            response = await client.chat.completions.create(
                model=request.agent_model,
                messages=[
                    {"role": "system", "content": request.agent_system_prompt},
                    {"role": "user", "content": scenario_input},
                ],
                max_tokens=1024,
            )
            return response.choices[0].message.content

        return openai_agent

    raise ValueError(f"Unsupported provider: {request.agent_provider}")


# --------------------------------------------------------------------------- #
# Trace evaluation — judge each recorded step
# --------------------------------------------------------------------------- #

async def _evaluate_spans(
    judge: JudgeAgent,
    goal: str,
    criteria_str: str | None,
    all_agent_names: list[str],
) -> tuple[list[AgentStepResult], str | None]:
    """
    Judge each span recorded by the @trace decorator.

    Also marks agents that were never reached due to upstream failures
    so the report can show the full call chain including skipped steps.
    """
    store = get_store()
    spans = store.get_spans()
    recorded_names = {s.agent_name for s in spans}

    step_results: list[AgentStepResult] = []
    first_failure_agent: str | None = None
    upstream_failed = False

    for agent_name in all_agent_names:
        # Agent was never called — upstream failure prevented it
        if agent_name not in recorded_names:
            step_results.append(AgentStepResult(
                agent_name=agent_name,
                input="[not reached]",
                output="[not reached]",
                passed=False,
                reasoning="This agent was never called — an upstream agent failed first.",
                latency_ms=0,
                skipped=True,
            ))
            continue

        # Find this agent's span
        span = next(s for s in spans if s.agent_name == agent_name)

        if span.error:
            result = AgentStepResult(
                agent_name=agent_name,
                input=span.input,
                output=span.output,
                passed=False,
                reasoning=f"Agent crashed: {span.error}",
                latency_ms=span.latency_ms,
                error=span.error,
            )
        elif upstream_failed:
            # Upstream failed but this agent still ran — judge its output
            # but flag that context may be corrupted
            verdict = await judge.evaluate(
                goal=f"[{agent_name}] {goal}",
                scenario_input=span.input,
                agent_output=span.output,
                success_criteria=criteria_str,
            )
            result = AgentStepResult(
                agent_name=agent_name,
                input=span.input,
                output=span.output,
                passed=verdict["passed"],
                reasoning=verdict["reasoning"] + " (note: upstream agent had issues)",
                latency_ms=span.latency_ms,
            )
        else:
            verdict = await judge.evaluate(
                goal=f"[{agent_name}] {goal}",
                scenario_input=span.input,
                agent_output=span.output,
                success_criteria=criteria_str,
            )
            result = AgentStepResult(
                agent_name=agent_name,
                input=span.input,
                output=span.output,
                passed=verdict["passed"],
                reasoning=verdict["reasoning"],
                latency_ms=span.latency_ms,
            )

        step_results.append(result)

        if not result.passed and first_failure_agent is None:
            first_failure_agent = agent_name
            upstream_failed = True

    return step_results, first_failure_agent


# --------------------------------------------------------------------------- #
# Per-agent pass rate aggregation
# --------------------------------------------------------------------------- #

def _compute_agent_pass_rates(
    results: list[ScenarioResult],
) -> tuple[list[AgentPassRate], str | None]:
    stats: dict[str, dict] = defaultdict(
        lambda: {"passed": 0, "total": 0, "failures": []}
    )
    # Preserve agent order from first scenario that has steps
    agent_order: list[str] = []
    for scenario in results:
        for step in scenario.step_results:
            if step.agent_name not in agent_order:
                agent_order.append(step.agent_name)

    for scenario in results:
        for step in scenario.step_results:
            if not step.skipped:
                stats[step.agent_name]["total"] += 1
                if step.passed:
                    stats[step.agent_name]["passed"] += 1
                else:
                    stats[step.agent_name]["failures"].append(step.reasoning)

    if not stats:
        return [], None

    pass_rates: list[AgentPassRate] = []
    for agent_name in agent_order:
        if agent_name not in stats:
            continue
        s = stats[agent_name]
        total   = s["total"]
        passed  = s["passed"]
        rate    = round(passed / total, 3) if total else 0.0
        failures = s["failures"]
        common   = max(set(failures), key=failures.count) if failures else ""
        pass_rates.append(AgentPassRate(
            agent_name=agent_name,
            passed=passed,
            total=total,
            pass_rate=rate,
            common_failure=common[:200],
        ))

    # Bottleneck = lowest pass rate
    bottleneck = min(pass_rates, key=lambda x: x.pass_rate).agent_name if pass_rates else None
    return pass_rates, bottleneck


# --------------------------------------------------------------------------- #
# Main runner
# --------------------------------------------------------------------------- #

async def run_eval(
    request: EvalRequest,
    agent_fn: Callable[[str], Awaitable[str]] | None = None,
    tracer=None,  # kept for backwards compatibility, ignored if @trace is used
) -> EvalReport:
    """
    Run a full Gauntlet eval.

    Parameters
    ----------
    request:
        Eval configuration including agent credentials and criteria.
    agent_fn:
        Optional override — your workflow function. If None, Gauntlet
        calls the agent directly using request.agent_model + agent_api_key.
    tracer:
        Deprecated. Use @trace decorator instead.
    """
    if agent_fn is None:
        agent_fn = _build_agent_fn(request)

    eval_id           = f"eval_{uuid.uuid4().hex[:8]}"
    scenario_agent    = ScenarioAgent()
    judge_agent       = JudgeAgent()
    adversarial_agent = AdversarialAgent()
    report_agent      = ReportAgent()
    store             = get_store()

    # 1. Standard scenarios
    scenarios = await scenario_agent.generate(
        goal=request.goal,
        agent_description=request.agent_description,
        count=request.runs,
    )

    # 2. Adversarial scenarios
    adversarial_findings: list[str] = []
    if request.mode in (EvalMode.adversarial, EvalMode.full):
        adv_scenarios, findings = await adversarial_agent.generate(
            goal=request.goal,
            agent_description=request.agent_description,
        )
        scenarios += adv_scenarios
        adversarial_findings = findings

    criteria_str = (
        "\n".join(f"- {c}" for c in request.success_criteria)
        if request.success_criteria else None
    )

    # 3. Run + judge each scenario
    results: list[ScenarioResult] = []
    # Track the full agent order across all scenarios
    all_agent_names: list[str] = []

    for i, scenario_input in enumerate(scenarios):
        # Start fresh span collection for this scenario
        store.start()

        t0 = time.time()
        try:
            agent_output = await agent_fn(scenario_input)
        except Exception as e:
            agent_output = f"[AGENT ERROR] {e}"
        latency_ms = int((time.time() - t0) * 1000)

        store.stop()

        # Update full agent order from this scenario's spans
        for name in store.agent_names():
            if name not in all_agent_names:
                all_agent_names.append(name)

        is_multi_agent = store.has_spans()

        # Judge the final output
        verdict = await judge_agent.evaluate(
            goal=request.goal,
            scenario_input=scenario_input,
            agent_output=agent_output,
            success_criteria=criteria_str,
        )

        # Judge individual steps if traces were recorded
        step_results: list[AgentStepResult] = []
        first_failure_agent: str | None = None

        if is_multi_agent:
            step_results, first_failure_agent = await _evaluate_spans(
                judge=judge_agent,
                goal=request.goal,
                criteria_str=criteria_str,
                all_agent_names=all_agent_names,
            )

        results.append(ScenarioResult(
            scenario_id=f"{eval_id}_s{i}",
            scenario_input=scenario_input,
            passed=verdict["passed"],
            agent_output=agent_output,
            judge_verdict="PASS" if verdict["passed"] else "FAIL",
            judge_reasoning=verdict["reasoning"],
            cost_usd=verdict.get("cost_usd", 0.0),
            latency_ms=latency_ms,
            is_multi_agent=is_multi_agent,
            step_results=step_results,
            first_failure_agent=first_failure_agent,
        ))

    # 4. Aggregate
    total  = len(results)
    passed = sum(1 for r in results if r.passed)
    is_multi_agent_eval = any(r.is_multi_agent for r in results)

    agent_pass_rates, bottleneck_agent = (
        _compute_agent_pass_rates(results)
        if is_multi_agent_eval else ([], None)
    )

    recommendations = await report_agent.recommend(
        goal=request.goal,
        results=results,
        adversarial_findings=adversarial_findings,
    )

    report = EvalReport(
        eval_id=eval_id,
        mode=request.mode,
        goal=request.goal,
        total_runs=total,
        passed=passed,
        failed=total - passed,
        pass_rate=round(passed / total, 3) if total else 0,
        avg_cost_usd=round(sum(r.cost_usd for r in results) / total if total else 0, 6),
        avg_latency_ms=round(sum(r.latency_ms for r in results) / total if total else 0, 1),
        scenarios=results,
        adversarial_findings=adversarial_findings,
        recommendations=recommendations,
        is_multi_agent=is_multi_agent_eval,
        agent_pass_rates=agent_pass_rates,
        bottleneck_agent=bottleneck_agent,
    )
    await save_report(report)
    return report