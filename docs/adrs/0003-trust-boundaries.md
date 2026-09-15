# ADR-0003: Trusted identity and evidence boundaries

- Status: accepted
- Date: 2026-09-15

## Decision

FastAPI constructs identity from independently verified credentials. Deterministic
policy derives namespaces, metadata filters, and allowed tools from that identity.
Answers cite stable evidence IDs and validation rejects IDs outside the authorized
evidence ledger. User and retrieved text are always untrusted data.

## Consequences

The model cannot select its role, tenant, filters, approval state, or tool permissions.
The activity stream exposes public execution summaries, not hidden reasoning, secrets,
tokens, or unrestricted document bodies.

