"""Basic model validation tests — no API key needed."""
import pytest
from gauntlet.core.models import EvalMode, EvalRequest, EvalReport, ScenarioResult
import time


def test_eval_request_defaults():
    req = EvalRequest(goal="test goal", agent_description="test agent")
    assert req.mode == EvalMode.standard
    assert req.runs == 5


def test_eval_request_runs_clamped():
    with pytest.raises(Exception):
        EvalRequest(goal="g", agent_description="d", runs=100)


def test_eval_report_pass_rate():
    results = [
        ScenarioResult(
            scenario_id=f"s{i}", scenario_input="in", passed=i < 4,
            agent_output="out", judge_verdict="PASS" if i < 4 else "FAIL",
            judge_reasoning="ok", cost_usd=0.001, latency_ms=100,
        ) for i in range(5)
    ]
    report = EvalReport(
        eval_id="eval_test", mode=EvalMode.standard, goal="test",
        total_runs=5, passed=4, failed=1, pass_rate=0.8,
        avg_cost_usd=0.001, avg_latency_ms=100.0, scenarios=results,
    )
    assert report.pass_rate == 0.8
    assert report.passed == 4
