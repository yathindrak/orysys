import pytest
from mcp import Client
from pytest import MonkeyPatch

from orysys.adapters.mcp_client import McpDirectoryClient
from orysys.domain.errors import ProviderUnavailable
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


@pytest.mark.asyncio
async def test_mcp_timeout_is_mapped_to_safe_provider_failure(monkeypatch: MonkeyPatch) -> None:
    class TimeoutClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> "TimeoutClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            del args

        async def call_tool(self, *args: object, **kwargs: object) -> object:
            del args, kwargs
            raise TimeoutError("simulated MCP timeout")

    monkeypatch.setattr("orysys.adapters.mcp_client.Client", TimeoutClient)

    with pytest.raises(ProviderUnavailable) as caught:
        await McpDirectoryClient("http://127.0.0.1:8001/mcp").call("service_catalog", "payment-api")

    assert caught.value.public_message == "The MCP service is temporarily unavailable."
