"""RSS feed fetching and parsing node."""

from __future__ import annotations
import datetime
import re
from typing import Any
import httpx
from langchain_core.runnables import RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.registry import NodeMetadata, registry


@registry.register(
    NodeMetadata(
        name="RSSNode",
        description="Fetch and parse RSS/Atom feeds from multiple sources",
        category="rss",
    )
)
class RSSNode(TaskNode):
    """Fetch RSS/Atom feeds via HTTP and parse their entries.

    Supports both RSS 2.0 ``<item>`` and Atom ``<entry>`` elements.
    Each source is fetched independently; per-source errors are captured
    without aborting the remaining feeds.
    """

    sources: list[str] = Field(description="RSS/Atom feed URLs to fetch")
    timeout: float = Field(
        default=15.0,
        ge=0.0,
        description="HTTP timeout in seconds per feed",
    )

    # ------------------------------------------------------------------
    # XML helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tag_text(xml: str, tag: str) -> str:
        """Extract text content of the first ``<tag>…</tag>`` occurrence."""
        open_tag = "<" + tag
        close_tag = "</" + tag + ">"
        start = xml.find(open_tag)
        if start == -1:
            return ""
        gt = xml.find(">", start)
        if gt == -1:
            return ""
        end = xml.find(close_tag, gt)
        if end == -1:
            return ""
        content = xml[gt + 1 : end]
        if content.strip().startswith("<![CDATA["):
            content = content.strip()[9:]
            if content.endswith("]]>"):
                content = content[:-3]
        return content.strip()

    @staticmethod
    def _extract_link(xml: str) -> str:
        """Extract a link from RSS ``<link>`` or Atom ``<link href="…">``."""
        fallback_href = ""
        link_start = xml.find("<link")
        while link_start != -1:
            tag_end = xml.find(">", link_start)
            if tag_end == -1:
                break
            tag_content = xml[link_start : tag_end + 1]

            attrs = {
                m.group(1).lower(): m.group(3)
                for m in re.finditer(
                    r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(['\"])(.*?)\2",
                    tag_content,
                )
            }

            href = attrs.get("href", "").strip()
            rel = attrs.get("rel", "").strip().lower()
            if href:
                if rel == "alternate":
                    return href
                if not fallback_href:
                    fallback_href = href

            close = xml.find("</link>", tag_end)
            next_link = xml.find("<link", tag_end)
            if not href and close != -1 and (next_link == -1 or close < next_link):
                return xml[tag_end + 1 : close].strip()
            link_start = next_link
        return fallback_href

    @classmethod
    def _parse_items(cls, body: str) -> list[dict[str, str]]:
        """Parse RSS/Atom items from an XML body using string operations."""
        items: list[dict[str, str]] = []
        for item_tag in ("item", "entry"):
            open_tag = "<" + item_tag
            close_tag = "</" + item_tag + ">"
            pos = 0
            while True:
                start = body.find(open_tag, pos)
                if start == -1:
                    break
                end = body.find(close_tag, start)
                if end == -1:
                    break
                fragment = body[start : end + len(close_tag)]

                title = cls._extract_tag_text(fragment, "title")
                link = cls._extract_link(fragment)
                description = cls._extract_tag_text(
                    fragment, "description"
                ) or cls._extract_tag_text(fragment, "summary")
                pub_date = (
                    cls._extract_tag_text(fragment, "pubDate")
                    or cls._extract_tag_text(fragment, "published")
                    or cls._extract_tag_text(fragment, "updated")
                )

                items.append(
                    {
                        "title": title,
                        "link": link,
                        "description": description,
                        "pubDate": pub_date,
                    }
                )
                pos = end + len(close_tag)
        return items

    # ------------------------------------------------------------------
    # Node execution
    # ------------------------------------------------------------------

    async def _fetch_source(
        self,
        client: httpx.AsyncClient,
        url: str,
        now_iso: str,
    ) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
        """Fetch a single source, returning (documents, error_or_None)."""
        try:
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            body = response.text
        except httpx.HTTPError as exc:
            return [], {"source": url, "error": str(exc)}

        if not body:
            return [], {"source": url, "error": "Empty feed response"}

        documents: list[dict[str, Any]] = []
        for item in self._parse_items(body):
            documents.append(
                {
                    "title": item.get("title", ""),
                    "link": item.get("link", ""),
                    "description": item.get("description", ""),
                    "pubDate": item.get("pubDate", ""),
                    "source": url,
                    "read": False,
                    "fetched_at": now_iso,
                }
            )
        return documents, None

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Fetch all configured RSS sources and return parsed documents."""
        now_iso = datetime.datetime.now(datetime.UTC).isoformat()
        documents: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []

        async with httpx.AsyncClient() as client:
            for url in self.sources:
                docs, error = await self._fetch_source(client, url, now_iso)
                documents.extend(docs)
                if error is not None:
                    errors.append(error)

        return {
            "documents": documents,
            "errors": errors,
            "fetched_count": len(documents),
            "failed_sources": len(errors),
        }
