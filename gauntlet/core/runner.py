"""
Core eval runner — orchestrates all four agents.

Flow:
  1. ScenarioAgent   → generates test inputs from the goal
  2. AdversarialAgent→ (if mode=adversarial|full) adds hostile inputs
  3. JudgeAgent      → scores each agent output pass/fail
  4. ReportAgent     → synthesises recommendations
"""
from __future__ import annotations
import time, uuid

from gauntlet.core.models import EvalMode, EvalReport, EvalRequest, ScenarioResult
from gauntlet.agents.scenario     import ScenarioAgent
from gauntlet.agents.judge        import JudgeAgent
from gauntlet.agents.adversarial  import AdversarialAgent
from gauntlet.agents.report       import ReportAgent
from gauntlet.storage.db          import save_report


async def run_eval(request: EvalRequest, agent_fn) -> EvalReport:
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
    total   = len(results)
    passed  = sum(1 for r in results if r.passed)
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
