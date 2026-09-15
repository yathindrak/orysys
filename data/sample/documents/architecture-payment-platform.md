# Payment Platform Architecture

The payment platform accepts authorization requests through the API gateway and routes them to the authorization service. The service records idempotency keys before calling the core ledger connector.

## Data layer

The authorization service uses a PostgreSQL primary with read replicas. Its connection pool is capped per application instance. The circuit breaker opens when database acquisition latency exceeds the configured threshold.

## Failure isolation

Settlement processing is asynchronous and does not share the authorization worker pool. A settlement backlog must not prevent new card authorizations. Downstream timeouts are classified and surfaced with correlation IDs.
