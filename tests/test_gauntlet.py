# tests/test_gauntlet.py
#
# All tests run without a real API key — Claude calls are mocked.
# Run with: pytest tests/ -v

import json
import asyncio
import pytest
from unittest.mock import MagicMock, patch

from gauntlet.core.models import (
    EvalMode,
    EvalRequest,
    EvalReport,
    ScenarioResult,
    AgentProvider,
)


# =========================================================================== #
# Helpers
# =========================================================================== #

def make_eval_request(**kwargs) -> EvalRequest:
    """Return a valid EvalRequest with sensible defaults for testing."""
    defaults = dict(
        goal="Classify a support ticket as billing, technical, or general",
        agent_description="Single Claude classifier agent",
        agent_api_key="sk-ant-test-key",
        agent_model="claude-sonnet-4-20250514",
        agent_provider=AgentProvider.anthropic,
        agent_system_prompt="You are a classifier. Reply with one word.",
        mode=EvalMode.standard,
        runs=2,
    )
    defaults.update(kwargs)
    return EvalRequest(**defaults)


def make_scenario_result(passed: bool = True, index: int = 0) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=f"eval_test_s{index}",
        scenario_input="Classify this ticket: my payment failed",
        passed=passed,
        agent_output="billing",
        judge_verdict="PASS" if passed else "FAIL",
        judge_reasoning="Correct classification." if passed else "Wrong category.",
        cost_usd=0.001,
        latency_ms=500,
    )


def async_return(value):
    """Wrap a value in a coroutine so it can be awaited."""
    async def _inner(*args, **kwargs):
        return value
    return _inner


# =========================================================================== #
# 1. Model validation — no API calls
# =========================================================================== #

class TestEvalRequestValidation:

    def test_valid_request_with_required_fields(self):
        req = make_eval_request()
        assert req.goal == "Classify a support ticket as billing, technical, or general"
        assert req.agent_api_key == "sk-ant-test-key"

    def test_default_mode_is_standard(self):
        req = make_eval_request()
        assert req.mode == EvalMode.standard

    def test_runs_above_max_raises(self):
        with pytest.raises(Exception):
            make_eval_request(runs=100)

    def test_runs_below_min_raises(self):
        with pytest.raises(Exception):
            make_eval_request(runs=0)

    def test_missing_agent_api_key_raises(self):
        with pytest.raises(Exception):
            EvalRequest(
                goal="test",
                agent_description="test agent",
                # agent_api_key intentionally omitted
            )

    def test_missing_goal_raises(self):
        with pytest.raises(Exception):
            EvalRequest(
                agent_description="test agent",
                agent_api_key="sk-ant-test",
            )

    def test_invalid_mode_raises(self):
        with pytest.raises(Exception):
            make_eval_request(mode="invalid_mode")

    def test_invalid_provider_raises(self):
        with pytest.raises(Exception):
            make_eval_request(agent_provider="gemini")

    def test_success_criteria_defaults_to_empty(self):
        req = make_eval_request()
        assert req.success_criteria == []

    def test_success_criteria_accepts_list(self):
        req = make_eval_request(success_criteria=["Must be one word", "Must be lowercase"])
        assert len(req.success_criteria) == 2

    def test_full_mode_accepted(self):
        req = make_eval_request(mode=EvalMode.full)
        assert req.mode == EvalMode.full

    def test_openai_provider_accepted(self):
        req = make_eval_request(agent_provider=AgentProvider.openai, agent_model="gpt-4o")
        assert req.agent_provider == AgentProvider.openai


# =========================================================================== #
# 2. EvalReport model
# =========================================================================== #

class TestEvalReport:

    def test_pass_rate_field(self):
        results = [make_scenario_result(passed=i < 4, index=i) for i in range(5)]
        report = EvalReport(
            eval_id="eval_test",
            mode=EvalMode.standard,
            goal="test goal",
            total_runs=5,
            passed=4,
            failed=1,
            pass_rate=0.8,
            avg_cost_usd=0.001,
            avg_latency_ms=500.0,
            scenarios=results,
        )
        assert report.pass_rate == 0.8
        assert report.passed == 4
        assert report.failed == 1

    def test_adversarial_findings_defaults_empty(self):
        report = EvalReport(
            eval_id="eval_test",
            mode=EvalMode.standard,
            goal="test",
            total_runs=1,
            passed=1,
            failed=0,
            pass_rate=1.0,
            avg_cost_usd=0.001,
            avg_latency_ms=100.0,
            scenarios=[make_scenario_result()],
        )
        assert report.adversarial_findings == []
        assert report.recommendations == []

    def test_multi_agent_fields_default_empty(self):
        report = EvalReport(
            eval_id="eval_test",
            mode=EvalMode.standard,
            goal="test",
            total_runs=1,
            passed=1,
            failed=0,
            pass_rate=1.0,
            avg_cost_usd=0.001,
            avg_latency_ms=100.0,
            scenarios=[make_scenario_result()],
        )
        assert report.is_multi_agent is False
        assert report.agent_pass_rates == []
        assert report.bottleneck_agent is None


