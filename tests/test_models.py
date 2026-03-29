# tests/test_models.py
"""Basic model validation tests — no API key needed."""
import pytest
from gauntlet.core.models import EvalMode, EvalRequest, EvalReport, ScenarioResult


def _make_result(passed: bool = True, index: int = 0) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=f"s{index}",
        scenario_input="test input",
        passed=passed,
        agent_output="test output",
        judge_verdict="PASS" if passed else "FAIL",
        judge_reasoning="looks good" if passed else "wrong",
        cost_usd=0.001,
        latency_ms=100,
    )


def test_eval_request_defaults():
    req = EvalRequest(
        goal="test goal",
        agent_description="test agent",
        agent_api_key="sk-ant-test",
    )
    assert req.mode == EvalMode.standard
    assert req.runs == 5
    assert req.success_criteria == []
    assert req.agent_system_prompt == "You are a helpful assistant."


def test_eval_request_runs_clamped():
    with pytest.raises(Exception):
        EvalRequest(
            goal="g",
            agent_description="d",
            agent_api_key="sk-ant-test",
            runs=100,
        )


def test_eval_request_missing_api_key_raises():
    with pytest.raises(Exception):
        EvalRequest(goal="g", agent_description="d")


def test_eval_report_pass_rate():
    results = [_make_result(passed=i < 4, index=i) for i in range(5)]
    report = EvalReport(
        eval_id="eval_test",
        mode=EvalMode.standard,
        goal="test",
        total_runs=5,
        passed=4,
        failed=1,
        pass_rate=0.8,
        avg_cost_usd=0.001,
        avg_latency_ms=100.0,
        scenarios=results,
    )
    assert report.pass_rate == 0.8
    assert report.passed == 4