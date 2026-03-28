"""
Gauntlet REST API (FastAPI).

Start: uvicorn gauntlet.api.app:app --reload
Docs:  http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gauntlet.core.models import EvalMode, EvalReport, EvalRequest
from gauntlet.core.runner import run_eval
from gauntlet.storage.db  import get_report, list_reports

app = FastAPI(
    title="Gauntlet",
    description=(
        "**Adversarial eval harness for multi-agent Claude pipelines.**\n\n"
        "Quick start:\n"
        "1. `POST /eval/run` — describe your agent + goal, get back a full report\n"
        "2. `GET /eval/{eval_id}` — fetch any past report by ID\n\n"
        "GitHub: https://github.com/yourname/gauntlet"
    ),
    version="0.1.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# Built-in demo agent (used when testing via the HTTP API directly)
async def _demo_agent(prompt: str) -> str:
    import anthropic
    from gauntlet.config import ANTHROPIC_API_KEY, GAUNTLET_MODEL
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=GAUNTLET_MODEL, max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


class RunRequest(BaseModel):
    goal: str
    agent_description: str
    mode: EvalMode = EvalMode.standard
    runs: int = 5


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Gauntlet", "version": "0.1.0", "docs": "/docs"}


@app.post("/eval/run", response_model=EvalReport, tags=["Eval"])
async def eval_run(body: RunRequest):
    """Run an eval. Uses the built-in demo agent — for your own agent use the Python SDK."""
    report = await run_eval(
        EvalRequest(goal=body.goal, agent_description=body.agent_description,
                    mode=body.mode, runs=body.runs),
        agent_fn=_demo_agent,
    )
    return report


@app.get("/eval/{eval_id}", response_model=EvalReport, tags=["Eval"])
async def get_eval(eval_id: str):
    """Fetch a completed eval report by ID."""
    report = await get_report(eval_id)
    if not report:
        raise HTTPException(404, f"Eval '{eval_id}' not found.")
    return report


@app.get("/evals", tags=["Eval"])
async def list_evals(limit: int = 20):
    """List recent eval runs."""
    return await list_reports(limit=limit)
