"""FastAPI application – web interface for the Software Generation Compiler."""

from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .pipeline.orchestrator import compile_prompt
from .evaluation.framework import run_evaluation
from .evaluation.prompts import ALL_PROMPTS, REAL_PROMPTS, EDGE_PROMPTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Software Generation Compiler",
    description="Natural language → structured config → validated → executable application",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


class CompileRequest(BaseModel):
    prompt: str


class EvalRequest(BaseModel):
    category: str = "all"  # "all", "real", "edge"


@app.get("/")
async def root():
    index = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Software Generation Compiler API", "docs": "/docs"}


@app.post("/api/compile")
def compile_endpoint(req: CompileRequest):
    """Run the full compilation pipeline on a natural-language prompt."""
    if not req.prompt or not req.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    try:
        result = compile_prompt(req.prompt)
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/evaluate")
def evaluate_endpoint(req: EvalRequest):
    """Run the evaluation framework on test prompts."""
    if req.category == "real":
        prompts = REAL_PROMPTS
    elif req.category == "edge":
        prompts = EDGE_PROMPTS
    else:
        prompts = ALL_PROMPTS

    try:
        report = run_evaluation(prompts)
        return report.model_dump(mode="json")
    except Exception as exc:
        logger.exception("Evaluation error")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/prompts")
async def list_prompts():
    """List all available test prompts."""
    return [
        {
            "id": p.id,
            "prompt": p.prompt,
            "category": p.category,
            "description": p.description,
        }
        for p in ALL_PROMPTS
    ]


@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}
