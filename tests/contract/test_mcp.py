import pytest
from mcp import Client

from orysys.adapters.mcp_client import McpDirectoryClient
from orysys.mcp_server.app import mcp


@pytest.mark.asyncio
async def test_mcp_server_exposes_only_bounded_read_tools() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
        result = await client.call_tool("service_catalog", {"identifier": "payment-api"})

    assert {tool.name for tool in tools.tools} == {
        "employee_directory",
        "service_catalog",
        "incident_record",
    }
    assert result.structured_content == {
        "found": True,
        "record": {"service": "payment-api", "owner": "Payments SRE", "tier": 1},
    }


@pytest.mark.asyncio
async def test_mcp_adapter_maps_structured_result() -> None:
    client = McpDirectoryClient(mcp)

    result = await client.call("incident_record", "PAY-2025-0214")

    assert result["found"] is True
    assert result["record"]["status"] == "resolved"  # type: ignore[index]
