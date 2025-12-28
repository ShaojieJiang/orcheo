"""WeCom bot responder workflow for direct messages.

Configure WeCom to send callback requests to:
`/api/workflows/{workflow_id}/triggers/webhook?preserve_raw_body=true`
so signatures can be verified.

Configurable inputs (workflow_config.json):
- corp_id (WeCom corp ID)
- agent_id (WeCom app agent ID)
- reply_message (fixed response content)

Orcheo vault secrets required:
- wecom_corp_secret: WeCom app secret for access token
- wecom_token: Callback token for signature validation
- wecom_encoding_aes_key: AES key for callback decryption
"""

from langgraph.graph import END, StateGraph
from orcheo.edges import Condition, IfElse
from orcheo.graph.state import State
from orcheo.nodes.wecom import (
    WeComAccessTokenNode,
    WeComEventsParserNode,
    WeComSendMessageNode,
)


async def build_graph() -> StateGraph:
    """Build the WeCom direct-message responder workflow."""
    graph = StateGraph(State)

    graph.add_node(
        "wecom_events_parser",
        WeComEventsParserNode(
            name="wecom_events_parser",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    graph.add_node(
        "get_access_token",
        WeComAccessTokenNode(
            name="get_access_token",
            corp_id="{{config.configurable.corp_id}}",
        ),
    )

    graph.add_node(
        "send_message",
        WeComSendMessageNode(
            name="send_message",
            agent_id="{{config.configurable.agent_id}}",
            message="{{config.configurable.reply_message}}",
        ),
    )

    # Entry point
    graph.set_entry_point("wecom_events_parser")

    # WeCom events parser routes based on immediate_response.
    # If immediate_response exists, the synchronous check will return it to WeCom
    # and queue an async run if should_process=True. End here to avoid running
    # expensive downstream nodes (API calls) during the synchronous check.
    immediate_response_router = IfElse(
        name="immediate_response_router",
        conditions=[
            Condition(
                left="{{wecom_events_parser.immediate_response}}",
                operator="is_truthy",
            ),
            Condition(
                left="{{wecom_events_parser.should_process}}",
                operator="is_falsy",
            ),
        ],
        condition_logic="or",
    )
    graph.add_conditional_edges(
        "wecom_events_parser",
        immediate_response_router,
        {
            "true": END,  # Immediate response handled, stop here
            "false": "get_access_token",  # Async run: continue to send message
        },
    )

    # Access token leads to send message
    graph.add_edge("get_access_token", "send_message")
    graph.add_edge("send_message", END)

    return graph
