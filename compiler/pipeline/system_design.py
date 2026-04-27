"""Stage 2 – System Design.

Converts a structured Intent into an architectural SystemDesign: entities with
attributes & relationships, pages, user flows, and role definitions.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set

from ..llm.client import llm_client
from ..schemas.design import (
    DataType,
    EntityAttribute,
    EntityDesign,
    EntityRelationship,
    FlowStep,
    PageDesign,
    PageType,
    RelationType,
    RoleDesign,
    RolePermission,
    SystemDesign,
    UserFlow,
)
from ..schemas.intent import AppType, DetectedEntity, FeatureCategory, Intent

# ── Default attributes by entity name ────────────────────────────────────

_DEFAULT_ATTRS: Dict[str, List[EntityAttribute]] = {
    "User": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="email", data_type=DataType.EMAIL, required=True, unique=True),
        EntityAttribute(name="password_hash", data_type=DataType.STRING, required=True),
        EntityAttribute(name="name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="role", data_type=DataType.STRING, required=True, default_value="user"),
        EntityAttribute(name="is_active", data_type=DataType.BOOLEAN, required=True, default_value="true"),
        EntityAttribute(name="avatar_url", data_type=DataType.URL, required=False),
    ],
    "Contact": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="first_name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="last_name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="email", data_type=DataType.EMAIL, required=False, unique=True),
        EntityAttribute(name="phone", data_type=DataType.STRING, required=False),
        EntityAttribute(name="company", data_type=DataType.STRING, required=False),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="active", enum_values=["active", "inactive", "lead"]),
        EntityAttribute(name="notes", data_type=DataType.TEXT, required=False),
    ],
    "Product": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="price", data_type=DataType.DECIMAL, required=True),
        EntityAttribute(name="sku", data_type=DataType.STRING, required=False, unique=True),
        EntityAttribute(name="stock_quantity", data_type=DataType.INTEGER, required=True, default_value="0"),
        EntityAttribute(name="is_active", data_type=DataType.BOOLEAN, required=True, default_value="true"),
        EntityAttribute(name="image_url", data_type=DataType.URL, required=False),
    ],
    "Order": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="order_number", data_type=DataType.STRING, required=True, unique=True),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="pending", enum_values=["pending", "confirmed", "shipped", "delivered", "cancelled"]),
        EntityAttribute(name="total_amount", data_type=DataType.DECIMAL, required=True),
        EntityAttribute(name="shipping_address", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="notes", data_type=DataType.TEXT, required=False),
    ],
    "Payment": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="amount", data_type=DataType.DECIMAL, required=True),
        EntityAttribute(name="currency", data_type=DataType.STRING, required=True, default_value="USD"),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="pending", enum_values=["pending", "completed", "failed", "refunded"]),
        EntityAttribute(name="payment_method", data_type=DataType.STRING, required=True),
        EntityAttribute(name="transaction_id", data_type=DataType.STRING, required=False, unique=True),
    ],
    "Post": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="title", data_type=DataType.STRING, required=True),
        EntityAttribute(name="body", data_type=DataType.TEXT, required=True),
        EntityAttribute(name="slug", data_type=DataType.STRING, required=True, unique=True),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="draft", enum_values=["draft", "published", "archived"]),
        EntityAttribute(name="featured_image", data_type=DataType.URL, required=False),
    ],
    "Comment": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="body", data_type=DataType.TEXT, required=True),
        EntityAttribute(name="is_approved", data_type=DataType.BOOLEAN, required=True, default_value="false"),
    ],
    "Task": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="title", data_type=DataType.STRING, required=True),
        EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="todo", enum_values=["todo", "in_progress", "review", "done"]),
        EntityAttribute(name="priority", data_type=DataType.ENUM, required=True, default_value="medium", enum_values=["low", "medium", "high", "critical"]),
        EntityAttribute(name="due_date", data_type=DataType.DATE, required=False),
    ],
    "Project": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="active", enum_values=["active", "paused", "completed", "archived"]),
    ],
    "Category": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="name", data_type=DataType.STRING, required=True, unique=True),
        EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="parent_id", data_type=DataType.UUID, required=False),
    ],
    "Message": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="subject", data_type=DataType.STRING, required=False),
        EntityAttribute(name="body", data_type=DataType.TEXT, required=True),
        EntityAttribute(name="is_read", data_type=DataType.BOOLEAN, required=True, default_value="false"),
    ],
    "Plan": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="name", data_type=DataType.STRING, required=True),
        EntityAttribute(name="price", data_type=DataType.DECIMAL, required=True),
        EntityAttribute(name="interval", data_type=DataType.ENUM, required=True, default_value="monthly", enum_values=["monthly", "yearly"]),
        EntityAttribute(name="features", data_type=DataType.JSON, required=False),
        EntityAttribute(name="is_active", data_type=DataType.BOOLEAN, required=True, default_value="true"),
    ],
    "Notification": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="title", data_type=DataType.STRING, required=True),
        EntityAttribute(name="message", data_type=DataType.TEXT, required=True),
        EntityAttribute(name="type", data_type=DataType.STRING, required=True),
        EntityAttribute(name="is_read", data_type=DataType.BOOLEAN, required=True, default_value="false"),
    ],
    "Course": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="title", data_type=DataType.STRING, required=True),
        EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        EntityAttribute(name="price", data_type=DataType.DECIMAL, required=False),
        EntityAttribute(name="is_published", data_type=DataType.BOOLEAN, required=True, default_value="false"),
    ],
    "Appointment": [
        EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
        EntityAttribute(name="title", data_type=DataType.STRING, required=True),
        EntityAttribute(name="start_time", data_type=DataType.DATETIME, required=True),
        EntityAttribute(name="end_time", data_type=DataType.DATETIME, required=True),
        EntityAttribute(name="status", data_type=DataType.ENUM, required=True, default_value="scheduled", enum_values=["scheduled", "confirmed", "cancelled", "completed"]),
        EntityAttribute(name="notes", data_type=DataType.TEXT, required=False),
    ],
}

# ── Relationship inference ───────────────────────────────────────────────

_COMMON_RELATIONS: Dict[str, List[tuple[str, RelationType]]] = {
    "Contact": [("User", RelationType.MANY_TO_MANY)],
    "Order": [("User", RelationType.MANY_TO_MANY), ("Product", RelationType.MANY_TO_MANY)],
    "Payment": [("User", RelationType.MANY_TO_MANY), ("Order", RelationType.ONE_TO_ONE)],
    "Post": [("User", RelationType.MANY_TO_MANY), ("Category", RelationType.MANY_TO_MANY)],
    "Comment": [("User", RelationType.MANY_TO_MANY), ("Post", RelationType.MANY_TO_MANY)],
    "Task": [("User", RelationType.MANY_TO_MANY), ("Project", RelationType.MANY_TO_MANY)],
    "Project": [("User", RelationType.MANY_TO_MANY)],
    "Message": [("User", RelationType.MANY_TO_MANY)],
    "Notification": [("User", RelationType.MANY_TO_MANY)],
    "Course": [("User", RelationType.MANY_TO_MANY)],
    "Appointment": [("User", RelationType.MANY_TO_MANY)],
    "Plan": [],
    "Category": [],
    "Dashboard": [],
    "Role": [],
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _plural(name: str) -> str:
    if name.endswith("s"):
        return name
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    return name + "s"


def _build_entities(intent: Intent) -> List[EntityDesign]:
    entities: List[EntityDesign] = []
    entity_names: Set[str] = {e.name for e in intent.entities}

    for det in intent.entities:
        attrs = list(_DEFAULT_ATTRS.get(det.name, [
            EntityAttribute(name="id", data_type=DataType.UUID, required=True, unique=True),
            EntityAttribute(name="name", data_type=DataType.STRING, required=True),
            EntityAttribute(name="description", data_type=DataType.TEXT, required=False),
        ]))
        # Add any user-specified attributes not already present
        existing = {a.name for a in attrs}
        for attr_name in det.attributes:
            if attr_name not in existing:
                attrs.append(EntityAttribute(name=attr_name, data_type=DataType.STRING, required=False))

        # Relationships
        rels: List[EntityRelationship] = []
        for target, rel_type in _COMMON_RELATIONS.get(det.name, []):
            if target in entity_names:
                rels.append(EntityRelationship(
                    target_entity=target,
                    relation_type=rel_type,
                    foreign_key=f"{target.lower()}_id",
                ))

        entities.append(EntityDesign(
            name=det.name,
            description=det.description,
            attributes=attrs,
            relationships=rels,
            is_auth_entity=det.name == "User",
        ))

    return entities


def _build_pages(intent: Intent, entity_names: Set[str]) -> List[PageDesign]:
    pages: List[PageDesign] = []
    role_names = [r.name for r in intent.roles] or ["admin", "user"]

    # Auth pages
    has_auth = any(f.category == FeatureCategory.AUTH for f in intent.features)
    if has_auth:
        pages.append(PageDesign(name="Login", route="/login", page_type=PageType.AUTH, access_roles=[]))
        pages.append(PageDesign(name="Register", route="/register", page_type=PageType.AUTH, access_roles=[]))

    # Dashboard
    if any(f.category == FeatureCategory.DASHBOARD for f in intent.features):
        pages.append(PageDesign(name="Dashboard", route="/dashboard", page_type=PageType.DASHBOARD, access_roles=role_names))

    # CRUD pages for each entity (excluding User for auth)
    for name in sorted(entity_names):
        if name in ("User", "Dashboard", "Role", "Notification"):
            continue
        slug = _plural(_slug(name))
        pages.append(PageDesign(name=f"{name} List", route=f"/{slug}", page_type=PageType.LIST, entity=name, access_roles=role_names))
        pages.append(PageDesign(name=f"{name} Detail", route=f"/{slug}/{{id}}", page_type=PageType.DETAIL, entity=name, access_roles=role_names))
        pages.append(PageDesign(name=f"Create {name}", route=f"/{slug}/new", page_type=PageType.FORM, entity=name, access_roles=role_names))

    # Analytics
    if any(f.category == FeatureCategory.ANALYTICS for f in intent.features):
        admin_roles = [r for r in role_names if r in ("admin", "manager")]
        pages.append(PageDesign(name="Analytics", route="/analytics", page_type=PageType.ANALYTICS, access_roles=admin_roles or role_names))

    # Settings
    if any(f.category == FeatureCategory.SETTINGS for f in intent.features):
        pages.append(PageDesign(name="Settings", route="/settings", page_type=PageType.SETTINGS, access_roles=role_names))

    return pages


def _build_user_flows(intent: Intent, pages: List[PageDesign]) -> List[UserFlow]:
    flows: List[UserFlow] = []
    page_routes = {p.name: p.route for p in pages}

    # Login flow
    if "Login" in page_routes:
        flows.append(UserFlow(
            name="User Login",
            description="User authenticates and reaches the dashboard",
            actor_role="user",
            steps=[
                FlowStep(step_number=1, description="Navigate to login page", page="Login", action="view"),
                FlowStep(step_number=2, description="Enter credentials", page="Login", action="submit_form"),
                FlowStep(step_number=3, description="Redirect to dashboard", page="Dashboard", action="view"),
            ],
        ))

    # Basic CRUD flow for the first non-auth entity
    for page in pages:
        if page.page_type == PageType.LIST and page.entity:
            entity = page.entity
            flows.append(UserFlow(
                name=f"Manage {entity}",
                description=f"Create, view, and manage {entity} records",
                actor_role="user",
                steps=[
                    FlowStep(step_number=1, description=f"View {entity} list", page=page.name, action="view"),
                    FlowStep(step_number=2, description=f"Click create new {entity}", page=f"Create {entity}", action="navigate"),
                    FlowStep(step_number=3, description=f"Fill in {entity} details", page=f"Create {entity}", action="submit_form"),
                    FlowStep(step_number=4, description=f"View created {entity}", page=f"{entity} Detail", action="view"),
                ],
            ))
            break  # Only one sample flow

    return flows


def _build_roles(intent: Intent) -> List[RoleDesign]:
    roles: List[RoleDesign] = []
    entity_names = [e.name for e in intent.entities]

    for det_role in intent.roles:
        is_admin = det_role.name.lower() in ("admin", "administrator", "superadmin")
        permissions: List[RolePermission] = []

        if is_admin or "*" in det_role.permissions:
            for ent in entity_names:
                permissions.append(RolePermission(resource=ent, actions=["create", "read", "update", "delete"]))
        else:
            for ent in entity_names:
                if ent == "User":
                    permissions.append(RolePermission(resource=ent, actions=["read", "update_own"]))
                else:
                    permissions.append(RolePermission(resource=ent, actions=["create", "read", "update_own", "delete_own"]))

        roles.append(RoleDesign(
            name=det_role.name,
            description=det_role.description,
            is_admin=is_admin,
            is_default=det_role.is_default,
            permissions=permissions,
        ))

    return roles


def design_system(intent: Intent) -> SystemDesign:
    """Convert an Intent into a full SystemDesign."""

    if llm_client.available:
        result = _design_with_llm(intent)
        if result:
            return result

    entities = _build_entities(intent)
    entity_names = {e.name for e in entities}
    pages = _build_pages(intent, entity_names)
    flows = _build_user_flows(intent, pages)
    roles = _build_roles(intent)

    decisions: List[str] = [
        f"Application type: {intent.app_type.value}",
        f"Identified {len(entities)} entities with inferred relationships",
        f"Generated {len(pages)} pages based on detected features",
        f"Defined {len(roles)} roles with entity-level permissions",
    ]

    return SystemDesign(
        app_name=intent.app_name,
        entities=entities,
        pages=pages,
        user_flows=flows,
        roles=roles,
        design_decisions=decisions,
    )


def _design_with_llm(intent: Intent) -> SystemDesign | None:
    system = (
        "You are Stage 2 of a software-generation compiler. "
        "Given a structured intent JSON, produce a system design JSON. "
        "Return: {app_name, entities, pages, user_flows, roles, design_decisions}. "
        "Each entity has: name, description, attributes (list of {name, data_type, required, unique, description}), "
        "relationships (list of {target_entity, relation_type, foreign_key}), is_auth_entity, timestamps. "
        "data_type is one of: string, integer, float, boolean, text, date, datetime, email, password, url, json, enum, uuid, decimal. "
        "relation_type is one of: one_to_one, one_to_many, many_to_many. "
        "Each page: {name, route, page_type, description, entity, access_roles}. "
        "page_type is one of: list, detail, form, dashboard, auth, settings, analytics, custom. "
        "Each user_flow: {name, description, actor_role, steps: [{step_number, description, page, action}]}. "
        "Each role: {name, description, is_admin, is_default, permissions: [{resource, actions}]}."
    )
    data = llm_client.generate_json(system, intent.model_dump_json())
    if data is None:
        return None
    try:
        return SystemDesign.model_validate(data)
    except Exception:
        return None
