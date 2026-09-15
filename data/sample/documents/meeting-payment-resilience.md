# Payment Resilience Review Notes

The team reviewed the February and November payment incidents. Both were traced to aggregate PostgreSQL connection demand exceeding the safe database budget.

## Decisions

Connection limits will be calculated centrally from maximum replica count. Retry budgets and acquisition-timeout alerts remain mandatory. The June settlement poison-record incident is tracked separately because its root cause was schema validation and dead-letter handling.
