"""Grounded generation node for conversational search pipelines."""

from __future__ import annotations
from typing import Any, Literal
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import Field
from orcheo.graph.state import State
from orcheo.nodes.base import TaskNode
from orcheo.nodes.conversational_search.models import SearchResult
from orcheo.nodes.registry import NodeMetadata, registry


def _truncate_snippet(text: str, limit: int = 160) -> str:
    snippet = text.strip().replace("\n", " ")
    if limit <= 0:
        return ""
    if len(snippet) <= limit:
        return snippet

    ellipsis = "…"
    if limit <= len(ellipsis):
        return ellipsis if limit >= len(ellipsis) else snippet[:limit]

    available = limit - len(ellipsis)
    truncated = snippet[:available].rstrip()
    if not truncated:
        return ellipsis
    return f"{truncated}{ellipsis}"


@registry.register(
    NodeMetadata(
        name="GroundedGeneratorNode",
        description="Generate grounded answers with citations and retry semantics.",
        category="conversational_search",
    )
)
class GroundedGeneratorNode(TaskNode):
    """Node that generates grounded responses using retrieved context."""

    query_key: str = Field(
        default="query", description="Key within ``state.inputs`` holding the query."
    )
    context_result_key: str = Field(
        default="retriever",
        description="Name of the upstream result entry containing retrieval output.",
    )
    context_field: str = Field(
        default="results",
        description=(
            "Field name under the retrieval result that stores SearchResult items."
        ),
    )
    system_prompt: str = Field(
        default=(
            "You are a grounded answer generator. Use the provided context to answer "
            "the user's query and include citation markers referencing the context "
            "entries."
        ),
        description="Instruction prefix prepended to the prompt.",
    )
    citation_style: Literal["inline", "footnote", "endnote"] = Field(
        default="inline", description="Style hint for formatting citations."
    )
    ai_model: str | None = Field(
        default=None,
        description=(
            "Optional model identifier (e.g., 'gpt-4', 'claude-3-5-sonnet-latest'). "
            "When specified, an agent is created using langchain.agents.create_agent. "
            "A deterministic fallback is used when omitted."
        ),
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keyword arguments passed to init_chat_model.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Generate a grounded response with citations and retry semantics.

        If no context is available, generates a response without RAG or citations.
        """
        inputs = state.get("inputs", {})
        query = inputs.get(self.query_key) or inputs.get("message")
        if not isinstance(query, str) or not query.strip():
            msg = "GroundedGeneratorNode requires a non-empty query string"
            raise ValueError(msg)

        # Extract conversation history from inputs (provided by ChatKit)
        history = inputs.get("history", [])

        context = self._resolve_context(state)

        # Handle non-RAG mode when no context is available
        if not context:
            completion = await self._generate_with_retries(
                query=query.strip(),
                history=history,
                context=None,
            )
            tokens_used = self._estimate_tokens_from_history(history, query, completion)
            return {
                "reply": completion,
                "citations": [],
                "tokens_used": tokens_used,
                "citation_style": self.citation_style,
                "mode": "non_rag",
            }

        # RAG mode with context and citations
        completion = await self._generate_with_retries(
            query=query.strip(),
            history=history,
            context=context,
        )

        citations = self._build_citations(context)
        response = self._attach_citations(completion, citations)
        tokens_used = self._estimate_tokens_from_history(history, query, response)

        return {
            "reply": response,
            "citations": citations,
            "tokens_used": tokens_used,
            "citation_style": self.citation_style,
            "mode": "rag",
        }

    def _resolve_context(self, state: State) -> list[SearchResult]:
        results = state.get("results", {})
        source = results.get(self.context_result_key, {})
        if isinstance(source, dict) and self.context_field in source:
            entries = source[self.context_field]
        else:
            entries = results.get(self.context_field)
        if not entries:
            return []
        if not isinstance(entries, list):
            msg = "Context payload must be a list of retrieval results"
            raise ValueError(msg)
        return [SearchResult.model_validate(item) for item in entries]

    async def _generate_with_retries(
        self,
        query: str,
        history: list[dict] | None = None,
        context: list[SearchResult] | None = None,
    ) -> str:
        return await self._invoke_ai_model(query, history, context)

    def _build_system_message(self, context: list[SearchResult] | None) -> str:
        """Build system message content based on context availability."""
        if context:
            # RAG mode system prompt with context
            context_block = "\n".join(
                f"[{index}] {entry.text}"
                for index, entry in enumerate(context, start=1)
            )
            return (
                f"{self.system_prompt}\n\n"
                f"Context:\n{context_block}\n\n"
                f"Cite sources in {self.citation_style} style using the provided "
                "identifiers."
            )
        # Non-RAG mode system prompt
        return (
            "You are a helpful assistant. Answer the user's question directly "
            "based on your knowledge."
        )

    def _add_history_to_messages(
        self,
        messages: list[Any],
        history: list[dict] | None,
    ) -> None:
        """Add conversation history to messages list."""
        from langchain_core.messages import AIMessage, HumanMessage

        if not history or not isinstance(history, list):
            return

        for turn in history:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role", "")
            content = turn.get("content", "")
            if role == "user" and content:
                messages.append(HumanMessage(content=content))
            elif role == "assistant" and content:
                messages.append(AIMessage(content=content))

    def _extract_response_text(self, result: Any) -> str:
        """Extract text content from agent result."""
        if isinstance(result, dict) and "messages" in result:
            last_message = result["messages"][-1]
            if hasattr(last_message, "content"):
                return last_message.content
            if isinstance(last_message, dict):
                return last_message.get("content", "")
            return str(last_message)
        return str(result)

    async def _invoke_ai_model(
        self,
        query: str,
        history: list[dict] | None = None,
        context: list[SearchResult] | None = None,
    ) -> str:
        if not self.ai_model:
            return self._default_ai_model(query, context)

        from langchain_core.messages import HumanMessage, SystemMessage

        # Initialize chat model
        model = init_chat_model(self.ai_model, **self.model_kwargs)

        # Build messages list
        messages: list[Any] = []
        system_content = self._build_system_message(context)
        messages.append(SystemMessage(content=system_content))

        # Add conversation history
        self._add_history_to_messages(messages, history)

        # Add current query
        messages.append(HumanMessage(content=query))

        # Create and invoke agent
        agent: Runnable = create_agent(model, tools=[], system_prompt="")
        result = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]

        # Extract and validate response
        text = self._extract_response_text(result)
        if not isinstance(text, str) or not text.strip():
            msg = "Agent must return a non-empty string response"
            raise ValueError(msg)
        return text.strip()

    def _default_ai_model(
        self, query: str, context: list[SearchResult] | None = None
    ) -> str:
        if context:
            return f"{query}\n\nResponse: See cited context for details."
        return f"{query}\n\nResponse: [Default response]"

    def _build_citations(self, context: list[SearchResult]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for index, entry in enumerate(context, start=1):
            citations.append(
                {
                    "id": str(index),
                    "source_id": entry.id,
                    "snippet": _truncate_snippet(entry.text),
                    "sources": entry.sources
                    or ([entry.source] if entry.source else []),
                    "metadata": entry.metadata,
                }
            )
        return citations

    def _attach_citations(
        self, completion: str, citations: list[dict[str, Any]]
    ) -> str:
        markers = " ".join(f"[{citation['id']}]" for citation in citations)
        if not markers:
            return completion
        if self.citation_style == "footnote":
            return f"{completion}\n\nFootnotes: {markers}".strip()
        if self.citation_style == "endnote":
            return f"{completion}\n\nEndnotes: {markers}".strip()
        return f"{completion} {markers}".strip()

    @staticmethod
    def _estimate_tokens(prompt: str, completion: str) -> int:
        return len((prompt + completion).split())

    @staticmethod
    def _estimate_tokens_from_history(
        history: list[dict] | None, query: str, completion: str
    ) -> int:
        """Estimate token count from history, query, and completion."""
        total_text = query + " " + completion
        if history and isinstance(history, list):
            for turn in history:
                if isinstance(turn, dict):
                    content = turn.get("content", "")
                    if content:
                        total_text += " " + content
        return len(total_text.split())


@registry.register(
    NodeMetadata(
        name="StreamingGeneratorNode",
        description="Generate responses and stream token chunks with backpressure.",
        category="conversational_search",
    )
)
class StreamingGeneratorNode(TaskNode):
    """Node that streams model output into bounded frames."""

    prompt_key: str = Field(
        default="prompt", description="Key under inputs containing the prompt."
    )
    chunk_size: int = Field(
        default=8, gt=0, description="Maximum tokens per emitted frame"
    )
    buffer_limit: int | None = Field(
        default=64,
        gt=0,
        description="Optional backpressure cap on total tokens streamed.",
    )
    ai_model: str | None = Field(
        default=None,
        description=(
            "Optional model identifier (e.g., 'gpt-4', 'claude-3-5-sonnet-latest'). "
            "When specified, an agent is created using langchain.agents.create_agent."
        ),
    )
    model_kwargs: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional keyword arguments passed to init_chat_model.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Stream a generated response into framed chunks with retries."""
        inputs = state.get("inputs", {})

        # Support both prompt-based (legacy) and message-based usage
        prompt = inputs.get(self.prompt_key)
        message = inputs.get("message")
        query = prompt or message

        if not isinstance(query, str) or not query.strip():
            msg = "StreamingGeneratorNode requires a non-empty prompt or message"
            raise ValueError(msg)

        # Extract conversation history from inputs (if available)
        history = inputs.get("history", [])

        completion = await self._generate_with_retries(query.strip(), history)
        stream, frames, truncated = self._stream_tokens(completion)
        return {
            "reply": completion,
            "stream": stream,
            "frames": frames,
            "token_count": len(stream),
            "truncated": truncated,
        }

    async def _generate_with_retries(
        self, query: str, history: list[dict] | None = None
    ) -> str:
        return await self._invoke_ai_model(query, history)

    def _build_streaming_messages(
        self, query: str, history: list[dict] | None = None
    ) -> list[Any]:
        """Build messages list for streaming generation."""
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages: list[Any] = [SystemMessage(content="You are a helpful assistant.")]

        # Add conversation history as proper message objects
        if history and isinstance(history, list):
            for turn in history:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("role", "")
                content = turn.get("content", "")
                if role == "user" and content:
                    messages.append(HumanMessage(content=content))
                elif role == "assistant" and content:
                    messages.append(AIMessage(content=content))

        # Add current query
        messages.append(HumanMessage(content=query))
        return messages

    async def _invoke_ai_model(
        self, query: str, history: list[dict] | None = None
    ) -> str:
        if not self.ai_model:
            return self._default_ai_model(query)

        # Initialize chat model
        model = init_chat_model(self.ai_model, **self.model_kwargs)

        # Build messages list
        messages = self._build_streaming_messages(query, history)

        # Create and invoke agent
        agent: Runnable = create_agent(model, tools=[], system_prompt="")
        result = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]

        # Extract text from the last message
        if isinstance(result, dict) and "messages" in result:
            last_message = result["messages"][-1]
            if hasattr(last_message, "content"):
                text = last_message.content
            elif isinstance(last_message, dict):
                text = last_message.get("content", "")
            else:
                text = str(last_message)
        else:
            text = str(result)

        if not isinstance(text, str) or not text.strip():
            msg = "Agent must return a non-empty string response"
            raise ValueError(msg)
        return text.strip()

    def _stream_tokens(
        self, completion: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], bool]:
        tokens = completion.split()
        truncated = False
        if self.buffer_limit and len(tokens) > self.buffer_limit:
            tokens = tokens[: self.buffer_limit]
            truncated = True

        stream: list[dict[str, Any]] = []
        frames: list[dict[str, Any]] = []
        buffer: list[str] = []
        for index, token in enumerate(tokens):
            stream.append({"index": index, "token": token})
            buffer.append(token)
            if len(buffer) == self.chunk_size:
                frames.append(
                    {
                        "index": len(frames),
                        "chunk": " ".join(buffer),
                        "size": len(buffer),
                    }
                )
                buffer = []
        if buffer:
            frames.append(
                {
                    "index": len(frames),
                    "chunk": " ".join(buffer),
                    "size": len(buffer),
                }
            )
        return stream, frames, truncated

    def _default_ai_model(self, query: str) -> str:
        return f"{query} :: streamed"


