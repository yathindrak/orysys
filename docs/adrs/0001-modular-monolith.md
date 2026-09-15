# ADR-0001: Modular monolith and explicit graph

- Status: accepted
- Date: 2026-09-15

## Decision

Build the API, application services, domain, LangGraph workflow, and provider adapters
as one Python deployment unit. Keep Streamlit and the MCP server as separate processes.
Implement the primary orchestration directly with explicit LangGraph nodes and routes.

## Consequences

State transitions, authorization, failure handling, and traces remain reviewable. The
application avoids premature distributed-system complexity. Provider ports preserve
future process or vendor changes without making them current requirements.

