"""Runtime code generator.

Transforms an AppConfig into executable source files (Flask + SQLAlchemy +
Jinja2 templates) that constitute a working application.
"""

from __future__ import annotations

from typing import List

from ..schemas.app_config import AppConfig, ColumnType, HTTPMethod
from ..schemas.pipeline_result import GeneratedCode

# ── Column type → SQLAlchemy mapping ─────────────────────────────────────

_SA_TYPE: dict[ColumnType, str] = {
    ColumnType.VARCHAR: "db.String({length})",
    ColumnType.TEXT: "db.Text",
    ColumnType.INTEGER: "db.Integer",
    ColumnType.BIGINT: "db.BigInteger",
    ColumnType.FLOAT: "db.Float",
    ColumnType.DECIMAL: "db.Numeric(10, 2)",
    ColumnType.BOOLEAN: "db.Boolean",
    ColumnType.DATE: "db.Date",
    ColumnType.TIMESTAMP: "db.DateTime",
    ColumnType.JSON: "db.JSON",
    ColumnType.UUID: "db.String(36)",
    ColumnType.ENUM: "db.String(50)",
}


def generate_code(config: AppConfig) -> List[GeneratedCode]:
    """Produce a set of ready-to-run source files from *config*."""

    files: List[GeneratedCode] = []
    files.append(_gen_requirements())
    files.append(_gen_models(config))
    files.append(_gen_routes(config))
    files.append(_gen_app(config))
    files.append(_gen_base_template(config))
    files.append(_gen_index_template(config))
    files.append(_gen_sql_migrations(config))
    return files


# ── requirements.txt ─────────────────────────────────────────────────────

def _gen_requirements() -> GeneratedCode:
    return GeneratedCode(
        filename="requirements.txt",
        language="text",
        description="Python dependencies for the generated app",
        content=(
            "flask==3.1.1\n"
            "flask-sqlalchemy==3.1.1\n"
            "flask-login==0.6.3\n"
            "flask-cors==5.0.1\n"
            "werkzeug==3.1.3\n"
            "python-dotenv==1.1.0\n"
        ),
    )


# ── SQLAlchemy models ────────────────────────────────────────────────────

def _gen_models(config: AppConfig) -> GeneratedCode:
    lines = [
        '"""Auto-generated SQLAlchemy models."""',
        "",
        "import uuid",
        "from datetime import datetime",
        "",
        "from flask_sqlalchemy import SQLAlchemy",
        "",
        "db = SQLAlchemy()",
        "",
    ]

    for table in config.db_schema.tables:
        class_name = _table_to_class(table.name)
        lines.append(f"class {class_name}(db.Model):")
        lines.append(f"    __tablename__ = '{table.name}'")
        lines.append("")

        for col in table.columns:
            sa_type = _sa_col_type(col.column_type, col.max_length)
            parts = [f"db.Column({sa_type}"]
            if col.primary_key:
                parts.append("primary_key=True")
                parts.append("default=lambda: str(uuid.uuid4())")
            if col.unique and not col.primary_key:
                parts.append("unique=True")
            if col.nullable:
                parts.append("nullable=True")
            else:
                parts.append("nullable=False")
            if col.default and not col.primary_key:
                if col.default == "CURRENT_TIMESTAMP":
                    parts.append("default=datetime.utcnow")
                elif col.default in ("true", "false"):
                    parts.append(f"default={col.default.capitalize()}")
                elif col.column_type in (ColumnType.INTEGER, ColumnType.BIGINT, ColumnType.FLOAT, ColumnType.DECIMAL):
                    parts.append(f"default={col.default}")
                else:
                    parts.append(f"default='{col.default}'")
            if col.foreign_key:
                fk = f"{col.foreign_key.table}.{col.foreign_key.column}"
                parts[0] = f"db.Column({sa_type}, db.ForeignKey('{fk}')"
            line = ", ".join(parts) + ")"
            lines.append(f"    {col.name} = {line}")

        lines.append("")
        lines.append(f"    def to_dict(self):")
        lines.append(f"        return {{c.name: getattr(self, c.name) for c in self.__table__.columns}}")
        lines.append("")
        lines.append("")

    return GeneratedCode(
        filename="models.py",
        language="python",
        description="SQLAlchemy ORM models",
        content="\n".join(lines),
    )


def _table_to_class(table_name: str) -> str:
    parts = table_name.split("_")
    return "".join(p.capitalize() for p in parts)


def _sa_col_type(ct: ColumnType, max_length: int | None) -> str:
    tpl = _SA_TYPE.get(ct, "db.String(255)")
    if "{length}" in tpl:
        return tpl.format(length=max_length or 255)
    return tpl


# ── Flask routes ─────────────────────────────────────────────────────────

