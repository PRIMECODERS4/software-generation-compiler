"""Stage 4 – Refinement.

Resolves cross-layer inconsistencies in the generated AppConfig:
- API endpoint references match DB tables
- UI data_source values map to existing API endpoints
- Auth roles are consistent across all layers
- Missing references are repaired
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set, Tuple

from ..schemas.app_config import (
    APIEndpoint,
    AppConfig,
    AuthPolicy,
    DBColumn,
    DBIndex,
    DBTable,
    ColumnType,
    ForeignKeyDef,
    HTTPMethod,
    NavItem,
    Permission,
    RoleDef,
    UIPage,
    ValidationRule,
)
from ..schemas.pipeline_result import ValidationIssue

logger = logging.getLogger(__name__)


def refine(config: AppConfig) -> Tuple[AppConfig, List[ValidationIssue]]:
    """Run all refinement passes and return the updated config + issues found."""

    issues: List[ValidationIssue] = []
    issues.extend(_fix_api_db_consistency(config))
    issues.extend(_fix_ui_api_consistency(config))
    issues.extend(_fix_auth_consistency(config))
    issues.extend(_fix_nav_consistency(config))
    issues.extend(_add_timestamp_columns(config))
    return config, issues


# ── API ↔ DB consistency ────────────────────────────────────────────────

def _fix_api_db_consistency(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    db_tables: Dict[str, DBTable] = {t.name: t for t in config.db_schema.tables}

    for ep in config.api_schema.endpoints:
        if not ep.related_entity:
            continue
        # Derive expected table name
        expected_table = _entity_to_table(ep.related_entity)
        if expected_table not in db_tables:
            continue

        table = db_tables[expected_table]
        col_names = {c.name for c in table.columns}

        # Check request body fields exist as columns
        if ep.request_body and "properties" in ep.request_body:
            for field in ep.request_body["properties"]:
                if field not in col_names and field not in ("confirm_password",):
                    issues.append(ValidationIssue(
                        severity="warning",
                        layer="api↔db",
                        field=f"{ep.path}.request.{field}",
                        message=f"API request field '{field}' has no matching DB column in '{expected_table}'",
                        auto_repaired=True,
                        repair_action=f"Added column '{field}' to table '{expected_table}'",
                    ))
                    table.columns.append(DBColumn(
                        name=field,
                        column_type=ColumnType.VARCHAR,
                        nullable=True,
                        max_length=255,
                    ))

    return issues


def _entity_to_table(entity: str) -> str:
    name = entity.lower()
    if name.endswith("s"):
        return name
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    return name + "s"


# ── UI ↔ API consistency ────────────────────────────────────────────────

def _fix_ui_api_consistency(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    api_paths: Set[str] = set()
    for ep in config.api_schema.endpoints:
        # Normalise path by replacing {id} placeholders
        normalised = ep.path.replace("{id}", ":id")
        api_paths.add(normalised)
        api_paths.add(ep.path)

    for page in config.ui_schema.pages:
        for comp in page.components:
            ds = comp.data_source
            if not ds:
                continue
            normalised_ds = ds.replace("{id}", ":id")
            if normalised_ds not in api_paths and ds not in api_paths:
                # Try to find a close match
                base = ds.split("/{")[0]
                matches = [p for p in api_paths if p.startswith(base)]
                if matches:
                    continue  # close enough
                issues.append(ValidationIssue(
                    severity="warning",
                    layer="ui↔api",
                    field=f"{page.page_id}.{comp.component_id}.data_source",
                    message=f"UI data_source '{ds}' does not match any API endpoint",
                ))

    return issues


# ── Auth consistency ─────────────────────────────────────────────────────

def _fix_auth_consistency(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    auth_role_names: Set[str] = {r.name for r in config.auth_schema.roles}

    # Check UI page roles
    for page in config.ui_schema.pages:
        for role in page.access_roles:
            if role not in auth_role_names:
                issues.append(ValidationIssue(
                    severity="warning",
                    layer="auth",
                    field=f"ui.{page.page_id}.access_roles",
                    message=f"Role '{role}' referenced in UI but not defined in auth schema",
                    auto_repaired=True,
                    repair_action=f"Added role '{role}' to auth schema",
                ))
                config.auth_schema.roles.append(RoleDef(
                    role_id=role.lower().replace(" ", "_"),
                    name=role,
                    description=f"Auto-added role: {role}",
                ))
                auth_role_names.add(role)

    # Check API endpoint roles
    for ep in config.api_schema.endpoints:
        for role in ep.allowed_roles:
            if role not in auth_role_names:
                issues.append(ValidationIssue(
                    severity="warning",
                    layer="auth",
                    field=f"api.{ep.endpoint_id}.allowed_roles",
                    message=f"Role '{role}' referenced in API but not defined in auth schema",
                    auto_repaired=True,
                    repair_action=f"Added role '{role}' to auth schema",
                ))
                config.auth_schema.roles.append(RoleDef(
                    role_id=role.lower().replace(" ", "_"),
                    name=role,
                    description=f"Auto-added role: {role}",
                ))
                auth_role_names.add(role)

    return issues


# ── Navigation consistency ───────────────────────────────────────────────

def _fix_nav_consistency(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    page_routes: Set[str] = {p.route for p in config.ui_schema.pages}

    for nav in config.ui_schema.navigation:
        if nav.route not in page_routes:
            issues.append(ValidationIssue(
                severity="info",
                layer="ui",
                field=f"nav.{nav.label}",
                message=f"Nav item '{nav.label}' points to '{nav.route}' which has no matching page",
            ))

    return issues


# ── Timestamp columns ────────────────────────────────────────────────────

def _add_timestamp_columns(config: AppConfig) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    for table in config.db_schema.tables:
        if not table.timestamps:
            continue
        col_names = {c.name for c in table.columns}
        for ts_col in ("created_at", "updated_at"):
            if ts_col not in col_names:
                table.columns.append(DBColumn(
                    name=ts_col,
                    column_type=ColumnType.TIMESTAMP,
                    nullable=False,
                    default="CURRENT_TIMESTAMP",
                ))
                issues.append(ValidationIssue(
                    severity="info",
                    layer="db",
                    field=f"{table.name}.{ts_col}",
                    message=f"Added timestamp column '{ts_col}' to table '{table.name}'",
                    auto_repaired=True,
                    repair_action=f"Inserted '{ts_col}' column",
                ))

    return issues
