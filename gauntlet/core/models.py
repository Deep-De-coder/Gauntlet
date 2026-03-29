"""Shared Pydantic models used across API, CLI, and agents."""
from __future__ import annotations
from enum import Enum
from typing import Any, Literal
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
        description="LLM provider for the agent under test. `anthropic` or `openai`.",
    )
    agent_model: str = Field(
        default="claude-sonnet-4-20250514",
        description=(
            "Model name for the agent under test. "
            "Examples: `claude-sonnet-4-20250514`, `gpt-4o`, `gpt-4o-mini`."
        ),
        example="claude-sonnet-4-20250514",
    )
    agent_api_key: str = Field(
        ...,
        description=(
            "API key for the agent under test. "
            "This key is used ONLY to call the agent — never stored or logged."
        ),
        example="sk-ant-...",
    )
    agent_system_prompt: str = Field(
        default="You are a helpful assistant.",
        description=(
            "System prompt for the agent under test. "
            "This is how you configure what your agent does."
        ),
        example="You are a news summariser. Always respond with exactly 3 bullet points starting with '•'.",
    )

    # ------------------------------------------------------------------ #
    # Custom pass/fail criteria (optional)
    # ------------------------------------------------------------------ #
    success_criteria: list[str] = Field(
        default=[],
        description=(
            "Optional list of custom rules the JudgeAgent uses to decide pass/fail. "
            "If empty, the judge uses the `goal` alone. "
            "Be specific — vague criteria lead to inconsistent verdicts."
        ),
        example=[
            "Response must contain exactly 3 bullet points",
            "Each bullet point must be under 30 words",
            "Response must not include phrases like 'I cannot' or 'As an AI'",
        ],
    )


class ScenarioResult(BaseModel):
    scenario_id: str
    scenario_input: str
    passed: bool
    agent_output: str
    judge_verdict: str
    judge_reasoning: str
    cost_usd: float
    latency_ms: int


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