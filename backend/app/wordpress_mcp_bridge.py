"""Call the existing public WordPress MCP through the central gateway."""

from typing import Any

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

PUBLIC_WORDPRESS_MCP = "https://alkemata.com/wp-json/mcp/alkemata-public"
PUBLIC_TOOLS = frozenset({
    "alkemata-get-site-info",
    "alkemata-search-published-content",
    "alkemata-get-published-content",
    "alkemata-get-agent-guidance",
})


async def call_public_wordpress_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in PUBLIC_TOOLS:
        raise ValueError("WordPress tool is not in the public allowlist")
    async with httpx2.AsyncClient(
        timeout=10,
        headers={"X-Alkemata-MCP-Upstream": "wordpress"},
    ) as http:
        async with Client(
            streamable_http_client(PUBLIC_WORDPRESS_MCP, http_client=http),
            read_timeout_seconds=10,
        ) as client:
            result = await client.call_tool(name, arguments)
    if result.is_error or not isinstance(result.structured_content, dict):
        raise RuntimeError("The public WordPress MCP tool failed")
    return result.structured_content
