# Gauntlet SKILL.md

## What this project is
Gauntlet is an adversarial eval harness for multi-agent Claude API pipelines.
It orchestrates four specialised agents to test, attack, judge, and report on
any user-supplied agent pipeline.

## Agent roles
| Agent            | File                        | Responsibility                                |
|------------------|-----------------------------|-----------------------------------------------|
| ScenarioAgent    | gauntlet/agents/scenario.py | Generates diverse realistic test inputs       |
| JudgeAgent       | gauntlet/agents/judge.py    | Scores each run pass/fail with reasoning      |
| AdversarialAgent | gauntlet/agents/adversarial.py | Generates hostile inputs to break the pipeline |
| ReportAgent      | gauntlet/agents/report.py   | Synthesises actionable recommendations        |

## Current status (update as you build)
- [x] Project scaffolded
- [x] Core models (EvalRequest, EvalReport, ScenarioResult)
- [x] Runner orchestration logic
- [x] All four agents implemented
- [x] SQLite storage
- [x] REST API (FastAPI)
- [x] CLI (Typer + Rich)
- [ ] Tests passing end-to-end
- [ ] Docker setup
- [ ] README complete

## Key conventions
- All agents are class-based with an `async` main method
- All Claude calls use `GAUNTLET_MODEL` from config (never hardcoded)
- All JSON parsing strips markdown fences before parsing
- Cost is estimated from token counts after every judge call
- The runner is the ONLY place that calls `save_report()`

## Tech stack
Python 3.10+, anthropic SDK, FastAPI, Pydantic v2, Typer, Rich, SQLite

## Where to add new features
- New agent type → `gauntlet/agents/newagent.py` + wire into `runner.py`
- New API endpoint → `gauntlet/api/app.py`
- New CLI command → `gauntlet/cli.py` using `@app.command()`
- New storage query → `gauntlet/storage/db.py`
