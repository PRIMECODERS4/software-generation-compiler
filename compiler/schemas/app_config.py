"""Stage 3 output: Complete application configuration (UI, API, DB, Auth)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# UI Schema
# ---------------------------------------------------------------------------

class ComponentType(str, Enum):
    FORM = "form"
    TABLE = "table"
    CARD = "card"
    CHART = "chart"
    LIST = "list"
    DETAIL = "detail"
    MODAL = "modal"
    NAV = "navigation"
    SIDEBAR = "sidebar"
    HEADER = "header"
    STATS = "stats_widget"
    BUTTON = "button"
    TEXT = "text"
    IMAGE = "image"


class FormField(BaseModel):
    name: str
    label: str
    field_type: str = "text"
    required: bool = True
    placeholder: str = ""
    validation: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = None


class TableColumn(BaseModel):
    key: str
    label: str
    sortable: bool = True
    filterable: bool = False
    data_type: str = "string"


class ComponentAction(BaseModel):
    label: str
    action_type: str
    endpoint: Optional[str] = None
    method: Optional[str] = None
    confirmation: bool = False


class UIComponent(BaseModel):
    component_id: str
    component_type: ComponentType
    name: str
    props: Dict[str, Any] = Field(default_factory=dict)
    data_source: Optional[str] = None
    form_fields: Optional[List[FormField]] = None
    table_columns: Optional[List[TableColumn]] = None
    actions: List[ComponentAction] = Field(default_factory=list)
    styles: Dict[str, str] = Field(default_factory=dict)


class LayoutType(str, Enum):
    SINGLE = "single_column"
    TWO_COL = "two_column"
    SIDEBAR = "sidebar_layout"
    DASHBOARD = "dashboard_grid"
    FULL = "full_width"


class UIPage(BaseModel):
    page_id: str
    name: str
    route: str
    layout: LayoutType = LayoutType.SINGLE
    components: List[UIComponent] = Field(default_factory=list)
    access_roles: List[str] = Field(default_factory=list)
    is_public: bool = False
    title: str = ""
    meta_description: str = ""


class NavItem(BaseModel):
    label: str
    route: str
    icon: str = ""
    access_roles: List[str] = Field(default_factory=list)
    children: List[NavItem] = Field(default_factory=list)


class UISchema(BaseModel):
    pages: List[UIPage] = Field(default_factory=list)
    navigation: List[NavItem] = Field(default_factory=list)
    theme: Dict[str, str] = Field(default_factory=lambda: {
        "primary_color": "#3B82F6",
        "secondary_color": "#10B981",
        "background": "#F9FAFB",
        "text_color": "#111827",
        "font_family": "Inter, sans-serif",
    })


# ---------------------------------------------------------------------------
# API Schema
# ---------------------------------------------------------------------------

class HTTPMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ValidationRule(BaseModel):
    field: str
    rule_type: str
    value: Any = None
    message: str = ""


class APIEndpoint(BaseModel):
    endpoint_id: str
    path: str
    method: HTTPMethod
    description: str = ""
    request_body: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    path_params: List[str] = Field(default_factory=list)
    query_params: List[str] = Field(default_factory=list)
    auth_required: bool = True
    allowed_roles: List[str] = Field(default_factory=list)
    validation_rules: List[ValidationRule] = Field(default_factory=list)
    rate_limit: Optional[int] = None
    related_entity: str = ""


class APISchema(BaseModel):
    base_url: str = "/api/v1"
    endpoints: List[APIEndpoint] = Field(default_factory=list)
    global_middleware: List[str] = Field(default_factory=lambda: [
        "cors", "rate_limiting", "request_logging",
    ])


# ---------------------------------------------------------------------------
# Database Schema
# ---------------------------------------------------------------------------

class ColumnType(str, Enum):
    VARCHAR = "VARCHAR"
    TEXT = "TEXT"
    INTEGER = "INTEGER"
    BIGINT = "BIGINT"
    FLOAT = "FLOAT"
    DECIMAL = "DECIMAL"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    JSON = "JSON"
    UUID = "UUID"
    ENUM = "ENUM"


class ForeignKeyDef(BaseModel):
    table: str
    column: str
    on_delete: str = "CASCADE"
    on_update: str = "CASCADE"


class DBColumn(BaseModel):
    name: str
    column_type: ColumnType
    nullable: bool = False
    primary_key: bool = False
    unique: bool = False
    default: Optional[str] = None
    foreign_key: Optional[ForeignKeyDef] = None
    max_length: Optional[int] = None
    enum_values: Optional[List[str]] = None


class DBIndex(BaseModel):
    name: str
    columns: List[str]
    unique: bool = False


class DBTable(BaseModel):
    table_id: str
    name: str
    columns: List[DBColumn] = Field(default_factory=list)
    indexes: List[DBIndex] = Field(default_factory=list)
    timestamps: bool = True
    description: str = ""


class DBSchema(BaseModel):
    tables: List[DBTable] = Field(default_factory=list)
    migrations_strategy: str = "sequential"


# ---------------------------------------------------------------------------
# Auth Schema
# ---------------------------------------------------------------------------

class Permission(BaseModel):
    resource: str
    actions: List[str] = Field(default_factory=list)
    conditions: Optional[Dict[str, Any]] = None


class RoleDef(BaseModel):
    role_id: str
    name: str
    description: str = ""
    permissions: List[Permission] = Field(default_factory=list)
    is_default: bool = False
    is_admin: bool = False
    inherits_from: Optional[str] = None


class AuthPolicy(BaseModel):
    policy_id: str
    name: str
    description: str = ""
    resource: str
    action: str
    condition: str
    effect: str = "allow"


class AuthSchema(BaseModel):
    strategy: str = "jwt"
    roles: List[RoleDef] = Field(default_factory=list)
    policies: List[AuthPolicy] = Field(default_factory=list)
    session_config: Dict[str, Any] = Field(default_factory=lambda: {
        "token_expiry_minutes": 60,
        "refresh_token_enabled": True,
        "max_sessions": 5,
    })
    password_policy: Dict[str, Any] = Field(default_factory=lambda: {
        "min_length": 8,
        "require_uppercase": True,
        "require_number": True,
        "require_special": True,
    })


# ---------------------------------------------------------------------------
# Full Application Config
# ---------------------------------------------------------------------------

class AppConfig(BaseModel):
    """Complete application configuration (Stage 3 output)."""

    app_name: str
    version: str = "1.0.0"
    ui_schema: UISchema = Field(default_factory=UISchema)
    api_schema: APISchema = Field(default_factory=APISchema)
    db_schema: DBSchema = Field(default_factory=DBSchema)
    auth_schema: AuthSchema = Field(default_factory=AuthSchema)
    business_rules: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
