"""Judge Agent — evaluates whether the agent's output satisfies the goal."""
import json
import anthropic
from gauntlet.config import ANTHROPIC_API_KEY, GAUNTLET_MODEL


class JudgeAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    async def evaluate(self, goal: str, scenario_input: str, agent_output: str) -> dict:
        prompt = f"""You are an impartial judge evaluating an AI agent's output.

Goal: {goal}
Input the agent received: {scenario_input}
Agent's output: {agent_output}

Did the agent achieve its goal? Be strict but fair.

Return ONLY this JSON (no markdown):
{{"passed": true or false, "reasoning": "one sentence explanation"}}"""

        msg = self.client.messages.create(
            model=GAUNTLET_MODEL, max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(raw)
        # Rough cost: $3/M input + $15/M output tokens (Sonnet pricing)
        cost = (msg.usage.input_tokens * 3 + msg.usage.output_tokens * 15) / 1_000_000
        result["cost_usd"] = round(cost, 8)
        return result
