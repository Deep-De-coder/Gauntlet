# Gauntlet ⚔️

> Adversarial eval harness for multi-agent Claude API pipelines.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Gauntlet runs your agent through a battery of **realistic and adversarial test scenarios**, judges each output, and gives you a pass rate, cost breakdown, and concrete recommendations — in one command.

---

## Why Gauntlet?

Every existing eval tool (DeepEval, LangSmith, OpenAI Evals) focuses on single-model metrics or is locked to a specific framework. **Gauntlet is different:**

- ✅ **Framework-agnostic** — works with any Claude API pipeline, no LangChain required
- ✅ **Adversarial by default** — an agent actively tries to break your pipeline (prompt injection, goal hijacking, edge cases)
- ✅ **Plain-English goals** — you describe success in plain English; Gauntlet generates the test scenarios automatically
- ✅ **Three interfaces** — CLI, REST API, Python SDK
- ✅ **Zero config** — one env var and you're running

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/yourname/gauntlet
cd gauntlet
pip install -e ".[dev]"

# 2. Set your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 3. Run your first eval (CLI)
gauntlet run \
  --goal "Correctly categorise a support ticket and draft a polite reply" \
  --agent-description "Two-agent pipeline: Router classifies the ticket, Writer drafts the reply" \
  --mode adversarial \
  --runs 5
```

**Or start the API server:**
```bash
gauntlet serve
# → http://localhost:8000/docs
```

**Or use the Python SDK:**
```python
import asyncio
from gauntlet.core.models import EvalRequest, EvalMode
from gauntlet.core.runner import run_eval

async def my_agent(prompt: str) -> str:
    # Your real agent logic here
    return "agent response"

async def main():
    request = EvalRequest(
        goal="Correctly handle a customer refund request",
        agent_description="Single Claude agent with access to order lookup tool",
        mode=EvalMode.full,
        runs=10,
    )
    report = await run_eval(request, agent_fn=my_agent)
    print(f"Pass rate: {report.pass_rate:.0%}")
    print(f"Recommendations: {report.recommendations}")

asyncio.run(main())
```

---

## How it works

```
Your agent
    │
    ▼
┌────────────────────────────────────────┐
│           Gauntlet Runner               │
│                                         │
│  1. ScenarioAgent  → test inputs        │
│  2. AdversarialAgent → hostile inputs   │
│  3. JudgeAgent     → pass/fail verdict  │
│  4. ReportAgent    → recommendations   │
└──────────────────┬─────────────────────┘
                   ▼
          gauntlet.db (SQLite)
```

1. **ScenarioAgent** reads your plain-English goal and generates N realistic test inputs (happy paths + edge cases)
2. **AdversarialAgent** (adversarial/full modes) generates hostile inputs — prompt injection, contradictory requirements, hallucination traps
3. **JudgeAgent** runs each input through your agent and scores the output pass/fail with reasoning
4. **ReportAgent** analyses all failures and returns prioritised recommendations

---

## REST API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/eval/run` | Run an eval, get full report |
| GET | `/eval/{id}` | Fetch a past report |
| GET | `/evals` | List recent runs |

Full interactive docs at `http://localhost:8000/docs`.

---

## CLI reference

```bash
gauntlet run    --goal "..." --agent-description "..." [--mode standard|adversarial|full] [--runs N]
gauntlet list   [--limit N]
gauntlet show   <eval_id>
gauntlet serve  [--port 8000]
```

---

## Project structure

```
gauntlet/
  agents/          Four specialised Claude agents
  api/             FastAPI REST endpoints
  core/            Models + orchestration runner
  storage/         SQLite persistence
  cli.py           Typer CLI
  config.py        Env var loading
tests/
docs/
  ARCHITECTURE.md  System design
SKILL.md           Agent role definitions (for Claude Projects)
```

---

## Contributing

PRs welcome. Please read `docs/ARCHITECTURE.md` before contributing.

```bash
pip install -e ".[dev]"
pytest tests/
```

---

## License

MIT — see [LICENSE](LICENSE).
