"""Stage 2 output: System architecture design derived from intent."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    TEXT = "text"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PASSWORD = "password"
    URL = "url"
    JSON = "json"
    ENUM = "enum"
    UUID = "uuid"
    DECIMAL = "decimal"


class RelationType(str, Enum):
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"
    MANY_TO_MANY = "many_to_many"


class EntityAttribute(BaseModel):
    name: str
    data_type: DataType
    required: bool = True
    unique: bool = False
    description: str = ""
    default_value: Optional[Any] = None
    enum_values: Optional[List[str]] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None


class EntityRelationship(BaseModel):
    target_entity: str
    relation_type: RelationType
    foreign_key: str = ""
    cascade_delete: bool = False
    description: str = ""


class EntityDesign(BaseModel):
    name: str
    description: str
    attributes: List[EntityAttribute] = Field(default_factory=list)
    relationships: List[EntityRelationship] = Field(default_factory=list)
    is_auth_entity: bool = False
    timestamps: bool = True


class PageType(str, Enum):
    LIST = "list"
    DETAIL = "detail"
    FORM = "form"
    DASHBOARD = "dashboard"
    AUTH = "auth"
    SETTINGS = "settings"
    ANALYTICS = "analytics"
    CUSTOM = "custom"


class PageDesign(BaseModel):
    name: str
    route: str
    page_type: PageType
    description: str = ""
    entity: Optional[str] = None
    access_roles: List[str] = Field(default_factory=list)
    parent_page: Optional[str] = None
    features: List[str] = Field(default_factory=list)


class FlowStep(BaseModel):
    step_number: int
    description: str
    page: str
    action: str


class UserFlow(BaseModel):
    name: str
    description: str
    actor_role: str
    steps: List[FlowStep] = Field(default_factory=list)


class RolePermission(BaseModel):
    resource: str
    actions: List[str] = Field(default_factory=list)


class RoleDesign(BaseModel):
    name: str
    description: str
    is_admin: bool = False
    is_default: bool = False
    permissions: List[RolePermission] = Field(default_factory=list)
    inherits_from: Optional[str] = None


class SystemDesign(BaseModel):
    """Full system architecture (Stage 2 output)."""

    app_name: str
    entities: List[EntityDesign] = Field(default_factory=list)
    pages: List[PageDesign] = Field(default_factory=list)
    user_flows: List[UserFlow] = Field(default_factory=list)
    roles: List[RoleDesign] = Field(default_factory=list)
    design_decisions: List[str] = Field(
        default_factory=list,
        description="Architectural decisions and rationale",
    )
