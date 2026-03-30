# Gauntlet — Architecture

## Overview

Gauntlet is a framework-agnostic adversarial eval harness for any LLM agent pipeline — single agent or multi-agent, Claude, OpenAI, or any model behind an HTTP endpoint. It exposes a REST API, a CLI, an MCP server, and a Python SDK.

---

## Evaluation pipeline

```
Your agent (single or multi-agent)
     │
     ▼
┌─────────────────────────────────────────┐
│              Gauntlet Runner             │
│                                          │
│  1. ScenarioAgent   → test inputs        │
│  2. AdversarialAgent→ hostile inputs     │
│  3. JudgeAgent      → pass/fail verdict  │
│  4. ReportAgent     → recommendations   │
└──────────────────┬──────────────────────┘
                   │
                   ▼
              SQLite DB (gauntlet.db)
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
   REST API       CLI       MCP Server
  (/docs)    (gauntlet run)  (Cursor/Antigravity)
```

---

## Multi-agent tracing

When agents are decorated with `@trace`, the runner intercepts every call automatically — no other changes to user code required.

```
Your workflow
     │
     ├── @trace("Router")    → span recorded
     │        │
     ├── @trace("Writer")    → span recorded
     │        │
     └── @trace("Validator") → span recorded
              │
              ▼
     JudgeAgent evaluates each span individually
              │
              ▼
     Per-agent pass rates + bottleneck detection
```

Usage:

```python
from gauntlet import trace
from gauntlet.core.runner import run_eval
from gauntlet.core.models import EvalRequest, EvalMode
import asyncio

@trace("Router")
async def router(input: str) -> str:
    ...

@trace("Writer")
async def writer(input: str) -> str:
    ...

@trace("Validator")
async def validator(input: str) -> str:
    ...

async def my_workflow(scenario: str) -> str:
    route  = await router(scenario)
    draft  = await writer(route)
    result = await validator(draft)
    return result

request = EvalRequest(
    goal="Classify and respond to support tickets",
    agent_description="Router → Writer → Validator pipeline",
    agent_api_key="sk-ant-...",
    mode=EvalMode.full,
    runs=5,
)
report = asyncio.run(run_eval(request, agent_fn=my_workflow))
print(f"Bottleneck: {report.bottleneck_agent}")
```

---

## Single-agent eval (Python SDK)

```python
from gauntlet.core.runner import run_eval
from gauntlet.core.models import EvalRequest, EvalMode
import asyncio

request = EvalRequest(
    goal="Classify a support ticket as billing, technical, or general",
    agent_description="Single Claude classifier",
    agent_api_key="sk-ant-...",
    agent_system_prompt="You are a classifier. Reply with one word.",
    mode=EvalMode.full,
    runs=5,
)
report = asyncio.run(run_eval(request))
print(f"Pass rate: {report.pass_rate:.0%}")
print(f"Recommendations: {report.recommendations}")
```

---

## Key design decisions

- **Framework-agnostic** — any async callable `str → str`, no LangChain required
- **Zero-config storage** — SQLite, no server needed
- **One env var** — only `ANTHROPIC_API_KEY` required to start
- **Automatic tracing** — `@trace` decorator requires zero changes to existing agent logic
- **Three interfaces** — CLI, REST API, MCP server — same eval engine behind all three

---

## Directory structure

```
gauntlet/
  agents/
    scenario.py      # Generates realistic test inputs from plain-English goal
    judge.py         # Scores agent outputs pass/fail, supports custom criteria
    adversarial.py   # Generates hostile inputs — prompt injection, edge cases
    report.py        # Synthesises failures into prioritised recommendations
  api/
    app.py           # FastAPI REST endpoints
  core/
    models.py        # Pydantic models — EvalRequest, EvalReport, AgentTrace, etc.
    runner.py        # Orchestrates the full eval pipeline
  storage/
    db.py            # SQLite read/write helpers
  cli.py             # Typer CLI — gauntlet run / list / show / serve
  config.py          # Env var loading
  tracing.py         # @trace decorator and global span store
  reporting.py       # Shared report formatter (CLI, API, MCP)
  mcp_server.py      # MCP server — gauntlet_find_agents, gauntlet_eval_file, gauntlet_eval_prompt
  __init__.py        # Exports: trace, GauntletTracer

tests/
  test_models.py     # Model validation tests (no API key needed)
  test_gauntlet.py   # End-to-end tests with mocked Claude calls

docs/
  ARCHITECTURE.md    # This file
  MCP_SETUP.md       # Cursor and Antigravity setup instructions
  CURSOR_PROMPT.md   # Ready-made prompt to paste in Cursor chat
```

---

## Interfaces

| Interface | How to use |
|---|---|
| CLI | `gauntlet run --goal "..." --agent-api-key "..."` |
| REST API | `POST http://localhost:8000/eval/run` |
| Python SDK | `from gauntlet.core.runner import run_eval` |
| MCP Server | Type `find` in Cursor or Antigravity chat |

---

## Data models

| Model | Purpose |
|---|---|
| `EvalRequest` | Input — goal, agent config, mode, success criteria |
| `EvalReport` | Output — pass rate, scenarios, per-agent stats, recommendations |
| `ScenarioResult` | One scenario's verdict including per-step trace results |
| `AgentStepResult` | One traced agent step — input, output, pass/fail, latency |
| `AgentPassRate` | Aggregated pass rate for one agent across all scenarios |

---

## Roadmap

- [ ] Async parallel scenario execution
- [ ] Web dashboard (HTML report output)
- [ ] `agent_url` support — evaluate any deployed HTTP endpoint
- [ ] Multi-turn conversation evals
- [ ] Cost Pareto curve — scenarios vs eval confidence tradeoff
- [ ] GitHub Actions integration example