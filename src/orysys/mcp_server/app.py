from mcp.server import MCPServer

mcp = MCPServer(
    "orysys-directory",
    description="Synthetic employee, service, and incident records for the Orysys assessment.",
)

_EMPLOYEES: dict[str, dict[str, object]] = {
    "E-100": {"employee_id": "E-100", "name": "Asha Perera", "team": "Payments SRE"},
    "E-200": {"employee_id": "E-200", "name": "Noah Silva", "team": "Risk Operations"},
}
_SERVICES: dict[str, dict[str, object]] = {
    "payment-api": {"service": "payment-api", "owner": "Payments SRE", "tier": 1},
    "settlement-worker": {
        "service": "settlement-worker",
        "owner": "Payments Platform",
        "tier": 1,
    },
}
_INCIDENTS: dict[str, dict[str, object]] = {
    "PAY-2025-0214": {
        "incident_id": "PAY-2025-0214",
        "service": "payment-api",
        "severity": "critical",
        "status": "resolved",
    },
    "PAY-2025-0603": {
        "incident_id": "PAY-2025-0603",
        "service": "settlement-worker",
        "severity": "high",
        "status": "resolved",
    },
}


@mcp.tool(structured_output=True)
def employee_directory(identifier: str) -> dict[str, object]:
    """Look up one synthetic employee by exact employee ID."""

    return _lookup(_EMPLOYEES, identifier)


@mcp.tool(structured_output=True)
def service_catalog(identifier: str) -> dict[str, object]:
    """Look up one synthetic service by exact service name."""

    return _lookup(_SERVICES, identifier)


@mcp.tool(structured_output=True)
def incident_record(identifier: str) -> dict[str, object]:
    """Look up one synthetic incident by exact incident ID."""

    return _lookup(_INCIDENTS, identifier)


def _lookup(records: dict[str, dict[str, object]], identifier: str) -> dict[str, object]:
    record = records.get(identifier)
    return {"found": record is not None, "record": record}


def main() -> None:
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        streamable_http_path="/mcp",
        json_response=True,
    )


if __name__ == "__main__":
    main()
