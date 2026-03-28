# Gauntlet — Cursor Prompt

Copy and paste this into Cursor chat with your agent file open.
No setup needed beyond having the Gauntlet MCP server connected.

---

## Prompt to paste in Cursor

```
I want to evaluate this agent using the Gauntlet MCP tool.

1. First, read the current file and find the system prompt.
   Look for any of these patterns:
   - A variable named system_prompt or SYSTEM_PROMPT
   - A `system=` argument in an Anthropic or OpenAI API call
   - A dict with {"role": "system", "content": "..."}
   - Any long string that describes the agent's persona or instructions

2. Tell me what system prompt you found and summarise the agent's 
   goal in one sentence so I can confirm it's correct.

3. Then call gauntlet_eval_file with:
   - goal: [what you determined the agent does]
   - agent_code: [the full contents of this file]
   - agent_api_key: [ask me for this before running]
   - agent_model: [detect from the code, default: claude-sonnet-4-20250514]
   - agent_provider: [detect from the code: anthropic or openai]
   - mode: full
   - runs: 3

Important: always ask me for the API key before calling the tool.
Never guess or hardcode it.
```

---

## What happens next

Cursor will:
1. Read your file and find the system prompt automatically
2. Confirm the goal with you in one sentence
3. Ask for your API key
4. Call Gauntlet and return a full report inline:
   - Pass rate
   - Per-scenario verdicts with reasoning
   - Adversarial findings
   - Prioritised recommendations

---

## Example

You open `classifier_agent.py` and paste the prompt above.
Cursor replies:

> I found this system prompt:
> `"You are a support ticket classifier. Reply with only one word: billing, technical, or general."`
> Goal: classify support tickets into three categories.
> Please share your Anthropic API key to run the eval.

You reply with your key. Gauntlet runs and returns the report.

---

## Tips

- Works best with files under 500 lines
- Use `runs: 2` for a quick smoke test, `runs: 5` for thorough coverage
- Add `success_criteria` if your agent has strict output format requirements:
  ```
  success_criteria: [
    "Response must be exactly one word",
    "Response must be one of: billing, technical, general"
  ]
  ```