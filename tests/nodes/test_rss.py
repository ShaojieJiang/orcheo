"""Tests for RSS node implementation."""

from unittest.mock import AsyncMock, Mock, patch
import httpx
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.nodes.rss import RSSNode


@pytest.mark.asyncio
async def test_rss_node_run():
    """Test RSS node run method."""
    sources = ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
    node = RSSNode(name="test_rss", sources=sources)
    state = {}
    config = RunnableConfig()

    feed1_xml = (
        "<rss><channel>"
        "<item><title>Test Entry 1</title><link>https://example.com/1</link></item>"
        "<item><title>Test Entry 2</title><link>https://example.com/2</link></item>"
        "</channel></rss>"
    )
    feed2_xml = (
        "<rss><channel>"
        "<item><title>Test Entry 3</title><link>https://example.com/3</link></item>"
        "</channel></rss>"
    )

    mock_resp1 = Mock()
    mock_resp1.text = feed1_xml
    mock_resp2 = Mock()
    mock_resp2.text = feed2_xml

    mock_client = AsyncMock()
    mock_client.get.side_effect = [mock_resp1, mock_resp2]

    with patch("orcheo.nodes.rss.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await node.run(state, config)

    assert result["fetched_count"] == 3
    assert len(result["documents"]) == 3
    assert result["documents"][0]["title"] == "Test Entry 1"
    assert result["documents"][0]["link"] == "https://example.com/1"
    assert result["documents"][1]["title"] == "Test Entry 2"
    assert result["documents"][2]["title"] == "Test Entry 3"
    assert mock_client.get.call_count == 2
    mock_client.get.assert_any_call("https://example.com/feed1.xml", timeout=15.0)
    mock_client.get.assert_any_call("https://example.com/feed2.xml", timeout=15.0)


@pytest.mark.asyncio
async def test_rss_node_run_empty_feeds():
    """Test RSS node run method with empty feeds."""
    sources = ["https://example.com/empty.xml"]
    node = RSSNode(name="test_rss", sources=sources)
    state = {}
    config = RunnableConfig()

    mock_resp = Mock()
    mock_resp.text = ""

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    with patch("orcheo.nodes.rss.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await node.run(state, config)

    assert result["documents"] == []
    assert result["fetched_count"] == 0
    assert len(result["errors"]) == 1
    mock_client.get.assert_called_once_with(
        "https://example.com/empty.xml", timeout=15.0
    )


@pytest.mark.asyncio
async def test_rss_node_run_no_sources():
    """Test RSS node run method with no sources."""
    node = RSSNode(name="test_rss", sources=[])
    state = {}
    config = RunnableConfig()

    mock_client = AsyncMock()

    with patch("orcheo.nodes.rss.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await node.run(state, config)

    assert result["documents"] == []
    assert result["fetched_count"] == 0
    mock_client.get.assert_not_called()


@pytest.mark.asyncio
async def test_rss_node_run_non_2xx_response_is_reported_as_error():
    """Test RSS node run reports non-2xx responses as source failures."""
    sources = ["https://example.com/protected.xml"]
    node = RSSNode(name="test_rss", sources=sources)
    state = {}
    config = RunnableConfig()

    mock_resp = Mock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Unauthorized",
        request=httpx.Request("GET", "https://example.com/protected.xml"),
        response=httpx.Response(401),
    )

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    with patch("orcheo.nodes.rss.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await node.run(state, config)

    assert result["documents"] == []
    assert result["fetched_count"] == 0
    assert len(result["errors"]) == 1
    assert result["failed_sources"] == 1
    assert result["errors"][0]["source"] == "https://example.com/protected.xml"
    mock_client.get.assert_called_once_with(
        "https://example.com/protected.xml", timeout=15.0
    )
