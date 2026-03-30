# Gauntlet — Cursor Prompt

Two ways to use Gauntlet in Cursor. Start with Option 1 — it's faster.

---

## Option 1 — Auto-detect (recommended)

Just type this in Cursor chat:

```
find gauntlet
```

Gauntlet scans your entire workspace, detects all agent files, and shows a table with the goal, provider, and model for each one. Reply with the file number to run the eval — no API key needed.

---

## Option 2 — Manual prompt (for a specific file)

Open the agent file you want to test, then paste this into Cursor chat:

```
I want to evaluate this agent using the Gauntlet MCP tool.

1. Read the current file and find the system prompt.
   Look for any of these patterns:
   - A variable named system_prompt or SYSTEM_PROMPT
   - A `system=` argument in an Anthropic or OpenAI API call
   - A dict with {"role": "system", "content": "..."}
   - Any long string that describes the agent's persona or instructions

2. Tell me what system prompt you found and summarise the agent's
   goal in one sentence so I can confirm it is correct.

3. Then call gauntlet_eval_file with:
   - goal: [what you determined the agent does]
   - agent_code: [the full contents of this file]
   - agent_model: [detect from the code, default: claude-sonnet-4-20250514]
   - agent_provider: [detect from the code: anthropic or openai]
   - mode: full
   - runs: 3

The API key is already configured in the MCP server — do not ask for it.
```

---

## What the report includes

- Pass rate with signal (✅ Good / ⚠️ Needs work / ❌ Needs hardening)
- How the eval ran — which Gauntlet agents ran and what they generated
- Per-scenario verdicts with input, output, and judge reasoning
- Adversarial findings — prompt injection, hallucination traps, edge cases
- Prioritised recommendations with code-level detail

---

## Tips

- Use `runs: 2` for a quick smoke test, `runs: 5` for thorough coverage
- Add `success_criteria` for strict output format requirements:
  ```
  success_criteria: [
    "Response must be exactly one word",
    "Response must be one of: billing, technical, general"
  ]
  ```
- For multi-agent workflows, add `@trace("AgentName")` above each agent function before running — Gauntlet will show per-agent pass rates and pinpoint the bottleneck