import json
from typing import Any

from mcp import Client
from mcp.types import TextContent

from orysys.domain.errors import ProviderUnavailable
from orysys.security.validation import validate_outbound_url


class McpDirectoryClient:
    def __init__(
        self,
        server: object | str,
        *,
        timeout_seconds: float = 5.0,
        allowed_hosts: frozenset[str] = frozenset({"127.0.0.1", "localhost"}),
    ) -> None:
        if isinstance(server, str):
            validate_outbound_url(server, allowed_hosts)
        self._server = server
        self._timeout = timeout_seconds

    async def call(self, operation: str, identifier: str) -> dict[str, object]:
        try:
            async with Client(self._server, read_timeout_seconds=self._timeout) as client:  # type: ignore[arg-type]
                result = await client.call_tool(
                    operation,
                    {"identifier": identifier},
                    read_timeout_seconds=self._timeout,
                )
        except Exception as error:
            raise ProviderUnavailable("MCP") from error
        if result.is_error:
            raise ProviderUnavailable("MCP")
        structured = result.structured_content
        if isinstance(structured, dict):
            return {str(key): value for key, value in structured.items()}
        text = "".join(block.text for block in result.content if isinstance(block, TextContent))
        try:
            parsed: Any = json.loads(text)
        except json.JSONDecodeError:
            return {"value": text[:2_000]}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
