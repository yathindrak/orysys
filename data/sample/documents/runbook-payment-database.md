# Payment Database Saturation Runbook

## Detection

Confirm elevated connection acquisition latency, `PAY-DB-042` errors, and pool utilization above 90 percent. Compare the sum of configured application pools with the database connection limit.

## Safe mitigation

Pause nonessential batch work, stop retry amplification, and gradually recycle unhealthy instances. Do not increase every instance's pool size without calculating the fleet-wide total.

## Escalation

Page the payments database owner when saturation continues for five minutes or authorization failures exceed five percent. Production configuration changes require administrator approval and a recorded change identifier.
