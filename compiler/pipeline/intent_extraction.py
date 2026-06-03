"""Stage 1 – Intent Extraction.

Parses a natural-language prompt into a structured ``Intent`` object using
keyword matching, pattern detection, and optional LLM enhancement.
"""

from __future__ import annotations

import re
from typing import Dict, List, Set, Tuple

from ..llm.client import llm_client
from ..schemas.intent import (
    AppType,
    BusinessRule,
    DetectedEntity,
    DetectedFeature,
    DetectedRole,
    FeatureCategory,
    Intent,
)

# ── Keyword → AppType mapping ───────────────────────────────────────────

_APP_TYPE_KEYWORDS: Dict[AppType, List[str]] = {
    AppType.CRM: ["crm", "customer relationship", "contacts", "leads", "sales pipeline"],
    AppType.ECOMMERCE: ["ecommerce", "e-commerce", "shop", "store", "cart", "checkout", "products", "catalog"],
    AppType.SOCIAL: ["social", "feed", "posts", "followers", "friends", "timeline"],
    AppType.BLOG: ["blog", "articles", "posts", "comments", "publishing"],
    AppType.PROJECT_MANAGEMENT: ["project management", "tasks", "kanban", "sprints", "boards", "tickets"],
    AppType.SAAS: ["saas", "subscription", "multi-tenant", "tenant"],
    AppType.MARKETPLACE: ["marketplace", "listings", "sellers", "buyers", "auction"],
    AppType.EDUCATION: ["education", "courses", "students", "teachers", "lms", "learning"],
    AppType.HEALTHCARE: ["healthcare", "patients", "doctors", "appointments", "medical", "clinic"],
}

# ── Keyword → Feature mapping ───────────────────────────────────────────

_FEATURE_KEYWORDS: Dict[FeatureCategory, List[str]] = {
    FeatureCategory.AUTH: ["login", "signup", "sign up", "register", "authentication", "auth", "sso", "oauth", "password", "2fa"],
    FeatureCategory.DASHBOARD: ["dashboard", "overview", "home page", "admin panel", "control panel"],
    FeatureCategory.PAYMENTS: ["payment", "billing", "stripe", "checkout", "subscription", "premium", "plan", "pricing", "invoice"],
    FeatureCategory.ANALYTICS: ["analytics", "metrics", "reports", "charts", "graphs", "statistics", "insights"],
    FeatureCategory.MESSAGING: ["messaging", "chat", "inbox", "messages", "notifications", "email"],
    FeatureCategory.SEARCH: ["search", "filter", "find", "query", "lookup"],
    FeatureCategory.NOTIFICATIONS: ["notification", "alert", "reminder", "push notification"],
    FeatureCategory.FILE_UPLOAD: ["upload", "file", "image", "attachment", "media", "document"],
    FeatureCategory.REPORTING: ["report", "export", "csv", "pdf", "download"],
    FeatureCategory.SETTINGS: ["settings", "preferences", "profile", "account settings", "configuration"],
}

# ── Role keywords ────────────────────────────────────────────────────────

_ROLE_KEYWORDS: Dict[str, List[str]] = {
    "admin": ["admin", "administrator", "superadmin", "super admin", "owner"],
    "user": ["user", "member", "customer", "client", "subscriber"],
    "manager": ["manager", "moderator", "supervisor", "team lead"],
    "editor": ["editor", "author", "writer", "contributor"],
    "viewer": ["viewer", "guest", "visitor", "readonly", "read-only"],
}

# ── Entity patterns ─────────────────────────────────────────────────────

_ENTITY_KEYWORDS: Dict[str, List[str]] = {
    "User": ["user", "account", "member", "profile"],
    "Contact": ["contact", "lead", "client", "customer"],
    "Product": ["product", "item", "goods", "inventory"],
    "Order": ["order", "purchase", "transaction", "booking"],
    "Payment": ["payment", "invoice", "billing", "charge"],
    "Post": ["post", "article", "blog", "content"],
    "Comment": ["comment", "reply", "review", "feedback"],
    "Category": ["category", "tag", "label", "group"],
    "Task": ["task", "ticket", "issue", "todo"],
    "Project": ["project", "workspace", "board", "sprint"],
    "Message": ["message", "chat", "conversation", "thread"],
    "Course": ["course", "lesson", "module", "class"],
    "Appointment": ["appointment", "schedule", "booking", "slot"],
    "Dashboard": ["dashboard", "analytics", "report", "metric"],
    "Role": ["role", "permission", "access"],
    "Plan": ["plan", "subscription", "tier", "pricing"],
    "Notification": ["notification", "alert", "reminder"],
}

