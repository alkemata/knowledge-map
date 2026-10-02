import pytest
from mcp import Client

from app.mcp_server import mcp


@pytest.mark.asyncio
async def test_real_mcp_client_lists_and_calls_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {"get_app_info", "get_agent_guidance", "search_topics", "get_topic", "get_region", "get_trail", "create_topic_at_position"} <= names
        result = await client.call_tool("get_app_info", {})
        assert not result.is_error
        assert result.structured_content["name"] == "Alkemata Knowledge Map"


@pytest.mark.asyncio
async def test_guidance_contains_untrusted_content_rule():
    async with Client(mcp) as client:
        result = await client.call_tool("get_agent_guidance", {})
        rules = result.structured_content["rules"]
        assert any("untrusted" in rule for rule in rules)
