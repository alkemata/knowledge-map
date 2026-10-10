import pytest
from mcp import Client

from app import mcp_server
from app.mcp_server import mcp


@pytest.mark.asyncio
async def test_real_mcp_client_lists_and_calls_tools():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {"get_app_info", "list_maps", "get_agent_guidance", "search_topics", "get_topic", "get_region", "get_trail", "search_articles", "get_article", "alkemata-get-site-info", "alkemata-search-published-content", "alkemata-get-published-content", "alkemata-get-agent-guidance", "create_topic_at_position"} <= names
        create_tool = next(tool for tool in tools.tools if tool.name == "create_topic_at_position")
        properties = create_tool.input_schema["properties"]
        assert {"x", "y", "min_zoom", "max_zoom", "label_priority"} <= properties.keys()
        read_tool = next(tool for tool in tools.tools if tool.name == "search_topics")
        assert {"type": "oauth2", "scopes": ["knowledge:read"]} in read_tool.model_dump(by_alias=True)["_meta"]["securitySchemes"]
        public_wordpress = next(tool for tool in tools.tools if tool.name == "alkemata-get-published-content")
        assert {"type": "noauth"} in public_wordpress.model_dump(by_alias=True)["_meta"]["securitySchemes"]
        assert create_tool.model_dump(by_alias=True)["_meta"]["securitySchemes"] == [
            {"type": "oauth2", "scopes": ["knowledge:contribute"]}
        ]
        result = await client.call_tool("get_app_info", {})
        assert not result.is_error
        assert result.structured_content["name"] == "Alkemata Knowledge Gateway"
        assert result.structured_content["map_discovery_tool"] == "list_maps"


@pytest.mark.asyncio
async def test_guidance_contains_untrusted_content_rule():
    async with Client(mcp) as client:
        result = await client.call_tool("get_agent_guidance", {})
        rules = result.structured_content["rules"]
        assert any("untrusted" in rule for rule in rules)


@pytest.mark.asyncio
async def test_invalid_map_id_returns_discovery_hint(monkeypatch):
    map_id = "ce5bfc4e-6b45-5d18-96d1-c835551b26ba"
    monkeypatch.setattr(mcp_server, "_map_choices", lambda _db: [{"id": map_id, "title": "Test map"}])
    async with Client(mcp) as client:
        result = await client.call_tool("create_topic_at_position", {
            "title": "Not created", "summary": "Test", "content": "Test content",
            "map_id": "main", "x": 0, "y": 0,
        })
        assert not result.is_error
        assert result.structured_content["error"] == "invalid_map_id"
        assert result.structured_content["maps"][0]["id"] == map_id
