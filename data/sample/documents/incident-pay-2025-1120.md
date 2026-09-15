# PAY-2025-1120 Checkout Payment Failures

## Impact

Payment failures reached 11 percent for 19 minutes. The public API returned `PAY-DB-042` and database acquisition timeout messages.

## Root cause

An application rollout increased each instance's connection-pool maximum without considering the aggregate database limit. Autoscaling then exhausted the PostgreSQL connection budget. This repeated the connection-pool saturation pattern seen in February.

## Resolution

The rollout was reverted. Pool sizing is now calculated from the database limit and maximum replica count, with a reserved operational margin.
