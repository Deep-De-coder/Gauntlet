# gauntlet/api/app.py
#
# WHY: The previous startup error came from two places:
#   1. config.py raising at import time (fixed in config.py)
#   2. Missing exception handlers — any unhandled exception in a route
#      would return a raw 500 with no JSON body, confusing FastAPI's
#      schema generator on the first request.
#
# We now use FastAPI's `lifespan` context manager (the modern replacement
# for deprecated @app.on_event) to validate the API key ONCE at startup
# and print a clear error instead of a silent crash.
#
# The /health endpoint gives Docker and CI a cheap liveness check.

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
    description="Adversarial eval harness for multi-agent Claude API pipelines.",
    version="0.1.0",
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
    return {"status": "ok"}

@app.post("/eval/run", response_model=EvalReport, tags=["eval"])
async def eval_run(request: EvalRequest):
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
    try:
        return await list_reports()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/eval/{report_id}", response_model=EvalReport, tags=["eval"])
async def eval_get(report_id: str):
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id!r} not found.")
    return report