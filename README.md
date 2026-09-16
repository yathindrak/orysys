# Orysys

Orysys is an access-scoped enterprise knowledge assistant. It is designed to
produce evidence-backed answers, expose safe execution activity, and keep model
decisions inside deterministic authorization and validation controls.

The repository includes the product baseline, ingestion and hybrid retrieval,
grounded direct and recursive-research LangGraph paths, a streaming FastAPI boundary,
a Streamlit client, portable Keycloak OIDC authentication, authorized analytics/MCP
tools, PostgreSQL checkpoints, and consent-based cross-thread memory.

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

## Corpus ingestion

Run the complete pipeline with deterministic local adapters:

```bash
uv run python -m orysys.ingestion.cli
```

After configuring Cloudflare and Pinecone in `.env`, ingest the sample corpus into
the live index:

```bash
uv run python -m orysys.ingestion.cli --live
```

The command parses and validates the manifest, creates structure-aware chunks,
fits and persists BM25 parameters, generates L2-normalized dense embeddings, and
reconciles deterministic records in the tenant namespace. Repeating an unchanged
ingestion produces zero inserts and deletes.

Run a live access-scoped search with:

```bash
uv run python -m orysys.retrieval.cli "What caused PAY-DB-042?"
```

Run the dense, hybrid, and reranked retrieval benchmark with:

```bash
uv run python -m orysys.evals.retrieval
```

The versioned results are stored under `evals/results/` and documented in
[`evals/README.md`](evals/README.md).

## Grounded answer graph

Run one live access-scoped question through retrieval, structured answer generation,
citation validation, and the bounded repair path:

```bash
uv run python -m orysys.graph.cli "What caused PAY-DB-042?"
```

The command prints the validated answer, evidence metadata, validation results, and
ordered public event types. It does not print retrieved excerpts or credentials.

Questions that ask for annual, comparative, recurring, or cross-document analysis are
routed to the bounded research graph. For example:

```bash
uv run python -m orysys.graph.cli \
  "Across all payment incidents in 2025, what recurring root causes appeared?"
```

The research path plans discovery queries, applies server-owned incident/date/access
filters, partitions evidence by document, fans out isolated workers, deterministically
reduces cited findings, and retries one failed batch when its depth and model-call
budgets allow. A child failure cannot expose another child's context and produces an
explicitly incomplete result if it cannot be recovered.

## API and Streamlit UI

Set `ORYSYS_USE_FAKE_ADAPTERS=false` to use the configured Cloudflare and Pinecone
adapters, then run the API and UI in separate terminals:

```bash
uv run uvicorn orysys.api.app:create_app --factory --reload
uv run streamlit run src/orysys/ui/app.py
```

The API exposes:

- `POST /v1/conversations` to create a server-owned conversation ID;
- `GET /v1/conversations/{id}` to load its visible history;
- `POST /v1/conversations/{id}/messages` to stream ordered SSE activity and answer events.
- `GET /v1/tools` and `POST /v1/tools/{name}/execute` for role-filtered, validated tools;
- `POST /v1/memories/proposals`, confirmation, listing, and deletion endpoints.
- `POST /v1/actions/proposals` and the decision endpoint for one-time, administrator-
  bound approval of a simulated restart;
- `POST /v1/feedback` and the administrator review endpoint for trace-linked feedback.

When `ORYSYS_USE_FAKE_ADAPTERS=false` and `DATABASE_URL` is configured, conversations,
rolling summaries, long-term memories, audits, and LangGraph checkpoints use PostgreSQL
and survive API restarts. Apply application migrations before starting the live API:

```bash
uv run alembic upgrade head
```

LangGraph owns its checkpoint tables through its own `setup()` migrations; Alembic owns
only Orysys application tables. Checkpoints use a no-pickle serializer with an explicit
allow-list of project state types.

Start the local PostgreSQL and Redis dependencies with:

```bash
docker compose up -d postgres redis
```

Production requires a shared Redis limiter, configured with either `REDIS_URL` or the
Upstash REST URL/token. The token bucket is keyed by verified tenant and subject.

## Human approval and feedback

Administrators can request a simulated service restart from the Streamlit sidebar. The
server persists an action hash and hashed, expiring, one-time approval token before the
UI offers approve/deny controls. Approval remains requester- and tenant-bound across an
API restart; denial, expiry, replay, and identity mismatch do not execute the action.

Chat responses expose thumbs feedback. Feedback is idempotent per owner/run and records
the trace, model, prompt, corpus, and route versions. It does not change prompts or
become evaluation data until an administrator reviews it. Export reviewed examples with:

```bash
uv run python -m orysys.feedback.export
uv run python -m orysys.feedback.export --langsmith-dataset orysys-reviewed
```

Run the deterministic security-control evaluation with:

```bash
uv run python -m orysys.evals.controls
uv run python -m orysys.evals.reliability
```

## Authorized tools and MCP

The tool gateway validates arguments, enforces the authenticated role before dispatch,
and each handler repeats authorization before provider access. Calls have deadlines,
idempotency keys, output caps, and redacted activity events.

