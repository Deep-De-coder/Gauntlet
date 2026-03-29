# Gauntlet ⚔️

> Adversarial eval harness for multi-agent Claude API pipelines.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Gauntlet solves a problem every AI engineer hits in production: **how do you know your agent pipeline actually works before it breaks in front of a real user?**

It generates realistic and adversarial test scenarios, runs them through your agent, judges each output, and returns a pass rate, cost breakdown, and actionable recommendations — automatically.

---

## Why Gauntlet?

Existing tools (DeepEval, LangSmith) are either single-model focused or locked to a specific framework. Gauntlet is different:

- **Framework-agnostic** — works with any Claude or OpenAI pipeline, no LangChain required
- **Adversarial by default** — a dedicated agent tries to break your pipeline using prompt injection, contradictory requirements, and hallucination traps
- **Plain-English goals** — describe what your agent should do; Gauntlet generates the test scenarios automatically
- **Three interfaces** — CLI, REST API, Python SDK
- **Zero infrastructure** — one env var, SQLite storage, runs locally

---

## Quick start

```bash
git clone https://github.com/yourname/gauntlet-eval
cd gauntlet-eval
pip install -e ".[dev]"

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env
```

# MCP Setup — Cursor & Antigravity

Gauntlet works as an MCP server inside any MCP-compatible IDE.
Once connected, type `find` in the chat and Gauntlet handles the rest.

---

## Cursor setup

1. Open your Cursor config file:
   ```
   %APPDATA%\Cursor\User\globalStorage\cursor.mcp\config.json
   ```

2. Add this (update the `cwd` path to your Gauntlet folder):
   ```json
   {
     "mcpServers": {
       "gauntlet": {
         "command": "python",
         "args": ["-m", "gauntlet.mcp_server"],
         "cwd": "C:\\path\\to\\your\\gauntlet",
         "env": {
           "ANTHROPIC_API_KEY": "your-key-here"
         }
       }
     }
   }
   ```

3. Restart Cursor. You should see `gauntlet` with a green dot in Settings → MCP.

---

## Antigravity setup

1. Go to Settings → MCP Servers → Add Server
2. Paste the same JSON config above
3. Restart the MCP connection

---

## Using it

With your agent file open, type in the chat:

```
find
```

Gauntlet will scan your workspace, detect agent files, and return a numbered list:

```
Found 2 agent files in your workspace:

1. agents/classifier_agent.py
   - Provider: anthropic
   - Model: claude-sonnet-4-20250514
   - System prompt: You are a support ticket classifier...

To run Gauntlet, reply with:
Run Gauntlet on file 1
Goal: [what this agent does]
API key: sk-ant-...
```

Then reply and Gauntlet runs the full eval inline.

---

## Available MCP tools

| Tool | When to use |
|---|---|
| `gauntlet_find_agents` | Type `find` — scans workspace for agent files |
| `gauntlet_eval_file` | Paste agent code directly for eval |
| `gauntlet_eval_prompt` | Provide model + system prompt manually |

**REST API:**
```bash
gauntlet serve
# Docs at http://localhost:8000/docs
```

**Python SDK:**
```python
from gauntlet.core.runner import run_eval
from gauntlet.core.models import EvalRequest, EvalMode
import asyncio

async def my_agent(prompt: str) -> str:
    # your real agent here
    return "agent response"

request = EvalRequest(
    goal="Handle a customer refund request",
    agent_description="Claude agent with order lookup tool",
    mode=EvalMode.full,
    runs=5,
)
report = asyncio.run(run_eval(request, agent_fn=my_agent))
print(f"Pass rate: {report.pass_rate:.0%}")
```

---

## How it works

```
Your agent
    │
    ▼
┌─────────────────────────────────────┐
│          Gauntlet Runner             │
│                                      │
│  1. ScenarioAgent   → test inputs    │
│  2. AdversarialAgent→ hostile inputs │
│  3. JudgeAgent      → pass/fail      │
│  4. ReportAgent     → recommendations│
└──────────────────┬──────────────────┘
                   ▼
           gauntlet.db (SQLite)
```

| Agent | What it does |
|---|---|
| **ScenarioAgent** | Generates realistic test inputs from your plain-English goal |
| **AdversarialAgent** | Generates hostile inputs — prompt injection, edge cases, hallucination traps |
| **JudgeAgent** | Scores each agent response pass/fail with reasoning |
| **ReportAgent** | Synthesises failures into prioritised recommendations |

---

## Testing an external agent via the API

Point Gauntlet at any Claude or OpenAI model with a system prompt:

```json
{
  "goal": "Summarise a news article in exactly three bullet points",
  "agent_description": "News summarisation agent",
  "agent_provider": "anthropic",
  "agent_model": "claude-sonnet-4-20250514",
  "agent_api_key": "sk-ant-...",
  "agent_system_prompt": "You are a news summariser. Always respond with exactly 3 bullet points starting with •",
  "mode": "full",
  "runs": 5,
  "success_criteria": [
    "Response must contain exactly 3 bullet points",
    "Each bullet point must start with •",
    "Each bullet point must be under 30 words"
  ]
}
```

`success_criteria` is optional — if omitted, the judge evaluates against the `goal` alone.

---

## CLI reference

```bash
gauntlet run    --goal "..." --agent-description "..." [--mode standard|adversarial|full] [--runs N]
gauntlet list   [--limit N]
gauntlet show   <eval_id>
gauntlet serve  [--port 8000]
```

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/eval/run` | Run an eval, returns full report |
| `GET` | `/eval/{id}` | Fetch a past report |
| `GET` | `/eval/list` | List all reports |
| `GET` | `/health` | Liveness check |

Interactive docs at `http://localhost:8000/docs`.

---

## Project structure

```
gauntlet/
  agents/       ScenarioAgent, AdversarialAgent, JudgeAgent, ReportAgent
  api/          FastAPI REST endpoints
  core/         Pydantic models + eval runner
  storage/      SQLite persistence
  cli.py        Typer CLI
  config.py     Env var loading
tests/
docs/
  ARCHITECTURE.md
```

---

## Contributing

```bash
pip install -e ".[dev]"
pytest tests/
ruff check gauntlet/
```

PRs welcome. See `docs/ARCHITECTURE.md` for system design.

---

## License

MIT — see [LICENSE](LICENSE).