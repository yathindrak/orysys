# PAY-2025-0214 Payment Authorization Outage

## Impact

Card authorization failures affected 18 percent of requests for 27 minutes. Customers saw error code `PAY-DB-042` at checkout.

## Root cause

A traffic burst exhausted the authorization service PostgreSQL connection pool. A retry loop held connections while waiting for the ledger connector, amplifying saturation.

## Resolution

Engineers disabled the retry loop, raised the emergency pool ceiling, and drained unhealthy application instances. Follow-up work added acquisition-timeout alerts and a retry budget.
