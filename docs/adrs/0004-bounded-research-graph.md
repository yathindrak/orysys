# ADR-0004: Explicit bounded research graph

## Status

Accepted

## Decision

Implement multi-document research as a project-owned LangGraph `StateGraph` with named
plan, discovery, partition, worker, reduce, retry, and compose nodes. Workers receive
isolated document batches through `Send`; append reducers collect typed outcomes. The
server supplies hard limits for depth, children, retrieval calls, model calls, tokens,
and wall-clock time. A failed child becomes a typed outcome, so successful siblings can
still produce an explicitly incomplete answer.

The reducer is deterministic: batches, evidence, and normalized finding keys are
sorted before composition. Only evidence IDs returned by authorized retrieval may be
cited. A single retry handles failed coverage when budget remains.

## Consequences

The execution path and budget decisions remain visible in code and activity events.
There is more orchestration code than an opaque research-agent library would require,
but authorization, failure isolation, citation checks, and tests remain under product
control. Deep Agents remains an optional compatibility experiment, not a runtime
dependency.
