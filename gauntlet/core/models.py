"""Shared Pydantic models used across API, CLI, and agents."""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
import time


class EvalMode(str, Enum):
    standard    = "standard"
    adversarial = "adversarial"
    full        = "full"


class AgentProvider(str, Enum):
    """Which LLM provider hosts the agent being evaluated."""
    anthropic = "anthropic"
    openai    = "openai"


class EvalRequest(BaseModel):
    # ------------------------------------------------------------------ #
    # What to evaluate
    # ------------------------------------------------------------------ #
    goal: str = Field(
        ...,
        description="What the agent is supposed to do.",
        example="Summarise a news article in exactly three bullet points.",
    )
    agent_description: str = Field(
        ...,
        description="Plain-English description of the agent pipeline.",
        example="A single Claude call with a summarisation system prompt.",
    )
    mode: EvalMode = Field(
        default=EvalMode.standard,
        description=(
            "**standard** — realistic scenarios only. "
            "**adversarial** — hostile/edge-case inputs only. "
            "**full** — both combined."
        ),
    )
    runs: int = Field(
        default=5, ge=1, le=50,
        description="Number of scenarios to generate and test.",
    )

    # ------------------------------------------------------------------ #
    # The agent being tested
    # ------------------------------------------------------------------ #
    agent_provider: AgentProvider = Field(
        default=AgentProvider.anthropic,
        description="LLM provider for the agent under test.",
    )
    agent_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model name for the agent under test.",
        example="claude-sonnet-4-20250514",
    )
    agent_api_key: str = Field(
        ...,
        description="API key for the agent under test. Never stored or logged.",
        example="sk-ant-...",
    )
    agent_system_prompt: str = Field(
        default="You are a helpful assistant.",
        description="System prompt that defines the agent behaviour.",
    )

    # ------------------------------------------------------------------ #
    # Custom pass/fail criteria (optional)
    # ------------------------------------------------------------------ #
    success_criteria: list[str] = Field(
        default=[],
        description=(
            "Optional list of custom rules the JudgeAgent uses to decide pass/fail. "
            "If empty, the judge uses the goal alone."
        ),
        example=[
            "Response must contain exactly 3 bullet points",
            "Each bullet point must be under 30 words",
        ],
    )


# --------------------------------------------------------------------------- #
# Tracing models — used when evaluating multi-agent workflows
# --------------------------------------------------------------------------- #

class AgentStepResult(BaseModel):
    """
    Judge verdict for a single step inside a multi-agent workflow.
    One of these is created per sub-agent per scenario.
    """
    agent_name: str   = Field(description="Name of the sub-agent e.g. Router, Writer")
    input: str        = Field(description="What this agent received")
    output: str       = Field(description="What this agent returned")
    passed: bool      = Field(description="Whether this step output was acceptable")
    reasoning: str    = Field(description="Judge reasoning for the verdict")
    latency_ms: int   = Field(default=0)
    error: str | None = Field(default=None, description="Error if the step crashed")
    skipped: bool     = Field(default=False, description="True if upstream failure prevented this agent from running")


class AgentPassRate(BaseModel):
    """Per-agent aggregated pass rate across all scenarios."""
    agent_name: str
    passed: int
    total: int
    pass_rate: float
    common_failure: str = Field(
        default="",
        description="Most common failure pattern for this agent",
    )


# --------------------------------------------------------------------------- #
# Core result models
# --------------------------------------------------------------------------- #

class ScenarioResult(BaseModel):
    scenario_id: str
    scenario_input: str
    passed: bool
    agent_output: str
    judge_verdict: str
    judge_reasoning: str
    cost_usd: float
    latency_ms: int

    # Multi-agent fields — empty for single-agent evals
    is_multi_agent: bool = Field(default=False)
    step_results: list[AgentStepResult] = Field(
        default=[],
        description="Per-step verdicts when tracing a multi-agent workflow",
    )
    first_failure_agent: str | None = Field(
        default=None,
        description="First agent that produced a bad output in this scenario",
    )


class EvalReport(BaseModel):
    eval_id: str
    mode: EvalMode
    goal: str
    total_runs: int
    passed: int
    failed: int
    pass_rate: float
    avg_cost_usd: float
    avg_latency_ms: float
    scenarios: list[ScenarioResult]
    adversarial_findings: list[str] = []
    recommendations: list[str] = []
    created_at: float = Field(default_factory=time.time)

    # Multi-agent fields — empty for single-agent evals
    is_multi_agent: bool = Field(default=False)
    agent_pass_rates: list[AgentPassRate] = Field(
        default=[],
        description="Per-agent pass rates — shows which agent is the bottleneck",
    )
    bottleneck_agent: str | None = Field(
        default=None,
        description="Agent with the lowest pass rate across all scenarios",
    )