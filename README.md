# Gauntlet ⚔️

> Adversarial eval harness for any LLM agent pipeline — Claude, OpenAI, or your own

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![CI](https://github.com/Deep-De-coder/Gauntlet/actions/workflows/ci.yml/badge.svg)](https://github.com/Deep-De-coder/Gauntlet/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/gauntlet-eval.svg)](https://pypi.org/project/gauntlet-eval/)

📦 **[gauntlet-eval on PyPI](https://pypi.org/project/gauntlet-eval/)** — `pip install gauntlet-eval`

Gauntlet solves a problem every AI engineer hits in production: **how do you know your agent pipeline actually works before it breaks in front of a real user?**

Point it at Claude, OpenAI, or any LLM agent, describe what it should do in plain English, and get back a pass rate, per-agent breakdown, adversarial findings, and concrete recommendations automatically.

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

Or if using the CLI/API directly, add it to a `.env` file:
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

→ Full IDE setup: [docs/MCP_SETUP.md](docs/MCP_SETUP.md)

---

## Three ways to use it

### 1. IDE — least manual work
Connect Gauntlet as an MCP server in Cursor or Antigravity. Type `find` in the chat — Gauntlet scans your workspace, detects agent files automatically, and runs the eval. No JSON, no terminal.

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
| **JudgeAgent** | Scores each response pass/fail — supports custom success criteria |
| **ReportAgent** | Turns failures into prioritised, code-level recommendations |

Average cost per full eval run(Approximate): **~$0.002**

---

## Single-agent eval

Point Gauntlet at any Claude or OpenAI model with a system prompt via the REST API, CLI, or Python SDK. It generates test scenarios, runs them through your agent, and returns a full report.

→ See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for SDK usage.

---

## Multi-agent eval — automatic flow tracing

Add `@trace("AgentName")` above each agent function. Gauntlet automatically records every call, judges each step individually, and pinpoints exactly which agent is the bottleneck.

→ See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full `@trace` example.

The report shows the complete execution flow:
```
Traced flow: Router → Writer → Validator

⚠️ Bottleneck: Writer (43% pass rate)

| Agent     | Pass Rate | Status        |
|-----------|-----------|---------------|
| Router    | 86%       | ✅            |
| Writer    | 43%       | ❌ bottleneck |
| Validator | 100%      | ✅            |

Scenario s2 — FAIL
  ✅ Router    → returned "billing" (120ms)
  ❌ Writer    → returned "" — output was empty
  ⚠️ Validator → never reached — upstream failure
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