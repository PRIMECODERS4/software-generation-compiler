"""Evaluation dataset: 10 real-world prompts + 10 edge cases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class TestPrompt:
    id: str
    prompt: str
    category: str  # "real" | "edge_vague" | "edge_conflicting" | "edge_incomplete"
    description: str
    expected_entities: List[str] = field(default_factory=list)
    expected_features: List[str] = field(default_factory=list)


# ── 10 Real-World Product Prompts ────────────────────────────────────────

REAL_PROMPTS: List[TestPrompt] = [
    TestPrompt(
        id="real_01",
        prompt="Build a CRM with login, contacts, dashboard, role-based access, and premium plan with payments. Admins can see analytics.",
        category="real",
        description="Full CRM application",
        expected_entities=["User", "Contact", "Payment", "Plan"],
        expected_features=["authentication", "dashboard", "payments", "analytics"],
    ),
    TestPrompt(
        id="real_02",
        prompt="Create an e-commerce store with product listings, shopping cart, checkout with Stripe, user accounts, order tracking, and admin inventory management.",
        category="real",
        description="E-commerce platform",
        expected_entities=["User", "Product", "Order", "Payment", "Category"],
        expected_features=["authentication", "payments", "search"],
    ),
    TestPrompt(
        id="real_03",
        prompt="I need a project management tool like Trello. Users can create boards, add tasks, assign members, set due dates, and move tasks between columns. Admins can manage teams.",
        category="real",
        description="Project management (Trello-like)",
        expected_entities=["User", "Project", "Task"],
        expected_features=["authentication", "dashboard"],
    ),
    TestPrompt(
        id="real_04",
        prompt="Build a blog platform where authors can write and publish articles, readers can comment, and admins can moderate content. Support categories and tags.",
        category="real",
        description="Blog / CMS platform",
        expected_entities=["User", "Post", "Comment", "Category"],
        expected_features=["authentication", "search"],
    ),
    TestPrompt(
        id="real_05",
        prompt="Create an online learning platform with courses, lessons, quizzes, student enrollment, progress tracking, and instructor dashboards. Support premium courses with payment.",
        category="real",
        description="LMS / e-learning platform",
        expected_entities=["User", "Course", "Payment"],
        expected_features=["authentication", "dashboard", "payments"],
    ),
    TestPrompt(
        id="real_06",
        prompt="Build a SaaS analytics dashboard. Users sign up, connect their data sources, create custom dashboards with charts, and export reports. Team accounts with role-based access.",
        category="real",
        description="SaaS analytics tool",
        expected_entities=["User", "Dashboard"],
        expected_features=["authentication", "dashboard", "analytics", "reporting"],
    ),
    TestPrompt(
        id="real_07",
        prompt="Create a healthcare appointment booking system. Patients can find doctors, book appointments, view medical records, and receive reminders. Doctors manage schedules and patient notes.",
        category="real",
        description="Healthcare appointment system",
        expected_entities=["User", "Appointment"],
        expected_features=["authentication", "notifications", "search"],
    ),
    TestPrompt(
        id="real_08",
        prompt="Build a marketplace where sellers can list products, buyers can browse and purchase, with reviews, messaging between users, and admin dispute resolution.",
        category="real",
        description="Marketplace platform",
        expected_entities=["User", "Product", "Order", "Message"],
        expected_features=["authentication", "payments", "messaging", "search"],
    ),
    TestPrompt(
        id="real_09",
        prompt="I want a social media app with user profiles, posts, comments, likes, follow/unfollow, a news feed, and direct messaging. Users can upload images.",
        category="real",
        description="Social media platform",
        expected_entities=["User", "Post", "Comment", "Message"],
        expected_features=["authentication", "messaging", "file_upload"],
    ),
    TestPrompt(
        id="real_10",
        prompt="Create a multi-tenant HR management system with employee profiles, leave management, payroll, performance reviews, and department management. Super admins manage tenants.",
        category="real",
        description="HR management SaaS",
        expected_entities=["User", "Task"],
        expected_features=["authentication", "dashboard", "reporting"],
    ),
]

# ── 10 Edge Case Prompts ─────────────────────────────────────────────────

EDGE_PROMPTS: List[TestPrompt] = [
    TestPrompt(
        id="edge_01",
        prompt="Build me an app",
        category="edge_vague",
        description="Extremely vague – minimal information",
    ),
    TestPrompt(
        id="edge_02",
        prompt="I need something with stuff and things",
        category="edge_vague",
        description="Intentionally meaningless input",
    ),
    TestPrompt(
        id="edge_03",
        prompt="Create a public platform where all data is private and no one can see anything but everyone can edit everything.",
        category="edge_conflicting",
        description="Contradictory requirements (public vs private)",
    ),
    TestPrompt(
        id="edge_04",
        prompt="Build an app with login. Also no login required. Users must authenticate but the app should be fully public.",
        category="edge_conflicting",
        description="Conflicting auth requirements",
    ),
    TestPrompt(
        id="edge_05",
        prompt="payments",
        category="edge_incomplete",
        description="Single word input",
    ),
    TestPrompt(
        id="edge_06",
        prompt="",
        category="edge_incomplete",
        description="Empty input",
    ),
    TestPrompt(
        id="edge_07",
        prompt="Create an app that handles 10 billion users simultaneously with zero latency, infinite storage, and automatic AI that writes itself. Also it should cost nothing.",
        category="edge_conflicting",
        description="Unrealistic requirements",
    ),
    TestPrompt(
        id="edge_08",
        prompt="I want a CRM but also it should be an e-commerce store and also a social network and also a game and also a banking app and also a streaming platform all in one.",
        category="edge_conflicting",
        description="Overloaded with contradictory app types",
    ),
    TestPrompt(
        id="edge_09",
        prompt="🚀 Build me something AMAZING!!! 💯🔥 with #AI and #blockchain and #metaverse",
        category="edge_vague",
        description="Emoji/hashtag-heavy with no substance",
    ),
    TestPrompt(
        id="edge_10",
        prompt="SELECT * FROM users; DROP TABLE users; -- Build me an app with admin panel",
        category="edge_vague",
        description="SQL injection attempt in prompt",
    ),
]

ALL_PROMPTS: List[TestPrompt] = REAL_PROMPTS + EDGE_PROMPTS
