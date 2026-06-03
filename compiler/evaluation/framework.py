"""Evaluation framework – runs all test prompts and collects metrics."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from ..pipeline.orchestrator import compile_prompt
from .prompts import ALL_PROMPTS, TestPrompt


class PromptResult(BaseModel):
    prompt_id: str
    category: str
    description: str
    success: bool
    duration_ms: float
    retries: int
    issues_found: int
    issues_repaired: int
    stages_completed: int
    stages_failed: int
    confidence: float
    entity_count: int = 0
    page_count: int = 0
    endpoint_count: int = 0
    table_count: int = 0
    generated_files: int = 0
    error: str | None = None


class EvaluationReport(BaseModel):
    total_prompts: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    avg_retries: float = 0.0
    total_issues_found: int = 0
    total_issues_repaired: int = 0
    results: List[PromptResult] = Field(default_factory=list)
    failure_types: Dict[str, int] = Field(default_factory=dict)
    category_breakdown: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


def run_evaluation(prompts: List[TestPrompt] | None = None) -> EvaluationReport:
    """Execute each prompt through the pipeline and aggregate metrics."""

    prompts = prompts or ALL_PROMPTS
    results: List[PromptResult] = []

    for tp in prompts:
        t0 = time.perf_counter()
        try:
            pr = compile_prompt(tp.prompt)
            duration = (time.perf_counter() - t0) * 1000
            results.append(PromptResult(
                prompt_id=tp.id,
                category=tp.category,
                description=tp.description,
                success=pr.success,
                duration_ms=round(duration, 2),
                retries=pr.metrics.total_retries,
                issues_found=pr.metrics.validation_issues_found,
                issues_repaired=pr.metrics.validation_issues_repaired,
                stages_completed=pr.metrics.stages_completed,
                stages_failed=pr.metrics.stages_failed,
                confidence=pr.metrics.confidence_score,
                entity_count=len(pr.design.entities) if pr.design else 0,
                page_count=len(pr.app_config.ui_schema.pages) if pr.app_config else 0,
                endpoint_count=len(pr.app_config.api_schema.endpoints) if pr.app_config else 0,
                table_count=len(pr.app_config.db_schema.tables) if pr.app_config else 0,
                generated_files=len(pr.generated_code),
                error=pr.error,
            ))
        except Exception as exc:
            duration = (time.perf_counter() - t0) * 1000
            results.append(PromptResult(
                prompt_id=tp.id,
                category=tp.category,
                description=tp.description,
                success=False,
                duration_ms=round(duration, 2),
                retries=0,
                issues_found=0,
                issues_repaired=0,
                stages_completed=0,
                stages_failed=1,
                confidence=0.0,
                error=str(exc),
            ))

    return _aggregate(results)


def _aggregate(results: List[PromptResult]) -> EvaluationReport:
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failed = total - successful

    durations = [r.duration_ms for r in results]
    retries = [r.retries for r in results]

    failure_types: Dict[str, int] = {}
    for r in results:
        if not r.success and r.error:
            key = r.error[:60]
            failure_types[key] = failure_types.get(key, 0) + 1

    cat_breakdown: Dict[str, Dict[str, Any]] = {}
    for r in results:
        cat = r.category
        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"total": 0, "success": 0, "avg_ms": 0.0, "durations": []}
        cat_breakdown[cat]["total"] += 1
        if r.success:
            cat_breakdown[cat]["success"] += 1
        cat_breakdown[cat]["durations"].append(r.duration_ms)

    for cat in cat_breakdown:
        ds = cat_breakdown[cat].pop("durations")
        cat_breakdown[cat]["avg_ms"] = round(sum(ds) / len(ds), 2) if ds else 0
        cat_breakdown[cat]["success_rate"] = round(
            cat_breakdown[cat]["success"] / cat_breakdown[cat]["total"] * 100, 1
        ) if cat_breakdown[cat]["total"] else 0

    return EvaluationReport(
        total_prompts=total,
        successful=successful,
        failed=failed,
        success_rate=round(successful / total * 100, 1) if total else 0,
        avg_duration_ms=round(sum(durations) / len(durations), 2) if durations else 0,
        avg_retries=round(sum(retries) / len(retries), 2) if retries else 0,
        total_issues_found=sum(r.issues_found for r in results),
        total_issues_repaired=sum(r.issues_repaired for r in results),
        results=results,
        failure_types=failure_types,
        category_breakdown=cat_breakdown,
    )
