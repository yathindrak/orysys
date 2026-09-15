# ADR-0002: Application-owned provider ports

- Status: accepted
- Date: 2026-09-15

## Decision

Domain and application modules depend on narrow asynchronous protocols owned by Orysys.
Cloudflare, Pinecone, PostgreSQL, Redis, Keycloak, MCP, and LangSmith implementations
will live in adapter packages. Graph nodes must not call provider SDKs directly.

## Consequences

Credential-free fakes can exercise the same contracts used in production. Provider
errors, retries, redaction, and lifecycle ownership remain localized. A port is added
only when it hides meaningful behavior rather than renaming an SDK method.

