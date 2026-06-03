"""Pipeline orchestrator – drives the four compilation stages with metrics."""

from __future__ import annotations

import logging
import time
from typing import List

from ..schemas.intent import Intent
from ..schemas.design import SystemDesign
from ..schemas.app_config import AppConfig
from ..schemas.pipeline_result import (
    PipelineMetrics,
    PipelineResult,
    StageResult,
    StageStatus,
    ValidationIssue,
)
from ..validation.validator import validate_config
from ..validation.repair import repair_config
from ..runtime.generator import generate_code
from .intent_extraction import extract_intent
from .system_design import design_system
from .schema_generation import generate_schemas
from .refinement import refine

logger = logging.getLogger(__name__)

MAX_REPAIR_CYCLES = 3


def compile_prompt(prompt: str) -> PipelineResult:
    """Run the full compilation pipeline: prompt → config → code."""

    stage_results: List[StageResult] = []
    all_issues: List[ValidationIssue] = []
    t_start = time.perf_counter()

    # ── Stage 1: Intent Extraction ───────────────────────────────────────
    s1 = StageResult(stage_name="intent_extraction", status=StageStatus.RUNNING)
    t1 = time.perf_counter()
    try:
        intent = extract_intent(prompt)
        s1.status = StageStatus.COMPLETED
    except Exception as exc:
        s1.status = StageStatus.FAILED
        s1.error_message = str(exc)
        stage_results.append(s1)
        return _fail(stage_results, all_issues, t_start, str(exc))
    s1.duration_ms = (time.perf_counter() - t1) * 1000
    stage_results.append(s1)

    # ── Stage 2: System Design ───────────────────────────────────────────
    s2 = StageResult(stage_name="system_design", status=StageStatus.RUNNING)
    t2 = time.perf_counter()
    try:
        design = design_system(intent)
        s2.status = StageStatus.COMPLETED
    except Exception as exc:
        s2.status = StageStatus.FAILED
        s2.error_message = str(exc)
        stage_results.append(s2)
        return _fail(stage_results, all_issues, t_start, str(exc))
    s2.duration_ms = (time.perf_counter() - t2) * 1000
    stage_results.append(s2)

    # ── Stage 3: Schema Generation ───────────────────────────────────────
    s3 = StageResult(stage_name="schema_generation", status=StageStatus.RUNNING)
    t3 = time.perf_counter()
    try:
        app_config = generate_schemas(design)
        s3.status = StageStatus.COMPLETED
    except Exception as exc:
        s3.status = StageStatus.FAILED
        s3.error_message = str(exc)
        stage_results.append(s3)
        return _fail(stage_results, all_issues, t_start, str(exc))
    s3.duration_ms = (time.perf_counter() - t3) * 1000
    stage_results.append(s3)

    # ── Stage 4: Refinement ──────────────────────────────────────────────
    s4 = StageResult(stage_name="refinement", status=StageStatus.RUNNING)
    t4 = time.perf_counter()
    try:
        app_config, refinement_issues = refine(app_config)
        all_issues.extend(refinement_issues)
        s4.validation_issues = refinement_issues
        s4.status = StageStatus.COMPLETED
    except Exception as exc:
        s4.status = StageStatus.FAILED
        s4.error_message = str(exc)
        stage_results.append(s4)
        return _fail(stage_results, all_issues, t_start, str(exc))
    s4.duration_ms = (time.perf_counter() - t4) * 1000
    stage_results.append(s4)

    # ── Validation + Repair loop ─────────────────────────────────────────
    total_retries = 0
    final_v_issues: List[ValidationIssue] = []
    for cycle in range(MAX_REPAIR_CYCLES):
        final_v_issues = validate_config(app_config)
        errors = [i for i in final_v_issues if i.severity == "error"]
        if not errors:
            break
        logger.info("Validation cycle %d: %d errors – repairing", cycle + 1, len(errors))
        app_config, repair_issues = repair_config(app_config, errors)
        all_issues.extend(repair_issues)
        total_retries += 1
    all_issues.extend(final_v_issues)

    # ── Code Generation ──────────────────────────────────────────────────
    generated = generate_code(app_config)

    # ── Assemble result ──────────────────────────────────────────────────
    total_ms = (time.perf_counter() - t_start) * 1000
    repaired = sum(1 for i in all_issues if i.auto_repaired)

    metrics = PipelineMetrics(
        total_duration_ms=round(total_ms, 2),
        total_retries=total_retries,
        validation_issues_found=len(all_issues),
        validation_issues_repaired=repaired,
        stages_completed=sum(1 for s in stage_results if s.status == StageStatus.COMPLETED),
        stages_failed=sum(1 for s in stage_results if s.status == StageStatus.FAILED),
        confidence_score=intent.confidence_score,
    )

    return PipelineResult(
        success=True,
        intent=intent,
        design=design,
        app_config=app_config,
        generated_code=generated,
        stage_results=stage_results,
        metrics=metrics,
        validation_issues=all_issues,
        assumptions=intent.assumptions,
    )


def _fail(
    stages: List[StageResult],
    issues: List[ValidationIssue],
    t_start: float,
    error: str,
) -> PipelineResult:
    total_ms = (time.perf_counter() - t_start) * 1000
    return PipelineResult(
        success=False,
        stage_results=stages,
        metrics=PipelineMetrics(
            total_duration_ms=round(total_ms, 2),
            stages_completed=sum(1 for s in stages if s.status == StageStatus.COMPLETED),
            stages_failed=sum(1 for s in stages if s.status == StageStatus.FAILED),
        ),
        validation_issues=issues,
        error=error,
    )
