# ADR-0005: Portable Keycloak OIDC boundary

## Status

Accepted

## Decision

Use upstream Keycloak, hosted by Skycloak for the assessment environment, through only
standard OpenID Connect discovery and JWKS endpoints. Streamlit performs Authorization
Code login and forwards the access token. FastAPI independently validates RS256
signatures, issuer, audience, lifetime, subject, and the `orysys-api` client-role claim
before constructing a trusted `Principal`.

Tenant, department, clearance, and role values come only from signed claims. Retrieval
filters and tool capabilities are derived by server policy. The repository includes an
equivalent Keycloak realm export and optional Compose profile; locally signed tokens
exercise the verifier without depending on the hosted service.

## Consequences

The application is portable between hosted and local Keycloak and does not place a
Skycloak SDK in the request path. Authentication fails closed when discovery or keys
are unavailable. Client secrets, automation credentials, access tokens, and bootstrap
passwords remain runtime configuration and are never committed.
