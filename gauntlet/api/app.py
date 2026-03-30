"""Gauntlet REST API."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi

from gauntlet.config import get_api_key
from gauntlet.core.models import EvalRequest, EvalReport
from gauntlet.core.runner import run_eval
from gauntlet.storage.db import list_reports, get_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        get_api_key()
        print("✓ ANTHROPIC_API_KEY found — Gauntlet API ready.")
    except EnvironmentError as exc:
        print(f"⚠  WARNING: {exc}")
    yield


app = FastAPI(
    title="Gauntlet",
    description="Adversarial eval harness for any LLM agent pipeline.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/openapi.json", include_in_schema=False)
async def custom_openapi():
    return JSONResponse(
        get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
    )


@app.get("/health", tags=["meta"])
async def health():
    """Liveness check — returns 200 if the server is running."""
    return {"status": "ok"}


@app.post("/eval/run", response_model=EvalReport, tags=["eval"])
async def eval_run(request: EvalRequest):
    """
    Run a full Gauntlet eval against your agent.

    Supports single-agent and multi-agent workflows.
    For multi-agent, decorate each sub-agent with @trace in your code.
    """
    try:
        get_api_key()
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    try:
        report = await run_eval(request)
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/eval/list", tags=["eval"])
async def eval_list():
    """Return a summary list of all stored eval reports."""
    try:
        return await list_reports()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/eval/{report_id}", response_model=EvalReport, tags=["eval"])
async def eval_get(report_id: str):
    """Fetch a single eval report by its ID."""
    report = await get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id!r} not found.")
    return report