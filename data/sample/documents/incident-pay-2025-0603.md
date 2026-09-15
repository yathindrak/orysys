# PAY-2025-0603 Settlement Delay

## Impact

Merchant settlement files were delayed by 73 minutes. Authorization remained available and no balances were lost.

## Root cause

A malformed partner file repeatedly restarted one settlement worker. The dead-letter threshold was absent, so the poison record blocked its partition.

## Resolution

The record was quarantined and processing resumed. The team added schema validation, a five-attempt dead-letter policy, and partition-level lag alerts.