# =========================================================================== #
# 3. JudgeAgent — mocked Claude call
# =========================================================================== #

class TestJudgeAgent:

    def _make_mock_client(self, response_text: str):
        mock_block = MagicMock()
        mock_block.text = response_text
        mock_message = MagicMock()
        mock_message.content = [mock_block]
        mock_message.usage.input_tokens = 100
        mock_message.usage.output_tokens = 50
        mock_client = MagicMock()
        # AsyncMock for async client
        import asyncio
        async def async_create(*args, **kwargs):
            return mock_message
        mock_client.messages.create = async_create
        return mock_client

    def test_evaluate_returns_pass(self):
        response = json.dumps({"passed": True, "reasoning": "Correct output."})
        mock_client = self._make_mock_client(response)

        import gauntlet.agents.judge as mod
        agent = mod.JudgeAgent()
        agent.client = mock_client

        result = asyncio.get_event_loop().run_until_complete(
            agent.evaluate(
                goal="Classify ticket",
                scenario_input="My payment failed",
                agent_output="billing",
            )
        )
        assert result["passed"] is True
        assert "reasoning" in result
        assert "cost_usd" in result

    def test_evaluate_returns_fail(self):
        response = json.dumps({"passed": False, "reasoning": "Wrong category."})
        mock_client = self._make_mock_client(response)

        import gauntlet.agents.judge as mod
        agent = mod.JudgeAgent()
        agent.client = mock_client

        result = asyncio.get_event_loop().run_until_complete(
            agent.evaluate(
                goal="Classify ticket",
                scenario_input="My payment failed",
                agent_output="technical",
            )
        )
        assert result["passed"] is False

    def test_evaluate_strips_markdown_fences(self):
        response = "```json\n{\"passed\": true, \"reasoning\": \"Good.\"}\n```"
        mock_client = self._make_mock_client(response)

        import gauntlet.agents.judge as mod
        agent = mod.JudgeAgent()
        agent.client = mock_client

        result = asyncio.get_event_loop().run_until_complete(
            agent.evaluate(
                goal="Classify ticket",
                scenario_input="input",
                agent_output="billing",
            )
        )
        assert result["passed"] is True


# =========================================================================== #
# 4. Full runner — all agents mocked
# =========================================================================== #

class TestRunner:

    def test_run_eval_standard_mode(self):
        fake_scenarios = ["Classify this ticket: payment failed"]
        fake_verdict = {
            "passed": True,
            "reasoning": "Correct.",
            "cost_usd": 0.001,
        }
        fake_recommendations = ["Add input validation"]

        with (
            patch("gauntlet.core.runner.ScenarioAgent") as MockScenario,
            patch("gauntlet.core.runner.JudgeAgent") as MockJudge,
            patch("gauntlet.core.runner.AdversarialAgent"),
            patch("gauntlet.core.runner.ReportAgent") as MockReport,
            patch("gauntlet.core.runner.save_report"),
            patch("gauntlet.core.runner._build_agent_fn"),
        ):
            MockScenario.return_value.generate = async_return(fake_scenarios)
            MockJudge.return_value.evaluate = async_return(fake_verdict)
            MockReport.return_value.recommend = async_return(fake_recommendations)

            from gauntlet.core.runner import run_eval

            async def fake_agent(s): return "billing"

            request = make_eval_request(mode=EvalMode.standard, runs=1)
            report = asyncio.get_event_loop().run_until_complete(
                run_eval(request, agent_fn=fake_agent)
            )

        assert isinstance(report, EvalReport)
        assert report.goal == request.goal
        assert report.total_runs == 1
        assert 0.0 <= report.pass_rate <= 1.0

    def test_run_eval_uses_agent_fn_override(self):
        """When agent_fn is passed, _build_agent_fn should not be called."""
        fake_scenarios = ["test scenario"]
        fake_verdict = {"passed": True, "reasoning": "ok", "cost_usd": 0.0}

        with (
            patch("gauntlet.core.runner.ScenarioAgent") as MockScenario,
            patch("gauntlet.core.runner.JudgeAgent") as MockJudge,
            patch("gauntlet.core.runner.AdversarialAgent"),
            patch("gauntlet.core.runner.ReportAgent") as MockReport,
            patch("gauntlet.core.runner.save_report"),
            patch("gauntlet.core.runner._build_agent_fn") as MockBuildAgent,
        ):
            MockScenario.return_value.generate = async_return(fake_scenarios)
            MockJudge.return_value.evaluate = async_return(fake_verdict)
            MockReport.return_value.recommend = async_return([])

            from gauntlet.core.runner import run_eval

            async def my_agent(s): return "test output"

            request = make_eval_request(runs=1)
            asyncio.get_event_loop().run_until_complete(
                run_eval(request, agent_fn=my_agent)
            )

            MockBuildAgent.assert_not_called()