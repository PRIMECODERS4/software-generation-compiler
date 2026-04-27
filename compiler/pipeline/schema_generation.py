"""Stage 3 – Schema Generation.

Converts a SystemDesign into a complete AppConfig containing UI, API, DB, and
Auth schemas.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from ..llm.client import llm_client
from ..schemas.app_config import (
    APIEndpoint,
    APISchema,
    AppConfig,
    AuthPolicy,
    AuthSchema,
    ColumnType,
    ComponentAction,
    ComponentType,
    DBColumn,
    DBIndex,
    DBSchema,
    DBTable,
    ForeignKeyDef,
    FormField,
    HTTPMethod,
    LayoutType,
    NavItem,
    Permission,
    RoleDef,
    TableColumn,
    UIComponent,
    UIPage,
    UISchema,
    ValidationRule,
)
from ..schemas.design import DataType, EntityDesign, PageDesign, PageType, RelationType, SystemDesign

# ── Helpers ──────────────────────────────────────────────────────────────

_DATA_TO_COL: Dict[DataType, ColumnType] = {
    DataType.STRING: ColumnType.VARCHAR,
    DataType.INTEGER: ColumnType.INTEGER,
    DataType.FLOAT: ColumnType.FLOAT,
    DataType.BOOLEAN: ColumnType.BOOLEAN,
    DataType.TEXT: ColumnType.TEXT,
    DataType.DATE: ColumnType.DATE,
    DataType.DATETIME: ColumnType.TIMESTAMP,
    DataType.EMAIL: ColumnType.VARCHAR,
    DataType.PASSWORD: ColumnType.VARCHAR,
    DataType.URL: ColumnType.VARCHAR,
    DataType.JSON: ColumnType.JSON,
    DataType.ENUM: ColumnType.ENUM,
    DataType.UUID: ColumnType.UUID,
    DataType.DECIMAL: ColumnType.DECIMAL,
}

_DATA_TO_FORM: Dict[DataType, str] = {
    DataType.STRING: "text",
    DataType.INTEGER: "number",
    DataType.FLOAT: "number",
    DataType.BOOLEAN: "checkbox",
    DataType.TEXT: "textarea",
    DataType.DATE: "date",
    DataType.DATETIME: "datetime-local",
    DataType.EMAIL: "email",
    DataType.PASSWORD: "password",
    DataType.URL: "url",
    DataType.ENUM: "select",
    DataType.DECIMAL: "number",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _plural(name: str) -> str:
    if name.endswith("s"):
        return name
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    return name + "s"


# ── UI generation ────────────────────────────────────────────────────────

def _gen_ui(design: SystemDesign) -> UISchema:
    pages: List[UIPage] = []
    nav_items: List[NavItem] = []
    comp_counter = 0

    for pg in design.pages:
        components: List[UIComponent] = []
        layout = LayoutType.SINGLE

        entity_design = None
        if pg.entity:
            entity_design = next((e for e in design.entities if e.name == pg.entity), None)

        if pg.page_type == PageType.AUTH:
            comp_counter += 1
            fields = [
                FormField(name="email", label="Email", field_type="email", required=True, placeholder="you@example.com"),
                FormField(name="password", label="Password", field_type="password", required=True),
            ]
            if "register" in pg.route.lower() or "signup" in pg.route.lower():
                fields.insert(0, FormField(name="name", label="Full Name", field_type="text", required=True))
                fields.append(FormField(name="confirm_password", label="Confirm Password", field_type="password", required=True))
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.FORM,
                name=pg.name,
                data_source=f"/api/v1/auth/{'register' if 'register' in pg.route else 'login'}",
                form_fields=fields,
                actions=[ComponentAction(label="Submit", action_type="submit", endpoint=f"/api/v1/auth/{'register' if 'register' in pg.route else 'login'}", method="POST")],
            ))

        elif pg.page_type == PageType.DASHBOARD:
            layout = LayoutType.DASHBOARD
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.STATS,
                name="Overview Stats",
                props={"widgets": ["total_records", "active_users", "recent_activity"]},
            ))
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.CHART,
                name="Activity Chart",
                props={"chart_type": "line", "period": "30d"},
            ))

        elif pg.page_type == PageType.LIST and entity_design:
            columns = [
                TableColumn(key=a.name, label=a.name.replace("_", " ").title(), sortable=True, filterable=a.data_type in (DataType.STRING, DataType.ENUM), data_type=a.data_type.value)
                for a in entity_design.attributes
                if a.name != "password_hash" and a.data_type != DataType.PASSWORD
            ]
            slug = _plural(_slug(pg.entity or ""))
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.TABLE,
                name=f"{pg.entity} Table",
                data_source=f"/api/v1/{slug}",
                table_columns=columns,
                actions=[
                    ComponentAction(label="View", action_type="navigate", endpoint=f"/{slug}/{{id}}"),
                    ComponentAction(label="Edit", action_type="navigate", endpoint=f"/{slug}/{{id}}/edit"),
                    ComponentAction(label="Delete", action_type="api_call", endpoint=f"/api/v1/{slug}/{{id}}", method="DELETE", confirmation=True),
                ],
            ))

        elif pg.page_type == PageType.DETAIL and entity_design:
            comp_counter += 1
            slug = _plural(_slug(pg.entity or ""))
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.DETAIL,
                name=f"{pg.entity} Details",
                data_source=f"/api/v1/{slug}/{{id}}",
                actions=[
                    ComponentAction(label="Edit", action_type="navigate", endpoint=f"/{slug}/{{id}}/edit"),
                    ComponentAction(label="Delete", action_type="api_call", endpoint=f"/api/v1/{slug}/{{id}}", method="DELETE", confirmation=True),
                ],
            ))

        elif pg.page_type == PageType.FORM and entity_design:
            fields = []
            for attr in entity_design.attributes:
                if attr.name in ("id", "password_hash") or attr.data_type == DataType.UUID:
                    continue
                field_type = _DATA_TO_FORM.get(attr.data_type, "text")
                options = attr.enum_values if attr.data_type == DataType.ENUM else None
                fields.append(FormField(
                    name=attr.name,
                    label=attr.name.replace("_", " ").title(),
                    field_type=field_type,
                    required=attr.required,
                    options=options,
                ))
            slug = _plural(_slug(pg.entity or ""))
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.FORM,
                name=f"{pg.entity} Form",
                data_source=f"/api/v1/{slug}",
                form_fields=fields,
                actions=[ComponentAction(label="Save", action_type="submit", endpoint=f"/api/v1/{slug}", method="POST")],
            ))

        elif pg.page_type == PageType.ANALYTICS:
            layout = LayoutType.DASHBOARD
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.CHART,
                name="Analytics Charts",
                props={"charts": ["bar", "line", "pie"]},
            ))

        elif pg.page_type == PageType.SETTINGS:
            comp_counter += 1
            components.append(UIComponent(
                component_id=f"comp_{comp_counter}",
                component_type=ComponentType.FORM,
                name="User Settings",
                form_fields=[
                    FormField(name="name", label="Name", field_type="text", required=True),
                    FormField(name="email", label="Email", field_type="email", required=True),
                    FormField(name="avatar_url", label="Avatar URL", field_type="url", required=False),
                ],
                actions=[ComponentAction(label="Save", action_type="submit", endpoint="/api/v1/users/me", method="PUT")],
            ))

        page_id = _slug(pg.name)
        pages.append(UIPage(
            page_id=page_id,
            name=pg.name,
            route=pg.route,
            layout=layout,
            components=components,
            access_roles=pg.access_roles,
            is_public=pg.page_type == PageType.AUTH,
            title=pg.name,
        ))

        if pg.page_type not in (PageType.DETAIL, PageType.FORM, PageType.AUTH):
            nav_items.append(NavItem(
                label=pg.name,
                route=pg.route,
                icon=_icon_for(pg.page_type),
                access_roles=pg.access_roles,
            ))

    return UISchema(pages=pages, navigation=nav_items)


def _icon_for(pt: PageType) -> str:
    return {
        PageType.DASHBOARD: "home",
        PageType.LIST: "list",
        PageType.ANALYTICS: "bar-chart",
        PageType.SETTINGS: "settings",
    }.get(pt, "circle")


# ── API generation ───────────────────────────────────────────────────────

def _gen_api(design: SystemDesign) -> APISchema:
    endpoints: List[APIEndpoint] = []
    ep_counter = 0
    all_roles = [r.name for r in design.roles]

    # Auth endpoints
    for action in ("register", "login", "logout", "me"):
        ep_counter += 1
        method = HTTPMethod.POST if action in ("register", "login", "logout") else HTTPMethod.GET
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/auth/{action}",
            method=method,
            description=f"User {action}",
            auth_required=action not in ("register", "login"),
            allowed_roles=all_roles if action not in ("register", "login") else [],
            related_entity="User",
        ))

    # CRUD endpoints per entity
    for entity in design.entities:
        if entity.name == "User":
            continue
        slug = _plural(_slug(entity.name))
        req_body: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        resp_item: Dict[str, Any] = {"type": "object", "properties": {}}

        for attr in entity.attributes:
            prop: Dict[str, Any] = {"type": attr.data_type.value}
            if attr.enum_values:
                prop["enum"] = attr.enum_values
            resp_item["properties"][attr.name] = prop
            if attr.name not in ("id",) and attr.data_type != DataType.UUID:
                req_body["properties"][attr.name] = prop
                if attr.required:
                    req_body["required"].append(attr.name)

        # LIST
        ep_counter += 1
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/{slug}",
            method=HTTPMethod.GET,
            description=f"List all {entity.name} records",
            response_schema={"type": "array", "items": resp_item},
            query_params=["page", "limit", "sort", "filter"],
            auth_required=True,
            allowed_roles=all_roles,
            related_entity=entity.name,
        ))
        # CREATE
        ep_counter += 1
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/{slug}",
            method=HTTPMethod.POST,
            description=f"Create a new {entity.name}",
            request_body=req_body,
            response_schema=resp_item,
            auth_required=True,
            allowed_roles=all_roles,
            related_entity=entity.name,
            validation_rules=[
                ValidationRule(field=r, rule_type="required", message=f"{r} is required")
                for r in req_body.get("required", [])
            ],
        ))
        # GET by ID
        ep_counter += 1
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/{slug}/{{id}}",
            method=HTTPMethod.GET,
            description=f"Get a single {entity.name} by ID",
            path_params=["id"],
            response_schema=resp_item,
            auth_required=True,
            allowed_roles=all_roles,
            related_entity=entity.name,
        ))
        # UPDATE
        ep_counter += 1
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/{slug}/{{id}}",
            method=HTTPMethod.PUT,
            description=f"Update a {entity.name}",
            path_params=["id"],
            request_body=req_body,
            response_schema=resp_item,
            auth_required=True,
            allowed_roles=all_roles,
            related_entity=entity.name,
        ))
        # DELETE
        ep_counter += 1
        endpoints.append(APIEndpoint(
            endpoint_id=f"ep_{ep_counter}",
            path=f"/api/v1/{slug}/{{id}}",
            method=HTTPMethod.DELETE,
            description=f"Delete a {entity.name}",
            path_params=["id"],
            auth_required=True,
            allowed_roles=all_roles,
            related_entity=entity.name,
        ))

    return APISchema(endpoints=endpoints)


# ── DB generation ────────────────────────────────────────────────────────

def _gen_db(design: SystemDesign) -> DBSchema:
    tables: List[DBTable] = []
    entity_names: Set[str] = {e.name for e in design.entities}

    for entity in design.entities:
        table_name = _plural(_slug(entity.name))
        columns: List[DBColumn] = []
        indexes: List[DBIndex] = []

        for attr in entity.attributes:
            col_type = _DATA_TO_COL.get(attr.data_type, ColumnType.VARCHAR)
            col = DBColumn(
                name=attr.name,
                column_type=col_type,
                nullable=not attr.required,
                primary_key=attr.name == "id",
                unique=attr.unique,
                default=str(attr.default_value) if attr.default_value is not None else None,
                max_length=attr.max_length or (255 if col_type == ColumnType.VARCHAR else None),
                enum_values=attr.enum_values,
            )
            columns.append(col)

            if attr.unique and attr.name != "id":
                indexes.append(DBIndex(name=f"idx_{table_name}_{attr.name}", columns=[attr.name], unique=True))

        # Foreign key columns from relationships
        for rel in entity.relationships:
            if rel.target_entity in entity_names:
                fk_col = rel.foreign_key or f"{_slug(rel.target_entity)}_id"
                if not any(c.name == fk_col for c in columns):
                    columns.append(DBColumn(
                        name=fk_col,
                        column_type=ColumnType.UUID,
                        nullable=True,
                        foreign_key=ForeignKeyDef(
                            table=_plural(_slug(rel.target_entity)),
                            column="id",
                        ),
                    ))
                    indexes.append(DBIndex(name=f"idx_{table_name}_{fk_col}", columns=[fk_col]))

        tables.append(DBTable(
            table_id=table_name,
            name=table_name,
            columns=columns,
            indexes=indexes,
            timestamps=entity.timestamps,
            description=entity.description,
        ))

    return DBSchema(tables=tables)


# ── Auth generation ──────────────────────────────────────────────────────

def _gen_auth(design: SystemDesign) -> AuthSchema:
    roles: List[RoleDef] = []
    policies: List[AuthPolicy] = []
    pol_counter = 0

    for rd in design.roles:
        perms: List[Permission] = [
            Permission(resource=rp.resource, actions=rp.actions)
            for rp in rd.permissions
        ]
        roles.append(RoleDef(
            role_id=_slug(rd.name),
            name=rd.name,
            description=rd.description,
            permissions=perms,
            is_default=rd.is_default,
            is_admin=rd.is_admin,
            inherits_from=rd.inherits_from,
        ))

        for perm in perms:
            for action in perm.actions:
                pol_counter += 1
                policies.append(AuthPolicy(
                    policy_id=f"pol_{pol_counter}",
                    name=f"{rd.name}_can_{action}_{_slug(perm.resource)}",
                    resource=perm.resource,
                    action=action,
                    condition=f"role == '{rd.name}'",
                    effect="allow",
                ))

    return AuthSchema(roles=roles, policies=policies)


# ── Public entry point ───────────────────────────────────────────────────

def generate_schemas(design: SystemDesign) -> AppConfig:
    """Generate the full AppConfig (UI + API + DB + Auth) from a SystemDesign."""

    if llm_client.available:
        result = _generate_with_llm(design)
        if result:
            return result

    return AppConfig(
        app_name=design.app_name,
        ui_schema=_gen_ui(design),
        api_schema=_gen_api(design),
        db_schema=_gen_db(design),
        auth_schema=_gen_auth(design),
    )


def _generate_with_llm(design: SystemDesign) -> AppConfig | None:
    system = (
        "You are Stage 3 of a software-generation compiler. "
        "Given a system design JSON, produce the full application configuration. "
        "Return JSON with: app_name, ui_schema, api_schema, db_schema, auth_schema. "
        "Ensure cross-layer consistency: API fields must match DB columns, "
        "UI data_source endpoints must exist in api_schema, "
        "auth roles must be referenced consistently."
    )
    data = llm_client.generate_json(system, design.model_dump_json(), max_tokens=8192)
    if data is None:
        return None
    try:
        return AppConfig.model_validate(data)
    except Exception:
        return None
