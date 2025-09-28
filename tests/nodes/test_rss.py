"""Tests for RSS node implementation."""

from unittest.mock import Mock, patch
import pytest
from langchain_core.runnables import RunnableConfig
from orcheo.nodes.rss import RSSNode


@pytest.mark.asyncio
async def test_rss_node_run():
    """Test RSS node run method."""
    # Setup
    sources = ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
    node = RSSNode(name="test_rss", sources=sources)
    state = {}
    config = RunnableConfig()

    # Mock feed data
    mock_entry1 = Mock()
    mock_entry1.title = "Test Entry 1"
    mock_entry1.link = "https://example.com/1"

    mock_entry2 = Mock()
    mock_entry2.title = "Test Entry 2"
    mock_entry2.link = "https://example.com/2"

    mock_entry3 = Mock()
    mock_entry3.title = "Test Entry 3"
    mock_entry3.link = "https://example.com/3"

    # Mock feedparser responses
    mock_feed1 = Mock()
    mock_feed1.entries = [mock_entry1, mock_entry2]

    mock_feed2 = Mock()
    mock_feed2.entries = [mock_entry3]

    # Mock feedparser.parse to return different feeds for different URLs
    with patch("orcheo.nodes.rss.feedparser.parse") as mock_parse:
        mock_parse.side_effect = [mock_feed1, mock_feed2]

        # Execute
        result = await node.run(state, config)

        # Verify
        assert len(result) == 3
        assert result[0] == mock_entry1
        assert result[1] == mock_entry2
        assert result[2] == mock_entry3

        # Verify feedparser.parse was called with correct URLs
        assert mock_parse.call_count == 2
        mock_parse.assert_any_call("https://example.com/feed1.xml")
        mock_parse.assert_any_call("https://example.com/feed2.xml")


@pytest.mark.asyncio
async def test_rss_node_run_empty_feeds():
    """Test RSS node run method with empty feeds."""
    # Setup
    sources = ["https://example.com/empty.xml"]
    node = RSSNode(name="test_rss", sources=sources)
    state = {}
    config = RunnableConfig()

    # Mock empty feed
    mock_feed = Mock()
    mock_feed.entries = []

    with patch("orcheo.nodes.rss.feedparser.parse") as mock_parse:
        mock_parse.return_value = mock_feed

        # Execute
        result = await node.run(state, config)

        # Verify
        assert result == []
        mock_parse.assert_called_once_with("https://example.com/empty.xml")


@pytest.mark.asyncio
async def test_rss_node_run_no_sources():
    """Test RSS node run method with no sources."""
    # Setup
    node = RSSNode(name="test_rss", sources=[])
    state = {}
    config = RunnableConfig()

    with patch("orcheo.nodes.rss.feedparser.parse") as mock_parse:
        # Execute
        result = await node.run(state, config)

        # Verify
        assert result == []
        mock_parse.assert_not_called()
