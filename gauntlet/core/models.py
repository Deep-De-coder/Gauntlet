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


class EvalRequest(BaseModel):
    goal: str = Field(..., example="Correctly categorise a support ticket and draft a reply.")
    agent_description: str = Field(..., example="Two-agent pipeline: Router + Writer.")
    mode: EvalMode = EvalMode.standard
    runs: int = Field(default=5, ge=1, le=50)


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
