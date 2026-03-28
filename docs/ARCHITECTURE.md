# Gauntlet — Architecture

## Overview
Gauntlet is a framework-agnostic, adversarial eval harness for multi-agent
Claude API pipelines. It exposes a REST API, a CLI, and a Python SDK.

## Agent pipeline

```
User's agent
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
          ┌────────┴────────┐
          ▼                 ▼
      REST API           CLI
   (FastAPI /docs)   (gauntlet run)
```

## Key design decisions
- **Framework-agnostic**: user's agent is any async callable `str → str`
- **Zero-config storage**: SQLite, no server needed
- **One env var**: only `ANTHROPIC_API_KEY` required to start
- **Bring your own agent**: HTTP API uses demo agent; Python SDK takes real agent

## Directory structure
```
gauntlet/
  agents/
    scenario.py      # Generates test inputs from plain-English goal
    judge.py         # Scores agent outputs pass/fail
    adversarial.py   # Generates hostile edge-case inputs
    report.py        # Synthesises recommendations from results
  api/
    app.py           # FastAPI REST endpoints
  core/
    models.py        # Pydantic models (EvalRequest, EvalReport, etc.)
    runner.py        # Orchestrates the full eval pipeline
  storage/
    db.py            # SQLite read/write helpers
  cli.py             # Typer CLI (gauntlet run / list / show / serve)
  config.py          # Env var loading

tests/
  test_models.py     # Unit tests (no API key needed)

docs/
  ARCHITECTURE.md    # This file
```

## Interfaces
| Interface   | How to use                                      |
|-------------|------------------------------------------------|
| CLI         | `gauntlet run --goal "..." --agent-description "..."` |
| REST API    | `POST http://localhost:8000/eval/run`           |
| Python SDK  | `from gauntlet.core.runner import run_eval`    |

## Future roadmap
- [ ] Async parallel scenario execution
- [ ] Web dashboard (HTML report output)
- [ ] GitHub Actions integration example
- [ ] Cost Pareto curve visualisation
- [ ] Support for multi-turn agent conversations