@registry.register(
    NodeMetadata(
        name="HallucinationGuardNode",
        description="Validate generator output for citations and completeness.",
        category="conversational_search",
    )
)
class HallucinationGuardNode(TaskNode):
    """Node that blocks responses missing citations or context alignment."""

    generator_result_key: str = Field(
        default="grounded_generator",
        description="Result entry containing model output and citations.",
    )
    response_field: str = Field(
        default="reply", description="Field containing the model response"
    )
    citations_field: str = Field(
        default="citations", description="Field containing citations metadata"
    )
    require_markers: bool = Field(
        default=True,
        description="Whether citation markers like [1] must appear in the response.",
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Validate generator output includes citations and markers."""
        payload = self._resolve_payload(state)
        response = self._extract_response(payload)
        citations = self._extract_citations(payload)

        if not citations:
            return self._block("Missing citations for generated response")

        missing_markers = self._missing_markers(response, citations)
        if missing_markers:
            reason = "Response is missing citation markers for ids: " + ", ".join(
                sorted(missing_markers)
            )
            return self._block(reason)

        if any(not self._has_snippet(citation) for citation in citations):
            return self._block("Citation entries must include snippets")

        return {
            "allowed": True,
            "reply": response,
            "citations": citations,
        }

    def _resolve_payload(self, state: State) -> dict[str, Any]:
        payload = state.get("results", {}).get(self.generator_result_key, {})
        if not isinstance(payload, dict):
            msg = "HallucinationGuardNode requires a mapping payload"
            raise ValueError(msg)
        return payload

    def _extract_response(self, payload: dict[str, Any]) -> str:
        response = payload.get(self.response_field)
        if not isinstance(response, str) or not response.strip():
            msg = "Response payload is missing or empty"
            raise ValueError(msg)
        return response.strip()

    def _extract_citations(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        citations = payload.get(self.citations_field)
        if not isinstance(citations, list) or not citations:
            return []
        normalized: list[dict[str, Any]] = []
        for citation in citations:
            if not isinstance(citation, dict):
                msg = "Citations must be dictionaries"
                raise ValueError(msg)
            normalized.append(citation)
        return normalized

    def _missing_markers(
        self, response: str, citations: list[dict[str, Any]]
    ) -> list[str]:
        if not self.require_markers:
            return []
        missing: list[str] = []
        for citation in citations:
            marker = citation.get("id")
            if marker is None:
                continue
            if f"[{marker}]" not in response:
                missing.append(str(marker))
        return missing

    @staticmethod
    def _has_snippet(citation: dict[str, Any]) -> bool:
        snippet = citation.get("snippet") if isinstance(citation, dict) else None
        return bool(snippet)

    def _block(self, reason: str) -> dict[str, Any]:
        return {
            "allowed": False,
            "reason": reason,
            "fallback_response": "Unable to provide an answer with proper grounding.",
        }


@registry.register(
    NodeMetadata(
        name="CitationsFormatterNode",
        description="Format citation metadata into human-readable strings.",
        category="conversational_search",
    )
)
class CitationsFormatterNode(TaskNode):
    """Node that normalizes and formats citation payloads."""

    source_result_key: str = Field(
        default="grounded_generator",
        description="Result entry containing citations to format.",
    )
    citations_field: str = Field(default="citations")
    include_sources: bool = Field(
        default=True, description="Include source identifiers when available"
    )

    async def run(self, state: State, config: RunnableConfig) -> dict[str, Any]:
        """Format citations into human-readable strings."""
        payload = state.get("results", {}).get(self.source_result_key, {})
        if isinstance(payload, dict) and self.citations_field in payload:
            citations = payload[self.citations_field]
        else:
            citations = payload
        if not isinstance(citations, list):
            msg = "CitationsFormatterNode requires a list of citations"
            raise ValueError(msg)

        formatted: list[str] = []
        normalized: list[dict[str, Any]] = []
        references: list[dict[str, str]] = []
        for citation in citations:
            if not isinstance(citation, dict):
                msg = "Citation entries must be mappings"
                raise ValueError(msg)
            citation_id = citation.get("id") or str(len(formatted) + 1)
            snippet = citation.get("snippet", "").strip()
            raw_sources = citation.get("sources")
            if isinstance(raw_sources, list):
                sources = [str(item) for item in raw_sources if item is not None]
            elif raw_sources is None:
                sources = []
            else:
                sources = [str(raw_sources)]
            metadata = citation.get("metadata")
            normalized_metadata = metadata if isinstance(metadata, dict) else {}
            normalized.append(
                {
                    "id": str(citation_id),
                    "snippet": snippet,
                    "sources": sources,
                    "source_id": citation.get("source_id"),
                    "metadata": normalized_metadata,
                }
            )
            source_label = (
                f" (sources: {', '.join(sources)})"
                if sources and self.include_sources
                else ""
            )
            base_text = snippet or str(citation_id)
            external_url = self._resolve_reference_url(citation, normalized_metadata)
            source_reference = f" ([source]({external_url}))" if external_url else ""
            formatted_text = (
                f"[{citation_id}] {base_text}{source_label}{source_reference}".strip()
            )
            formatted.append(formatted_text)
            references.append(
                {
                    "id": str(citation_id),
                    "line": formatted_text,
                }
            )

        base_reply = ""
        if isinstance(payload, dict):
            raw_reply = payload.get("reply")
            if isinstance(raw_reply, str):  # pragma: no branch
                base_reply = raw_reply
        reply = self._build_markdown_reply(base_reply, references)

        self._overwrite_source_reply(state, reply, normalized)

        return {"reply": reply, "formatted": formatted, "citations": normalized}

    def _overwrite_source_reply(
        self, state: State, reply: str, citations: list[dict[str, Any]]
    ) -> None:
        """Update the original source payload with the formatted reply."""
        results = state.get("results")
        if not isinstance(results, dict):
            return
        source_payload = results.get(self.source_result_key)
        if not isinstance(source_payload, dict):
            return
        source_payload["reply"] = reply
        source_payload["citations"] = citations

    def _resolve_reference_url(
        self, citation: dict[str, Any], metadata: dict[str, Any]
    ) -> str | None:
        """Prefer a URL from citation metadata or the citation dictionary."""
        url_fields = (
            "url",
            "link",
            "source_url",
            "permalink",
            "href",
        )
        candidates: list[str | None] = []
        for field in url_fields:
            candidate = citation.get(field)
            if candidate is None:  # pragma: no branch
                candidate = metadata.get(field)
            candidates.append(candidate)
        source_id = citation.get("source_id")
        candidates.append(source_id)

        for candidate in candidates:
            if isinstance(candidate, str):
                trimmed = candidate.strip()
                if trimmed.startswith(("http://", "https://")):  # pragma: no branch
                    return trimmed
        return None

    def _build_markdown_reply(
        self, base_reply: str, references: list[dict[str, str]]
    ) -> str:
        """Return the markdown reply that appends formatted reference entries."""
        sections: list[str] = []
        trimmed = base_reply.strip()
        if trimmed:
            sections.append(trimmed)
        if references:  # pragma: no branch
            lines = [f"- {ref['line']}" for ref in references]
            sections.append("References:\n" + "\n".join(lines))
        return "\n\n".join(sections).strip()
