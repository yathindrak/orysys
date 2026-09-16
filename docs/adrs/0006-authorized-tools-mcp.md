# ADR-0006: Double-authorized tools and MCP boundary

## Status

Accepted

## Decision

Expose tools through a project-owned `AuthorizedToolGateway`. It derives the allow-list
from the verified principal before dispatch, validates exact Pydantic arguments, applies
deadlines, idempotency, and output limits, and emits safe activity events. Every handler
repeats the role check immediately before provider access.

Python analytics is a closed set of named aggregations over structured incident records;
arbitrary code and expressions are not accepted. Read-only employee, service, and
incident lookups run in a separate official MCP v2 server over Streamable HTTP. The MCP
client is hidden behind a narrow adapter and can be tested in-process against the same
server definition.

## Consequences

Models and request bodies can select only registered operations and bounded parameters;
they cannot select authorization scope. MCP protocol changes remain isolated in one
adapter. An unavailable MCP server degrades as a typed provider failure without opening
another execution path.
