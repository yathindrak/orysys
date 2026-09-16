# Local pilot operations

## Fast path

Install Docker with Compose v2, then run:

```bash
make pilot
```

This builds one non-root runtime image, applies Alembic migrations, and starts the
credential-free pilot topology:

- Streamlit: `http://127.0.0.1:8501`
- FastAPI readiness: `http://127.0.0.1:8000/health/ready`
- MCP Streamable HTTP: `http://127.0.0.1:8001/mcp`
- PostgreSQL (`55432`) and Redis (`6379`) bound to loopback only

The default topology uses deterministic fake model/retrieval adapters and does not pass
provider credentials from `.env` into containers. PostgreSQL and Redis still start so
migrations, health checks, and operational topology match the live deployment shape.

The project maps PostgreSQL to host port 55432 so it does not conflict with a standard
local PostgreSQL installation on 5432. Containers continue to use port 5432 internally.

Inspect logs and stop the pilot with:

```bash
make logs
make down
```

## Live provider overlay

After completing `.env`, `.streamlit/secrets.toml`, corpus ingestion, and identity
provisioning, run:

```bash
make pilot-live
```

`compose.live.yaml` enables production settings and injects only the Cloudflare,
Pinecone, LangSmith, and Keycloak variables needed by the API. Database and Redis stay
inside the Compose network. The UI receives no model, vector-store, database, or Redis
credentials.

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