def _gen_routes(config: AppConfig) -> GeneratedCode:
    lines = [
        '"""Auto-generated API routes."""',
        "",
        "from flask import Blueprint, jsonify, request",
        "from models import db",
        "",
        "api = Blueprint('api', __name__)",
        "",
    ]

    # Group endpoints by path prefix
    for ep in config.api_schema.endpoints:
        method = ep.method.value.lower()
        path = ep.path

        # Normalise Flask-style params
        flask_path = path.replace("{", "<").replace("}", ">")

        lines.append(f"@api.route('{flask_path}', methods=['{ep.method.value}'])")
        func_name = _route_func_name(ep.method.value, ep.path)
        params = ""
        if ep.path_params:
            params = ", ".join(ep.path_params)
        lines.append(f"def {func_name}({params}):")

        # Determine the model class
        model_class = _table_to_class(_plural(_slug(ep.related_entity))) if ep.related_entity else None

        if ep.path.endswith("/health"):
            lines.append("    return jsonify({'status': 'ok'})")
        elif "auth" in ep.path:
            lines.append(f"    # TODO: implement {ep.description}")
            lines.append(f"    return jsonify({{'message': '{ep.description}'}}), 200")
        elif ep.method == HTTPMethod.GET and not ep.path_params:
            if model_class:
                lines.append(f"    from models import {model_class}")
                lines.append(f"    page = request.args.get('page', 1, type=int)")
                lines.append(f"    limit = request.args.get('limit', 20, type=int)")
                lines.append(f"    items = {model_class}.query.paginate(page=page, per_page=limit)")
                lines.append(f"    return jsonify([i.to_dict() for i in items.items])")
            else:
                lines.append(f"    return jsonify([])")
        elif ep.method == HTTPMethod.GET and ep.path_params:
            if model_class:
                lines.append(f"    from models import {model_class}")
                lines.append(f"    item = {model_class}.query.get_or_404(id)")
                lines.append(f"    return jsonify(item.to_dict())")
            else:
                lines.append(f"    return jsonify({{}})")
        elif ep.method == HTTPMethod.POST:
            if model_class:
                lines.append(f"    from models import {model_class}")
                lines.append(f"    data = request.get_json()")
                lines.append(f"    item = {model_class}(**data)")
                lines.append(f"    db.session.add(item)")
                lines.append(f"    db.session.commit()")
                lines.append(f"    return jsonify(item.to_dict()), 201")
            else:
                lines.append(f"    return jsonify({{'created': True}}), 201")
        elif ep.method == HTTPMethod.PUT:
            if model_class:
                lines.append(f"    from models import {model_class}")
                lines.append(f"    item = {model_class}.query.get_or_404(id)")
                lines.append(f"    data = request.get_json()")
                lines.append(f"    for key, val in data.items():")
                lines.append(f"        if hasattr(item, key):")
                lines.append(f"            setattr(item, key, val)")
                lines.append(f"    db.session.commit()")
                lines.append(f"    return jsonify(item.to_dict())")
            else:
                lines.append(f"    return jsonify({{'updated': True}})")
        elif ep.method == HTTPMethod.DELETE:
            if model_class:
                lines.append(f"    from models import {model_class}")
                lines.append(f"    item = {model_class}.query.get_or_404(id)")
                lines.append(f"    db.session.delete(item)")
                lines.append(f"    db.session.commit()")
                lines.append(f"    return jsonify({{'deleted': True}})")
            else:
                lines.append(f"    return jsonify({{'deleted': True}})")
        else:
            lines.append(f"    return jsonify({{'message': 'not implemented'}}), 501")
        lines.append("")
        lines.append("")

    return GeneratedCode(
        filename="routes.py",
        language="python",
        description="Flask API routes",
        content="\n".join(lines),
    )


def _route_func_name(method: str, path: str) -> str:
    parts = path.strip("/").replace("{", "").replace("}", "").split("/")
    name = "_".join(parts)
    return f"{method.lower()}_{name}"


def _slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _plural(name: str) -> str:
    if name.endswith("s"):
        return name
    if name.endswith("y") and not name.endswith("ey"):
        return name[:-1] + "ies"
    return name + "s"


# ── Flask app entry point ────────────────────────────────────────────────

def _gen_app(config: AppConfig) -> GeneratedCode:
    content = f'''"""Auto-generated Flask application – {config.app_name}."""

import os
from flask import Flask
from flask_cors import CORS
from models import db
from routes import api


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///app.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    CORS(app)
    db.init_app(app)
    app.register_blueprint(api)

    with app.app_context():
        db.create_all()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
'''
    return GeneratedCode(
        filename="app.py",
        language="python",
        description="Flask application entry point",
        content=content,
    )


# ── HTML template ────────────────────────────────────────────────────────

