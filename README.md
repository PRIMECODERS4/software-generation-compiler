# Software Generation Compiler

A multi-stage compilation system that converts natural language descriptions into fully structured, validated, and executable application configurations.

## Architecture

```
Natural Language → Intent Extraction → System Design → Schema Generation → Refinement → Executable Code
                      Stage 1             Stage 2           Stage 3           Stage 4       Runtime
```

### Pipeline Stages

| Stage | Input | Output | Description |
|-------|-------|--------|-------------|
| 1. Intent Extraction | Natural language prompt | `Intent` (structured) | Parses app type, features, entities, roles, business rules |
| 2. System Design | `Intent` | `SystemDesign` | Defines entity attributes, relationships, pages, user flows, role permissions |
| 3. Schema Generation | `SystemDesign` | `AppConfig` (UI + API + DB + Auth) | Generates complete application schemas with cross-layer consistency |
| 4. Refinement | `AppConfig` | Refined `AppConfig` | Resolves cross-layer inconsistencies, adds missing fields |

### Validation + Repair Engine

The system includes a multi-layer validation engine that checks:

- **Structural completeness**: Required fields, non-empty collections
- **Type consistency**: Column types, data type mappings
- **Cross-layer references**: UI→API→DB→Auth consistency
- **Duplicate detection**: Tables, columns, routes, endpoints

When issues are found, the **repair engine** applies targeted fixes:

- Missing primary keys → auto-insert UUID PK column
- Missing roles → auto-create role definitions
- Missing timestamp columns → auto-add created_at/updated_at
- Empty tables → populate with default columns

### Runtime Code Generator

Generates executable code from the validated AppConfig:

- **models.py** – SQLAlchemy ORM models
- **routes.py** – Flask API routes (CRUD + auth endpoints)
- **app.py** – Flask application entry point
- **templates/** – Jinja2 HTML templates with navigation
- **migrations/** – SQL DDL statements

## Tech Stack

- **Backend**: Python, FastAPI, Pydantic v2
- **Schema Validation**: Pydantic models with strict typing
- **Code Generation**: Template-based Flask + SQLAlchemy
- **LLM Integration**: Optional OpenAI API (falls back to rule-based engine)
- **Frontend**: Vanilla HTML/CSS/JS (dark theme)

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn compiler.main:app --reload --port 8000

# Open in browser
open http://localhost:8000
```

### With Docker

```bash
docker build -t software-compiler .
docker run -p 8000:8000 software-compiler
```

### With OpenAI (optional)

```bash
export OPENAI_API_KEY=sk-...
uvicorn compiler.main:app --reload --port 8000
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/compile` | Compile a natural language prompt |
| POST | `/api/evaluate` | Run evaluation framework |
| GET | `/api/prompts` | List test prompts |
| GET | `/api/health` | Health check |

## Evaluation Framework

Includes 20 test prompts:

- **10 real-world prompts**: CRM, e-commerce, project management, blog, LMS, SaaS analytics, healthcare, marketplace, social media, HR management
- **10 edge cases**: vague inputs, conflicting requirements, empty input, SQL injection, emoji-heavy, single word, unrealistic requirements

Metrics tracked:
- Success rate
- Retries per request
- Failure types
- Latency
- Issues found vs. auto-repaired

## Design Decisions

### Why Rule-Based + LLM Hybrid?

1. **Reliability**: Rule-based engine guarantees consistent output regardless of LLM availability
2. **Determinism**: Same input produces same output (no LLM variance)
3. **Speed**: Rule-based processing is instant (~1ms) vs LLM calls (~2-5s)
4. **Cost**: Zero cost when running without LLM
5. **Fallback**: System degrades gracefully when LLM is unavailable

### Why Pydantic for Schemas?

- Strict type enforcement at every pipeline stage
- Automatic JSON serialization/validation
- Clear contract between stages
- Self-documenting models

### Cost vs Quality Tradeoffs

| Mode | Latency | Cost | Quality |
|------|---------|------|---------|
| Rule-based only | ~1-5ms | Free | Good (template-based) |
| LLM-enhanced | ~3-8s | ~$0.01-0.05/call | Excellent (contextual) |
| Hybrid (fallback) | Varies | Minimal | Best effort |

## Project Structure

```
compiler/
├── main.py                      # FastAPI application
├── config.py                    # Configuration
├── pipeline/
│   ├── orchestrator.py          # Pipeline coordinator
│   ├── intent_extraction.py     # Stage 1: NL → Intent
│   ├── system_design.py         # Stage 2: Intent → Design
│   ├── schema_generation.py     # Stage 3: Design → AppConfig
│   └── refinement.py            # Stage 4: Cross-layer fixes
├── schemas/
│   ├── intent.py                # Intent data models
│   ├── design.py                # System design models
│   ├── app_config.py            # Full app config (UI/API/DB/Auth)
│   └── pipeline_result.py       # Pipeline result wrapper
├── validation/
│   ├── validator.py             # Multi-layer validation
│   └── repair.py                # Intelligent repair engine
├── runtime/
│   └── generator.py             # Code generation
├── evaluation/
│   ├── framework.py             # Evaluation runner
│   └── prompts.py               # 20 test prompts
└── llm/
    └── client.py                # LLM client with fallback
frontend/
├── index.html                   # Web interface
├── style.css                    # Dark theme styles
└── app.js                       # Frontend logic
```
