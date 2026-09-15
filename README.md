# Orysys

Orysys is an access-scoped enterprise knowledge assistant. It is designed to
produce evidence-backed answers, expose safe execution activity, and keep model
decisions inside deterministic authorization and validation controls.

The repository currently includes the product baseline and document-ingestion
pipeline: domain contracts, provider ports, deterministic test adapters,
configuration, FastAPI health boundaries, a synthetic bank corpus, Cloudflare
embeddings, corpus-fitted BM25 encoding, idempotent Pinecone writes, scoped hybrid
retrieval, and hosted reranking. LangGraph orchestration and Streamlit follow in
later work packages.

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
- deterministic sample corpus with access-control and evaluation fixtures;
- Markdown, text, structured JSON, and text-native PDF loaders;
- structure-aware chunking with stable document, chunk, and content hashes;
- corpus-fitted BM25 parameters in `data/index/bm25.json`;
- Cloudflare embedding and Pinecone index-writer adapters;
- dry-run and live ingestion CLI with idempotent stale-record reconciliation.
- query-time dense and BM25 weighting with server-derived metadata filters;
- evidence conversion, hosted reranking, and deterministic reranker fallback;
- repeatable retrieval evaluation with recall, reciprocal-rank, and leakage metrics.

The traceability matrix remains the authority for implementation and verification
status. A requirement is not considered verified merely because its interface exists.
