# ADR-0007: Separate checkpoint and consented-memory persistence

## Status

Accepted

## Decision

Use `AsyncPostgresSaver` for LangGraph-owned run checkpoints and ordinary PostgreSQL
tables for conversations, memory items, and audits. LangGraph runs its own checkpoint
setup migrations. Alembic exclusively owns application tables. Checkpoints disable
pickle fallback and allow deserialization only for an explicit list of Orysys state
types.

Conversation history remains visible while a bounded rolling summary plus the eight
most recent messages controls model context. Long-term memory has a two-step lifecycle:
proposal and explicit owner confirmation. Only active, unexpired, same-tenant and
same-owner items are recalled. Sensitive credential-like content is rejected; deletion
is soft and lifecycle changes are audited.

## Consequences

Conversation and graph state survive process restarts without conflating thread history
with cross-thread user memory. Cross-thread recall cannot occur through model initiative
alone. PostgreSQL is now a required dependency for the live profile, while in-memory
repositories keep unit and contract tests deterministic.
