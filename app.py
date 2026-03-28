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

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from gauntlet.config import get_api_key
from gauntlet.core.models import EvalRequest, EvalReport
from gauntlet.core.runner import run_eval
from gauntlet.storage.db import list_reports, get_report


# --------------------------------------------------------------------------- #
# Lifespan: runs once at startup and once at shutdown
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP — validate key early so the error message is obvious
    try:
        get_api_key()
        print("✓ ANTHROPIC_API_KEY found — Gauntlet API ready.")
    except EnvironmentError as exc:
        # Don't crash the server; warn loudly so the operator can fix it
        # without needing to restart. Requests will fail with 503 until fixed.
        print(f"⚠  WARNING: {exc}")
    yield
    # SHUTDOWN — nothing to clean up (SQLite closes its own connections)


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Gauntlet",
    description=(
        "Adversarial eval harness for multi-agent Claude API pipelines. "
        "Run evals, inspect results, and get actionable recommendations."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get("/health", tags=["meta"])
async def health():
    """Liveness check — returns 200 if the server is running."""
    return {"status": "ok"}


@app.post("/eval/run", response_model=EvalReport, tags=["eval"])
async def eval_run(request: EvalRequest):
    """Run a full Gauntlet eval against the built-in demo agent.

    Pass `mode` as `"standard"`, `"adversarial"`, or `"full"`.
    """
    try:
        get_api_key()  # Raises 503-style error if key missing
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    try:
        report = await run_eval(request)
        return report
    except Exception as exc:
        # Surface the real error in the response body so it's debuggable
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/eval/list", tags=["eval"])
async def eval_list():
    """Return a summary list of all stored eval reports."""
    try:
        return list_reports()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/eval/{report_id}", response_model=EvalReport, tags=["eval"])
async def eval_get(report_id: str):
    """Fetch a single eval report by its ID."""
    report = get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report {report_id!r} not found.")
    return report
