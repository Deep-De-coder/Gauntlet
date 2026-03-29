"""Scenario Agent — generates realistic test inputs from a plain-English goal."""
import json
import anthropic
from gauntlet.config import ANTHROPIC_API_KEY, GAUNTLET_MODEL


class ScenarioAgent:
    def __init__(self):
        # WHY AsyncAnthropic: all agents run inside async functions.
        # Using the sync client blocks the entire event loop, freezing
        # the server while waiting for Claude. AsyncAnthropic fixes this.
        self.client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    async def generate(self, goal: str, agent_description: str, count: int = 5) -> list[str]:
        prompt = f"""You are a test scenario generator for AI agent pipelines.

Agent goal: {goal}
Agent description: {agent_description}

Generate exactly {count} diverse test scenario inputs. Cover:
- Happy path (clear, well-formed input)
- Edge cases (missing info, ambiguous phrasing)
- Unusual but valid inputs
- Borderline cases

Return ONLY a JSON array of {count} strings. No explanation, no markdown fences.
Example: ["scenario 1", "scenario 2"]"""

        msg = await self.client.messages.create(
            model=GAUNTLET_MODEL, max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(raw)[:count]