- `knowledge.search` accepts only query and limit; namespace and filters come from the
  verified principal.
- `analytics.incidents` exposes named aggregations over validated incident records. It
  cannot execute Python expressions, imports, files, subprocesses, or network requests.
- `mcp.read` calls only the employee-directory, service-catalog, and incident-record
  operations exposed by the separate MCP server.

Run the official MCP v2 Streamable HTTP server separately:

```bash
uv run python -m orysys.mcp_server.app
```

It listens at `http://127.0.0.1:8001/mcp` by default. Override the API-side endpoint with
`ORYSYS_MCP_SERVER_URL`.

## Durable memory

Memory is never saved from model output automatically. The API first creates a proposal;
the authenticated owner must confirm it before it can be recalled across conversations.
Recall, confirmation, expiry, and deletion are tenant-and-owner scoped. Credential-like
content is rejected, expiry is capped at one year, and lifecycle changes are audited.

## Authentication and roles

For credential-free development, leave `ORYSYS_AUTH_ENABLED=false`; the server uses the
configured `ORYSYS_DEMO_*` identity. Production refuses to start in this mode.

For the hosted assessment realm, configure the Skycloak automation and OIDC values in
the ignored `.env`, then provision the realm, clients, roles, and temporary demo users
idempotently:

```bash
uv run python -m orysys.auth.provision
```

Copy `.streamlit/secrets.toml.example` to the ignored
`.streamlit/secrets.toml`, add the `orysys-ui` client secret and realm discovery URL,
and set `ORYSYS_AUTH_ENABLED=true`. Streamlit then performs Authorization Code login
and forwards only the access token; FastAPI verifies that token independently.

An equivalent local upstream Keycloak is available at `http://localhost:8080`:

```bash
docker compose --profile identity up -d keycloak
```

Point `KEYCLOAK_ISSUER` and Streamlit's `server_metadata_url` at the local `orysys`
realm. The imported `viewer`, `analyst`, and `administrator` users receive the temporary
password declared in the local realm export and must change it at first login.

The role policy is server-owned: viewers get scoped knowledge search; analysts also get
analytics and read-only MCP access; administrators additionally qualify for approval-
gated impactful actions. Request bodies and model output cannot choose tenant, role,
department, clearance, retrieval namespace, or tool capabilities.

## Architecture

The system is a modular monolith with a separate MCP process at the
protocol boundary. Domain and application code depend on project-owned ports;
provider SDKs remain in adapters. See:

- [`docs/architecture-plan.md`](docs/architecture-plan.md)
- [`docs/implementation-plan.md`](docs/implementation-plan.md)
- [`docs/requirements-traceability.md`](docs/requirements-traceability.md)
- [`docs/threat-model.md`](docs/threat-model.md)
- [`docs/reliability.md`](docs/reliability.md)
- [`docs/adrs/README.md`](docs/adrs/README.md)

## Current scope

Implemented in the baseline:

- immutable identity and server-derived access-scope contracts;
- evidence, claim, plan, event, tool, validation, memory, and feedback schemas;
- async ports for models, retrieval, identity, tools, limits, and telemetry;
- deterministic fake adapters for credential-free tests;
- validated environment settings and FastAPI health endpoints;
- lint, formatting, type-checking, test, and CI configuration.
- deterministic sample corpus with access-control and evaluation fixtures;
- Markdown, text, structured JSON, and text-native PDF loaders;
- structure-aware chunking with stable document, chunk, and content hashes;
- corpus-fitted BM25 parameters in `data/index/bm25.json`;
- Cloudflare embedding and Pinecone index-writer adapters;
- dry-run and live ingestion CLI with idempotent stale-record reconciliation.
- query-time dense and BM25 weighting with server-derived metadata filters;
- evidence conversion, hosted reranking, and deterministic reranker fallback;
- repeatable retrieval evaluation with recall, reciprocal-rank, and leakage metrics.
- explicit direct-answer `StateGraph` with scoped retrieval and structured output;
- evidence-ledger citation checks, one repair attempt, and safe insufficient-evidence output;
- redacted structured logging and manually scoped LangSmith traces.
- lifecycle-managed FastAPI dependencies and a versioned SSE chat boundary;
- process-local, owner-scoped conversation history with disconnect cancellation;
- Streamlit chat, activity, validation, and evidence views using native components.
- bounded plan/discover/partition/fan-out/reduce research with one gap retry;
- deterministic recurring-cause aggregation with authorized citation validation;
- Skycloak-hosted Keycloak realm provisioning and equivalent local realm export;
- cached OIDC discovery/JWKS verification, bearer forwarding, and complete role policy;
- token-derived conversation ownership and cross-tenant denial.
- double-authorized knowledge, constrained analytics, and read-only MCP tools;
- official MCP v2 in-process contract tests and Streamable HTTP server entrypoint;
- PostgreSQL conversation history, rolling context summaries, and LangGraph checkpoints;
- explicit memory proposal/confirmation/recall/expiry/deletion with audit events.

The traceability matrix remains the authority for implementation and verification
status. A requirement is not considered verified merely because its interface exists.
