"""Report Agent — synthesises eval results into actionable recommendations."""
import json
import anthropic
from gauntlet.config import ANTHROPIC_API_KEY, GAUNTLET_MODEL
from gauntlet.core.models import ScenarioResult


class ReportAgent:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def recommend(
        self,
        goal: str,
        results: list[ScenarioResult],
        adversarial_findings: list[str],
    ) -> list[str]:
        failures = [r for r in results if not r.passed]
        if not failures:
            return ["All scenarios passed. Consider increasing run count or enabling adversarial mode."]

        failure_summary = "\n".join(
            f"- Input: {r.scenario_input[:120]}\n  Reason: {r.judge_reasoning}"
            for r in failures[:8]
        )
        adv_text = (
            "\nAdversarial findings:\n" + "\n".join(f"- {f}" for f in adversarial_findings)
            if adversarial_findings else ""
        )
        prompt = f"""You are an AI systems improvement advisor.

Agent goal: {goal}

Failed scenarios:
{failure_summary}
{adv_text}

Give 3-5 concrete, actionable recommendations to improve this agent pipeline.
Reference the actual failure patterns you observed.

Return ONLY a JSON array of recommendation strings."""

        msg = await self.client.messages.create(
            model=GAUNTLET_MODEL, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)