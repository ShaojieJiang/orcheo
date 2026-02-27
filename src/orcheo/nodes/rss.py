"""RSS feed fetching and parsing node."""

from __future__ import annotations
import datetime
from typing import Any
from xml.etree import ElementTree
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
    def _local_name(tag: str) -> str:
        """Return an XML tag without its namespace prefix."""
        if not tag:
            return ""
        if "}" in tag:
            return tag.rsplit("}", 1)[1]
        return tag

    @staticmethod
    def _child_text(
        parent: ElementTree.Element,
        names: set[str],
    ) -> str:
        """Return first matching child element text by local-name."""
        lowered = {name.lower() for name in names}
        for child in list(parent):
            if RSSNode._local_name(child.tag).lower() not in lowered:
                continue
            text = "".join(child.itertext()).strip()
            if text:
                return text
        return ""

    @staticmethod
    def _extract_link(parent: ElementTree.Element) -> str:
        """Extract RSS/Atom links from item or entry children."""
        fallback_href = ""
        for child in list(parent):
            if RSSNode._local_name(child.tag).lower() != "link":
                continue
            href = (child.attrib.get("href") or "").strip()
            rel = (child.attrib.get("rel") or "").strip().lower()
            if href:
                if rel == "alternate":
                    return href
                if not fallback_href:
                    fallback_href = href
                continue
            text = "".join(child.itertext()).strip()
            if text:
                return text
        return fallback_href

    @classmethod
    def _parse_items(cls, body: str) -> list[dict[str, str]]:
        """Parse RSS/Atom items from an XML body."""
        try:
            root = ElementTree.fromstring(body)
        except ElementTree.ParseError as exc:
            msg = "Malformed XML feed response"
            raise ValueError(msg) from exc

        items: list[dict[str, str]] = []
        for element in root.iter():
            local_name = cls._local_name(element.tag).lower()
            if local_name not in {"item", "entry"}:
                continue

            title = cls._child_text(element, {"title"})
            link = cls._extract_link(element)
            description = cls._child_text(element, {"description", "summary"})
            pub_date = cls._child_text(element, {"pubDate", "published", "updated"})

            items.append(
                {
                    "title": title,
                    "link": link,
                    "description": description,
                    "pubDate": pub_date,
                }
            )
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

        try:
            parsed_items = self._parse_items(body)
        except ValueError as exc:
            return [], {"source": url, "error": str(exc)}

        documents: list[dict[str, Any]] = []
        for item in parsed_items:
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