# ── Business-rule patterns ───────────────────────────────────────────────

_RULE_PATTERNS: List[Tuple[str, str, str]] = [
    (r"(?:only|just)\s+(\w+)\s+can\s+(.*)", "role_restriction", "restrict access"),
    (r"(\w+)\s+(?:requires?|needs?)\s+(.*)", "prerequisite", "enforce prerequisite"),
    (r"premium\s+(?:users?|plan|tier)\s+(.*)", "premium_gating", "gate behind premium"),
    (r"(?:if|when)\s+(.*?)\s+then\s+(.*)", "conditional", "conditional logic"),
    (r"(\w+)\s+(?:must|should)\s+(?:be|have)\s+(.*)", "constraint", "apply constraint"),
]


def _lower(text: str) -> str:
    return text.lower().strip()


def _detect_app_type(text: str) -> AppType:
    text_l = _lower(text)
    scores: Dict[AppType, int] = {}
    for app_type, keywords in _APP_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_l)
        if score:
            scores[app_type] = score
    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return AppType.CUSTOM


def _detect_features(text: str) -> List[DetectedFeature]:
    text_l = _lower(text)
    features: List[DetectedFeature] = []
    seen: Set[FeatureCategory] = set()
    for category, keywords in _FEATURE_KEYWORDS.items():
        matched = [kw for kw in keywords if kw in text_l]
        if matched and category not in seen:
            seen.add(category)
            features.append(
                DetectedFeature(
                    name=category.value.replace("_", " ").title(),
                    category=category,
                    description=f"Detected from keywords: {', '.join(matched)}",
                    priority="high" if len(matched) > 1 else "medium",
                    requires_auth=category not in {FeatureCategory.SEARCH},
                )
            )
    if not any(f.category == FeatureCategory.AUTH for f in features):
        features.insert(
            0,
            DetectedFeature(
                name="Authentication",
                category=FeatureCategory.AUTH,
                description="Default: authentication assumed required",
                priority="high",
                requires_auth=False,
            ),
        )
    return features


def _detect_entities(text: str, app_type: AppType) -> List[DetectedEntity]:
    text_l = _lower(text)
    entities: List[DetectedEntity] = []
    seen: Set[str] = set()
    for entity_name, keywords in _ENTITY_KEYWORDS.items():
        if any(kw in text_l for kw in keywords) and entity_name not in seen:
            seen.add(entity_name)
            entities.append(
                DetectedEntity(
                    name=entity_name,
                    description=f"{entity_name} entity for the application",
                    attributes=[],
                    is_primary=entity_name == "User",
                )
            )
    if "User" not in seen:
        entities.insert(
            0,
            DetectedEntity(
                name="User",
                description="Application user",
                attributes=["email", "password", "name"],
                is_primary=True,
            ),
        )
    return entities


def _detect_roles(text: str) -> List[DetectedRole]:
    text_l = _lower(text)
    roles: List[DetectedRole] = []
    seen: Set[str] = set()
    for role_name, keywords in _ROLE_KEYWORDS.items():
        if any(kw in text_l for kw in keywords) and role_name not in seen:
            seen.add(role_name)
            roles.append(
                DetectedRole(
                    name=role_name,
                    description=f"{role_name.title()} role",
                    permissions=[],
                    is_default=role_name == "user",
                )
            )
    if not roles:
        roles = [
            DetectedRole(name="admin", description="Administrator", permissions=["*"], is_default=False),
            DetectedRole(name="user", description="Regular user", permissions=["read", "write_own"], is_default=True),
        ]
    return roles


