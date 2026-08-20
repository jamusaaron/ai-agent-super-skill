#!/usr/bin/env python3
"""Runnable extract of the FastAPI agent server from SKILL.md (section 8.2).

The endpoints and request/response models follow the skill. The agent
"execution logic" is a minimal deterministic stub (no LLM key required) so the
service can be exercised end-to-end, plus a tiny in-memory job store so the
async endpoints actually work.

Run it:

    python3 -m uvicorn agent_server:app --app-dir examples --host 0.0.0.0 --port 8080

Then:

    curl -s localhost:8080/health
    curl -s -X POST localhost:8080/agent/run -H 'content-type: application/json' \\
        -d '{"query": "hello", "max_steps": 3}'
"""

import time
import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Agent Service", version="1.0.0")

# Minimal in-memory job store for the async endpoints.
_JOBS: dict[str, dict] = {}


class AgentRequest(BaseModel):
    query: str
    session_id: str | None = None
    max_steps: int = 10
    metadata: dict = {}


class AgentResponse(BaseModel):
    result: str
    session_id: str
    steps_used: int
    cost_usd: float
    latency_ms: float


def _run_agent_logic(request: AgentRequest) -> tuple[str, int, float]:
    """Deterministic stand-in for real agent execution.

    Echoes the query and reports how many (capped) steps it "used". Returns
    ``(result, steps_used, cost_usd)``.
    """
    steps_used = min(max(request.max_steps, 1), 3)
    result = f"Processed query in {steps_used} step(s): {request.query}"
    cost_usd = round(steps_used * 0.0001, 6)
    return result, steps_used, cost_usd


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/agent/run", response_model=AgentResponse)
async def run_agent(request: AgentRequest):
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    session_id = request.session_id or str(uuid.uuid4())
    start = time.time()
    result, steps_used, cost_usd = _run_agent_logic(request)
    latency_ms = (time.time() - start) * 1000
    return AgentResponse(
        result=result,
        session_id=session_id,
        steps_used=steps_used,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
    )


@app.post("/agent/run-async")
async def run_agent_async(request: AgentRequest):
    job_id = str(uuid.uuid4())
    result, steps_used, cost_usd = _run_agent_logic(request)
    _JOBS[job_id] = {
        "status": "completed",
        "result": result,
        "steps_used": steps_used,
        "cost_usd": cost_usd,
    }
    return {"job_id": job_id, "status": "queued"}


@app.get("/agent/status/{job_id}")
async def get_status(job_id: str):
    job = _JOBS.get(job_id)
    if job is None:
        return {"job_id": job_id, "status": "unknown"}
    return {"job_id": job_id, **job}
