# Gauntlet ⚔️

> Adversarial eval harness for multi-agent Claude API pipelines.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/Deep-De-coder/Gauntlet/actions/workflows/ci.yml/badge.svg)](https://github.com/Deep-De-coder/Gauntlet/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/gauntlet-eval.svg)](https://pypi.org/project/gauntlet-eval/)

Gauntlet solves a problem every AI engineer hits in production: **how do you know your agent pipeline actually works before it breaks in front of a real user?**

Point it at any Claude or OpenAI agent, describe what it should do in plain English, and get back a pass rate, adversarial findings, and concrete recommendations — automatically.

---

## Install
```bash
pip install gauntlet-eval
```

Add your Anthropic API key to your MCP config (recommended):
```json
{
  "mcpServers": {
    "gauntlet": {
      "command": "python",
      "args": ["-m", "gauntlet.mcp_server"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key-here"
      }
    }
  }
}
```

Or if using the CLI/API directly, add it to a `.env` file instead:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

→ Full IDE setup: [docs/MCP_SETUP.md](docs/MCP_SETUP.md)

---

## Three ways to use it

### 1. IDE (MCP Servers) — least manual work
Connect Gauntlet as an MCP server in Cursor or Antigravity, then type `find` in the chat. Gauntlet scans your workspace, detects agent files, and walks you through the eval.

→ [docs/MCP_SETUP.md](docs/MCP_SETUP.md)

### 2. REST API
```bash
gauntlet serve
# Interactive docs at http://localhost:8000/docs
```

### 3. CLI
```bash
gauntlet run \
  --goal "Classify a support ticket as billing, technical, or general" \
  --agent-description "Single Claude classifier" \
  --agent-api-key "sk-ant-..." \
  --system-prompt "You are a classifier. Reply with one word." \
  --mode full \
  --runs 5
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
| **AdversarialAgent** | Prompt injection, contradictory requirements, hallucination traps |
| **JudgeAgent** | Scores each response pass/fail — supports custom criteria |
| **ReportAgent** | Turns failures into prioritised, code-level recommendations |

---

## Python SDK

```python
from gauntlet.core.runner import run_eval
from gauntlet.core.models import EvalRequest, EvalMode
import asyncio

request = EvalRequest(
    goal="Handle a customer refund request",
    agent_description="Claude agent with order lookup tool",
    agent_api_key="sk-ant-...",
    agent_system_prompt="You are a refund handler...",
    mode=EvalMode.full,
    runs=5,
)
report = asyncio.run(run_eval(request))
print(f"Pass rate: {report.pass_rate:.0%}")
```

---

## Docs

| Document | What's in it |
|---|---|
| [docs/MCP_SETUP.md](docs/MCP_SETUP.md) | Cursor & Antigravity setup, `find` command walkthrough |
| [docs/CURSOR_PROMPT.md](docs/CURSOR_PROMPT.md) | Ready-made prompt to paste in Cursor chat |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, agent flow, data models |

---

## Contributing

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check gauntlet/
```

PRs welcome.

---

## License

MIT — see [LICENSE](LICENSE).
