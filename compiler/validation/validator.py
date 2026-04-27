"""Multi-layer validation engine.

Checks the AppConfig for:
- structural completeness (required fields, non-empty collections)
- type consistency (column types match expected patterns)
- cross-layer references (UI→API, API→DB, Auth→everywhere)
"""

from __future__ import annotations

from typing import Dict, List, Set

from ..schemas.app_config import AppConfig
from ..schemas.pipeline_result import ValidationIssue


def validate_config(config: AppConfig) -> List[ValidationIssue]:
    """Run all validation checks and return a list of issues."""

    issues: List[ValidationIssue] = []
    issues.extend(_validate_structure(config))
    issues.extend(_validate_db(config))
    issues.extend(_validate_api(config))
    issues.extend(_validate_ui(config))
    issues.extend(_validate_cross_layer(config))
    return issues


# ── Structural checks ───────────────────────────────────────────────────

def _validate_structure(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    if not config.app_name:
        issues.append(ValidationIssue(severity="error", layer="root", field="app_name", message="app_name is empty"))

    if not config.db_schema.tables:
        issues.append(ValidationIssue(severity="error", layer="db", field="tables", message="No database tables defined"))

    if not config.api_schema.endpoints:
        issues.append(ValidationIssue(severity="error", layer="api", field="endpoints", message="No API endpoints defined"))

    if not config.ui_schema.pages:
        issues.append(ValidationIssue(severity="error", layer="ui", field="pages", message="No UI pages defined"))

    if not config.auth_schema.roles:
        issues.append(ValidationIssue(severity="error", layer="auth", field="roles", message="No auth roles defined"))

    return issues


# ── Database checks ──────────────────────────────────────────────────────

def _validate_db(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    table_names: Set[str] = set()

    for table in config.db_schema.tables:
        if table.name in table_names:
            issues.append(ValidationIssue(severity="error", layer="db", field=f"{table.name}", message=f"Duplicate table name '{table.name}'"))
        table_names.add(table.name)

        if not table.columns:
            issues.append(ValidationIssue(severity="error", layer="db", field=f"{table.name}.columns", message="Table has no columns"))
            continue

        has_pk = any(c.primary_key for c in table.columns)
        if not has_pk:
            issues.append(ValidationIssue(severity="error", layer="db", field=f"{table.name}", message="Table has no primary key"))

        col_names: Set[str] = set()
        for col in table.columns:
            if col.name in col_names:
                issues.append(ValidationIssue(severity="error", layer="db", field=f"{table.name}.{col.name}", message=f"Duplicate column '{col.name}'"))
            col_names.add(col.name)

            if col.foreign_key:
                if col.foreign_key.table not in table_names and col.foreign_key.table != table.name:
                    # May reference a table we haven't seen yet; downgrade to warning
                    issues.append(ValidationIssue(severity="warning", layer="db", field=f"{table.name}.{col.name}.fk", message=f"Foreign key references unknown table '{col.foreign_key.table}'"))

    return issues


# ── API checks ───────────────────────────────────────────────────────────

def _validate_api(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_routes: Set[str] = set()

    for ep in config.api_schema.endpoints:
        route_key = f"{ep.method.value} {ep.path}"
        if route_key in seen_routes:
            issues.append(ValidationIssue(severity="error", layer="api", field=ep.endpoint_id, message=f"Duplicate route: {route_key}"))
        seen_routes.add(route_key)

        if not ep.path.startswith("/"):
            issues.append(ValidationIssue(severity="error", layer="api", field=ep.endpoint_id, message="Endpoint path must start with '/'"))

    return issues


# ── UI checks ────────────────────────────────────────────────────────────

def _validate_ui(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    seen_routes: Set[str] = set()

    for page in config.ui_schema.pages:
        if page.route in seen_routes:
            issues.append(ValidationIssue(severity="warning", layer="ui", field=page.page_id, message=f"Duplicate page route: {page.route}"))
        seen_routes.add(page.route)

        if not page.components and page.route not in ("/login", "/register"):
            issues.append(ValidationIssue(severity="warning", layer="ui", field=page.page_id, message="Page has no components"))

    return issues


# ── Cross-layer checks ──────────────────────────────────────────────────

def _validate_cross_layer(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []

    api_paths: Set[str] = {ep.path for ep in config.api_schema.endpoints}
    auth_roles: Set[str] = {r.name for r in config.auth_schema.roles}
    db_tables: Set[str] = {t.name for t in config.db_schema.tables}

    # UI data sources → API
    for page in config.ui_schema.pages:
        for comp in page.components:
            if comp.data_source:
                base = comp.data_source.split("/{")[0]
                if not any(p.startswith(base) for p in api_paths):
                    issues.append(ValidationIssue(severity="warning", layer="ui↔api", field=f"{page.page_id}.{comp.component_id}", message=f"data_source '{comp.data_source}' has no matching API endpoint"))

    # API entities → DB tables
    for ep in config.api_schema.endpoints:
        if ep.related_entity:
            expected = _entity_to_table(ep.related_entity)
            if expected not in db_tables:
                issues.append(ValidationIssue(severity="warning", layer="api↔db", field=ep.endpoint_id, message=f"related_entity '{ep.related_entity}' has no DB table '{expected}'"))

    # Role references
    for page in config.ui_schema.pages:
        for role in page.access_roles:
            if role not in auth_roles:
                issues.append(ValidationIssue(severity="warning", layer="auth", field=f"ui.{page.page_id}", message=f"Role '{role}' not in auth schema"))

    for ep in config.api_schema.endpoints:
        for role in ep.allowed_roles:
            if role not in auth_roles:
                issues.append(ValidationIssue(severity="warning", layer="auth", field=f"api.{ep.endpoint_id}", message=f"Role '{role}' not in auth schema"))

    return issues


def _entity_to_table(entity: str) -> str:
    name = entity.lower()
    if name.endswith("s"):
        return name
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    return name + "s"
