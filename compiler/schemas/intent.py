"""Stage 1 output: Structured representation of user intent."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AppType(str, Enum):
    CRM = "crm"
    ECOMMERCE = "ecommerce"
    SOCIAL = "social_network"
    BLOG = "blog"
    PROJECT_MANAGEMENT = "project_management"
    SAAS = "saas"
    MARKETPLACE = "marketplace"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    CUSTOM = "custom"


class FeatureCategory(str, Enum):
    AUTH = "authentication"
    CRUD = "crud"
    DASHBOARD = "dashboard"
    PAYMENTS = "payments"
    ANALYTICS = "analytics"
    MESSAGING = "messaging"
    SEARCH = "search"
    NOTIFICATIONS = "notifications"
    FILE_UPLOAD = "file_upload"
    REPORTING = "reporting"
    SETTINGS = "settings"
    CUSTOM = "custom"


class DetectedFeature(BaseModel):
    name: str = Field(..., description="Feature name")
    category: FeatureCategory
    description: str = Field(..., description="Brief description")
    priority: str = Field(default="medium", pattern=r"^(high|medium|low)$")
    requires_auth: bool = Field(default=False)


class DetectedEntity(BaseModel):
    name: str
    description: str
    attributes: List[str] = Field(default_factory=list)
    is_primary: bool = Field(default=False)


class DetectedRole(BaseModel):
    name: str
    description: str
    permissions: List[str] = Field(default_factory=list)
    is_default: bool = Field(default=False)


class BusinessRule(BaseModel):
    name: str
    description: str
    condition: str
    action: str
    affected_entities: List[str] = Field(default_factory=list)


class Intent(BaseModel):
    """Structured representation of parsed user intent (Stage 1 output)."""

    app_name: str = Field(..., description="Inferred application name")
    app_type: AppType
    description: str = Field(..., description="Concise app description")
    features: List[DetectedFeature] = Field(default_factory=list)
    entities: List[DetectedEntity] = Field(default_factory=list)
    roles: List[DetectedRole] = Field(default_factory=list)
    business_rules: List[BusinessRule] = Field(default_factory=list)
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions made for vague/incomplete inputs",
    )
    ambiguities: List[str] = Field(
        default_factory=list,
        description="Detected ambiguities in the input",
    )
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_input: str = Field(default="", description="Original user prompt")
