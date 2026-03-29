"""
Core eval runner — orchestrates all four agents.

Flow:
  1. ScenarioAgent    → generates test inputs from the goal
  2. AdversarialAgent → (if mode=adversarial|full) adds hostile inputs
  3. JudgeAgent       → scores each agent output pass/fail
  4. ReportAgent      → synthesises recommendations
"""
from __future__ import annotations
import time
import uuid
from typing import Callable, Awaitable

from gauntlet.core.models import EvalMode, EvalReport, EvalRequest, ScenarioResult
from gauntlet.agents.scenario    import ScenarioAgent
from gauntlet.agents.judge       import JudgeAgent
from gauntlet.agents.adversarial import AdversarialAgent
from gauntlet.agents.report      import ReportAgent
from gauntlet.storage.db         import save_report


# --------------------------------------------------------------------------- #
# Agent factory — builds a real callable from the request's agent config
# --------------------------------------------------------------------------- #

def _build_agent_fn(request: EvalRequest) -> Callable[[str], Awaitable[str]]:
    """
    Return an async callable that sends a scenario to the user's agent
    and returns its response as a string.

    Supports Anthropic and OpenAI providers.
    The user's API key is used only for this call and never stored.
    """
    if request.agent_provider.value == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=request.agent_api_key)

        async def anthropic_agent(scenario_input: str) -> str:
            response = client.messages.create(
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
            raise ImportError(
                "openai package is not installed. "
                "Run: pip install openai"
            )

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

    else:
        raise ValueError(f"Unsupported agent_provider: {request.agent_provider}")


# --------------------------------------------------------------------------- #
# Main runner
# --------------------------------------------------------------------------- #

async def run_eval(
    request: EvalRequest,
    agent_fn: Callable[[str], Awaitable[str]] | None = None,
) -> EvalReport:
    """
    Run a full Gauntlet eval.

    Parameters
    ----------
    request:
        The eval configuration including agent credentials and criteria.
    agent_fn:
        Optional override — pass your own async callable for testing/CLI use.
        If None, the agent is built from request.agent_model + request.agent_api_key.
    """
    # Build agent from request if no override provided
    if agent_fn is None:
        agent_fn = _build_agent_fn(request)

    eval_id           = f"eval_{uuid.uuid4().hex[:8]}"
    scenario_agent    = ScenarioAgent()
    judge_agent       = JudgeAgent()
    adversarial_agent = AdversarialAgent()
    report_agent      = ReportAgent()

    # 1. Standard scenarios
    scenarios = await scenario_agent.generate(
        goal=request.goal,
        agent_description=request.agent_description,
        count=request.runs,
    )

    # 2. Adversarial scenarios (optional)
    adversarial_findings: list[str] = []
    if request.mode in (EvalMode.adversarial, EvalMode.full):
        adv_scenarios, findings = await adversarial_agent.generate(
            goal=request.goal,
            agent_description=request.agent_description,
        )
        scenarios += adv_scenarios
        adversarial_findings = findings

    # 3. Run + judge each scenario
    # Build criteria string for the judge from success_criteria if provided
    criteria_str = ""
    if request.success_criteria:
        criteria_str = "\n".join(
            f"- {c}" for c in request.success_criteria
        )

    results: list[ScenarioResult] = []
    for i, scenario_input in enumerate(scenarios):
        t0 = time.time()
        try:
            agent_output = await agent_fn(scenario_input)
        except Exception as e:
            agent_output = f"[AGENT ERROR] {e}"
        latency_ms = int((time.time() - t0) * 1000)

        verdict = await judge_agent.evaluate(
            goal=request.goal,
            scenario_input=scenario_input,
            agent_output=agent_output,
            # Pass custom criteria to the judge if provided
            success_criteria=criteria_str or None,
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
        ))

    # 4. Aggregate
    total  = len(results)
    passed = sum(1 for r in results if r.passed)

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
    )
    await save_report(report)
    return report