def _detect_business_rules(text: str) -> List[BusinessRule]:
    rules: List[BusinessRule] = []
    sentences = re.split(r"[.;!?\n]", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for pattern, rule_type, action_desc in _RULE_PATTERNS:
            match = re.search(pattern, sentence, re.IGNORECASE)
            if match:
                rules.append(
                    BusinessRule(
                        name=rule_type,
                        description=sentence,
                        condition=match.group(1) if match.lastindex and match.lastindex >= 1 else sentence,
                        action=action_desc,
                        affected_entities=[],
                    )
                )
                break
    return rules


def _infer_app_name(text: str, app_type: AppType) -> str:
    patterns = [
        r"(?:build|create|make|design)\s+(?:a|an|the)\s+(\w+(?:\s+\w+)?)",
        r"^(\w+(?:\s+\w+)?)\s+(?:app|application|system|platform)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip().title()
            if len(name) > 2 and name.lower() not in {"a", "an", "the", "my"}:
                return name
    return app_type.value.replace("_", " ").title() + " App"


def _detect_ambiguities(text: str) -> List[str]:
    ambiguities: List[str] = []
    if len(text.split()) < 10:
        ambiguities.append("Input is very short – many details were assumed")
    if "?" in text:
        ambiguities.append("Input contains questions – treated as requirements")
    vague_terms = ["some", "maybe", "possibly", "might", "could", "etc", "stuff", "things"]
    found_vague = [t for t in vague_terms if t in text.lower()]
    if found_vague:
        ambiguities.append(f"Vague terms detected: {', '.join(found_vague)}")
    return ambiguities


def extract_intent(prompt: str) -> Intent:
    """Parse a natural-language prompt into a structured Intent."""

    if not prompt or not prompt.strip():
        return Intent(
            app_name="Unknown",
            app_type=AppType.CUSTOM,
            description="Empty prompt",
            assumptions=["No input provided – generated minimal skeleton"],
            confidence_score=0.1,
            raw_input=prompt or "",
        )

    # Try LLM first
    if llm_client.available:
        llm_result = _extract_with_llm(prompt)
        if llm_result:
            return llm_result

    # Fallback: rule-based extraction
    app_type = _detect_app_type(prompt)
    features = _detect_features(prompt)
    entities = _detect_entities(prompt, app_type)
    roles = _detect_roles(prompt)
    business_rules = _detect_business_rules(prompt)
    ambiguities = _detect_ambiguities(prompt)
    app_name = _infer_app_name(prompt, app_type)

    assumptions: List[str] = []
    if len(entities) <= 1:
        assumptions.append("Limited entities detected – added common defaults for app type")
    if not business_rules:
        assumptions.append("No explicit business rules – standard CRUD assumed")

    feature_count = len(features)
    entity_count = len(entities)
    confidence = min(1.0, 0.3 + (feature_count * 0.08) + (entity_count * 0.06) + (len(roles) * 0.05))

    return Intent(
        app_name=app_name,
        app_type=app_type,
        description=f"A {app_type.value.replace('_', ' ')} application with {feature_count} features and {entity_count} entities",
        features=features,
        entities=entities,
        roles=roles,
        business_rules=business_rules,
        assumptions=assumptions,
        ambiguities=ambiguities,
        confidence_score=round(confidence, 2),
        raw_input=prompt,
    )


def _extract_with_llm(prompt: str) -> Intent | None:
    """Use the LLM to produce a richer Intent extraction."""

    system = (
        "You are Stage 1 of a software-generation compiler. "
        "Given a natural-language product description, extract structured intent. "
        "Return a JSON object with keys: app_name, app_type, description, features, "
        "entities, roles, business_rules, assumptions, ambiguities, confidence_score. "
        "app_type must be one of: crm, ecommerce, social_network, blog, project_management, "
        "saas, marketplace, education, healthcare, custom. "
        "Each feature: {name, category, description, priority, requires_auth}. "
        "category must be one of: authentication, crud, dashboard, payments, analytics, "
        "messaging, search, notifications, file_upload, reporting, settings, custom. "
        "Each entity: {name, description, attributes: [string], is_primary}. "
        "Each role: {name, description, permissions: [string], is_default}. "
        "Each business_rule: {name, description, condition, action, affected_entities}."
    )
    data = llm_client.generate_json(system, prompt)
    if data is None:
        return None
    try:
        data["raw_input"] = prompt
        return Intent.model_validate(data)
    except Exception:
        return None
