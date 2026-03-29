# tests/test_gauntlet.py — updated for production models
#
# WHY: These tests cover the four most important units without ever calling
# the real Anthropic API. We use `unittest.mock.patch` to swap out the
# `anthropic.Anthropic` constructor with a factory that returns our fake
# client from conftest.py. Patch target must match WHERE the name is used
# (i.e. `gauntlet.agents.scenario.anthropic.Anthropic`), not where it's
# defined.

import json
import pytest
from unittest.mock import patch, MagicMock

from gauntlet.core.models import EvalRequest, EvalReport, ScenarioResult


# =========================================================================== #
# 1. Model validation — no API calls, pure Pydantic
# =========================================================================== #

class TestEvalRequestValidation:
    def test_valid_request(self):
        req = EvalRequest(
            goal="Summarise news articles",
            agent_description="A summarisation agent",
            mode="standard",
            num_scenarios=3,
        )
        assert req.mode == "standard"
        assert req.num_scenarios == 3

    def test_defaults(self):
        req = EvalRequest(
            goal="Test agent",
            agent_description="My agent",
        )
        # Confirm sensible defaults exist (adjust field names to match your model)
        assert req.goal == "Test agent"

    def test_invalid_mode_raises(self):
        with pytest.raises(Exception):
            EvalRequest(
                goal="Test",
                agent_description="Agent",
                mode="invalid_mode",  # should fail validation
            )


# =========================================================================== #
# 2. ScenarioAgent.generate() — mocked Claude call
# =========================================================================== #

class TestScenarioAgent:
    def test_generate_returns_list(self, scenario_response):
        """ScenarioAgent should return a list of scenario strings."""
        from tests.conftest import make_mock_client
        mock_client = make_mock_client(scenario_response)

        # Patch wherever ScenarioAgent imports anthropic
        with patch("gauntlet.agents.scenario.anthropic.Anthropic", return_value=mock_client):
            from gauntlet.agents.scenario import ScenarioAgent
            import importlib
            import gauntlet.agents.scenario as mod
            importlib.reload(mod)  # reload so the patch takes effect

            agent = mod.ScenarioAgent()
            # Force the internal client to our mock
            agent.client = mock_client

            import asyncio
            request = EvalRequest(
                goal="Summarise news articles",
                agent_description="Summarisation agent",
                num_scenarios=3,
            )
            result = asyncio.get_event_loop().run_until_complete(
                agent.generate(request)
            )

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(s, str) for s in result)


# =========================================================================== #
# 3. JudgeAgent.evaluate() — mocked Claude call
# =========================================================================== #

class TestJudgeAgent:
    def test_evaluate_pass(self, judge_response):
        """JudgeAgent should parse the mock response into a ScenarioResult."""
        from tests.conftest import make_mock_client
        mock_client = make_mock_client(judge_response)

        import gauntlet.agents.judge as mod
        import importlib
        importlib.reload(mod)

        agent = mod.JudgeAgent()
        agent.client = mock_client

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.evaluate(
                scenario="Summarise this article.",
                agent_output="• Point 1\n• Point 2\n• Point 3",
                goal="Produce three bullet points",
            )
        )

        # The result should indicate a pass
        assert result.passed is True
        assert result.score >= 0.0
        assert isinstance(result.reasoning, str)

    def test_evaluate_fail(self):
        """JudgeAgent should handle a failing verdict correctly."""
        from tests.conftest import make_mock_client
        fail_response = json.dumps({
            "passed": False,
            "score": 0.2,
            "reasoning": "Output was empty.",
            "issues": ["No content returned"],
        })
        mock_client = make_mock_client(fail_response)

        import gauntlet.agents.judge as mod
        import importlib
        importlib.reload(mod)

        agent = mod.JudgeAgent()
        agent.client = mock_client

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            agent.evaluate(
                scenario="Summarise this article.",
                agent_output="",
                goal="Produce three bullet points",
            )
        )

        assert result.passed is False
        assert result.score < 0.5


# =========================================================================== #
# 4. Full runner — all agents mocked end-to-end
# =========================================================================== #

class TestRunner:
    def test_run_eval_standard_mode(
        self, scenario_response, judge_response, report_response
    ):
        """run_eval() should return an EvalReport with the right shape."""
        from tests.conftest import make_mock_client

        # We need different responses for different agents.
        # Simplest approach: patch each agent class to return canned data.
        fake_scenario_result = ["Scenario A", "Scenario B"]
        fake_judge_result = ScenarioResult(
            scenario="Scenario A",
            agent_output="output",
            passed=True,
            score=0.9,
            reasoning="Good",
            issues=[],
        )

        with (
            patch("gauntlet.core.runner.ScenarioAgent") as MockScenario,
            patch("gauntlet.core.runner.JudgeAgent") as MockJudge,
            patch("gauntlet.core.runner.ReportAgent") as MockReport,
            patch("gauntlet.core.runner.save_report"),  # Don't write to disk
        ):
            # Configure what each agent returns when called
            MockScenario.return_value.generate = MagicMock(
                return_value=_async_return(fake_scenario_result)
            )
            MockJudge.return_value.evaluate = MagicMock(
                return_value=_async_return(fake_judge_result)
            )

            mock_report = EvalReport(
                id="test-123",
                goal="Test goal",
                agent_description="Test agent",
                mode="standard",
                results=[fake_judge_result],
                summary="Passed 1/1",
                strengths=["Good"],
                weaknesses=[],
                recommendations=["Keep it up"],
                overall_grade="A",
                pass_rate=1.0,
                total_cost_usd=0.001,
            )
            MockReport.return_value.synthesise = MagicMock(
                return_value=_async_return(mock_report)
            )

            from gauntlet.core.runner import run_eval
            import asyncio

            request = EvalRequest(
                goal="Test goal",
                agent_description="Test agent",
                mode="standard",
                num_scenarios=2,
            )
            report = asyncio.get_event_loop().run_until_complete(run_eval(request))

        assert isinstance(report, EvalReport)
        assert report.goal == "Test goal"
        assert 0.0 <= report.pass_rate <= 1.0


# Helper: wrap a value in a coroutine so it can be awaited
import asyncio as _asyncio

def _async_return(value):
    async def _inner(*args, **kwargs):
        return value
    return _inner