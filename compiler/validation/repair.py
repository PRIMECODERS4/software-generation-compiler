"""Intelligent repair engine.

Given a list of validation errors, applies targeted fixes to the AppConfig
rather than blindly regenerating the entire output.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..schemas.app_config import (
    AppConfig,
    ColumnType,
    DBColumn,
    DBTable,
    RoleDef,
    UIComponent,
    ComponentType,
)
from ..schemas.pipeline_result import ValidationIssue


def repair_config(
    config: AppConfig, errors: List[ValidationIssue]
) -> Tuple[AppConfig, List[ValidationIssue]]:
    """Apply targeted repairs for known error patterns.

    Returns the (possibly-modified) config and a list of new issues
    documenting what was repaired.
    """

    repair_issues: List[ValidationIssue] = []

    for err in errors:
        repaired = _try_repair(config, err)
        if repaired:
            repair_issues.append(repaired)

    return config, repair_issues


def _try_repair(config: AppConfig, err: ValidationIssue) -> ValidationIssue | None:
    """Dispatch to a specific repair strategy based on the error."""

    key = (err.layer, err.message[:40])  # use prefix for pattern matching

    if err.layer == "root" and "app_name" in err.field:
        return _repair_app_name(config, err)

    if err.layer == "db" and "no primary key" in err.message.lower():
        return _repair_missing_pk(config, err)

    if err.layer == "db" and "no columns" in err.message.lower():
        return _repair_empty_table(config, err)

    if err.layer == "db" and "tables" in err.field and "No database" in err.message:
        return _repair_no_tables(config, err)

    if err.layer == "api" and "No API" in err.message:
        return _repair_no_endpoints(config, err)

    if err.layer == "ui" and "No UI" in err.message:
        return _repair_no_pages(config, err)

    if err.layer == "auth" and "No auth" in err.message:
        return _repair_no_roles(config, err)

    if err.layer == "auth" and "not in auth schema" in err.message:
        return _repair_missing_role(config, err)

    return None


# ── Repair strategies ────────────────────────────────────────────────────

def _repair_app_name(config: AppConfig, err: ValidationIssue) -> ValidationIssue:
    config.app_name = config.app_name or "Generated App"
    return ValidationIssue(
        severity="info", layer="root", field="app_name",
        message="Set app_name to default", auto_repaired=True,
        repair_action="app_name = 'Generated App'",
    )


def _repair_missing_pk(config: AppConfig, err: ValidationIssue) -> ValidationIssue:
    table_name = err.field.split(".")[0] if "." in err.field else err.field
    for table in config.db_schema.tables:
        if table.name == table_name:
            if not any(c.primary_key for c in table.columns):
                table.columns.insert(0, DBColumn(
                    name="id", column_type=ColumnType.UUID,
                    nullable=False, primary_key=True, unique=True,
                ))
            break
    return ValidationIssue(
        severity="info", layer="db", field=f"{table_name}.id",
        message=f"Added missing primary key to '{table_name}'",
        auto_repaired=True, repair_action="Inserted 'id UUID PK' column",
    )


def _repair_empty_table(config: AppConfig, err: ValidationIssue) -> ValidationIssue:
    table_name = err.field.split(".")[0] if "." in err.field else err.field
    for table in config.db_schema.tables:
        if table.name == table_name:
            table.columns = [
                DBColumn(name="id", column_type=ColumnType.UUID, nullable=False, primary_key=True, unique=True),
                DBColumn(name="name", column_type=ColumnType.VARCHAR, nullable=False, max_length=255),
            ]
            break
    return ValidationIssue(
        severity="info", layer="db", field=table_name,
        message=f"Added default columns to empty table '{table_name}'",
        auto_repaired=True, repair_action="Inserted id + name columns",
    )


def _repair_no_tables(config: AppConfig, _err: ValidationIssue) -> ValidationIssue:
    config.db_schema.tables.append(DBTable(
        table_id="users", name="users",
        columns=[
            DBColumn(name="id", column_type=ColumnType.UUID, nullable=False, primary_key=True, unique=True),
            DBColumn(name="email", column_type=ColumnType.VARCHAR, nullable=False, unique=True, max_length=255),
            DBColumn(name="password_hash", column_type=ColumnType.VARCHAR, nullable=False, max_length=255),
            DBColumn(name="name", column_type=ColumnType.VARCHAR, nullable=False, max_length=255),
        ],
    ))
    return ValidationIssue(
        severity="info", layer="db", field="tables",
        message="Added default 'users' table", auto_repaired=True,
        repair_action="Created users table with id, email, password_hash, name",
    )


def _repair_no_endpoints(config: AppConfig, _err: ValidationIssue) -> ValidationIssue:
    from ..schemas.app_config import APIEndpoint, HTTPMethod
    config.api_schema.endpoints.append(APIEndpoint(
        endpoint_id="ep_health", path="/api/v1/health", method=HTTPMethod.GET,
        description="Health check", auth_required=False,
    ))
    return ValidationIssue(
        severity="info", layer="api", field="endpoints",
        message="Added default health-check endpoint", auto_repaired=True,
        repair_action="Created GET /api/v1/health",
    )


def _repair_no_pages(config: AppConfig, _err: ValidationIssue) -> ValidationIssue:
    from ..schemas.app_config import UIPage, LayoutType
    config.ui_schema.pages.append(UIPage(
        page_id="home", name="Home", route="/", layout=LayoutType.SINGLE,
        is_public=True, title="Home",
    ))
    return ValidationIssue(
        severity="info", layer="ui", field="pages",
        message="Added default home page", auto_repaired=True,
        repair_action="Created '/' page",
    )


def _repair_no_roles(config: AppConfig, _err: ValidationIssue) -> ValidationIssue:
    config.auth_schema.roles.extend([
        RoleDef(role_id="admin", name="admin", description="Administrator", is_admin=True),
        RoleDef(role_id="user", name="user", description="Regular user", is_default=True),
    ])
    return ValidationIssue(
        severity="info", layer="auth", field="roles",
        message="Added default admin + user roles", auto_repaired=True,
        repair_action="Created admin and user roles",
    )


def _repair_missing_role(config: AppConfig, err: ValidationIssue) -> ValidationIssue:
    # Extract role name from message
    import re
    match = re.search(r"Role '(\w+)'", err.message)
    role_name = match.group(1) if match else "unknown"
    existing = {r.name for r in config.auth_schema.roles}
    if role_name not in existing:
        config.auth_schema.roles.append(RoleDef(
            role_id=role_name.lower().replace(" ", "_"),
            name=role_name,
            description=f"Auto-repaired role: {role_name}",
        ))
    return ValidationIssue(
        severity="info", layer="auth", field=err.field,
        message=f"Added missing role '{role_name}'",
        auto_repaired=True, repair_action=f"Inserted role '{role_name}'",
    )
