# Orysys

Orysys is an access-scoped enterprise knowledge assistant. It is designed to
produce evidence-backed answers, expose safe execution activity, and keep model
decisions inside deterministic authorization and validation controls.

The repository is currently at the product-baseline stage: domain contracts,
provider ports, deterministic test adapters, configuration, and a FastAPI health
boundary are available. Retrieval, LangGraph orchestration, Streamlit, and live
provider adapters follow in later work packages.

## Requirements

- Python 3.13
- `uv`

## Local setup

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run mypy src tests
uv run uvicorn orysys.api.app:create_app --factory --reload
```

The liveness endpoint is `GET /health/live`. The readiness endpoint is
`GET /health/ready`; at this stage it reports the deterministic fake-adapter
profile.

Copy `.env.example` to `.env` only for local development. Never commit tokens,
credentials, customer content, or production traces.

## Architecture

The system is a modular monolith with a separate MCP process planned at the
protocol boundary. Domain and application code depend on project-owned ports;
provider SDKs remain in adapters. See:

- [`docs/architecture-plan.md`](docs/architecture-plan.md)
- [`docs/implementation-plan.md`](docs/implementation-plan.md)
- [`docs/requirements-traceability.md`](docs/requirements-traceability.md)
- [`docs/adrs/README.md`](docs/adrs/README.md)

## Current scope

Implemented in the baseline:

- immutable identity and server-derived access-scope contracts;
- evidence, claim, plan, event, tool, validation, memory, and feedback schemas;
- async ports for models, retrieval, identity, tools, limits, and telemetry;
- deterministic fake adapters for credential-free tests;
- validated environment settings and FastAPI health endpoints;
- lint, formatting, type-checking, test, and CI configuration.

The traceability matrix remains the authority for implementation and verification
status. A requirement is not considered verified merely because its interface exists.

