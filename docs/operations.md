# Local pilot operations

## Fast path (live pilot)

Install Docker with Compose v2, complete `.env`, `.streamlit/secrets.toml`, corpus
ingestion, and identity provisioning, then run:

```bash
make pilot
```

This is the default live path. It builds one non-root runtime image, applies Alembic
migrations, and starts the live provider topology:

- Streamlit: `http://127.0.0.1:8501`
- FastAPI readiness: `http://127.0.0.1:8000/health/ready` (reports `adapter_profile: live`)
- MCP Streamable HTTP: `http://127.0.0.1:8001/mcp`
- PostgreSQL (`55432`) and Redis (`6379`) bound to loopback only

`compose.live.yaml` enables production settings and injects only the Cloudflare,
Pinecone, LangSmith, and Keycloak variables needed by the API. Database and Redis stay
inside the Compose network. The UI receives no model, vector-store, database, or Redis
credentials.

`make pilot-live` remains as an explicit alias of `make pilot`.

## Credential-free packaging check

Without provider credentials, run:

```bash
make pilot-fake
```

- FastAPI readiness: `http://127.0.0.1:8000/health/ready` (reports `adapter_profile: fake`)
- MCP Streamable HTTP: `http://127.0.0.1:8001/mcp`
- PostgreSQL (`55432`) and Redis (`6379`) bound to loopback only

The fake topology uses deterministic fake model/retrieval adapters and does not pass
provider credentials from `.env` into containers. PostgreSQL and Redis still start so
migrations, health checks, and operational topology match the live deployment shape.
Use it for packaging checks and CI only.

The project maps PostgreSQL to host port 55432 so it does not conflict with a standard
local PostgreSQL installation on 5432. Containers continue to use port 5432 internally.

Inspect logs and stop the pilot with:

```bash
make logs
make down
```

## Local Keycloak

To use the optional local Keycloak container, start the `identity` profile and point
`KEYCLOAK_ISSUER` plus Streamlit discovery settings at the imported `orysys` realm:

```bash
docker compose --profile identity up --detach --wait keycloak
```

## Verification commands

```bash
make setup
make verify
make compose-check
make image
make migrate-check
```

`make migrate-check` always targets the loopback Compose PostgreSQL instance, even when
the ignored `.env` contains a hosted Neon URL. CI additionally tests migration from an
empty database, downgrade to base, and re-upgrade to head.

## Conversation history, claims, and MCP enrichment

- The Streamlit sidebar `PREVIOUS CONVERSATIONS` picker calls
  `GET /v1/conversations?limit=20` and reloads the selected thread with
  `GET /v1/conversations/{id}`. Entries are owner- and tenant-scoped, newest
  first, with message count plus last-message preview. A listing failure shows an
  empty history section; chat creation and streaming keep working.
- Assistant turns render the answer summary plus per-claim bullets from
  `ANSWER_COMPLETED.answer.claims`. Identical claim/summary text is collapsed.
- Direct answers run `enrich_with_mcp` before composition: exact allow-listed IDs
  (`E-100`, `E-200`, `payment-api`, `settlement-worker`, `PAY-2025-0214`,
  `PAY-2025-0603`, max 3) become `mcp:{operation}:{identifier}` evidence when the
  verified principal holds `mcp.read`. Viewers see `tool.denied`; MCP misses and
  timeouts degrade to retrieval-only evidence. Confirm with
  `GET /health/ready`, `GET /v1/tools`, and the MCP/activity events in the UI.

## Troubleshooting

- If port 55432 or another service port is occupied, stop the conflicting local process
  or change its loopback mapping in `compose.yaml`.
- If a service is unhealthy, run `docker compose ps` and `make logs`; the API waits for
  PostgreSQL, Redis, and MCP before starting.
- If the API exits during live startup, verify the required Cloudflare, Pinecone, and
  Keycloak values without printing their contents.
- If old local schema/data is intentionally disposable, `docker compose down --volumes`
  removes the named PostgreSQL and Redis volumes. This cannot be undone.
- Docker Desktop must be running before image or pilot commands can connect to its
  daemon.

## CI gates

GitHub Actions runs formatting, linting, strict type checks, tests, deterministic
evaluations, empty-database migration cycling, dependency vulnerability and license
inventory, secret scanning, image build, full Compose startup, and HTTP health probes.
