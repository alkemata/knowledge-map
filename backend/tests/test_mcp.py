import pytest
from mcp import Client

from app.mcp_server import mcp


@pytest.mark.asyncio
async def test_real_mcp_client_lists_and_calls_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {"get_app_info", "get_agent_guidance", "search_topics", "get_topic", "get_region", "get_trail", "create_topic_at_position"} <= names
        create_tool = next(tool for tool in tools.tools if tool.name == "create_topic_at_position")
        properties = create_tool.input_schema["properties"]
        assert {"x", "y", "min_zoom", "max_zoom", "label_priority"} <= properties.keys()
        read_tool = next(tool for tool in tools.tools if tool.name == "search_topics")
        assert {"type": "oauth2", "scopes": ["knowledge:read"]} in read_tool.model_dump(by_alias=True)["_meta"]["securitySchemes"]
        assert create_tool.model_dump(by_alias=True)["_meta"]["securitySchemes"] == [
            {"type": "oauth2", "scopes": ["knowledge:contribute"]}
        ]
        result = await client.call_tool("get_app_info", {})
        assert not result.is_error
        assert result.structured_content["name"] == "Alkemata Knowledge Map"


@pytest.mark.asyncio
async def test_guidance_contains_untrusted_content_rule():
    async with Client(mcp) as client:
        result = await client.call_tool("get_agent_guidance", {})
        rules = result.structured_content["rules"]
        assert any("untrusted" in rule for rule in rules)