def _gen_base_template(config: AppConfig) -> GeneratedCode:
    nav_links = "\n".join(
        f'            <a href="{n.route}">{n.label}</a>'
        for n in config.ui_schema.navigation
    )
    content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{config.app_name}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: {config.ui_schema.theme.get("font_family", "Inter, sans-serif")}; background: {config.ui_schema.theme.get("background", "#F9FAFB")}; color: {config.ui_schema.theme.get("text_color", "#111827")}; }}
        nav {{ background: {config.ui_schema.theme.get("primary_color", "#3B82F6")}; padding: 1rem 2rem; display: flex; gap: 1rem; }}
        nav a {{ color: #fff; text-decoration: none; padding: .5rem 1rem; border-radius: 4px; }}
        nav a:hover {{ background: rgba(255,255,255,0.2); }}
        .container {{ max-width: 1200px; margin: 2rem auto; padding: 0 1rem; }}
    </style>
</head>
<body>
    <nav>
        <strong style="color:#fff;margin-right:auto">{config.app_name}</strong>
{nav_links}
    </nav>
    <div class="container">
        {{% block content %}}{{% endblock %}}
    </div>
</body>
</html>
'''
    return GeneratedCode(
        filename="templates/base.html",
        language="html",
        description="Base Jinja2 template with navigation",
        content=content,
    )


def _gen_index_template(config: AppConfig) -> GeneratedCode:
    content = f'''{{% extends "base.html" %}}
{{% block content %}}
<h1>Welcome to {config.app_name}</h1>
<p>This application was generated by the Software Generation Compiler.</p>
<div style="margin-top: 2rem; display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 1rem;">
    {{% for page_name in pages %}}
    <div style="background: #fff; padding: 1.5rem; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <h3>{{{{ page_name }}}}</h3>
    </div>
    {{% endfor %}}
</div>
{{% endblock %}}
'''
    return GeneratedCode(
        filename="templates/index.html",
        language="html",
        description="Index page template",
        content=content,
    )


# ── SQL Migrations ───────────────────────────────────────────────────────

def _gen_sql_migrations(config: AppConfig) -> GeneratedCode:
    lines = [f"-- Auto-generated SQL schema for {config.app_name}", ""]

    for table in config.db_schema.tables:
        lines.append(f"CREATE TABLE IF NOT EXISTS {table.name} (")
        col_defs = []
        for col in table.columns:
            parts = [f"    {col.name} {_sql_type(col.column_type, col.max_length)}"]
            if col.primary_key:
                parts.append("PRIMARY KEY")
            if not col.nullable and not col.primary_key:
                parts.append("NOT NULL")
            if col.unique and not col.primary_key:
                parts.append("UNIQUE")
            if col.default and col.default != "CURRENT_TIMESTAMP":
                parts.append(f"DEFAULT '{col.default}'")
            elif col.default == "CURRENT_TIMESTAMP":
                parts.append("DEFAULT CURRENT_TIMESTAMP")
            col_defs.append(" ".join(parts))

        # Foreign keys
        for col in table.columns:
            if col.foreign_key:
                col_defs.append(
                    f"    FOREIGN KEY ({col.name}) REFERENCES {col.foreign_key.table}({col.foreign_key.column}) "
                    f"ON DELETE {col.foreign_key.on_delete} ON UPDATE {col.foreign_key.on_update}"
                )

        lines.append(",\n".join(col_defs))
        lines.append(");")
        lines.append("")

        # Indexes
        for idx in table.indexes:
            unique = "UNIQUE " if idx.unique else ""
            cols = ", ".join(idx.columns)
            lines.append(f"CREATE {unique}INDEX IF NOT EXISTS {idx.name} ON {table.name} ({cols});")
        lines.append("")

    return GeneratedCode(
        filename="migrations/001_initial.sql",
        language="sql",
        description="Initial SQL migration",
        content="\n".join(lines),
    )


def _sql_type(ct: ColumnType, max_length: int | None) -> str:
    mapping = {
        ColumnType.VARCHAR: f"VARCHAR({max_length or 255})",
        ColumnType.TEXT: "TEXT",
        ColumnType.INTEGER: "INTEGER",
        ColumnType.BIGINT: "BIGINT",
        ColumnType.FLOAT: "FLOAT",
        ColumnType.DECIMAL: "DECIMAL(10,2)",
        ColumnType.BOOLEAN: "BOOLEAN",
        ColumnType.DATE: "DATE",
        ColumnType.TIMESTAMP: "TIMESTAMP",
        ColumnType.JSON: "JSON",
        ColumnType.UUID: "VARCHAR(36)",
        ColumnType.ENUM: "VARCHAR(50)",
    }
    return mapping.get(ct, "VARCHAR(255)")
