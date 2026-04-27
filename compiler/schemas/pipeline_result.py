"""Pipeline execution result wrapper with metrics and diagnostics."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .app_config import AppConfig
from .design import SystemDesign
from .intent import Intent


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REPAIRED = "repaired"


class ValidationIssue(BaseModel):
    severity: str = Field(..., pattern=r"^(error|warning|info)$")
    layer: str
    field: str
    message: str
    auto_repaired: bool = False
    repair_action: Optional[str] = None


class StageResult(BaseModel):
    stage_name: str
    status: StageStatus = StageStatus.PENDING
    duration_ms: float = 0.0
    retries: int = 0
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    error_message: Optional[str] = None


class PipelineMetrics(BaseModel):
    total_duration_ms: float = 0.0
    total_retries: int = 0
    validation_issues_found: int = 0
    validation_issues_repaired: int = 0
    stages_completed: int = 0
    stages_failed: int = 0
    confidence_score: float = 0.0


class GeneratedCode(BaseModel):
    filename: str
    language: str
    content: str
    description: str = ""


class PipelineResult(BaseModel):
    """Complete pipeline execution result."""

    success: bool = False
    intent: Optional[Intent] = None
    design: Optional[SystemDesign] = None
    app_config: Optional[AppConfig] = None
    generated_code: List[GeneratedCode] = Field(default_factory=list)
    stage_results: List[StageResult] = Field(default_factory=list)
    metrics: PipelineMetrics = Field(default_factory=PipelineMetrics)
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    error: Optional[str] = None
